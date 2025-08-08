import os
import uuid
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

from database.main import MySQLClient
from image.main import ImageAnalysis
from video.main import VideoAnalysis
from text.main import TextAnalysis

# Load environment variables from .env file
load_dotenv()


from fastapi import APIRouter

app = FastAPI(
    title="Unvelit Moderation API",
    description="API for moderating images, videos, and text content.",
    version="1.0.0",
)

# Create a router for all endpoints
router = APIRouter()

# --- Pydantic Models for Request Bodies ---

class ImageRequest(BaseModel):
    url: str = Field(..., description="The public URL of the image to analyze.")
    user_uuid: str = Field(..., description="The UUID of the user making the request.")

class BatchImageRequest(BaseModel):
    images: List[ImageRequest] = Field(..., description="List of images to analyze in batch.")
    max_concurrent: int = Field(5, description="Maximum number of concurrent analyses (1-10).")

class VideoRequest(BaseModel):
    url: str = Field(..., description="The public URL of the video to analyze.")
    user_uuid: str = Field(..., description="The UUID of the user making the request.")

class TextRequest(BaseModel):
    text: str = Field(..., description="The text content to analyze.")
    user_uuid: str = Field(..., description="The UUID of the user making the request.")
    thread_context: Optional[List[str]] = Field(None, description="A list of previous messages for context.")

# --- Database Dependency ---

db_client = None

@app.on_event("startup")
def startup_db_client():
    global db_client
    db_client = MySQLClient(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASS', ''),
        database=os.getenv('DB_NAME', 'unvelit')
    )

@app.on_event("shutdown")
def shutdown_db_client():
    # The pool will be managed by the MySQLClient class, no explicit shutdown needed here
    # unless you implement a specific pool termination method.
    pass

def get_db() -> MySQLClient:
    if db_client is None:
        raise HTTPException(status_code=500, detail="Database client not initialized.")
    return db_client

# --- API Endpoints ---

@router.post("/analyse/image", tags=["Moderation"])
async def analyse_image_endpoint(request: ImageRequest, db: MySQLClient = Depends(get_db)):
    """
    Analyzes an image for duplicate content and inappropriate material.

    - **Generates a perceptual hash** of the image.
    - **Checks for duplicates** against the database.
    - **If not a duplicate**, sends the image to SightEngine for moderation.
    - **Logs every request** and its outcome to the `moderation_log` table.
    - **Saves hashes** of flagged content to the `images` table.
    """
    request_id = str(uuid.uuid4())
    try:
        analyzer = ImageAnalysis(url=request.url)
        # Only save to DB if it's not a duplicate (to avoid wasting API credits and DB writes)
        result = analyzer.analyse(db_connection=db, save_to_db=True)
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='image',
            content_identifier=request.url,
            content_hash=str(analyzer.image_hash),
            decision=result.get('decision', 'Error'),
            reason=result.get('reason', 'An unexpected error occurred.'),
            raw_response=result
        )
        return {"request_id": request_id, **result}
    except ValueError as e:
        # Log the URL access error to moderation logs
        error_result = {
            "decision": "error", 
            "reason": "url_access_failed", 
            "error": str(e),
            "is_duplicate": False
        }
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='image',
            content_identifier=request.url,
            content_hash=None,
            decision="error",
            reason="url_access_failed",
            raw_response=error_result
        )
        
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log unexpected errors to moderation logs
        error_result = {
            "decision": "error", 
            "reason": "unexpected_error", 
            "error": str(e),
            "is_duplicate": False
        }
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='image',
            content_identifier=request.url,
            content_hash=None,
            decision="error",
            reason="unexpected_error",
            raw_response=error_result
        )
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyse/video", tags=["Moderation"])
async def analyse_video_endpoint(request: VideoRequest, db: MySQLClient = Depends(get_db)):
    """
    Analyzes a video for duplicate content and inappropriate material.

    - **Streams the video** and samples frames for a perceptual hash fingerprint.
    - **Checks for duplicate videos** based on the fingerprint.
    - **If not a duplicate**, analyzes frames every 3 seconds for inappropriate content.
    - **Logs every request** and its outcome to the `moderation_log` table.
    - **Saves fingerprints** of flagged videos to the `videos` table.
    """
    request_id = str(uuid.uuid4())
    try:
        analyzer = VideoAnalysis(url=request.url)
        # The analyse method will generate the hash internally
        result = analyzer.analyse(db_connection=db, save_to_db=True)
        
        # analyzer.frame_hashes is a list of ints, convert to string
        hashes_str = ", ".join(map(str, analyzer.frame_hashes)) if analyzer.frame_hashes else None

        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='video',
            content_identifier=request.url,
            content_hash=hashes_str,
            decision=result.get('decision', 'Error'),
            reason=result.get('reason', 'An unexpected error occurred.'),
            raw_response=result
        )
        return {"request_id": request_id, **result}
    except ValueError as e:
        # Log the URL access error to moderation logs
        error_result = {
            "decision": "error", 
            "reason": "url_access_failed", 
            "error": str(e),
            "is_duplicate": False
        }
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='video',
            content_identifier=request.url,
            content_hash=None,
            decision="error",
            reason="url_access_failed",
            raw_response=error_result
        )
        
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log unexpected errors to moderation logs
        error_result = {
            "decision": "error", 
            "reason": "unexpected_error", 
            "error": str(e),
            "is_duplicate": False
        }
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='video',
            content_identifier=request.url,
            content_hash=None,
            decision="error",
            reason="unexpected_error",
            raw_response=error_result
        )
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyse/text", tags=["Moderation"])
async def analyse_text_endpoint(request: TextRequest, db: MySQLClient = Depends(get_db)):
    """
    Analyzes text for community standard violations using the Gemini API.

    - **Considers conversation context** if provided.
    - **Logs every request** and its outcome to the `moderation_log` table.
    - **Saves flagged text** to the `text_moderation` table.
    """
    request_id = str(uuid.uuid4())
    try:
        analyzer = TextAnalysis(text=request.text, thread_context=request.thread_context or [])
        result = analyzer.analyse(db_connection=db, save_to_db=True)
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='text',
            content_identifier=request.text,
            content_hash=None,
            decision=result.get('decision', 'Error'),
            reason=result.get('reason', 'An unexpected error occurred.'),
            raw_response=result
        )
        return {"request_id": request_id, **result}
    except Exception as e:
        # Log unexpected errors to moderation logs
        error_result = {
            "decision": "error", 
            "reason": "unexpected_error", 
            "error": str(e)
        }
        
        db.log_moderation_request(
            request_id=request_id,
            user_uuid=request.user_uuid,
            content_type='text',
            content_identifier=request.text,
            content_hash=None,
            decision="error",
            reason="unexpected_error",
            raw_response=error_result
        )
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyse/images/batch", tags=["Moderation", "Batch"])
async def analyse_images_batch_endpoint(request: BatchImageRequest, db: MySQLClient = Depends(get_db)):
    """
    Analyzes multiple images concurrently for better performance.
    
    - **Processes up to 10 images simultaneously**
    - **Returns results in the same order as input**
    - **Fails gracefully** - continues processing other images if one fails
    - **Uses connection pooling** for optimal database performance
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    # Limit concurrent processing to prevent resource exhaustion
    max_concurrent = min(max(1, request.max_concurrent), 10)
    
    async def process_single_image(image_request: ImageRequest) -> dict:
        """Process a single image asynchronously."""
        request_id = str(uuid.uuid4())
        try:
            # Run the blocking image analysis in a thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                analyzer = await loop.run_in_executor(executor, ImageAnalysis, image_request.url)
                result = await loop.run_in_executor(
                    executor, 
                    lambda: analyzer.analyse(db_connection=db, save_to_db=True)
                )
            
            db.log_moderation_request(
                request_id=request_id,
                user_uuid=image_request.user_uuid,
                content_type='image',
                content_identifier=image_request.url,
                content_hash=str(analyzer.image_hash),
                decision=result.get('decision', 'Error'),
                reason=result.get('reason', 'An unexpected error occurred.'),
                raw_response=result
            )
            return {"request_id": request_id, "url": image_request.url, "status": "success", **result}
            
        except Exception as e:
            error_result = {
                "decision": "error", 
                "reason": "processing_failed", 
                "error": str(e),
                "is_duplicate": False
            }
            
            db.log_moderation_request(
                request_id=request_id,
                user_uuid=image_request.user_uuid,
                content_type='image',
                content_identifier=image_request.url,
                content_hash=None,
                decision="error",
                reason="processing_failed",
                raw_response=error_result
            )
            
            return {"request_id": request_id, "url": image_request.url, "status": "error", "error": str(e)}
    
    # Process images concurrently with semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(image_request: ImageRequest):
        async with semaphore:
            return await process_single_image(image_request)
    
    # Execute all image processing tasks concurrently
    tasks = [process_with_semaphore(img) for img in request.images]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions that occurred during processing
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "request_id": str(uuid.uuid4()),
                "url": request.images[i].url,
                "status": "error",
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return {
        "batch_id": str(uuid.uuid4()),
        "total_images": len(request.images),
        "processed": len(processed_results),
        "max_concurrent": max_concurrent,
        "results": processed_results
    }

@router.post("/debug/clear-database")
def clear_database():
    """Clear all data from database tables. Use with caution!"""
    if not db_client:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        db_client.clear_all_data()
        return {"message": "✅ All tables cleared successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {str(e)}")

@router.get("/debug/database-content")
def get_database_content():
    """Debug endpoint to see what's in the database."""
    if not db_client:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        conn = db_client.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get images
        cursor.execute("SELECT * FROM images ORDER BY created_at DESC LIMIT 10")
        images = cursor.fetchall()
        
        # Get videos
        cursor.execute("SELECT * FROM videos ORDER BY created_at DESC LIMIT 10")
        videos = cursor.fetchall()
        
        # Get moderation logs
        cursor.execute("SELECT * FROM moderation_log ORDER BY created_at DESC LIMIT 10")
        logs = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "images": images,
            "videos": videos,
            "moderation_logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database content: {str(e)}")

@router.post("/debug/test-video-similarity")
def test_video_similarity(video_hashes: List[int], threshold: int = 10):
    """Debug endpoint to test video similarity search."""
    if not db_client:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        results = db_client.find_similar_videos(video_hashes, threshold)
        return {
            "search_hashes": video_hashes,
            "threshold": threshold,
            "results_found": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test similarity: {str(e)}")


# Register the router with the prefix '/unvelit_mod'
app.include_router(router, prefix="/unvelit_mod")

# To run the API, use the command: uvicorn api:app --reload
