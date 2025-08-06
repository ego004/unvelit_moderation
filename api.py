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

app = FastAPI(
    title="Unvelit Moderation API",
    description="API for moderating images, videos, and text content.",
    version="1.0.0",
)

# --- Pydantic Models for Request Bodies ---

class ImageRequest(BaseModel):
    url: str = Field(..., description="The public URL of the image to analyze.")
    user_uuid: str = Field(..., description="The UUID of the user making the request.")

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

@app.post("/analyse/image", tags=["Moderation"])
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

@app.post("/analyse/video", tags=["Moderation"])
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

@app.post("/analyse/text", tags=["Moderation"])
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

# To run the API, use the command: uvicorn api:app --reload
