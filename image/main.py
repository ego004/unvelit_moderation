import imagehash
from typing import Dict
from PIL import Image
import sys
import os
import json
import requests
from io import BytesIO

class ImageAnalysis():
    # 64-bit pHash (8x8 DCT). A 16-bit hash has only 65,536 values: with a
    # threshold of 8 bits, about 60% of unrelated image pairs "match", and a
    # new upload would inherit some other image's verdict (including "pass").
    # At 64 bits and a threshold of 8, unrelated images essentially never
    # match, while re-encodes, resizes and light edits land within 0-6 bits.
    HASH_SIZE = 8

    def __init__(self, url: str = "", content: bytes = None):
        self.url = url
        if content is None:
            response = requests.get(url, timeout=30)  # Added timeout
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch image from {url}. Status code: {response.status_code}")
            content = response.content
        self.image_hash = imagehash.phash(Image.open(BytesIO(content)), hash_size=self.HASH_SIZE)
        print(f"Image hash (64-bit): {self.image_hash}")

    @property
    def hash_bytes(self) -> bytes:
        return int(str(self.image_hash), 16).to_bytes(8, 'big')

    def analyse(self, db_connection, similarity_threshold: int = 8, 
               table_name: str = "images", save_to_db: bool = True) -> Dict:
        """
        Analyse the image by comparing its hash against the database.
        
        Args:
            db_connection (SupabaseConnection): Database connection instance
            similarity_threshold (int): Maximum hamming distance for similarity (default: 5)
            table_name (str): Name of the table containing image hashes
            save_to_db (bool): Whether to save this hash to the database
            
        Returns:
            Dict: Analysis results including similar images and similarity scores
        """
        # Find similar images in the database
        similar_images = db_connection.find_similar_images(
            self.hash_bytes, 
            threshold=similarity_threshold
        )

        if similar_images:
            # Use the decision from the existing similar image instead of always flagging
            existing_decision = similar_images[0]["decision"]
            existing_labels = similar_images[0]["labels"]
            
            return {
                "is_duplicate": True,
                "similar_items": [{"url": image["url"], "similarity": image["similarity_score"], "labels": image["labels"]} for image in similar_images],
                "decision": existing_decision,  # Use existing decision (pass/review/flagged)
                "reason": f"duplicate_image_{existing_decision}",  # More descriptive reason
                "review_details": json.loads(existing_labels) if existing_labels else {}
            }
        
        else:
            params = {
             'url': self.url,
             'models': 'nudity-2.1,recreational_drug,medical,gore-2.0',
             'api_user': os.getenv('SIGHTENGINE_API_USER'),
             'api_secret': os.getenv('SIGHTENGINE_API_KEY')
            }
            r = requests.get('https://api.sightengine.com/1.0/check.json', params=params)
            output = r.json()
            if output.get('status') == 'success':
                result = self._moderation_response(output)
                
                # Save to database regardless of decision (per user requirements)
                if save_to_db:
                    db_connection.save_image_hash(self.hash_bytes, self.url, result['decision'], json.dumps(result['review_details']))
                
                return {
                    "is_duplicate": False,
                    "decision": result['decision'],
                    "reason": result['reason'],
                    "review_details": result['review_details']
                }

            # API failure
            return {
                "is_duplicate": False, 
                "decision": "review", 
                "reason": "api_error", 
                "error": "API call failed or returned non-success status", 
                "raw_response": output
            }

    def _moderation_response(self, output: Dict) -> Dict:
        """
        Build moderation response from SightEngine output.
        """
        review_details = {"sexual_content": "pass", "recreational_drug": "pass", "gore": "pass", "medical": "pass"}
        nudity = output.get('nudity', {})
        # Explicit flag
        for check in ['sexual_activity', 'sexual_display', 'erotica', 'visibly_undressed']:
            if nudity.get(check, 0) > 0.85:
                review_details['sexual_content'] = 'flagged'
                break
        # Suggestive review
        if review_details['sexual_content'] == 'pass' and any(nudity.get(k, 0) > 0.85 for k in ['suggestive', 'mildly_suggestive']):
            review_details['sexual_content'] = 'review'
        # Cleavage low threat
        if review_details['sexual_content'] == 'pass' and nudity.get('suggestive_classes', {}).get('cleavage', 0) > 0.85:
            review_details['sexual_content'] = 'low_threat'
        # Other models
        if output.get('recreational_drug', {}).get('prob', 0) > 0.85:
            review_details['recreational_drug'] = 'flagged'
        elif output.get('recreational_drug', {}).get('prob', 0) >= 0.5:
            review_details['recreational_drug'] = 'review'
        if output.get('medical', {}).get('prob', 0) > 0.85:
            review_details['medical'] = 'review'
        if output.get('gore', {}).get('prob', 0) > 0.85:
            review_details['gore'] = 'flagged'
        elif output.get('gore', {}).get('prob', 0) >= 0.5:
            review_details['gore'] = 'review'
        
        decision = 'flagged' if 'flagged' in review_details.values() else ('review' if 'review' in review_details.values() else 'pass')
        
        reason = "content_approved"
        if decision == 'flagged':
            for k, v in review_details.items():
                if v == 'flagged':
                    reason = f"{k}_flagged"
                    break
        elif decision == 'review':
            for k, v in review_details.items():
                if v == 'review':
                    reason = f"{k}_for_review"
                    break

        return {'review_details': review_details, 'decision': decision, 'reason': reason}

