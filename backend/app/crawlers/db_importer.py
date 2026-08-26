import asyncio
import os
from datetime import datetime, timezone

from app.core.database import mongo_db
from app.crawlers.bgg_database import BGG_DATABASE

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "images")
THUMBNAIL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "thumbnails")


def _has_local_image(bgg_id: int) -> bool:
    return os.path.exists(os.path.join(IMAGE_DIR, f"{bgg_id}.jpg"))


def _has_local_thumbnail(bgg_id: int) -> bool:
    return os.path.exists(os.path.join(THUMBNAIL_DIR, f"{bgg_id}.jpg"))


def _to_db_record(bgg_id: int, data: dict) -> dict:
    categories = [{"id": i, "name": c} for i, c in enumerate(data.get("categories", []))]
    mechanics = [{"id": i, "name": m} for i, m in enumerate(data.get("mechanics", []))]

    local_image = f"/images/{bgg_id}.jpg" if _has_local_image(bgg_id) else ""
    local_thumbnail = f"/thumbnails/{bgg_id}.jpg" if _has_local_thumbnail(bgg_id) else local_image

    return {
        "bgg_id": bgg_id,
        "name_en": data.get("name", ""),
        "name_zh": data.get("name_zh", ""),
        "description_en": data.get("description", ""),
        "description_zh": data.get("description_zh", ""),
        "image": "",
        "thumbnail": "",
        "local_image": local_image,
        "local_thumbnail": local_thumbnail,
        "year_published": data.get("year_published", 0),
        "min_players": data.get("min_players", 0),
        "max_players": data.get("max_players", 0),
        "min_playtime": data.get("playing_time", 0),
        "max_playtime": data.get("playing_time", 0),
        "min_age": data.get("min_age", 0),
        "bgg_rating": data.get("bgg_rating", 0),
        "bgg_rank": data.get("rank") or 99999,
        "bgg_weight": 0,
        "users_rated": 0,
        "categories": categories,
        "mechanics": mechanics,
        "expansions": [],
        "series": [],
        "designers": data.get("designers", []),
        "publishers": data.get("publishers", []),
        "updated_at": datetime.now(timezone.utc),
    }


async def import_bgg_database():
    count = 0
    with_images = 0
    batch = []

    for bgg_id, data in BGG_DATABASE.items():
        game = _to_db_record(bgg_id, data)
        if game["local_image"]:
            with_images += 1
        batch.append(game)
        count += 1

        if len(batch) >= 50:
            await _save_batch(batch)
            batch = []

    if batch:
        await _save_batch(batch)

    print(f"Import complete: {count} games ({with_images} with local images)")


async def _save_batch(games: list[dict]):
    for game in games:
        await mongo_db.board_games.update_one(
            {"bgg_id": game["bgg_id"]},
            {
                "$set": game,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )


async def import_all_local_images():
    """Import stub records for ALL games that have local images but no DB entry yet."""
    if not os.path.exists(IMAGE_DIR):
        print(f"Image directory not found: {IMAGE_DIR}")
        return

    image_files = [f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg")]
    existing_ids = set()
    async for doc in mongo_db.board_games.find({}, {"bgg_id": 1}):
        existing_ids.add(doc["bgg_id"])

    new_count = 0
    batch = []

    for img_file in image_files:
        bgg_id = int(img_file.replace(".jpg", ""))
        if bgg_id in existing_ids:
            continue

        local_image = f"/images/{bgg_id}.jpg"
        local_thumbnail = f"/thumbnails/{bgg_id}.jpg" if _has_local_thumbnail(bgg_id) else local_image

        game = {
            "bgg_id": bgg_id,
            "name_en": f"Board Game #{bgg_id}",
            "name_zh": "",
            "description_en": "",
            "description_zh": "",
            "image": "",
            "thumbnail": "",
            "local_image": local_image,
            "local_thumbnail": local_thumbnail,
            "year_published": 0,
            "min_players": 0,
            "max_players": 0,
            "min_playtime": 0,
            "max_playtime": 0,
            "min_age": 0,
            "bgg_rating": 0,
            "bgg_rank": 99999,
            "bgg_weight": 0,
            "users_rated": 0,
            "categories": [],
            "mechanics": [],
            "expansions": [],
            "series": [],
            "designers": [],
            "publishers": [],
            "updated_at": datetime.now(timezone.utc),
        }
        batch.append(game)
        new_count += 1

        if len(batch) >= 100:
            await _save_batch(batch)
            batch = []

    if batch:
        await _save_batch(batch)

    print(f"Imported {new_count} stub records for games with local images")
