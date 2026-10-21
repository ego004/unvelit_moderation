# Demo: near-duplicate detection in plain MySQL

Unvelit is an anonymous college forum, so every upload is screened before it
appears. Paid moderation (SightEngine for images and video, Gemini for text)
costs money per call, so an image that was already moderated once should be
recognised when it is reposted, and its verdict reused, without calling the API again.

## Run it (no API keys needed)

```bash
pip install -r requirements.txt
mysql -uroot -e "CREATE DATABASE unvelit_moderation"
cp .env.example .env            # fill in DB_HOST / DB_USER / DB_PASS
python demo/dedup_demo.py
```

The script stores ten images as already moderated (three flagged, seven passed)
through the real `MySQLClient`, then looks up reposts and brand-new images
with the real `find_similar_images`:

```
Reposts of stored images (each should match its original and reuse its verdict):
  recompressed (JPEG q=35)   10/10 caught, original verdict reused   distance 0-2/64
  downscaled to 40%          10/10 caught, original verdict reused   distance 0-2/64
  brightened +25%            10/10 caught, original verdict reused   distance 0-6/64
  cropped 6% off each side    1/10 caught, original verdict reused   distance 8-8/64
  watermark strip added       3/10 caught, original verdict reused   distance 8-8/64

Images never seen before (none should match):
  new image 0: no match   nearest stored image is 18/64 bits away
  ...
Same inputs, previous scheme (16-bit pHash, range pre-filter):
  reposts caught: 34/50     new images wrongly matched: 4/9
Current scheme: reposts caught 34/50, new images wrongly matched 0/9
```

## How it works

- `image/main.py`: a 64-bit pHash (8×8 DCT of the downscaled greyscale image) per upload.
- `database/main.py`: the lookup is one query,
  `SELECT … WHERE BIT_COUNT(hash ^ %s) <= 8 ORDER BY BIT_COUNT(hash ^ %s)`: Hamming distance as a
  popcount over a `BIGINT UNSIGNED`, with no vector database or extra service.
- A hit reuses the stored verdict (`flagged` / `review` / `pass`); a miss calls SightEngine and stores the result.
- Video: five frames are sampled and hashed; a repost matches when the summed distance is small.
  Frames are screened one by one and screening stops at the first failing frame.
- Every request lands in `moderation_log` with the verdict and reason.

## What changed while building this demo

The service used 16-bit hashes with a threshold of 8 bits. With only 65,536 possible
hashes, about 60% of unrelated image pairs land within 8 bits of each other, so a
new upload could inherit some other image's verdict, including `pass`. A numeric
`BETWEEN` pre-filter hid part of that, but it also dropped real duplicates whose
differing bits were the high ones. Hashes are now 64-bit and the pre-filter is gone.
Old rows are kept, tagged `hash_bits = 16`, and ignored by lookups; the column is
widened automatically on startup.
