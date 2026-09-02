#!/usr/bin/env python3
"""Download all CDN images/thumbnails to local flat-file storage.

Follows the EXISTING flat-file convention:
  - Thumbnails: data/thumbnails/{bgg_id}.jpg
  - Full images: data/images/{bgg_id}.jpg

NOT the ImageDownloader subdirectory convention (data/images/{bgg_id}/thumb.jpg).

After downloading, updates MongoDB:
  - local_thumbnail: "/thumbnails/{bgg_id}.jpg"  (served by FastAPI static mount)
  - local_image: "/images/{bgg_id}.jpg"

User instruction: "全部local不要依賴外部" — ALL data must be local, no external dependency.

Callers: mongo_db.board_games collection; httpx.AsyncClient for CDN downloads.
Data schemas: MongoDB fields local_image (str), local_thumbnail (str); image/thumbnail (CDN URLs).
Existing convention: data/images/{bgg_id}.jpg flat files (7,753 exist), data/thumbnails/{bgg_id}.jpg (9,998 exist).

Usage:
  python scripts/preload_images.py --thumbnails          # download missing thumbnails only
  python scripts/preload_images.py --images              # download missing full images only
  python scripts/preload_images.py --both                # download both (default)
  python scripts/preload_images.py --both --limit 1000   # limit to 1000 games
  python scripts/preload_images.py --both --all          # process ALL games (180k+)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend/ is on sys.path
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.database import mongo_db

try:
    import httpx
except ImportError:
    print("httpx is required: pip install httpx")
    sys.exit(1)

# Directories — flat-file convention matching existing data
THUMB_DIR = Path(os.getenv("THUMB_DIR", "data/thumbnails"))
IMAGE_DIR = Path(os.getenv("IMAGE_DIR", "data/images"))

# Concurrency & rate limiting
CONCURRENCY = 10
RATE_LIMIT = 1.0  # seconds between requests (shortened from 5.0 for faster batches)


async def download_file(client: httpx.AsyncClient, url: str, dest: Path, sem: asyncio.Semaphore, rate_limit: float) -> bool:
    """Download url to dest. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 0:
        return True  # already downloaded

    async with sem:
        try:
            await asyncio.sleep(rate_limit)
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 500:
                # Sanity check: a real image should be > 500 bytes
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                return True
        except Exception:
            pass  # silent — will be reported as skipped
    return False


async def preload_thumbnails(client: httpx.AsyncClient, sem: asyncio.Semaphore, limit: int | None = None, all_games: bool = False, rate_limit: float = RATE_LIMIT):
    """Download missing thumbnails."""
    query = {
        "thumbnail": {"$ne": "", "$exists": True},
        "$or": [
            {"local_thumbnail": ""},
            {"local_thumbnail": {"$exists": False}},
        ],
    }
    projection = {"bgg_id": 1, "thumbnail": 1}

    cursor = mongo_db.board_games.find(query, projection)
    if not all_games and limit:
        cursor = cursor.limit(limit)

    games = await cursor.to_list(length=limit)
    total = len(games)
    print(f"Thumbnails to download: {total}")

    if total == 0:
        return 0, 0

    success = 0
    fail = 0

    for i, game in enumerate(games, 1):
        bgg_id = game["bgg_id"]
        url = game.get("thumbnail", "")
        if not url:
            fail += 1
            continue

        dest = THUMB_DIR / f"{bgg_id}.jpg"
        ok = await download_file(client, url, dest, sem, rate_limit)
        if ok:
            await mongo_db.board_games.update_one(
                {"bgg_id": bgg_id},
                {"$set": {"local_thumbnail": f"/thumbnails/{bgg_id}.jpg"}},
            )
            success += 1
        else:
            fail += 1

        if i % 100 == 0 or i == total:
            print(f"  [{i}/{total}] thumbs: ok={success} fail={fail}")

    return success, fail


async def preload_images(client: httpx.AsyncClient, sem: asyncio.Semaphore, limit: int | None = None, all_games: bool = False, rate_limit: float = RATE_LIMIT):
    """Download missing full-size images."""
    query = {
        "image": {"$ne": "", "$exists": True},
        "$or": [
            {"local_image": ""},
            {"local_image": {"$exists": False}},
        ],
    }
    projection = {"bgg_id": 1, "image": 1}

    cursor = mongo_db.board_games.find(query, projection)
    if not all_games and limit:
        cursor = cursor.limit(limit)

    games = await cursor.to_list(length=limit)
    total = len(games)
    print(f"Full images to download: {total}")

    if total == 0:
        return 0, 0

    success = 0
    fail = 0

    for i, game in enumerate(games, 1):
        bgg_id = game["bgg_id"]
        url = game.get("image", "")
        if not url:
            fail += 1
            continue

        dest = IMAGE_DIR / f"{bgg_id}.jpg"
        ok = await download_file(client, url, dest, sem, rate_limit)
        if ok:
            await mongo_db.board_games.update_one(
                {"bgg_id": bgg_id},
                {"$set": {"local_image": f"/images/{bgg_id}.jpg"}},
            )
            success += 1
        else:
            fail += 1

        if i % 100 == 0 or i == total:
            print(f"  [{i}/{total}] images: ok={success} fail={fail}")

    return success, fail


async def run(do_thumbs: bool, do_images: bool, limit: int | None, all_games: bool, concurrency: int = CONCURRENCY, rate_limit: float = RATE_LIMIT):
    """Main entry: download selected image types."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        if do_thumbs:
            s, f = await preload_thumbnails(client, sem, limit, all_games, rate_limit)
            print(f"\nThumbnails done: success={s} fail={f}")

        if do_images:
            s, f = await preload_images(client, sem, limit, all_games, rate_limit)
            print(f"\nFull images done: success={s} fail={f}")


def main():
    parser = argparse.ArgumentParser(description="Preload images/thumbnails to local storage")
    parser.add_argument("--thumbnails", action="store_true", help="Download thumbnails only")
    parser.add_argument("--images", action="store_true", help="Download full images only")
    parser.add_argument("--both", action="store_true", help="Download both (default)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of games to process")
    parser.add_argument("--all", dest="all_games", action="store_true", help="Process ALL games (no limit)")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY, help=f"Max concurrent downloads (default: {CONCURRENCY})")
    parser.add_argument("--rate-limit", type=float, default=RATE_LIMIT, help=f"Seconds between requests (default: {RATE_LIMIT})")
    args = parser.parse_args()

    do_thumbs = args.thumbnails or args.both or (not args.images)
    do_images = args.images or args.both or (not args.thumbnails)

    if not args.all_games and args.limit is None:
        args.limit = 500  # safe default

    concurrency = args.concurrency
    print(f"Preload config: thumbs={do_thumbs} images={do_images} limit={args.limit} all={args.all_games} concurrency={concurrency} rate_limit={args.rate_limit}s")

    asyncio.run(run(do_thumbs, do_images, args.limit, args.all_games, concurrency, args.rate_limit))


if __name__ == "__main__":
    main()
