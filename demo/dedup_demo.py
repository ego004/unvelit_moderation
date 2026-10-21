"""
Duplicate-detection demo: does a repost of an already-moderated image get
caught without paying for another moderation call, and does a new image
never get mistaken for an old one?

    python demo/dedup_demo.py          # needs MySQL and DB_* in .env; no API keys

1. Ten images are stored as already moderated (as SightEngine would have
   left them: 3 flagged, 7 passed), through the real MySQLClient.
2. Each is "reposted" five ways: recompressed, downscaled, brightened,
   cropped and watermarked. Every repost is looked up with the real
   find_similar_images (BIT_COUNT Hamming distance in MySQL).
3. Nine images the system has never seen are looked up too: these must
   not match anything.

The same inputs are then scored with the previous scheme (16-bit pHash,
threshold 8, numeric range pre-filter) for comparison.

The sample images are GAN-generated faces (StyleGAN), not real people.
"""
import io
import os
import sys
from pathlib import Path

import imagehash
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from database.main import MySQLClient  # noqa: E402
from image.main import ImageAnalysis  # noqa: E402

SAMPLES = sorted((Path(__file__).parent / "samples").glob("*.jpg"))
THRESHOLD = 8  # the default in ImageAnalysis.analyse
SEEDED = {0: "flagged", 3: "flagged", 7: "flagged"}  # the rest passed


def jpeg(img, quality):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def reposts(img):
    w, h = img.size
    marked = img.copy()
    d = ImageDraw.Draw(marked)
    d.rectangle((0, h - 34, w, h), fill=(0, 0, 0))
    d.text((8, h - 26), "@reposted_from_insta", fill=(255, 255, 255))
    return {
        "recompressed (JPEG q=35)": jpeg(img, 35),
        "downscaled to 40%": jpeg(img.resize((int(w * .4), int(h * .4))), 85),
        "brightened +25%": jpeg(ImageEnhance.Brightness(img).enhance(1.25), 85),
        "cropped 6% off each side": jpeg(img.crop((int(w * .06), int(h * .06), int(w * .94), int(h * .94))), 85),
        "watermark strip added": jpeg(marked, 85),
    }


def old_scheme_match(candidate, stored):
    """The previous lookup: 16-bit pHash, distance <= 8, hash within +/- 2^8"""
    c = int(str(imagehash.phash(Image.open(io.BytesIO(candidate)), hash_size=4)), 16)
    hits = []
    for s_bytes in stored:
        s = int(str(imagehash.phash(Image.open(io.BytesIO(s_bytes)), hash_size=4)), 16)
        if abs(c - s) <= (1 << THRESHOLD) and bin(c ^ s).count("1") <= THRESHOLD:
            hits.append(s)
    return bool(hits)


def main():
    load_dotenv(ROOT / ".env")
    db = MySQLClient(os.getenv("DB_HOST", "localhost"), os.getenv("DB_USER"),
                     os.getenv("DB_PASS"), os.getenv("DB_NAME", "unvelit_moderation"), pool_size=4)
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM images WHERE url LIKE 'demo://%'")
    conn.commit()
    cur.close()
    conn.close()

    originals = [Image.open(p).convert("RGB") for p in SAMPLES]
    known, fresh = originals[:10], originals[10:]

    print(f"Stored as already moderated: {len(known)} images "
          f"({len(SEEDED)} flagged, {len(known) - len(SEEDED)} passed)")
    stored_bytes = []
    for i, img in enumerate(known):
        data = jpeg(img, 92)
        stored_bytes.append(data)
        a = ImageAnalysis(url=f"demo://original/{i}", content=data)
        db.save_image_hash(a.hash_bytes, a.url, SEEDED.get(i, "pass"), "{}")

    print("\nReposts of stored images (each should match its original and reuse its verdict):")
    caught = total = old_caught = 0
    by_kind = {}
    for i, img in enumerate(known):
        for how, data in reposts(img).items():
            a = ImageAnalysis(url=f"demo://repost/{i}", content=data)
            hits = db.find_similar_images(a.hash_bytes, THRESHOLD)
            ok = bool(hits) and hits[0]["url"] == f"demo://original/{i}"
            verdict_ok = ok and hits[0]["decision"] == SEEDED.get(i, "pass")
            total += 1
            caught += verdict_ok
            old_caught += old_scheme_match(data, [stored_bytes[i]])
            row = by_kind.setdefault(how, [0, 0, []])
            row[0] += verdict_ok
            row[1] += 1
            if ok:
                row[2].append(hits[0]["similarity_score"])
    for how, (n, of, dists) in by_kind.items():
        span = f"distance {min(dists)}-{max(dists)}/64" if dists else ""
        print(f"  {how:<26} {n:>2}/{of} caught, original verdict reused   {span}")
    print(f"  {caught}/{total} reposts caught: each one is a moderation API call saved.")
    print("  pHash is built for re-encodes and resizes, not crops; catching crops needs local")
    print("  features or embeddings, which this service does not do.")

    print("\nImages never seen before (none should match):")
    false_hits = old_false = 0
    for j, img in enumerate(fresh):
        data = jpeg(img, 90)
        a = ImageAnalysis(url=f"demo://new/{j}", content=data)
        hits = db.find_similar_images(a.hash_bytes, THRESHOLD)
        false_hits += bool(hits)
        old_false += old_scheme_match(data, stored_bytes)
        nearest = min(bin(int(str(a.image_hash), 16) ^ int(str(ImageAnalysis(content=s).image_hash), 16)).count("1")
                      for s in stored_bytes)
        print(f"  new image {j}: {'MATCHED (wrong)' if hits else 'no match'}   nearest stored image is {nearest}/64 bits away")

    print("\nSame inputs, previous scheme (16-bit pHash, range pre-filter):")
    print(f"  reposts caught: {old_caught}/{total}     new images wrongly matched: {old_false}/{len(fresh)}")
    print("  (a wrong match makes a new upload inherit another image's verdict, including 'pass')")
    print(f"\nCurrent scheme: reposts caught {caught}/{total}, new images wrongly matched {false_hits}/{len(fresh)}")


if __name__ == "__main__":
    main()
