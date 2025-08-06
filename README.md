# Unvelit Moderation API 🛡️

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-00a393.svg)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1.svg)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

The Unvelit Moderation API is a comprehensive, production-ready content moderation solution designed to analyze images, videos, and text content for inappropriate material, hate speech, and duplicate detection. Built with FastAPI and MySQL, it provides robust logging, perceptual hashing for media analysis, and AI-powered text moderation.

### Key Features

🖼️ **Image Moderation**: Advanced analysis using perceptual hashing and external moderation APIs
🎬 **Video Moderation**: Frame-by-frame analysis with multi-hash fingerprinting for duplicate detection
📝 **Text Moderation**: AI-powered analysis with conversational context awareness
📊 **Comprehensive Logging**: Complete audit trail of every moderation request
🔍 **Duplicate Detection**: Sophisticated similarity matching using Hamming distance
🚀 **Production Ready**: Connection pooling, error handling, and scalable architecture

## Quick Start

### Prerequisites

- Python 3.8+
- MySQL Server 8.0+
- API keys for external services:
  - SightEngine (for image/video moderation)
  - Google Gemini API (for text analysis)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/unvelit-moderation-api.git
   cd unvelit-moderation-api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Copy the example environment file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your actual values:
   ```env
   # Database Configuration
   DB_HOST=localhost
   DB_USER=your_mysql_username
   DB_PASS=your_mysql_password
   DB_NAME=unvelit_moderation

   # SightEngine API Configuration (for image/video moderation)
   # Sign up at: https://sightengine.com/
   SIGHTENGINE_API_USER=your_sightengine_user_id
   SIGHTENGINE_API_KEY=your_sightengine_api_key

   # Google Gemini API Configuration (for text moderation)
   # Get your API key from: https://ai.google.dev/
   GEMINI_API_KEY=your_gemini_api_key
   ```

5. **Initialize the database**
   
   Connect to MySQL and create the database:
   ```sql
   CREATE DATABASE unvelit_moderation;
   ```
   
   The application will automatically create the required tables on first run.

6. **Start the server**
   ```bash
   uvicorn api:app --reload
   ```
   
   The API will be available at `http://127.0.0.1:8000`

### Testing the API

Run the included test suite:
```bash
python test_api.py
```

Access interactive documentation:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## Database Schema

### Core Tables

#### `moderation_log`
Complete audit trail of all moderation requests:
```sql
CREATE TABLE moderation_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  request_id VARCHAR(36) UNIQUE NOT NULL,
  user_uuid VARCHAR(36) NOT NULL,
  content_type ENUM('image', 'video', 'text'),
  content_identifier TEXT NOT NULL,
  content_hash VARCHAR(255),
  decision VARCHAR(50) NOT NULL,
  reason VARCHAR(255),
  raw_response JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `images`
Stores perceptual hashes and decisions for all analyzed images:
```sql
CREATE TABLE images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  hash BIGINT UNSIGNED NOT NULL,
  url VARCHAR(2048) NOT NULL,
  decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'pass',
  labels JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX hash_idx (hash)
);
```

#### `videos`
Stores multi-hash fingerprints and decisions for all analyzed videos:
```sql
CREATE TABLE videos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  hash_1 BIGINT UNSIGNED NOT NULL,
  hash_2 BIGINT UNSIGNED NOT NULL,
  hash_3 BIGINT UNSIGNED NOT NULL,
  hash_4 BIGINT UNSIGNED NOT NULL,
  hash_5 BIGINT UNSIGNED NOT NULL,
  url VARCHAR(2048) NOT NULL,
  decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'pass',
  labels JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX hash_1_idx (hash_1),
  INDEX hash_2_idx (hash_2),
  INDEX hash_3_idx (hash_3),
  INDEX hash_4_idx (hash_4),
  INDEX hash_5_idx (hash_5)
);
```

#### `text_moderation`
Archives all analyzed text content with decisions:
```sql
CREATE TABLE text_moderation (
  id INT AUTO_INCREMENT PRIMARY KEY,
  text TEXT NOT NULL,
  decision ENUM('flagged', 'review', 'pass') NOT NULL DEFAULT 'flagged',
  reason VARCHAR(255),
  raw_response JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

All endpoints require a `user_uuid` parameter for tracking and audit purposes. Every request generates a unique `request_id` and logs comprehensive details to the `moderation_log` table.

### 🖼️ Image Analysis

Analyzes images for inappropriate content and detects duplicates using perceptual hashing.

```http
POST /analyse/image
Content-Type: application/json
```

#### Request Body
```json
{
  "url": "https://example.com/image.jpg",
  "user_uuid": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### Parameters
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Public URL of the image to analyze |
| `user_uuid` | string | Yes | UUID of the user making the request |

#### Response Examples

**✅ Safe Content (New Image)**
```json
{
  "request_id": "987fcdeb-51a2-43d1-9f4e-123456789abc",
  "is_duplicate": false,
  "decision": "pass",
  "reason": "content_approved",
  "review_details": {
    "sexual_content": "pass",
    "recreational_drug": "pass",
    "gore": "pass",
    "medical": "pass"
  }
}
```

**⚠️ Content for Review**
```json
{
  "request_id": "abc123de-f456-7890-ghij-klmnopqrstuv",
  "is_duplicate": false,
  "decision": "review",
  "reason": "sexual_content_for_review",
  "review_details": {
    "sexual_content": "review",
    "recreational_drug": "pass",
    "gore": "pass",
    "medical": "pass"
  }
}
```

**🚫 Flagged Content**
```json
{
  "request_id": "def456gh-ijkl-9012-mnop-qrstuvwxyzab",
  "is_duplicate": false,
  "decision": "flagged",
  "reason": "sexual_content_flagged",
  "review_details": {
    "sexual_content": "flagged",
    "recreational_drug": "pass",
    "gore": "pass",
    "medical": "pass"
  }
}
```

**🔄 Duplicate Detected**
```json
{
  "request_id": "ghi789jk-lmno-3456-pqrs-tuvwxyzabcde",
  "is_duplicate": true,
  "decision": "flagged",
  "reason": "duplicate_image",
  "similar_items": [
    {
      "url": "https://example.com/original.jpg",
      "similarity": 2,
      "labels": "{\"sexual_content\": \"flagged\", \"gore\": \"pass\"}"
    }
  ]
}
```

**❌ URL Error**
```json
{
  "detail": "Failed to fetch image from https://example.com/404.jpg. Status code: 404"
}
```

#### HTTP Status Codes
- `200` - Success (analysis completed)
- `400` - Bad Request (invalid URL, inaccessible image)
- `422` - Validation Error (missing/invalid parameters)
- `500` - Internal Server Error

---

### 🎬 Video Analysis

Analyzes videos for inappropriate content using frame sampling and detects duplicates with multi-hash fingerprinting.

```http
POST /analyse/video
Content-Type: application/json
```

#### Request Body
```json
{
  "url": "https://example.com/video.mp4",
  "user_uuid": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### Parameters
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Public URL of the video to analyze |
| `user_uuid` | string | Yes | UUID of the user making the request |

#### Response Examples

**✅ Safe Content (New Video)**
```json
{
  "request_id": "video123-4567-890a-bcde-fghijklmnopq",
  "is_duplicate": false,
  "decision": "pass",
  "reason": "content_approved",
  "frames_analyzed": 15
}
```

**⚠️ Content for Review**
```json
{
  "request_id": "video456-789b-cdef-0123-456789abcdef",
  "is_duplicate": false,
  "decision": "review",
  "reason": "suggestive_content",
  "flagged_at_timestamp": 12.5,
  "review_details": {
    "nudity": "medium"
  }
}
```

**� Flagged Content**
```json
{
  "request_id": "video789-cdef-0123-4567-89abcdefghij",
  "is_duplicate": false,
  "decision": "flagged",
  "reason": "explicit_content",
  "flagged_at_timestamp": 8.2,
  "review_details": {
    "nudity": "high"
  }
}
```

**🔄 Duplicate Detected**
```json
{
  "request_id": "videoadc-def0-1234-5678-9abcdefghijk",
  "is_duplicate": true,
  "decision": "flagged",
  "reason": "duplicate_video",
  "similar_items": [
    {
      "url": "https://example.com/original.mp4",
      "similarity": 5,
      "labels": "{\"decision\": \"flagged\"}"
    }
  ]
}
```

**❌ Processing Error**
```json
{
  "request_id": "videobcd-efgh-ijkl-mnop-qrstuvwxyzab",
  "is_duplicate": false,
  "decision": "review",
  "reason": "processing_error",
  "error": "Failed to stream video from URL: 404 Client Error"
}
```

#### HTTP Status Codes
- `200` - Success (analysis completed or error handled gracefully)
- `400` - Bad Request (invalid URL, inaccessible video)
- `422` - Validation Error (missing/invalid parameters)
- `500` - Internal Server Error

#### Processing Details
- **Frame Sampling**: Extracts frames every 3 seconds for analysis
- **Fingerprinting**: Generates 5 perceptual hashes at fixed points (10%, 30%, 50%, 70%, 90%)
- **Concurrent Analysis**: Processes multiple frames simultaneously for faster results
- **Early Termination**: Stops immediately when flagged content is detected

---

### �📝 Text Analysis

Analyzes text content for community standard violations using AI with conversational context awareness.

```http
POST /analyse/text
Content-Type: application/json
```

#### Request Body
```json
{
  "text": "Message to analyze for inappropriate content",
  "user_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "thread_context": [
    "Previous message 1",
    "Previous message 2"
  ]
}
```

#### Parameters
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Text content to analyze |
| `user_uuid` | string | Yes | UUID of the user making the request |
| `thread_context` | array | No | Previous messages for contextual analysis |

#### Response Examples

**✅ Safe Content**
```json
{
  "request_id": "text1234-5678-90ab-cdef-ghijklmnopqr",
  "decision": "pass",
  "reason": "The message is polite and does not violate any community standards."
}
```

**⚠️ Content for Review**
```json
{
  "request_id": "text5678-90ab-cdef-0123-456789abcdef",
  "decision": "review",
  "reason": "The message contains language that may require human review for context."
}
```

**🚫 Flagged Content**
```json
{
  "request_id": "text9abc-def0-1234-5678-9abcdefghijk",
  "decision": "flagged",
  "reason": "The message contains harassment and personal attacks directed at another user."
}
```

**❌ API Error**
```json
{
  "request_id": "textdef0-1234-5678-9abc-defghijklmno",
  "decision": "error",
  "reason": "API_REQUEST_FAILED",
  "details": "Failed to connect to Gemini API"
}
```

#### HTTP Status Codes
- `200` - Success (analysis completed)
- `422` - Validation Error (missing/invalid parameters)
- `500` - Internal Server Error

#### Analysis Features
- **Contextual Understanding**: Uses conversation history for better accuracy
- **Multi-Category Detection**: Identifies hate speech, harassment, threats, spam, and more
- **AI-Powered**: Leverages Google Gemini for advanced natural language understanding
- **Explainable Results**: Provides clear reasoning for moderation decisions

---

### 📊 Interactive Documentation

When the server is running, access comprehensive interactive API documentation:

- **Swagger UI**: `http://127.0.0.1:8000/docs`
  - Try endpoints directly in the browser
  - View detailed request/response schemas
  - Generate code examples

- **ReDoc**: `http://127.0.0.1:8000/redoc`
  - Clean, readable documentation
  - Detailed parameter descriptions
  - Example requests and responses

### 🔧 Common Use Cases

#### Batch Content Moderation
```python
import requests

base_url = "http://127.0.0.1:8000"
user_uuid = "your-user-uuid"

# Analyze multiple images
image_urls = [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg"
]

for url in image_urls:
    response = requests.post(f"{base_url}/analyse/image", json={
        "url": url,
        "user_uuid": user_uuid
    })
    result = response.json()
    print(f"Image {url}: {result['decision']}")
```

#### Content with Context
```python
# Analyze text with conversation context
response = requests.post(f"{base_url}/analyse/text", json={
    "text": "That's a terrible idea!",
    "user_uuid": user_uuid,
    "thread_context": [
        "User A: I think we should implement feature X",
        "User B: I disagree, here's why...",
        "User A: What about approach Y?"
    ]
})
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Analysis Logic  │    │  MySQL Database │
│                 │◄──►│                  │◄──►│                 │
│  • Endpoints    │    │  • Image Hash    │    │  • Audit Logs   │
│  • Validation   │    │  • Video Hash    │    │  • Content Hash │
│  • Error Handle │    │  • Text AI       │    │  • Flagged Data │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         └─────────────►│ External APIs    │
                        │                  │
                        │ • SightEngine    │
                        │ • Gemini AI      │
                        └──────────────────┘
```

## Development

### Project Structure
```
unvelit-moderation-api/
├── api.py              # FastAPI application and endpoints
├── requirements.txt    # Python dependencies
├── test_api.py        # API test suite
├── .env.example       # Environment variables template
├── database/
│   └── main.py        # Database client and operations
├── image/
│   └── main.py        # Image analysis and hashing
├── video/
│   └── main.py        # Video analysis and fingerprinting
└── text/
    └── main.py        # Text moderation with AI
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Testing

The project includes comprehensive tests for all endpoints:

```bash
# Run all tests
python test_api.py

# Test specific endpoint
curl -X POST "http://127.0.0.1:8000/analyse/image" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/test.jpg", "user_uuid": "test-uuid"}'
```

## Configuration

### Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `DB_HOST` | MySQL server hostname | Yes | `localhost` or `192.168.1.100` |
| `DB_USER` | MySQL username | Yes | `root` or `mysql_user` |
| `DB_PASS` | MySQL password | Yes | `your_secure_password` |
| `DB_NAME` | Database name | Yes | `unvelit_moderation` |
| `SIGHTENGINE_API_USER` | SightEngine API user ID | Yes | `123456789` |
| `SIGHTENGINE_API_KEY` | SightEngine API key | Yes | `abc123def456...` |
| `GEMINI_API_KEY` | Google Gemini API key | Yes | `AIza...` |

### Performance Tuning

The application uses connection pooling for optimal database performance:

```python
# Adjust pool size based on expected load
pool_size = 10  # Default: 5

# Connection pool automatically manages:
# - Connection reuse
# - Automatic reconnection
# - Transaction isolation
```

## Monitoring & Logging

All moderation requests are logged to the `moderation_log` table with:
- ✅ Unique request ID
- 👤 User identification
- 📊 Content metadata
- 🎯 Moderation decision
- 📝 Detailed reasoning
- 🕒 Timestamp

Query logs for analysis:
```sql
-- Recent moderation activity
SELECT * FROM moderation_log 
ORDER BY created_at DESC 
LIMIT 100;

-- Flagged content summary
SELECT content_type, decision, COUNT(*) as count
FROM moderation_log 
GROUP BY content_type, decision;
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Built with ❤️ for safer online communities
