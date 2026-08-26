import json
from fastapi import APIRouter, Query, Request

from app.core.security import decode_access_token
from app.core.database import redis_client
from app.recommenders.hybrid import HybridRecommender
from app.recommenders.content_based import ContentBasedRecommender
from app.recommenders.embedding import index_games, search_similar_with_data

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_hybrid = HybridRecommender()
_cb = ContentBasedRecommender()


async def _cached(key: str, ttl: int = 180):
    raw = redis_client.get(key)
    if raw:
        return json.loads(raw)
    return None


def _set_cache(key: str, data, ttl: int = 180):
    try:
        redis_client.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


@router.get("/similar/{bgg_id}")
async def similar_games(
    bgg_id: int,
    top_k: int = Query(6, ge=1, le=20),
    method: str = Query("hybrid", enum=["content", "collaborative", "hybrid"]),
):
    cache_key = f"rec:similar:{bgg_id}:{top_k}:{method}"
    cached = await _cached(cache_key, ttl=180)
    if cached:
        return cached

    if method == "content":
        games = await _cb.get_similar_games_with_data(bgg_id, top_k)
    elif method == "collaborative":
        games = await _hybrid.cf.get_similar_games_with_data(bgg_id, top_k)
    else:
        games = await _hybrid.get_similar_with_data(bgg_id, top_k)
    result = {"bgg_id": bgg_id, "method": method, "recommendations": games}
    _set_cache(cache_key, result, ttl=180)
    return result


@router.get("/for-me")
async def recommend_for_me(
    request: Request,
    top_k: int = Query(10, ge=1, le=50),
    min_players: int | None = None,
    max_players: int | None = None,
    max_playtime: int | None = None,
):
    token = request.cookies.get("token")
    user_id = None
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")

    if user_id:
        games = await _hybrid.recommend_for_user(
            user_id, top_k, min_players=min_players,
            max_players=max_players, max_playtime=max_playtime,
        )
    else:
        from app.core.database import mongo_db
        cursor = mongo_db.board_games.find(
            {"name_en": {"$not": {"$regex": r"^Board Game #"}}, "bgg_rating": {"$gt": 0}}
        ).sort("bgg_rating", -1).limit(top_k)
        games = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["recommendation_score"] = doc.get("bgg_rating", 0)
            games.append(doc)

    return {"user_id": user_id, "recommendations": games}


@router.get("/context")
async def context_recommendations(
    top_k: int = Query(10, ge=1, le=50),
    players: int | None = None,
    playtime: int | None = None,
    max_weight: float | None = None,
    category: str | None = None,
    mechanic: str | None = None,
):
    cache_key = f"rec:ctx:{top_k}:{players}:{playtime}:{max_weight}:{category}:{mechanic}"
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query: dict = {}
    filter_query["name_en"] = {"$not": {"$regex": r"^Board Game #"}}
    if players:
        filter_query["min_players"] = {"$lte": players}
        filter_query["max_players"] = {"$gte": players}
    if playtime:
        filter_query["min_playtime"] = {"$lte": playtime}
    if max_weight:
        filter_query["bgg_weight"] = {"$lte": max_weight}
    if category:
        filter_query["categories.name"] = {"$regex": category, "$options": "i"}
    if mechanic:
        filter_query["mechanics.name"] = {"$regex": mechanic, "$options": "i"}

    from app.core.database import mongo_db
    cursor = mongo_db.board_games.find(filter_query).sort("bgg_rating", -1).limit(top_k)
    games = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc["recommendation_score"] = doc.get("bgg_rating", 0)
        games.append(doc)

    result = {"context": filter_query, "recommendations": games}
    _set_cache(cache_key, result, ttl=120)
    return result


@router.post("/index")
async def build_index():
    count = await index_games(batch_size=500)
    return {"status": "ok", "indexed": count}


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
):
    cache_key = f"rec:sem:{q}:{top_k}"
    cached = await _cached(cache_key, ttl=300)
    if cached:
        return cached

    from app.core.database import mongo_db

    enriched = []
    games = await search_similar_with_data(q, top_k * 5)
    enriched = [g for g in games if g.get("name_zh") or (g.get("name_en") and not g["name_en"].startswith("Board Game #"))][:top_k]

    if len(enriched) < top_k:
        remaining = top_k - len(enriched)
        existing_ids = [g["bgg_id"] for g in enriched]
        fq = {
            "name_en": {"$not": {"$regex": r"^Board Game #"}},
            "bgg_id": {"$nin": existing_ids},
            "$or": [
                {"name_en": {"$regex": q, "$options": "i"}},
                {"name_zh": {"$regex": q, "$options": "i"}},
                {"categories.name": {"$regex": q, "$options": "i"}},
                {"categories.name_zh": {"$regex": q, "$options": "i"}},
                {"mechanics.name": {"$regex": q, "$options": "i"}},
            ],
        }
        cursor = mongo_db.board_games.find(fq).sort("bgg_rating", -1).limit(remaining)
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["recommendation_score"] = 0.5
            enriched.append(doc)

    if len(enriched) < top_k:
        remaining = top_k - len(enriched)
        existing_ids = [g["bgg_id"] for g in enriched]
        cursor = mongo_db.board_games.find({
            "name_en": {"$not": {"$regex": r"^Board Game #"}},
            "bgg_id": {"$nin": existing_ids},
        }).sort("bgg_rating", -1).limit(remaining)
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["recommendation_score"] = 0.1
            enriched.append(doc)

    result = {"query": q, "recommendations": enriched}
    _set_cache(cache_key, result, ttl=300)
    return result
