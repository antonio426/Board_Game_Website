"""Translate request parameters into one Mongo filter.

`list_games`, `search_games` and the facet counts must agree on what a filter
means, otherwise the count beside a chip does not match the result page you get
after clicking it.

Two vocabularies exist for players and playtime:

    players / playtime_max / playtime_min      what a person is asking for
    min_players / max_players / min_playtime /
    max_playtime                               single-sided range-overlap tests

The second set reads backwards (`max_playtime=30` means "its ceiling is at
least 30 minutes") and only survives for compatibility with existing callers.
"""
from app.core.quality import merge_filters
from app.core.tags import tag_filter

# Expansions outscore their own base games and bury them in name searches.
BASE_GAMES_ONLY = {"is_expansion": {"$ne": True}}


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _tag_condition(names: list[str], mode: str) -> dict:
    return {"$all": names} if mode == "all" else {"$in": names}


def build_filters(
    *,
    categories: str | None = None,
    mechanics: str | None = None,
    categories_mode: str = "any",
    mechanics_mode: str = "any",
    exclude_categories: str | None = None,
    exclude_mechanics: str | None = None,
    designers: str | None = None,
    publishers: str | None = None,
    players: int | None = None,
    best_at_players: bool = False,
    playtime_max: int | None = None,
    playtime_min: int | None = None,
    min_players: int | None = None,
    max_players: int | None = None,
    min_playtime: int | None = None,
    max_playtime: int | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    min_rating: float | None = None,
    min_ratings: int | None = None,
) -> dict:
    """Every filter except the quality gate, the name query and expansions."""
    include: dict = {}
    overlap: dict = {}

    category_names = _split(categories)
    if category_names:
        include["categories.name"] = _tag_condition(category_names, categories_mode)
    mechanic_names = _split(mechanics)
    if mechanic_names:
        include["mechanics.name"] = _tag_condition(mechanic_names, mechanics_mode)

    excluded_categories = _split(exclude_categories)
    excluded_mechanics = _split(exclude_mechanics)
    exclusions: dict = {}
    if excluded_categories:
        exclusions["categories.name"] = {"$nin": excluded_categories}
    if excluded_mechanics:
        exclusions["mechanics.name"] = {"$nin": excluded_mechanics}

    designer_names = _split(designers)
    if designer_names:
        include["designers.name"] = {"$in": designer_names}
    publisher_names = _split(publishers)
    if publisher_names:
        include["publishers.name"] = {"$in": publisher_names}

    if players is not None:
        if best_at_players:
            include["best_players"] = players
        else:
            include["min_players"] = {"$lte": players}
            include["max_players"] = {"$gte": players}
    if playtime_max is not None:
        # An unknown playtime is stored as 0, and unknown is not "instant".
        include["max_playtime"] = {"$gt": 0, "$lte": playtime_max}
    if playtime_min is not None:
        include["min_playtime"] = {"$gte": playtime_min}

    if min_players is not None:
        overlap["min_players"] = {"$lte": min_players}
    if max_players is not None:
        overlap["max_players"] = {"$gte": max_players}
    if min_playtime is not None:
        overlap["min_playtime"] = {"$lte": min_playtime}
    if max_playtime is not None:
        overlap["max_playtime"] = {"$gte": max_playtime}

    if min_weight is not None or max_weight is not None:
        weight: dict = {}
        if min_weight is not None:
            weight["$gte"] = min_weight
        if max_weight is not None:
            weight["$lte"] = max_weight
        include["bgg_weight"] = weight

    if min_rating is not None:
        include["bgg_rating"] = {"$gte": min_rating}
    if min_ratings is not None:
        include["users_rated"] = {"$gte": min_ratings}

    return merge_filters(include, overlap, exclusions)


async def single_tag_filters(category: str | None, mechanic: str | None) -> dict:
    """Legacy single-value `category` / `mechanic` params, canonicalized."""
    fragments = []
    if category:
        fragments.append(await tag_filter("categories", category))
    if mechanic:
        fragments.append(await tag_filter("mechanics", mechanic))
    return merge_filters(*fragments)
