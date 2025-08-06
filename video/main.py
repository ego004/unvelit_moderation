import cv2
import imagehash
from PIL import Image
import requests
import json
import os
import tempfile
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

class VideoAnalysis:
    def __init__(self, url: str):
        self.url = url
        self.frame_hashes: Optional[List[int]] = None
        self.temp_video_path: Optional[str] = None
        
        # Check if URL is accessible (similar to image module)
        try:
            response = requests.head(url, timeout=15)  # Increased timeout
            if response.status_code not in [200, 206]:  # 206 is for partial content (range requests)
                raise ValueError(f"Failed to access video from {url}. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to access video from {url}. Error: {str(e)}")

    def _stream_video_to_temp_file(self):
        """
        Stream video from URL and save it to a temporary file.
        """
        if self.temp_video_path and os.path.exists(self.temp_video_path):
            return

        try:
            # Create a temporary file to store the video
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                self.temp_video_path = temp_file.name
                
                # Stream the video content
                with requests.get(self.url, stream=True) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
        except requests.exceptions.RequestException as e:
            self._cleanup_temp_file()
            raise ValueError(f"Failed to stream video from URL: {e}")

    def _get_frame_hashes(self) -> List[int]:
        """
        Sample 5 frames at fixed points (10%, 30%, 50%, 70%, 90%)
        and generate a perceptual hash for each.
        """
        if self.frame_hashes:
            return self.frame_hashes

        if not self.temp_video_path:
            self._stream_video_to_temp_file()

        cap = cv2.VideoCapture(self.temp_video_path) # type: ignore
        if not cap.isOpened():
            raise ValueError("Could not open video file")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_points = [0.1, 0.3, 0.5, 0.7, 0.9]
        hashes = []

        for point in sample_points:
            frame_pos = int(total_frames * point)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            if ret:
                # Convert frame to PIL Image for hashing
                pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                # Generate perceptual hash with optimized size and convert to integer
                phash = imagehash.phash(pil_img, hash_size=4)  # 16-bit hash for better performance
                hashes.append(int(str(phash), 16))
        
        cap.release()

        if len(hashes) != 5:
            raise ValueError(f"Could not extract 5 frames for hashing, only got {len(hashes)}")

        self.frame_hashes = hashes
        return self.frame_hashes

    def analyse(self, db_connection=None, similarity_threshold: int = 10, save_to_db: bool = True, table_name: str = "videos") -> Dict:
        """
        Analyse the video for duplicates and inappropriate content.
        
        Args:
            db_connection: Database connection instance.
            similarity_threshold (int): Max total Hamming distance for similarity.
            save_to_db (bool): Whether to save flagged video hashes to the DB.
            
        Returns:
            Dict: Analysis results.
        """
        try:
            # 1. Generate fingerprint
            video_hashes = self._get_frame_hashes()

            # 2. Check for duplicates if DB is connected
            if db_connection:
                similar_videos = db_connection.find_similar_videos(video_hashes, similarity_threshold)
                if similar_videos:
                    self._cleanup_temp_file()
                    # Use the decision from the existing similar video instead of always flagging
                    existing_decision = similar_videos[0]["decision"]
                    existing_labels = similar_videos[0]["labels"]
                    
                    return {
                        "is_duplicate": True,
                        "similar_items": similar_videos,
                        "decision": existing_decision,  # Use existing decision (pass/review/flagged)
                        "reason": f"duplicate_video_{existing_decision}",  # More descriptive reason
                        "review_details": json.loads(existing_labels) if existing_labels else {}
                    }
            
            # 3. If not a duplicate, perform full frame analysis
            moderation_result = self._analyze_video_frames_concurrently()

            # 4. Save hash regardless of decision (per user requirements)
            if save_to_db and db_connection:
                db_connection.save_video_hashes(video_hashes, self.url, moderation_result["decision"], json.dumps(moderation_result.get("review_details", {})))
            
            self._cleanup_temp_file()
            return moderation_result

        except Exception as e:
            self._cleanup_temp_file()
            return {
                "is_duplicate": False,
                "decision": "review",
                "reason": "processing_error",
                "error": str(e)
            }

    def _analyze_video_frames_concurrently(self) -> Dict:
        """
        Extract frames every 3 seconds and analyze them concurrently.
        Stops immediately if a "flagged" frame is found.
        Otherwise, completes analysis and returns the first "review" frame, or "pass".
        """
        if not self.temp_video_path:
            try:
                self._stream_video_to_temp_file()
            except ValueError as e:
                return {"decision": "review", "reason": "video_streaming_error", "error": str(e)}

        cap = cv2.VideoCapture(self.temp_video_path) # type: ignore
        if not cap.isOpened():
            return {"decision": "review", "reason": "video_loading_error"}

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(fps * 3) if fps > 0 else 30
        frames_to_analyze = []

        for frame_number in range(0, total_frames, frame_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if ret:
                timestamp = frame_number / fps if fps > 0 else 0
                frames_to_analyze.append((frame, timestamp))
        
        cap.release()

        if not frames_to_analyze:
            return {"decision": "pass", "reason": "no_frames_to_analyze"}

        first_review_result = None
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_frame = {executor.submit(self._analyze_frame, frame, ts): ts for frame, ts in frames_to_analyze}
            
            for future in as_completed(future_to_frame):
                result = future.result()
                timestamp = future_to_frame[future]
                
                if result["decision"] == "flagged":
                    # Immediate stop on flagged content
                    executor.shutdown(wait=False, cancel_futures=True)
                    return {
                        "is_duplicate": False,
                        "decision": "flagged",
                        "reason": result["reason"],
                        "flagged_at_timestamp": timestamp,
                        "review_details": result.get("review", {}),
                    }
                
                if result["decision"] == "review" and first_review_result is None:
                    # Store the first review result but continue processing
                    first_review_result = {
                        "is_duplicate": False,
                        "decision": "review",
                        "reason": result["reason"],
                        "flagged_at_timestamp": timestamp,
                        "review_details": result.get("review", {}),
                    }

        # If we finish and have a review result, return it
        if first_review_result:
            return first_review_result

        # Otherwise, all frames passed
        return {
            "is_duplicate": False,
            "decision": "pass",
            "reason": "content_approved",
            "frames_analyzed": len(frames_to_analyze)
        }

    def _analyze_frame(self, frame, timestamp: float) -> Dict:
        """
        Analyze a single frame using SightEngine API.
        """
        try:
            # Convert frame to temporary image file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                cv2.imwrite(temp_file.name, frame)
                file_path = temp_file.name

            with open(file_path, 'rb') as f:
                files = {'media': f}
                params = {
                    'models': 'nudity-2.1,recreational_drug,medical,gore-2.0',
                    'api_user': os.getenv('SIGHTENGINE_API_USER'),
                    'api_secret': os.getenv('SIGHTENGINE_API_KEY')
                }
                r = requests.post('https://api.sightengine.com/1.0/check.json', files=files, data=params)
            
            os.unlink(file_path) # Clean up temp file
            
            output = r.json()

            if output.get('status') != 'success':
                return {"decision": "review", "reason": "api_error", "error": output.get('error', {})}
            
            return self._apply_moderation_logic(output, timestamp)
            
        except Exception as e:
            return {"decision": "review", "reason": "frame_processing_error", "error": str(e)}

    def _apply_moderation_logic(self, output: Dict, timestamp: float) -> Dict:
        """
        Apply moderation logic to the API output for a single frame.
        """
        review_details = {}
        
        # Nudity check
        nudity = output.get('nudity', {})
        if nudity.get('sexual_activity', 0) > 0.85 or nudity.get('sexual_display', 0) > 0.85:
            return {"decision": "flagged", "reason": "explicit_content", "review_details": {"nudity": "high"}}
        if nudity.get('suggestive', 0) > 0.85:
            return {"decision": "review", "reason": "suggestive_content", "review_details": {"nudity": "medium"}}

        # Other checks (drugs, gore, etc.)
        if output.get('recreational_drug', {}).get('prob', 0) > 0.9:
            return {"decision": "flagged", "reason": "drug_content", "review_details": {"recreational_drug": "high"}}
        if output.get('gore', {}).get('prob', 0) > 0.9:
            return {"decision": "flagged", "reason": "gore_content", "review_details": {"gore": "high"}}

        return {"decision": "pass", "reason": "frame_approved"}

    def _cleanup_temp_file(self):
        """Remove the temporary video file if it exists."""
        if self.temp_video_path and os.path.exists(self.temp_video_path):
            os.unlink(self.temp_video_path)
            self.temp_video_path = None