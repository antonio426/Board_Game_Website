import json
import logging
from fastapi import APIRouter, Query
from bson import ObjectId

from app.core.cjk import expand_query_variants
from app.core.database import mongo_db, redis_client
from app.recommenders.embedding import search_similar, search_similar_with_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["games"])

SORT_MAP = {
    "rating": [("bgg_rating", -1)],
    "rank": [("bgg_rank", 1)],
    "name": [("name_en", 1)],
    "weight": [("bgg_weight", -1)],
    "year": [("year_published", -1)],
}


def _format_game(doc: dict, locale: str = "en") -> dict:
    """Locale-aware game formatting: zh → name_zh priority, local images."""
    doc["id"] = str(doc.pop("_id", ""))

    if locale and locale.startswith("zh"):
        display_name = doc.get("name_zh") or doc.get("name_en") or ""
        doc["display_name"] = display_name
    else:
        doc["display_name"] = doc.get("name_en") or doc.get("name_zh") or ""

    bgg_id = doc.get("bgg_id")
    if not doc.get("local_thumbnail") and bgg_id:
        doc["local_thumbnail"] = f"/thumbnails/{bgg_id}.jpg"
    if not doc.get("local_image") and bgg_id:
        doc["local_image"] = f"/images/{bgg_id}.jpg"

    return doc


def _should_hide_low_rated(doc: dict, locale: str) -> bool:
    """In zh locale, hide games with very low rating and few ratings."""
    if not locale or not locale.startswith("zh"):
        return False
    rating = doc.get("bgg_rating", 0) or 0
    num_ratings = doc.get("num_ratings", 0) or 0
    return rating < 3 and num_ratings < 50


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
    locale: str = Query("en"),
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
    cache_key = _cache_key("games", page=page, per_page=per_page, sort=sort, locale=locale,
                           min_players=min_players, max_players=max_players,
                           min_playtime=min_playtime, max_playtime=max_playtime,
                           min_rating=min_rating, max_weight=max_weight, min_weight=min_weight,
                           category=category, mechanic=mechanic, q=q)
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query = {}
    if locale and locale.startswith("zh"):
        filter_query["$or"] = [
            {"bgg_rating": {"$gte": 3}},
            {"num_ratings": {"$gte": 50}},
        ]

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
        q_variants = expand_query_variants(q)
        or_clauses = []
        for v in q_variants:
            or_clauses.append({"name_en": {"$regex": v, "$options": "i"}})
            or_clauses.append({"name_zh": {"$regex": v, "$options": "i"}})
            or_clauses.append({"aliases": {"$regex": v, "$options": "i"}})
        if "$or" in filter_query:
            filter_query = {"$and": [
                filter_query,
                {"$or": or_clauses}
            ]}
        else:
            filter_query["$or"] = or_clauses

    stub_filter = {"description_en": {"$exists": True, "$ne": ""}}
    if "$and" in filter_query:
        filter_query["$and"].append(stub_filter)
    else:
        filter_query = {"$and": [filter_query, stub_filter]}

    sort_key = SORT_MAP.get(sort, [("bgg_rank", 1)])
    skip = (page - 1) * per_page

    total = await mongo_db.board_games.count_documents(filter_query)
    cursor = mongo_db.board_games.find(filter_query).sort(sort_key).skip(skip).limit(per_page)

    games = []
    async for doc in cursor:
        games.append(_format_game(doc, locale))

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
        {"$group": {"_id": "$categories.name", "name_zh": {"$first": "$categories.name_zh"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
    ]
    results = []
    async for doc in mongo_db.board_games.aggregate(pipeline):
        results.append({"name": doc["_id"], "name_zh": doc.get("name_zh") or doc["_id"], "count": doc["count"]})
    return results


@router.get("/mechanics")
async def list_mechanics():
    pipeline = [
        {"$unwind": "$mechanics"},
        {"$group": {"_id": "$mechanics.name", "name_zh": {"$first": "$mechanics.name_zh"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
    ]
    results = []
    async for doc in mongo_db.board_games.aggregate(pipeline):
        results.append({"name": doc["_id"], "name_zh": doc.get("name_zh") or doc["_id"], "count": doc["count"]})
    return results


@router.get("/search")
async def search_games(
    q: str | None = None,
    semantic: bool = Query(False),
    locale: str = Query("en"),
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    categories: str | None = None,
    min_players: int | None = None,
    max_players: int | None = None,
    min_playtime: int | None = None,
    max_playtime: int | None = None,
    mechanics: str | None = None,
    designers: str | None = None,
    publishers: str | None = None,
    min_ratings: int | None = None,
):
    cache_key = _cache_key("search", q=q, semantic=semantic, locale=locale, page=page,
                           per_page=per_page, categories=categories,
                           min_players=min_players, max_players=max_players,
                           min_playtime=min_playtime, max_playtime=max_playtime,
                           mechanics=mechanics, designers=designers, publishers=publishers,
                           min_ratings=min_ratings)
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query: dict = {}
    if categories:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()]
        if cat_list:
            filter_query["categories.name"] = {"$in": cat_list}
    if mechanics:
        mech_list = [m.strip() for m in mechanics.split(",") if m.strip()]
        if mech_list:
            filter_query["mechanics.name"] = {"$in": mech_list}
    if designers:
        des_list = [d.strip() for d in designers.split(",") if d.strip()]
        if des_list:
            filter_query["designers.name"] = {"$in": des_list}
    if publishers:
        pub_list = [p.strip() for p in publishers.split(",") if p.strip()]
        if pub_list:
            filter_query["publishers.name"] = {"$in": pub_list}
    if min_players is not None:
        filter_query["min_players"] = {"$lte": min_players}
    if max_players is not None:
        filter_query["max_players"] = {"$gte": max_players}
    if min_playtime is not None:
        filter_query["min_playtime"] = {"$lte": min_playtime}
    if max_playtime is not None:
        filter_query["max_playtime"] = {"$gte": max_playtime}
    if min_ratings is not None:
        filter_query["num_ratings"] = {"$gte": min_ratings}
    # Quality filter: only games with actual BGG data
    filter_query["description_en"] = {"$exists": True, "$ne": ""}

    if semantic and q:
        try:
            results = search_similar(q, limit=200)
            bgg_ids = [r.get("bgg_id") or r.get("id") for r in results if r]
            if bgg_ids:
                filter_query["bgg_id"] = {"$in": bgg_ids}
                docs = []
                async for doc in mongo_db.board_games.find(filter_query):
                    docs.append(doc)
                id_order = {gid: i for i, gid in enumerate(bgg_ids)}
                docs.sort(key=lambda d: id_order.get(d.get("bgg_id"), 9999))
                total = len(docs)
                skip = (page - 1) * per_page
                page_docs = docs[skip:skip + per_page]
                games = [_format_game(d, locale) for d in page_docs]
            else:
                games = []
                total = 0
        except Exception:
            q_variants = expand_query_variants(q)
            or_clauses = []
            for v in q_variants:
                or_clauses.append({"name_en": {"$regex": v, "$options": "i"}})
                or_clauses.append({"name_zh": {"$regex": v, "$options": "i"}})
                or_clauses.append({"aliases": {"$regex": v, "$options": "i"}})
            filter_query["$or"] = or_clauses
            total = await mongo_db.board_games.count_documents(filter_query)
            skip = (page - 1) * per_page
            cursor = mongo_db.board_games.find(filter_query).sort("bgg_rating", -1).skip(skip).limit(per_page)
            games = []
            async for doc in cursor:
                games.append(_format_game(doc, locale))
    elif q:
        q_variants = expand_query_variants(q)
        or_clauses = []
        for v in q_variants:
            or_clauses.append({"name_en": {"$regex": v, "$options": "i"}})
            or_clauses.append({"name_zh": {"$regex": v, "$options": "i"}})
            or_clauses.append({"aliases": {"$regex": v, "$options": "i"}})
        filter_query["$or"] = or_clauses
        total = await mongo_db.board_games.count_documents(filter_query)
        skip = (page - 1) * per_page
        cursor = mongo_db.board_games.find(filter_query).sort("bgg_rating", -1).skip(skip).limit(per_page)
        games = []
        async for doc in cursor:
            games.append(_format_game(doc, locale))
    else:
        total = await mongo_db.board_games.count_documents(filter_query)
        skip = (page - 1) * per_page
        cursor = mongo_db.board_games.find(filter_query).sort("bgg_rating", -1).skip(skip).limit(per_page)
        games = []
        async for doc in cursor:
            games.append(_format_game(doc, locale))



    result = {
        "games": games,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "semantic": semantic and bool(q),
    }
    _set_cache(cache_key, result, ttl=120)
    return result


@router.get("/{bgg_id}")
async def get_game(bgg_id: int, locale: str = Query("en")):
    cache_key = f"game:{bgg_id}:{locale}"
    cached = await _cached(cache_key, ttl=300)
    if cached:
        return cached

    game = await mongo_db.board_games.find_one({"bgg_id": bgg_id})
    if not game:
        return {"error": "not_found"}

    _format_game(game, locale)

    _set_cache(cache_key, game, ttl=300)
    return game
