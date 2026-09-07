import json

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.core.database import mongo_db, redis_client
from app.core.filters import BASE_GAMES_ONLY, build_filters
from app.core.quality import QUALITY_FILTER, merge_filters, quality_gate
from app.core.search import build_name_query, rank_by_relevance
from app.core.security import decode_access_token
from app.recommenders.content_based import ContentBasedRecommender, attach_games
from app.recommenders.diversity import CANDIDATE_MULTIPLIER, diversify
from app.recommenders.embedding import index_games, search_similar_with_data, semantic_enabled
from app.recommenders.hybrid import HybridRecommender, popular_games

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


def _user_id(request: Request) -> str | None:
    token = request.cookies.get("token")
    if not token:
        return None
    payload = decode_access_token(token)
    return payload.get("sub") if payload else None


def _showable(games: list[dict]) -> list[dict]:
    return [game for game in games if (game.get("description_en") or "").strip()]


@router.get("/similar/{bgg_id}")
async def similar_games(
    bgg_id: int,
    top_k: int = Query(6, ge=1, le=20),
    method: str = Query("hybrid", enum=["content", "collaborative", "hybrid"]),
    diverse: bool = Query(True, description="Spread results across series and designers"),
):
    """Games like this one, each carrying the tags it has in common."""
    cache_key = f"rec:similar:{bgg_id}:{top_k}:{method}:{diverse}"
    cached = await _cached(cache_key, ttl=180)
    if cached:
        return cached

    pool = top_k * CANDIDATE_MULTIPLIER if diverse else top_k

    if method == "content":
        games = await _cb.get_similar_games_with_data(bgg_id, pool)
    elif method == "collaborative":
        games = await attach_games(await _hybrid.cf.get_similar_games(bgg_id, pool))
    else:
        games = await _hybrid.get_similar_with_data(bgg_id, pool)

    games = _showable(games)
    games = diversify(games, top_k) if diverse else games[:top_k]

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
    """Personalised where possible, popular where not — never empty."""
    user_id = _user_id(request)

    if user_id:
        games = await _hybrid.recommend_for_user(
            user_id, top_k * CANDIDATE_MULTIPLIER,
            min_players=min_players, max_players=max_players, max_playtime=max_playtime,
        )
        games = diversify(_showable(games), top_k)
    else:
        games = await popular_games(top_k)

    return {"user_id": user_id, "recommendations": games}


class PreferenceRequest(BaseModel):
    """The survey answers, in the shape the content recommender scores against."""
    categories: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)
    weight: float | None = Field(default=None, ge=1, le=5)
    playtime: float | None = Field(default=None, ge=0)
    players: int | None = Field(default=None, ge=1)
    exclude_ids: list[int] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/preferences")
async def recommend_for_preferences(preferences: PreferenceRequest):
    """Cold-start path: rank on stated taste when there is no history to learn from."""
    scored = await _cb.recommend_for_preferences(
        liked_categories=preferences.categories,
        liked_mechanics=preferences.mechanics,
        preferred_weight=preferences.weight,
        preferred_playtime=preferences.playtime,
        exclude_ids=set(preferences.exclude_ids),
        top_k=preferences.top_k * CANDIDATE_MULTIPLIER,
    )
    games = _showable(await attach_games(scored))

    if preferences.players:
        games = [
            game for game in games
            if (game.get("min_players") or 0) <= preferences.players <= (game.get("max_players") or 0)
        ]

    if not games:
        return {"recommendations": await popular_games(preferences.top_k), "fallback": "popular"}

    return {"recommendations": diversify(games, preferences.top_k), "fallback": None}


@router.get("/context")
async def context_recommendations(
    top_k: int = Query(10, ge=1, le=50),
    locale: str = Query("en"),
    players: int | None = None,
    playtime: int | None = None,
    max_weight: float | None = None,
    category: str | None = None,
    mechanic: str | None = None,
):
    """"We are three people with an hour" — filter first, then rank by quality."""
    cache_key = f"rec:ctx:{top_k}:{locale}:{players}:{playtime}:{max_weight}:{category}:{mechanic}"
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query = merge_filters(
        build_filters(
            categories=category, mechanics=mechanic,
            players=players, playtime_max=playtime, max_weight=max_weight,
        ),
        quality_gate(locale),
        BASE_GAMES_ONLY,
    )

    cursor = mongo_db.board_games.find(filter_query).sort("quality_score", -1).limit(top_k * CANDIDATE_MULTIPLIER)
    games = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc["recommendation_score"] = doc.get("quality_score", 0)
        games.append(doc)

    result = {"context": filter_query, "recommendations": diversify(games, top_k)}
    _set_cache(cache_key, result, ttl=120)
    return result


@router.post("/index")
async def build_index():
    count = await index_games()
    return {"status": "ok", "indexed": count}


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    locale: str = Query("en"),
):
    """Meaning-based search, with a lexical top-up when vectors fall short."""
    cache_key = f"rec:sem:{q}:{top_k}:{locale}"
    cached = await _cached(cache_key, ttl=300)
    if cached:
        return cached

    games: list[dict] = []
    if semantic_enabled():
        games = _showable(await search_similar_with_data(q, top_k * 2))[:top_k]

    if len(games) < top_k:
        seen = {game["bgg_id"] for game in games}
        lexical_filter = merge_filters(
            QUALITY_FILTER,
            BASE_GAMES_ONLY,
            {"bgg_id": {"$nin": list(seen)}},
            build_name_query(q),
        )
        cursor = mongo_db.board_games.find(lexical_filter).sort("quality_score", -1).limit(top_k * 3)
        extra = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["recommendation_score"] = doc.get("quality_score", 0)
            extra.append(doc)
        games.extend(rank_by_relevance(extra, q)[: top_k - len(games)])

    if not games:
        games = await popular_games(top_k)

    result = {"query": q, "semantic": semantic_enabled(), "recommendations": games}
    _set_cache(cache_key, result, ttl=300)
    return result
