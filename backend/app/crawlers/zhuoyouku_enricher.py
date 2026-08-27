"""
Zhuoyouku.com Chinese enrichment adapter.

Scrapes zhuoyouku.com for Chinese game names, descriptions, categories,
mechanics, designers, and publishers. Links games to our MongoDB docs
via BGG ID extracted from each detail page.

Page structure:
  - List pages: /boardgame/redu, /boardgame/liupai/*, /boardgame/changjing/*
    contain game links with opaque hash IDs like /boardgame/zg2lv5l1seg00gifmkzrjg7j
  - Detail pages: /boardgame/{hash_id}
    contain ld+json Game schema, BGG link, Chinese categories/mechanics

Two-phase approach:
  Phase 1: Scrape list pages to collect all unique hash IDs
  Phase 2: Fetch each detail page, extract data, write to MongoDB
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://www.zhuoyouku.com"
CONCURRENCY = 3
PER_REQUEST_SLEEP = 2.0
REQUEST_TIMEOUT = 30.0
DEFAULT_LIMIT = 100

# Regex patterns
BGG_ID_RE = re.compile(r"boardgamegeek\.com/boardgame/(\d+)")
LD_JSON_RE = re.compile(
    r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL,
)
GAME_LINK_RE = re.compile(r'/boardgame/([a-zA-Z0-9]+)')
CATEGORY_LINK_RE = re.compile(r'/boardgame/fenlei/(?:zhuti|leixing)/([^/"]+)')
MECHANIC_LINK_RE = re.compile(r'/boardgame/fenlei/jizhi/([^/"]+)')

# List page paths to scrape for game hash IDs
LIST_PAGES = [
    "/boardgame/redu",          # hot / popular
    "/boardgame/xinp",          # new
    "/boardgame/zuigao",        # highest rated
]


def _extract_bgg_id(html: str) -> Optional[int]:
    """Extract BGG numeric ID from a detail page HTML."""
    m = BGG_ID_RE.search(html)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _extract_ld_json(html: str) -> list[dict]:
    """Extract all ld+json script blocks from HTML."""
    blocks = []
    for m in LD_JSON_RE.finditer(html):
        try:
            blocks.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return blocks


def _find_game_schema(schemas: list[dict]) -> Optional[dict]:
    """Find the Game schema from ld+json blocks."""
    for s in schemas:
        if isinstance(s, dict) and s.get("@type") == "Game":
            return s
        # Some sites wrap in @graph
        if isinstance(s, dict) and "@graph" in s:
            for item in s["@graph"]:
                if isinstance(item, dict) and item.get("@type") == "Game":
                    return item
    return None


def _extract_categories_zh(html: str) -> list[str]:
    """Extract Chinese category names from detail page links."""
    cats = []
    seen = set()
    for m in CATEGORY_LINK_RE.finditer(html):
        slug = m.group(1)
        if slug not in seen:
            seen.add(slug)
            # Extract visible text near the link
            after = html[m.end():m.end() + 80]
            text_match = re.search(r'>([^<]+)<', after)
            if text_match:
                text = text_match.group(1).strip()
                if text:
                    cats.append(text)
    return cats


def _extract_mechanics_zh(html: str) -> list[str]:
    """Extract Chinese mechanic names from detail page links."""
    mechs = []
    seen = set()
    for m in MECHANIC_LINK_RE.finditer(html):
        slug = m.group(1)
        if slug not in seen:
            seen.add(slug)
            after = html[m.end():m.end() + 80]
            text_match = re.search(r'>([^<]+)<', after)
            if text_match:
                text = text_match.group(1).strip()
                if text:
                    mechs.append(text)
    return mechs


def _extract_hash_ids(html: str) -> list[str]:
    """Extract all game hash IDs from a list page."""
    ids = []
    seen = set()
    for m in GAME_LINK_RE.finditer(html):
        hid = m.group(1)
        if hid not in seen:
            seen.add(hid)
            ids.append(hid)
    return ids


def _extract_designers(schema: dict) -> list[str]:
    """Extract designer names from Game schema."""
    authors = schema.get("author") or []
    if isinstance(authors, dict):
        authors = [authors]
    result = []
    for a in authors:
        if isinstance(a, dict):
            name = a.get("name", "")
            if name:
                result.append(name)
        elif isinstance(a, str):
            result.append(a)
    return result


def _extract_publishers(schema: dict) -> list[str]:
    """Extract publisher names from Game schema."""
    pubs = schema.get("publisher") or []
    if isinstance(pubs, dict):
        pubs = [pubs]
    result = []
    for p in pubs:
        if isinstance(p, dict):
            name = p.get("name", "")
            if name:
                result.append(name)
        elif isinstance(p, str):
            result.append(p)
    return result


def _extract_players(schema: dict) -> tuple[Optional[int], Optional[int]]:
    """Extract min/max players from Game schema."""
    players = schema.get("numberOfPlayers")
    if isinstance(players, dict):
        return players.get("minValue"), players.get("maxValue")
    return None, None


def parse_detail_page(html: str, hash_id: str) -> Optional[dict]:
    """Parse a zhuoyouku detail page and return update dict."""
    bgg_id = _extract_bgg_id(html)
    if not bgg_id:
        logger.debug("zhuoyouku %s: no BGG ID found", hash_id)
        return None

    schemas = _extract_ld_json(html)
    game_schema = _find_game_schema(schemas)

    update: dict = {"bgg_id": bgg_id, "zhuoyouku_id": hash_id}

    if game_schema:
        name = game_schema.get("name", "")
        if name:
            update["name_zh"] = name

        alt_name = game_schema.get("alternateName", "")
        if alt_name:
            update["name_en_from_zhuoyouku"] = alt_name

        desc = game_schema.get("description", "")
        if desc:
            # Strip any residual HTML
            desc = re.sub(r"<[^>]+>", "", desc).strip()
            if desc:
                update["description_zh"] = desc

        genre = game_schema.get("genre", "")
        if isinstance(genre, list):
            genre = ", ".join(genre)
        if genre:
            update["genre_zh"] = genre

        designers = _extract_designers(game_schema)
        if designers:
            update["designers_zh"] = designers

        publishers = _extract_publishers(game_schema)
        if publishers:
            update["publishers_zh"] = publishers

        min_p, max_p = _extract_players(game_schema)
        if min_p is not None:
            update["min_players_zh"] = int(min_p)
        if max_p is not None:
            update["max_players_zh"] = int(max_p)

        date_pub = game_schema.get("datePublished", "")
        if date_pub:
            try:
                update["year_published_zhuoyouku"] = int(str(date_pub)[:4])
            except ValueError:
                pass

    # Extract categories and mechanics from page links (not in ld+json)
    categories_zh = _extract_categories_zh(html)
    if categories_zh:
        update["categories_zh"] = categories_zh

    mechanics_zh = _extract_mechanics_zh(html)
    if mechanics_zh:
        update["mechanics_zh"] = mechanics_zh

    update["last_zhuoyouku_enriched_at"] = datetime.now(timezone.utc)

    return update


# ── Phase 1: collect hash IDs from list pages ──────────────────────────


async def _fetch_list_page(client: httpx.AsyncClient, path: str) -> list[str]:
    """Fetch a list page and return game hash IDs found on it."""
    url = f"{BASE_URL}{path}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning("zhuoyouku list %s -> HTTP %s", url, resp.status_code)
            return []
        return _extract_hash_ids(resp.text)
    except Exception as e:
        logger.warning("zhuoyouku list %s error: %s", url, e)
        return []


async def collect_hash_ids(client: httpx.AsyncClient) -> list[str]:
    """Collect all unique game hash IDs from known list pages."""
    all_ids: list[str] = []
    seen: set[str] = set()

    for path in LIST_PAGES:
        ids = await _fetch_list_page(client, path)
        for hid in ids:
            if hid not in seen:
                seen.add(hid)
                all_ids.append(hid)
        await asyncio.sleep(PER_REQUEST_SLEEP)

    # Also scrape category pages for broader coverage
    category_paths = [
        "/boardgame/liupai/meishi",       # beauty / aesthetic
        "/boardgame/liupai/tehui",        # party
        "/boardgame/liupai/ershui",       # two-player
        "/boardgame/changjing/changju",   # long
        "/boardgame/changjing/zhongdeng", # medium
        "/boardgame/changjing/duanzan",   # short
    ]
    for path in category_paths:
        ids = await _fetch_list_page(client, path)
        for hid in ids:
            if hid not in seen:
                seen.add(hid)
                all_ids.append(hid)
        await asyncio.sleep(PER_REQUEST_SLEEP)

    logger.info("[zhuoyouku] collected %d unique hash IDs", len(all_ids))
    return all_ids


# ── Phase 2: fetch detail pages and write to MongoDB ───────────────────


async def _process_one(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    db,
    hash_id: str,
    stats: dict,
) -> None:
    """Fetch one detail page, parse, and upsert into MongoDB."""
    async with sem:
        try:
            await asyncio.sleep(PER_REQUEST_SLEEP)
            url = f"{BASE_URL}/boardgame/{hash_id}"
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning("zhuoyouku detail %s -> HTTP %s", hash_id, resp.status_code)
                stats["failed"] += 1
                return

            update = parse_detail_page(resp.text, hash_id)
            if not update:
                stats["no_bgg_id"] += 1
                return

            bgg_id = update.pop("bgg_id")

            # Only write if we have meaningful Chinese data
            has_zh = bool(update.get("name_zh") or update.get("description_zh"))
            if not has_zh:
                stats["no_zh_data"] += 1
                return

            await db.board_games.update_one(
                {"bgg_id": bgg_id},
                {"$set": update},
            )
            stats["updated"] += 1

        except Exception as e:
            logger.warning("zhuoyouku process %s error: %s", hash_id, e)
            stats["failed"] += 1


# ── Public entry point ──────────────────────────────────────────────────


async def enrich_from_zhuoyouku(
    limit: int = DEFAULT_LIMIT,
    only_missing_zh: bool = True,
) -> dict:
    """
    Enrich MongoDB board_games with Chinese data from zhuoyouku.com.

    Args:
        limit: Max number of detail pages to process.
        only_missing_zh: If True, only update docs that lack name_zh.

    Returns:
        Stats dict with updated/failed/skipped counts.
    """
    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    db = mongo_client[settings.MONGO_DB_NAME]

    stats = {
        "updated": 0,
        "failed": 0,
        "no_bgg_id": 0,
        "no_zh_data": 0,
        "total_hash_ids": 0,
        "processed": 0,
    }

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": "BoardGameHub/1.0 (zhuoyouku-enricher)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    ) as client:
        # Phase 1: collect hash IDs
        hash_ids = await collect_hash_ids(client)
        stats["total_hash_ids"] = len(hash_ids)

        if not hash_ids:
            logger.info("[zhuoyouku] no hash IDs found, nothing to do")
            mongo_client.close()
            return stats

        # Apply limit
        hash_ids = hash_ids[:limit]

        # Phase 2: process detail pages
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [
            asyncio.create_task(_process_one(sem, client, db, hid, stats))
            for hid in hash_ids
        ]

        total = len(tasks)
        stats["processed"] = total

        for i, t in enumerate(asyncio.as_completed(tasks), 1):
            await t
            if i % 10 == 0 or i == total:
                logger.info(
                    "[zhuoyouku] %d/%d updated=%d failed=%d no_bgg=%d no_zh=%d",
                    i, total,
                    stats["updated"], stats["failed"],
                    stats["no_bgg_id"], stats["no_zh_data"],
                )

    mongo_client.close()

    logger.info(
        "[zhuoyouku] done updated=%d failed=%d no_bgg=%d no_zh=%d",
        stats["updated"], stats["failed"],
        stats["no_bgg_id"], stats["no_zh_data"],
    )
    return stats


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIMIT
    asyncio.run(enrich_from_zhuoyouku(limit=lim))
