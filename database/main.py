import mysql.connector
from mysql.connector import pooling
from typing import List, Dict, Optional
import json

class MySQLClient:
    def __init__(self, host: str, user: str, password: str, database: str, pool_size: int = 15):  # Increased from 5
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
                    hash INT UNSIGNED NOT NULL,
                    url VARCHAR(2048) NOT NULL,
                    decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'pass',
                    labels JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX hash_idx (hash),
                    INDEX hash_decision_idx (hash, decision),
                    INDEX decision_idx (decision)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    hash_1 INT UNSIGNED NOT NULL,
                    hash_2 INT UNSIGNED NOT NULL,
                    hash_3 INT UNSIGNED NOT NULL,
                    hash_4 INT UNSIGNED NOT NULL,
                    hash_5 INT UNSIGNED NOT NULL,
                    url VARCHAR(2048) NOT NULL,
                    decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'pass',
                    labels JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX hash_1_idx (hash_1),
                    INDEX hash_2_idx (hash_2),
                    INDEX hash_3_idx (hash_3),
                    INDEX hash_4_idx (hash_4),
                    INDEX hash_5_idx (hash_5),
                    INDEX decision_idx (decision),
                    INDEX composite_idx (hash_1, hash_2, decision)
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
    
    def clear_all_data(self):
        """Clear all data from all tables. Use with caution!"""
        tables = ['moderation_log', 'text_moderation', 'videos', 'images']
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Disable foreign key checks temporarily
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table}")
                print(f"Cleared all data from {table} table")
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            conn.commit()
            print("✅ All tables cleared successfully!")
            
        except Exception as e:
            print(f"❌ Error clearing tables: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
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
        """Find similar images using optimized Hamming distance with range filtering."""
        hash_int = int.from_bytes(image_hash, 'big')
        
        # Pre-filter by hash range to reduce BIT_COUNT calculations
        # This significantly improves performance by limiting the search space
        lower_bound = max(0, hash_int - (1 << threshold))
        upper_bound = min(0xFFFF, hash_int + (1 << threshold))  # 16-bit max value
        
        query = """
        SELECT url, decision, labels, BIT_COUNT(hash ^ %s) AS similarity_score
        FROM images 
        WHERE hash BETWEEN %s AND %s 
        AND BIT_COUNT(hash ^ %s) <= %s
        ORDER BY similarity_score ASC
        LIMIT 10
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (hash_int, lower_bound, upper_bound, hash_int, threshold))
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
        """Find similar videos using optimized Hamming distance on multiple frame hashes."""
        if len(video_hashes) != 5:
            print(f"ERROR: Expected 5 video hashes, got {len(video_hashes)}")
            return []
            
        h1, h2, h3, h4, h5 = video_hashes
        
        # Build the similarity calculation for all 5 hashes
        query = """
        SELECT url, decision, labels, 
               (BIT_COUNT(hash_1 ^ %s) + BIT_COUNT(hash_2 ^ %s) + BIT_COUNT(hash_3 ^ %s) + BIT_COUNT(hash_4 ^ %s) + BIT_COUNT(hash_5 ^ %s)) AS similarity_score
        FROM videos
        WHERE (BIT_COUNT(hash_1 ^ %s) + BIT_COUNT(hash_2 ^ %s) + BIT_COUNT(hash_3 ^ %s) + BIT_COUNT(hash_4 ^ %s) + BIT_COUNT(hash_5 ^ %s)) <= %s
        ORDER BY similarity_score ASC
        LIMIT 10
        """
        
        # Parameters: 5 hashes for SELECT, 5 hashes for WHERE, 1 threshold
        params = [h1, h2, h3, h4, h5, h1, h2, h3, h4, h5, threshold]
        
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            print(f"DEBUG: Video similarity query parameters: {params}")
            print(f"DEBUG: Searching for exact hashes: {video_hashes}")
            print(f"DEBUG: Threshold: {threshold}")
            cursor.execute(query, params)
            results = cursor.fetchall()
            print(f"DEBUG: Video similarity results count: {len(results)}")
            for i, result in enumerate(results):
                print(f"DEBUG: Result {i+1}: similarity={result.get('similarity_score')}, url={result.get('url', '')[:50]}...")
            return results
        except Exception as e:
            print(f"Error finding similar videos: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
