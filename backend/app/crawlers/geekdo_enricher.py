import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

logger = logging.getLogger(__name__)

GEEKDO_BASE = "https://api.geekdo.com/api/geekitems"
CONCURRENCY = 5
PER_REQUEST_SLEEP = 1.5
REQUEST_TIMEOUT = 30.0
DEFAULT_LIMIT = 100

CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _pick_cjk_name(alternatenames: list[dict]) -> Optional[str]:
    for entry in alternatenames or []:
        name = entry.get("name", "")
        if name and CJK_RE.search(name):
            return name
    return None


def _pick_link_names(links: dict, link_type: str) -> list[str]:
    out = []
    for entry in links.get(link_type, []) or []:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict):
            n = entry.get("name")
            if n:
                out.append(n)
    return out


def _parse_game_payload(payload: dict, bgg_id: int) -> dict:
    item = payload.get("item") or {}
    if not item:
        return {}

    images = item.get("images") or {}
    links = item.get("links") or {}

    update: dict = {}

    description_text = _strip_html(item.get("description") or "")
    if description_text:
        update["description_en"] = description_text

    if item.get("yearpublished"):
        update["year_published"] = int(item["yearpublished"])

    if item.get("minplayers") is not None:
        update["min_players"] = int(item["minplayers"])
    if item.get("maxplayers") is not None:
        update["max_players"] = int(item["maxplayers"])
    if item.get("minplaytime") is not None:
        update["min_playtime"] = int(item["minplaytime"])
    if item.get("maxplaytime") is not None:
        update["max_playtime"] = int(item["maxplaytime"])
    if item.get("minage") is not None:
        update["min_age"] = int(item["minage"])

    image_url = item.get("imageurl") or images.get("original")
    thumb_url = images.get("thumb") or item.get("thumbnail")
    if image_url:
        update["image"] = image_url
    if thumb_url:
        update["thumbnail"] = thumb_url

    categories = _pick_link_names(links, "boardgamecategory")
    update["categories"] = categories

    mechanics = _pick_link_names(links, "boardgamemechanic")
    update["mechanics"] = mechanics

    designers = _pick_link_names(links, "boardgamedesigner")
    update["designers"] = designers

    publishers = _pick_link_names(links, "boardgamepublisher")
    update["publishers"] = publishers

    cjk = _pick_cjk_name(item.get("alternatenames") or [])
    if cjk:
        update["name_zh"] = cjk

    update["bgg_id"] = bgg_id

    return update


async def _fetch_one(client: httpx.AsyncClient, bgg_id: int) -> tuple[int, Optional[dict]]:
    url = f"{GEEKDO_BASE}?objectid={bgg_id}&objecttype=thing&showstats=1"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return bgg_id, resp.json()
        logger.warning("geekdo %s -> HTTP %s", bgg_id, resp.status_code)
        return bgg_id, None
    except Exception as e:
        logger.warning("geekdo %s error: %s", bgg_id, e)
        return bgg_id, None


async def _process_one(sem, client, db, bgg_id: int, stats: dict) -> None:
    async with sem:
        try:
            await asyncio.sleep(PER_REQUEST_SLEEP)
            _id, payload = await _fetch_one(client, bgg_id)
            if not payload:
                stats["failed"] += 1
                return

            update = _parse_game_payload(payload, _id)
            update.pop("bgg_id", None)
            update["last_enriched_at"] = datetime.now(timezone.utc)

            if not update:
                stats["skipped"] += 1
                return

            await db.board_games.update_one({"bgg_id": _id}, {"$set": update})
            stats["updated"] += 1
        except Exception as e:
            logger.warning("process %s error: %s", bgg_id, e)
            stats["failed"] += 1


async def enrich_from_geekdo(
    limit: int = DEFAULT_LIMIT,
    only_missing: bool = True,
    max_rank: Optional[int] = None,
    min_rank: Optional[int] = None,
) -> dict:
    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    db = mongo_client[settings.MONGO_DB_NAME]

    query: dict = {}
    if only_missing:
        query = {
            "$or": [
                {"description_en": {"$exists": False}},
                {"description_en": ""},
                {"image": {"$exists": False}},
                {"image": ""},
                {"categories": {"$exists": False}},
                {"categories": []},
            ]
        }

    if max_rank is not None or min_rank is not None:
        # Restrict to a ranked slice. Docs without a real rank have
        # bgg_rank=99999 (normalised placeholder) and are excluded.
        rank_clause: dict = {"bgg_rank": {"$gt": (min_rank or 1) - 1}}
        if max_rank is not None:
            rank_clause["bgg_rank"]["$lte"] = max_rank
        if min_rank is not None and min_rank > 1:
            rank_clause["bgg_rank"]["$gte"] = min_rank
        query = {**rank_clause, **query} if not query else {"$and": [rank_clause, query]}

    scan_limit = limit if (max_rank is not None or min_rank is not None) else limit * 3
    cursor = db.board_games.find(query, {"bgg_id": 1}).limit(scan_limit)
    ids = []
    seen = set()
    async for doc in cursor:
        bid = doc.get("bgg_id")
        if bid and bid not in seen:
            seen.add(bid)
            ids.append(bid)
        if len(ids) >= limit:
            break

    print(f"[geekdo] candidates={len(ids)} (limit={limit}, max_rank={max_rank})")

    stats = {"updated": 0, "failed": 0, "skipped": 0, "total": len(ids)}
    if not ids:
        mongo_client.close()
        return stats

    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "BoardGameHub/1.0 (geekdo-enricher)"},
    ) as client:
        tasks = [
            asyncio.create_task(_process_one(sem, client, db, bid, stats))
            for bid in ids
        ]
        total = len(tasks)
        for i, t in enumerate(asyncio.as_completed(tasks), 1):
            await t
            if i % 25 == 0 or i == total:
                print(
                    f"[geekdo] {i}/{total} "
                    f"updated={stats['updated']} failed={stats['failed']} skipped={stats['skipped']}"
                )

    mongo_client.close()
    print(
        f"[geekdo] done updated={stats['updated']} "
        f"failed={stats['failed']} skipped={stats['skipped']}"
    )
    return stats


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIMIT
    max_rank = int(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(enrich_from_geekdo(limit=lim, max_rank=max_rank))
