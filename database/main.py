import mysql.connector
from mysql.connector import pooling
from typing import List, Dict, Optional
import json

class MySQLClient:
    def __init__(self, host: str, user: str, password: str, database: str, pool_size: int = 5):
        self.db_config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
        }
        self.pool = pooling.MySQLConnectionPool(
            pool_name="moderation_pool",
            pool_size=pool_size,
            **self.db_config
        )
        print("Database connection pool created.")
        self._create_tables_if_not_exist()

    def get_connection(self):
        """Get a connection from the pool."""
        return self.pool.get_connection()

    def _create_tables_if_not_exist(self):
        """Create the images and videos tables if they do not already exist."""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    hash BIGINT UNSIGNED NOT NULL,
                    url VARCHAR(2048) NOT NULL,
                    decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'pass',
                    labels JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY `hash_idx` (`hash`)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    hash_1 BIGINT UNSIGNED NOT NULL,
                    hash_2 BIGINT UNSIGNED NOT NULL,
                    hash_3 BIGINT UNSIGNED NOT NULL,
                    hash_4 BIGINT UNSIGNED NOT NULL,
                    hash_5 BIGINT UNSIGNED NOT NULL,
                    url VARCHAR(2048) NOT NULL,
                    decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'pass',
                    labels JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS text_moderation (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    text TEXT NOT NULL,
                    decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'flagged',
                    reason VARCHAR(255),
                    raw_response JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS moderation_log (
                  `id` INT NOT NULL AUTO_INCREMENT,
                  `request_id` VARCHAR(36) NOT NULL,
                  `user_uuid` VARCHAR(36) NOT NULL,
                  `content_type` ENUM('image', 'video', 'text') NOT NULL,
                  `content_identifier` TEXT NOT NULL,
                  `content_hash` VARCHAR(255) DEFAULT NULL,
                  `decision` VARCHAR(50) NOT NULL,
                  `reason` VARCHAR(255) DEFAULT NULL,
                  `raw_response` JSON DEFAULT NULL,
                  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  UNIQUE KEY `request_id_UNIQUE` (`request_id`)
                )
            """)
            conn.commit()
            print("Tables created/verified successfully.")
        except Exception as e:
            print(f"Error creating tables: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def close(self):
        """This method is no longer needed for individual connections, but can be used to terminate the pool if necessary."""
        pass
    
    def log_moderation_request(self, request_id: str, user_uuid: str, content_type: str, content_identifier: str, content_hash: Optional[str], decision: str, reason: Optional[str], raw_response: Optional[Dict] = None):
        """Logs a moderation request and its outcome to the database."""
        query = """
        INSERT INTO moderation_log (request_id, user_uuid, content_type, content_identifier, content_hash, decision, reason, raw_response)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            params = (request_id, user_uuid, content_type, content_identifier, content_hash, decision, reason, json.dumps(raw_response) if raw_response else None)
            cursor.execute(query, params)
            conn.commit()
            print(f"Moderation log saved: {request_id}")
        except Exception as e:
            print(f"Error logging moderation request: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def save_flagged_text(self, text: str, decision: str, reason: str, raw_response: Dict):
        """Save text and the moderation decision to the database."""
        query = """
        INSERT INTO text_moderation (text, decision, reason, raw_response)
        VALUES (%s, %s, %s, %s)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, (text, decision, reason, json.dumps(raw_response)))
            conn.commit()
            print(f"Text moderation saved: {decision}")
        except Exception as e:
            print(f"Error saving text moderation: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def save_image_hash(self, image_hash: bytes, url: str, decision: str, labels: str):
        """Save an image hash to the database with moderation decision."""
        hash_value = int.from_bytes(image_hash, 'big', signed=False)
        query = "INSERT INTO images (hash, url, decision, labels) VALUES (%s, %s, %s, %s)"
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, (hash_value, url, decision, labels))
            conn.commit()
            print(f"Image hash saved: {decision}")
        except Exception as e:
            print(f"Error saving image hash: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def save_video_hashes(self, video_hashes: List[int], url: str, decision: str, labels: str):
        """Save video frame hashes to the database with moderation decision."""
        query = """
        INSERT INTO videos (hash_1, hash_2, hash_3, hash_4, hash_5, url, decision, labels)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, (*video_hashes, url, decision, labels))
            conn.commit()
            print(f"Video hashes saved: {decision}")
        except Exception as e:
            print(f"Error saving video hashes: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def find_similar_images(self, image_hash: bytes, threshold: int) -> List[Dict]:
        """Find similar images using Hamming distance."""
        hash_int = int.from_bytes(image_hash, 'big')
        query = """
        SELECT url, decision, labels, BIT_COUNT(hash ^ %s) AS similarity_score
        FROM images
        WHERE BIT_COUNT(hash ^ %s) <= %s
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (hash_int, hash_int, threshold))
            results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Error finding similar images: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def find_similar_videos(self, video_hashes: List[int], threshold: int) -> List[Dict]:
        """Find similar videos using Hamming distance on multiple frame hashes."""
        similarity_query_parts = [f"BIT_COUNT(hash_{i+1} ^ %s)" for i in range(len(video_hashes))]
        total_similarity_query = " + ".join(similarity_query_parts)

        query = f"""
        SELECT url, decision, labels, ({total_similarity_query}) AS similarity_score
        FROM videos
        WHERE ({total_similarity_query}) <= %s
        """
        
        params = video_hashes * 2 + [threshold]
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Error finding similar videos: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
