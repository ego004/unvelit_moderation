import imagehash
from typing import Dict
from PIL import Image
import sys
import os
import json
import requests
from io import BytesIO

class ImageAnalysis():
    def __init__(self, url: str = ""):
        self.url = url
        respone = requests.get(url)
        if respone.status_code != 200:
            raise ValueError(f"Failed to fetch image from {url}. Status code: {respone.status_code}")
        self.image_hash = imagehash.phash(Image.open(BytesIO(respone.content)))  # Using a hash size of 16 for better performance
        print(f"Image hash: {self.image_hash}")

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
        hash_int = int(str(self.image_hash), 16)  # Convert imagehash to integer
        hash_bytes = hash_int.to_bytes(8, 'big')  # 64-bit hash = 8 bytes
        similar_images = db_connection.find_similar_images(
            hash_bytes, 
            threshold=similarity_threshold
        )

        if similar_images:
            return {
                "is_duplicate": True,
                "similar_items": [{"url": image["url"], "similarity": image["similarity_score"], "labels": image["labels"]} for image in similar_images],
                "decision": "flagged",
                "reason": "duplicate_image"
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
                    # Convert imagehash to integer for database storage
                    hash_int = int(str(self.image_hash), 16)  # imagehash string is hexadecimal
                    hash_bytes = hash_int.to_bytes(8, 'big')  # 64-bit hash = 8 bytes
                    db_connection.save_image_hash(hash_bytes, self.url, result['decision'], json.dumps(result['review_details']))
                
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

