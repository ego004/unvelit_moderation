# unvelit moderation

Content moderation service I built for Unvelit, an anonymous college forum. Anonymous posting plus image uploads is a risky combination, so every upload — image, video or text — goes through this API before it becomes visible.

The part I care about most is the duplicate detection. Media that was already moderated once shouldn't cost money to moderate again: every image gets a 64-bit perceptual hash, and near-duplicate lookup happens directly in MySQL using `BIT_COUNT(stored_hash ^ candidate)` as the Hamming distance — no vector database, no extra service. A repost of an already-rejected image gets blocked without ever hitting the paid moderation API (SightEngine).

## How it works

- `image/` — perceptual hashing, then a SightEngine call only on cache miss
- `video/` — sampled frames screened one by one; stops early the moment a frame fails
- `text/` — Gemini-based moderation with conversation context
- `database/` — the MySQL layer: hash lookups, audit log, connection pooling
- `api.py` — the FastAPI app tying it together

Batch endpoints run analyses concurrently (about 5x the throughput of sequential). Every request lands in an audit table with the verdict and the reason, so moderation decisions can be traced later.

## Running it

```
pip install -r requirements.txt
cp .env.example .env   # MySQL credentials + SightEngine/Gemini keys
uvicorn api:app
```

`demo/dedup_demo.py` shows the dedup path against a local MySQL with no API keys (see [DEMO.md](DEMO.md)); `comprehensive_duplicate_test.py` exercises it end to end through the API. Notes from the optimization passes are in [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md).
