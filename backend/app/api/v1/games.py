import asyncio
import json
import logging
from fastapi import APIRouter, Query
from bson import ObjectId

from app.core.database import mongo_db, redis_client
from app.core.filters import BASE_GAMES_ONLY, build_filters, single_tag_filters
from app.core.quality import merge_filters, quality_gate
from app.core.search import build_name_query, paged_search, rank_by_relevance, rerank_semantic
from app.core import vocab
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


def _format_game(doc: dict, locale: str = "en", translations: dict | None = None) -> dict:
    """Locale-aware game formatting: zh → name_zh priority, local images.

    `translations` is the tag vocabulary, hoisted by `_format_games` so a page
    of results loads it once rather than per game.
    """
    doc["id"] = str(doc.pop("_id", ""))
    vocab.normalize_tags_with(doc, translations or {})

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


async def _tag_translations() -> dict[str, dict[str, str]]:
    return {field: await vocab.zh_map(field) for field in vocab.TAG_COLLECTIONS}


async def _format_games(docs: list[dict], locale: str = "en") -> list[dict]:
    translations = await _tag_translations()
    return [_format_game(doc, locale, translations) for doc in docs]


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
    return _format_game(docs[0], locale, await _tag_translations())


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
    games = await _format_games(docs, locale)

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
async def list_categories(locale: str = Query("en")):
    return await _tag_vocabulary("categories", locale)


@router.get("/mechanics")
async def list_mechanics(locale: str = Query("en")):
    return await _tag_vocabulary("mechanics", locale)


async def _tag_vocabulary(field: str, locale: str) -> list[dict]:
    """Every term with how many showable games carry it.

    Counting runs against the same quality gate the list uses, so the number
    beside a chip is the number of games clicking it returns. Terms nobody uses
    still appear with a count of zero — the chip search box and the tags page
    both want the complete vocabulary, and the old `$limit: 100` was hiding 96
    of the 196 mechanics outright.
    """
    cache_key = _cache_key("vocab", field=field, locale=locale)
    cached = await _cached(cache_key, ttl=600)
    if cached:
        return cached

    path = vocab.TAG_PATHS[field]
    pipeline = [
        {"$match": quality_gate(locale)},
        {"$unwind": f"${field}"},
        {"$match": {path: {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${path}", "count": {"$sum": 1}}},
    ]
    counts = {row["_id"]: row["count"] async for row in mongo_db.board_games.aggregate(pipeline)}

    terms = await vocab.vocabulary(field)
    known = {term["name"] for term in terms}
    results = [
        {"name": term["name"], "name_zh": term["name_zh"], "count": counts.get(term["name"], 0)}
        for term in terms
    ]
    # A term the games use but the mapping has never heard of still has to be
    # filterable; it just goes out untranslated.
    results.extend(
        {"name": name, "name_zh": name, "count": count}
        for name, count in counts.items()
        if name not in known
    )
    results.sort(key=lambda row: row["count"], reverse=True)

    _set_cache(cache_key, results, ttl=600)
    return results


# Chip options, defined once and shared with the facet counts below.
PLAYER_FACET_COUNTS = (1, 2, 3, 4, 5, 6, 8)
# Cumulative "finishes within N minutes", matching PLAYTIME_OPTIONS on the client.
PLAYTIME_EDGES = (30, 60, 120, 240)
# (band, min_weight, max_weight) on BGG's 1-5 complexity scale.
WEIGHT_BANDS = (("light", None, 2.0), ("medium", 2.0, 3.5), ("heavy", 3.5, None))

# High enough that no vocabulary term (85 + 196) falls out of the facet map,
# which is what made chips outside the top 60 render a misleading 0.
FACET_TAG_LIMIT = 200


def _tag_facet(field: str) -> list[dict]:
    return [
        {"$unwind": f"${field}"},
        {"$match": {f"{field}.name": {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${field}.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": FACET_TAG_LIMIT},
    ]


def _option_stage(**criteria) -> list[dict]:
    """Count the games one chip would leave.

    The stage is built by `build_filters`, the same function the list endpoint
    uses, so the number on a chip cannot drift from the results behind it. The
    hand-written version of these stages is why the 240-minute chip never showed
    a count and the complexity bands silently dropped everything between 3 and 4.
    """
    return [{"$match": build_filters(**criteria)}, {"$count": "count"}]


async def _run_facet(filter_query: dict, stages: dict) -> dict:
    pipeline = [{"$match": filter_query}, {"$facet": stages}]
    rows = await mongo_db.board_games.aggregate(pipeline).to_list(length=1)
    return rows[0] if rows else {}


def _count_of(buckets: dict, key: str) -> int:
    entries = buckets.get(key) or []
    return entries[0]["count"] if entries else 0


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
    nothing, and only finds out after clicking. Each single-select dimension is
    counted with its own filter removed, so switching from "2 players" to
    "4 players" shows the real size of that choice rather than the size of the
    overlap with the current one.
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

    shared = dict(
        categories=categories, mechanics=mechanics,
        categories_mode=categories_mode, mechanics_mode=mechanics_mode,
        exclude_categories=exclude_categories, exclude_mechanics=exclude_mechanics,
        min_ratings=min_ratings,
    )
    selection = dict(
        players=players, best_at_players=best_at_players,
        playtime_max=playtime_max, playtime_min=playtime_min,
        min_weight=min_weight, max_weight=max_weight,
    )

    def scope(**overrides) -> dict:
        return merge_filters(
            build_filters(**shared, **{**selection, **overrides}),
            quality_gate(locale),
            None if include_expansions else BASE_GAMES_ONLY,
            build_name_query(q),
        )

    tag_stages = {
        "categories": _tag_facet("categories"),
        "mechanics": _tag_facet("mechanics"),
        "total": [{"$count": "count"}],
    }
    player_stages = {f"players_{count}": _option_stage(players=count) for count in PLAYER_FACET_COUNTS}
    playtime_stages = {f"playtime_{edge}": _option_stage(playtime_max=edge) for edge in PLAYTIME_EDGES}
    weight_stages = {
        f"weight_{band}": _option_stage(min_weight=low, max_weight=high)
        for band, low, high in WEIGHT_BANDS
    }

    tags, player_counts, playtime_counts, weight_counts = await asyncio.gather(
        _run_facet(scope(), tag_stages),
        _run_facet(scope(players=None, best_at_players=False), player_stages),
        _run_facet(scope(playtime_max=None, playtime_min=None), playtime_stages),
        _run_facet(scope(min_weight=None, max_weight=None), weight_stages),
    )

    translations = await _tag_translations()

    def tag_rows(field: str) -> list[dict]:
        labels = translations.get(field, {})
        return [
            {"name": row["_id"], "name_zh": labels.get(row["_id"], row["_id"]), "count": row["count"]}
            for row in tags.get(field) or []
        ]

    result = {
        "total": _count_of(tags, "total"),
        "categories": tag_rows("categories"),
        "mechanics": tag_rows("mechanics"),
        "players": [
            {"value": count, "count": _count_of(player_counts, f"players_{count}")}
            for count in PLAYER_FACET_COUNTS
        ],
        "playtime": [
            {"max": edge, "count": _count_of(playtime_counts, f"playtime_{edge}")}
            for edge in PLAYTIME_EDGES
        ],
        "weight": [
            {"band": band, "min": low, "max": high, "count": _count_of(weight_counts, f"weight_{band}")}
            for band, low, high in WEIGHT_BANDS
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
        "games": await _format_games(docs, locale),
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

    _format_game(game, locale, await _tag_translations())

    _set_cache(cache_key, game, ttl=300)
    return game
