"""Description translation.

The category/mechanic half of this module is gone. It carried a 159-entry
dictionary — a stale subset of the 281 terms in `bgg_categories` and
`bgg_mechanics` — and wrote `translated or cname`, so any term missing from that
dictionary had the *English* name written into its `name_zh`. That is where the
24 English-labelled tags came from, and the route was unauthenticated, so it
could be triggered again at any time. `scripts/backfill_tag_objects.py` repairs
tags from the mapping collections instead.
"""
import re

from fastapi import APIRouter, Query

from app.core.database import mongo_db

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("/descriptions")
async def translate_descriptions(batch_size: int = Query(10, ge=1, le=100)):
    cursor = mongo_db.board_games.find(
        {"description_en": {"$ne": ""}, "description_zh": ""},
        {"bgg_id": 1, "name_en": 1, "description_en": 1},
    ).limit(batch_size)

    games = []
    async for doc in cursor:
        games.append(doc)

    return {
        "status": "ok",
        "pending_count": len(games),
        "message": "Description translation requires LLM API. Use /translate/terms for immediate term translation.",
        "pending_games": [{"bgg_id": g["bgg_id"], "name_en": g.get("name_en", "")} for g in games],
    }
