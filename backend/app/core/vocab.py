"""The authority on what a category or mechanic is called.

Two collections, `bgg_categories` (85) and `bgg_mechanics` (196), carry a clean
`{id, name, name_zh}` row for every term. Nothing read them: the endpoints took
the Chinese name from the denormalized copy inside each game document, where
`POST /translate/terms` had written the English name over 48 of them, and
`{"$first": ...}` in the aggregation picked whichever copy it happened to see.

Everything that needs a tag name — the vocabulary endpoints, the facets, the
game payloads, the filter canonicalizer — goes through here instead.

Join on `name`, never on `id`: `bgg_categories.id` is a sequence 1..85 assigned
by scripts/translate_and_migrate.py, not the BGG link id, so the ids in game
documents written by the crawler mean something different.
"""
import logging
import time

from app.core.database import mongo_db

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 600

TAG_COLLECTIONS = {
    "categories": "bgg_categories",
    "mechanics": "bgg_mechanics",
}
TAG_PATHS = {
    "categories": "categories.name",
    "mechanics": "mechanics.name",
}

# field -> (rows, fetched_at)
_cache: dict[str, tuple[list[dict], float]] = {}


async def _fetch(field: str) -> list[dict]:
    collection = mongo_db[TAG_COLLECTIONS[field]]
    rows = [
        {"id": row.get("id") or 0, "name": row["name"], "name_zh": row.get("name_zh") or row["name"]}
        async for row in collection.find({}, {"_id": 0, "id": 1, "name": 1, "name_zh": 1})
        if row.get("name")
    ]
    if rows:
        return sorted(rows, key=lambda row: row["name"])

    # A database that was never seeded still has to serve pages, so fall back to
    # whatever names the games themselves carry — without translations.
    logger.warning("%s is empty; falling back to names from board_games", TAG_COLLECTIONS[field])
    names = await mongo_db.board_games.distinct(TAG_PATHS[field])
    return sorted(
        ({"id": 0, "name": name, "name_zh": name} for name in names if isinstance(name, str) and name),
        key=lambda row: row["name"],
    )


async def ensure_loaded(field: str | None = None) -> None:
    """Warm the cache. Called at startup and defensively before each read."""
    for target in ([field] if field else list(TAG_COLLECTIONS)):
        rows, fetched_at = _cache.get(target, ([], 0.0))
        if rows and time.monotonic() - fetched_at < CACHE_TTL_SECONDS:
            continue
        _cache[target] = (await _fetch(target), time.monotonic())


async def vocabulary(field: str) -> list[dict]:
    """Every known term, name-sorted."""
    await ensure_loaded(field)
    return _cache[field][0]


async def zh_map(field: str) -> dict[str, str]:
    """English name -> Chinese name."""
    return {row["name"]: row["name_zh"] for row in await vocabulary(field)}


async def canonical_map(field: str) -> dict[str, str]:
    """Lowercased English *or Chinese* name -> the stored English name.

    Filtering matches `categories.name`, which is English, so accepting 「卡牌遊戲」
    from a Chinese UI means translating it back here — not running a regex over
    `name_zh`, which would abandon the index.
    """
    mapping: dict[str, str] = {}
    for row in await vocabulary(field):
        mapping[row["name"].lower()] = row["name"]
        mapping[row["name_zh"].lower()] = row["name"]
    return mapping


async def canonical(field: str, value: str) -> str | None:
    return (await canonical_map(field)).get((value or "").strip().lower())


def _normalize_field(items, translations: dict[str, str]) -> list[dict]:
    """Repair one tag array in place-safe fashion.

    Three shapes turn up in the data: plain strings (10,959 documents predate
    the object migration), objects whose `name_zh` echoes the English name, and
    objects with a null `name` — the entries that made Splendor's categories
    render as `,,`.
    """
    normalized: list[dict] = []
    for item in items or []:
        if isinstance(item, str):
            name, tag_id = item, 0
        elif isinstance(item, dict):
            name, tag_id = item.get("name"), item.get("id") or 0
        else:
            continue
        if not name:
            continue
        normalized.append({"id": tag_id, "name": name, "name_zh": translations.get(name) or name})
    return normalized


async def normalize_tags(doc: dict) -> dict:
    """Give a game document well-formed, translated `categories`/`mechanics`."""
    for field in TAG_COLLECTIONS:
        if field in doc:
            doc[field] = _normalize_field(doc[field], await zh_map(field))
    return doc


def normalize_tags_with(doc: dict, translations: dict[str, dict[str, str]]) -> dict:
    """`normalize_tags` for loops, with the translation maps hoisted out."""
    for field in TAG_COLLECTIONS:
        if field in doc:
            doc[field] = _normalize_field(doc[field], translations.get(field, {}))
    return doc
