"""Canonical category / mechanic names.

A case-insensitive `$regex` on `categories.name` cannot use the
`categories_name` index, so tag filtering degraded into a 43k-document scan
(~240 ms). The tag vocabulary is tiny — 85 categories, 196 mechanics — so we
cache it and turn the caller's input into the exact stored name, which the
index can serve directly.
"""
import time

from app.core.database import mongo_db

CACHE_TTL_SECONDS = 600

_FIELDS = {
    "categories": "categories.name",
    "mechanics": "mechanics.name",
}

# field -> (lowercase name -> canonical name, fetched_at)
_cache: dict[str, tuple[dict[str, str], float]] = {}


async def _load(field: str) -> dict[str, str]:
    names = await mongo_db.board_games.distinct(_FIELDS[field])
    return {name.lower(): name for name in names if isinstance(name, str) and name}


async def _lookup(field: str) -> dict[str, str]:
    cached, fetched_at = _cache.get(field, ({}, 0.0))
    if cached and time.monotonic() - fetched_at < CACHE_TTL_SECONDS:
        return cached
    names = await _load(field)
    _cache[field] = (names, time.monotonic())
    return names


async def tag_filter(field: str, value: str) -> dict:
    """Mongo fragment matching one category or mechanic.

    Exact (index-friendly) match when the value is a known tag, case-insensitive
    regex otherwise so partial input still finds something.
    """
    path = _FIELDS[field]
    names = await _lookup(field)
    canonical = names.get(value.strip().lower())
    if canonical:
        return {path: canonical}
    return {path: {"$regex": value, "$options": "i"}}
