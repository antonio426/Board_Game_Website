import json
from fastapi import APIRouter, Query
from bson import ObjectId

from app.core.database import mongo_db, redis_client

router = APIRouter(prefix="/games", tags=["games"])

SORT_MAP = {
    "rating": [("bgg_rating", -1)],
    "rank": [("bgg_rank", 1)],
    "name": [("name_en", 1)],
    "weight": [("bgg_weight", -1)],
    "year": [("year_published", -1)],
}


def _cache_key(prefix: str, **kwargs) -> str:
    parts = [prefix] + [f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None]
    return ":".join(parts)


async def _cached(key: str, ttl: int = 300):
    raw = redis_client.get(key)
    if raw:
        return json.loads(raw)
    return None


def _set_cache(key: str, data, ttl: int = 300):
    try:
        redis_client.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


@router.get("")
async def list_games(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    sort: str = Query("rank"),
    min_players: int | None = None,
    max_players: int | None = None,
    min_playtime: int | None = None,
    max_playtime: int | None = None,
    min_rating: float | None = None,
    max_weight: float | None = None,
    min_weight: float | None = None,
    category: str | None = None,
    mechanic: str | None = None,
    q: str | None = None,
):
    cache_key = _cache_key("games", page=page, per_page=per_page, sort=sort,
                           min_players=min_players, max_players=max_players,
                           min_playtime=min_playtime, max_playtime=max_playtime,
                           min_rating=min_rating, max_weight=max_weight, min_weight=min_weight,
                           category=category, mechanic=mechanic, q=q)
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query = {}

    if min_players is not None:
        filter_query["min_players"] = {"$lte": min_players}
    if max_players is not None:
        filter_query["max_players"] = {"$gte": max_players}
    if min_playtime is not None:
        filter_query["min_playtime"] = {"$lte": min_playtime}
    if max_playtime is not None:
        filter_query["max_playtime"] = {"$gte": max_playtime}
    if min_rating is not None:
        filter_query["bgg_rating"] = {"$gte": min_rating}
    if min_weight is not None or max_weight is not None:
        w = {}
        if min_weight is not None:
            w["$gte"] = min_weight
        if max_weight is not None:
            w["$lte"] = max_weight
        filter_query["bgg_weight"] = w
    if category:
        filter_query["categories.name"] = {"$regex": category, "$options": "i"}
    if mechanic:
        filter_query["mechanics.name"] = {"$regex": mechanic, "$options": "i"}
    if q:
        filter_query["$or"] = [
            {"name_en": {"$regex": q, "$options": "i"}},
            {"name_zh": {"$regex": q, "$options": "i"}},
        ]
    else:
        filter_query["name_en"] = {"$not": {"$regex": r"^Board Game #"}}

    sort_key = SORT_MAP.get(sort, [("bgg_rank", 1)])
    skip = (page - 1) * per_page

    total = await mongo_db.board_games.count_documents(filter_query)
    cursor = mongo_db.board_games.find(filter_query).sort(sort_key).skip(skip).limit(per_page)

    games = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        games.append(doc)

    result = {
        "games": games,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }
    _set_cache(cache_key, result, ttl=120)
    return result


@router.get("/categories")
async def list_categories():
    pipeline = [
        {"$unwind": "$categories"},
        {"$group": {"_id": "$categories.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
    ]
    results = []
    async for doc in mongo_db.board_games.aggregate(pipeline):
        results.append({"name": doc["_id"], "count": doc["count"]})
    return results


@router.get("/mechanics")
async def list_mechanics():
    pipeline = [
        {"$unwind": "$mechanics"},
        {"$group": {"_id": "$mechanics.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
    ]
    results = []
    async for doc in mongo_db.board_games.aggregate(pipeline):
        results.append({"name": doc["_id"], "count": doc["count"]})
    return results


@router.get("/{bgg_id}")
async def get_game(bgg_id: int):
    cache_key = f"game:{bgg_id}"
    cached = await _cached(cache_key, ttl=300)
    if cached:
        return cached

    game = await mongo_db.board_games.find_one({"bgg_id": bgg_id})
    if not game:
        return {"error": "not_found"}
    game["id"] = str(game.pop("_id"))

    similar = []
    if game.get("categories") or game.get("mechanics"):
        match = {}
        if game.get("categories"):
            match["categories.name"] = {"$in": [c["name"] for c in game["categories"]]}
        similar_cursor = mongo_db.board_games.find(
            {"bgg_id": {"$ne": bgg_id}, "name_en": {"$not": {"$regex": r"^Board Game #"}}, **match}
        ).sort("bgg_rating", -1).limit(6)
        async for doc in similar_cursor:
            doc["id"] = str(doc.pop("_id"))
            similar.append(doc)

    game["similar_games"] = similar
    _set_cache(cache_key, game, ttl=300)
    return game
