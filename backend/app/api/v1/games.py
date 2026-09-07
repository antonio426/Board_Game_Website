import json
import logging
from fastapi import APIRouter, Query
from bson import ObjectId

from app.core.database import mongo_db, redis_client
from app.core.filters import BASE_GAMES_ONLY, build_filters, single_tag_filters
from app.core.quality import merge_filters, quality_gate
from app.core.search import build_name_query, paged_search, rank_by_relevance, rerank_semantic
from app.recommenders.embedding import search_similar, semantic_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["games"])

SORT_MAP = {
    "quality": [("quality_score", -1)],
    "rating": [("bgg_rating", -1)],
    "rank": [("bgg_rank", 1)],
    "name": [("name_en", 1)],
    "weight": [("bgg_weight", -1)],
    "year": [("year_published", -1)],
}
DEFAULT_SORT = "quality"


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


# How many vector hits to pull before applying the Mongo filter. Large enough
# that filtering does not empty the page, small enough to stay one query.
SEMANTIC_CANDIDATES = 200


async def _semantic_page(query: str, filter_query: dict, page: int, per_page: int) -> tuple[list[dict], int]:
    """Vector hits, narrowed by the same filters and kept in similarity order."""
    hits = await search_similar(query, top_k=SEMANTIC_CANDIDATES)
    if not hits:
        return [], 0

    scores = {hit["bgg_id"]: hit["score"] for hit in hits}
    scoped = merge_filters(filter_query, {"bgg_id": {"$in": list(scores)}})
    docs = await mongo_db.board_games.find(scoped).to_list(length=SEMANTIC_CANDIDATES)
    docs = rerank_semantic(docs, scores)

    skip = (page - 1) * per_page
    return docs[skip:skip + per_page], len(docs)


@router.get("/random")
async def random_game(locale: str = Query("en")):
    """Random pick, sampled from the showable set so it never lands on a stub."""
    pipeline = [{"$match": quality_gate(locale)}, {"$sample": {"size": 1}}]
    docs = await mongo_db.board_games.aggregate(pipeline).to_list(length=1)
    if not docs:
        return {"error": "no_games"}
    return _format_game(docs[0], locale)


@router.get("")
async def list_games(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    sort: str = Query(DEFAULT_SORT),
    locale: str = Query("en"),
    include_expansions: bool = Query(False),
    players: int | None = Query(None, description="Playable with this many players"),
    best_at_players: bool = Query(False, description="Restrict `players` to counts BGG voted best"),
    playtime_max: int | None = Query(None, description="Finishes within this many minutes"),
    playtime_min: int | None = Query(None, description="Runs at least this many minutes"),
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
    """List games.

    `players` / `playtime_max` / `playtime_min` express what a person actually
    wants ("we are four people and have an hour"). The older `min_players`,
    `max_players`, `min_playtime` and `max_playtime` parameters are single-sided
    range-overlap tests kept for compatibility: `max_playtime=30` means "its
    ceiling is at least 30 minutes", which is the opposite of what most callers
    assume. Prefer the first three.
    """
    cache_key = _cache_key("games", page=page, per_page=per_page, sort=sort, locale=locale,
                           include_expansions=include_expansions,
                           min_players=min_players, max_players=max_players,
                           min_playtime=min_playtime, max_playtime=max_playtime,
                           min_rating=min_rating, max_weight=max_weight, min_weight=min_weight,
                           players=players, best_at_players=best_at_players,
                           playtime_max=playtime_max, playtime_min=playtime_min,
                           category=category, mechanic=mechanic, q=q)
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query = merge_filters(
        build_filters(
            players=players, best_at_players=best_at_players,
            playtime_max=playtime_max, playtime_min=playtime_min,
            min_players=min_players, max_players=max_players,
            min_playtime=min_playtime, max_playtime=max_playtime,
            min_rating=min_rating, min_weight=min_weight, max_weight=max_weight,
        ),
        await single_tag_filters(category, mechanic),
    )

    filter_query = merge_filters(
        filter_query,
        quality_gate(locale),
        None if include_expansions else BASE_GAMES_ONLY,
        build_name_query(q),
    )

    sort_key = SORT_MAP.get(sort, SORT_MAP[DEFAULT_SORT])
    docs, total = await paged_search(mongo_db.board_games, filter_query, q, page, per_page, sort_key)
    games = [_format_game(doc, locale) for doc in docs]

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
        {"$match": {"categories.name": {"$nin": [None, ""]}}},
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
        {"$match": {"mechanics.name": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$mechanics.name", "name_zh": {"$first": "$mechanics.name_zh"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
    ]
    results = []
    async for doc in mongo_db.board_games.aggregate(pipeline):
        results.append({"name": doc["_id"], "name_zh": doc.get("name_zh") or doc["_id"], "count": doc["count"]})
    return results



PLAYER_FACET_COUNTS = (1, 2, 3, 4, 5, 6, 8)
PLAYTIME_BUCKETS = ((0, 30), (31, 60), (61, 120), (121, 100000))
WEIGHT_BUCKETS = ((1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0))
FACET_TAG_LIMIT = 60


def _bucket_key(prefix: str, low: float, high: float) -> str:
    """`$facet` keys are field paths, so they cannot contain a dot."""
    return f"{prefix}_{low}_{high}".replace(".", "_")


def _tag_facet(field: str) -> list[dict]:
    return [
        {"$unwind": f"${field}"},
        {"$match": {f"{field}.name": {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${field}.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": FACET_TAG_LIMIT},
    ]


@router.get("/facets")
async def game_facets(
    locale: str = Query("en"),
    q: str | None = None,
    categories: str | None = None,
    mechanics: str | None = None,
    categories_mode: str = Query("any", enum=["any", "all"]),
    mechanics_mode: str = Query("any", enum=["any", "all"]),
    exclude_categories: str | None = None,
    exclude_mechanics: str | None = None,
    include_expansions: bool = Query(False),
    players: int | None = None,
    best_at_players: bool = Query(False),
    playtime_max: int | None = None,
    playtime_min: int | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    min_ratings: int | None = None,
):
    """How many games each filter option would still leave, given the others.

    Without this a user can assemble a combination that is guaranteed to return
    nothing, and only finds out after clicking.
    """
    cache_key = _cache_key(
        "facets", locale=locale, q=q, categories=categories, mechanics=mechanics,
        categories_mode=categories_mode, mechanics_mode=mechanics_mode,
        exclude_categories=exclude_categories, exclude_mechanics=exclude_mechanics,
        include_expansions=include_expansions, players=players, best_at_players=best_at_players,
        playtime_max=playtime_max, playtime_min=playtime_min,
        min_weight=min_weight, max_weight=max_weight, min_ratings=min_ratings,
    )
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query = merge_filters(
        build_filters(
            categories=categories, mechanics=mechanics,
            categories_mode=categories_mode, mechanics_mode=mechanics_mode,
            exclude_categories=exclude_categories, exclude_mechanics=exclude_mechanics,
            players=players, best_at_players=best_at_players,
            playtime_max=playtime_max, playtime_min=playtime_min,
            min_weight=min_weight, max_weight=max_weight, min_ratings=min_ratings,
        ),
        quality_gate(locale),
        None if include_expansions else BASE_GAMES_ONLY,
        build_name_query(q),
    )

    facet_stage: dict = {
        "categories": _tag_facet("categories"),
        "mechanics": _tag_facet("mechanics"),
        "total": [{"$count": "count"}],
    }
    for count in PLAYER_FACET_COUNTS:
        facet_stage[f"players_{count}"] = [
            {"$match": {"min_players": {"$lte": count}, "max_players": {"$gte": count}}},
            {"$count": "count"},
        ]
    for low, high in PLAYTIME_BUCKETS:
        facet_stage[_bucket_key("playtime", low, high)] = [
            {"$match": {"max_playtime": {"$gt": 0, "$gte": low, "$lte": high}}},
            {"$count": "count"},
        ]
    for low, high in WEIGHT_BUCKETS:
        facet_stage[_bucket_key("weight", low, high)] = [
            {"$match": {"bgg_weight": {"$gte": low, "$lt": high}}},
            {"$count": "count"},
        ]

    pipeline = [{"$match": filter_query}, {"$facet": facet_stage}]
    raw = await mongo_db.board_games.aggregate(pipeline).to_list(length=1)
    buckets = raw[0] if raw else {}

    def count_of(key: str) -> int:
        entries = buckets.get(key) or []
        return entries[0]["count"] if entries else 0

    result = {
        "total": count_of("total"),
        "categories": [{"name": row["_id"], "count": row["count"]} for row in buckets.get("categories", [])],
        "mechanics": [{"name": row["_id"], "count": row["count"]} for row in buckets.get("mechanics", [])],
        "players": [{"value": count, "count": count_of(f"players_{count}")} for count in PLAYER_FACET_COUNTS],
        "playtime": [
            {"min": low, "max": high, "count": count_of(_bucket_key("playtime", low, high))}
            for low, high in PLAYTIME_BUCKETS
        ],
        "weight": [
            {"min": low, "max": high, "count": count_of(_bucket_key("weight", low, high))}
            for low, high in WEIGHT_BUCKETS
        ],
    }
    _set_cache(cache_key, result, ttl=120)
    return result


@router.get("/search")
async def search_games(
    q: str | None = None,
    semantic: bool = Query(False),
    locale: str = Query("en"),
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    sort: str = Query(DEFAULT_SORT),
    categories: str | None = Query(None, description="Comma separated category names"),
    mechanics: str | None = Query(None, description="Comma separated mechanic names"),
    categories_mode: str = Query("any", enum=["any", "all"]),
    mechanics_mode: str = Query("any", enum=["any", "all"]),
    exclude_categories: str | None = None,
    exclude_mechanics: str | None = None,
    designers: str | None = None,
    publishers: str | None = None,
    include_expansions: bool = Query(False),
    players: int | None = None,
    best_at_players: bool = Query(False),
    playtime_max: int | None = None,
    playtime_min: int | None = None,
    min_players: int | None = None,
    max_players: int | None = None,
    min_playtime: int | None = None,
    max_playtime: int | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    min_ratings: int | None = None,
):
    """Search with multi-value tag filters.

    `categories=Card Game,Fantasy` matches either by default; `categories_mode=all`
    demands both. `exclude_categories` removes matches outright, which is the
    only way to say "anything but wargames".
    """
    cache_key = _cache_key(
        "search", q=q, semantic=semantic, locale=locale, page=page, per_page=per_page, sort=sort,
        categories=categories, mechanics=mechanics, categories_mode=categories_mode,
        mechanics_mode=mechanics_mode, exclude_categories=exclude_categories,
        exclude_mechanics=exclude_mechanics, designers=designers, publishers=publishers,
        include_expansions=include_expansions, players=players, best_at_players=best_at_players,
        playtime_max=playtime_max, playtime_min=playtime_min,
        min_players=min_players, max_players=max_players,
        min_playtime=min_playtime, max_playtime=max_playtime,
        min_weight=min_weight, max_weight=max_weight, min_ratings=min_ratings,
    )
    cached = await _cached(cache_key, ttl=120)
    if cached:
        return cached

    filter_query = build_filters(
        categories=categories, mechanics=mechanics,
        categories_mode=categories_mode, mechanics_mode=mechanics_mode,
        exclude_categories=exclude_categories, exclude_mechanics=exclude_mechanics,
        designers=designers, publishers=publishers,
        players=players, best_at_players=best_at_players,
        playtime_max=playtime_max, playtime_min=playtime_min,
        min_players=min_players, max_players=max_players,
        min_playtime=min_playtime, max_playtime=max_playtime,
        min_weight=min_weight, max_weight=max_weight, min_ratings=min_ratings,
    )
    filter_query = merge_filters(
        filter_query,
        quality_gate(locale),
        None if include_expansions else BASE_GAMES_ONLY,
    )

    sort_key = SORT_MAP.get(sort, SORT_MAP[DEFAULT_SORT])
    use_semantic = semantic and bool(q) and semantic_enabled()

    if use_semantic:
        docs, total = await _semantic_page(q, filter_query, page, per_page)
    else:
        filter_query = merge_filters(filter_query, build_name_query(q))
        docs, total = await paged_search(mongo_db.board_games, filter_query, q, page, per_page, sort_key)

    result = {
        "games": [_format_game(doc, locale) for doc in docs],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "semantic": use_semantic,
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
