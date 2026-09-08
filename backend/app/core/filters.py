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
from app.core.tags import canonical_names, tag_filter

# Expansions outscore their own base games and bury them in name searches.
BASE_GAMES_ONLY = {"is_expansion": {"$ne": True}}

# BGG's own top-level families, the way a player describes an evening. The
# subdomain field also carries a handful of video-game values with one document
# each, so selection is restricted to this list.
BGG_FAMILIES = (
    "strategygames",
    "familygames",
    "partygames",
    "thematic",
    "abstracts",
    "wargames",
    "childrensgames",
    "cgs",
)

# BGG's five community verdicts on how much text a game makes you read,
# collapsed into the three answers a buyer actually needs. "(no votes)" is
# never selectable: it is not an answer.
LANGUAGE_DEPENDENCE_BANDS = {
    "low": [
        "No necessary in-game text",
        "Some necessary text - easily memorized or small crib sheet",
    ],
    "medium": ["Moderate in-game text - needs crib sheet or paste ups"],
    "high": [
        "Extensive use of text - massive conversion needed to be playable",
        "Unplayable in another language",
    ],
}


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
    family: str | None = None,
    language_dependence: str | None = None,
    max_min_age: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
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

    # Stored as flat string arrays, not objects — `designers.name` matched
    # nothing at all, so both parameters silently returned an empty list.
    designer_names = _split(designers)
    if designer_names:
        include["designers"] = {"$in": designer_names}
    publisher_names = _split(publishers)
    if publisher_names:
        include["publishers"] = {"$in": publisher_names}

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
        # An unrated complexity is stored as 0. Without the floor, every game
        # BGG has not weighted yet counts as "light".
        weight: dict = {"$gt": 0}
        if min_weight is not None:
            weight["$gte"] = min_weight
        if max_weight is not None:
            weight["$lte"] = max_weight
        include["bgg_weight"] = weight

    if min_rating is not None:
        include["bgg_rating"] = {"$gte": min_rating}
    if min_ratings is not None:
        include["users_rated"] = {"$gte": min_ratings}

    if family in BGG_FAMILIES:
        include["subcategory_ranks.subdomain"] = family
    if language_dependence in LANGUAGE_DEPENDENCE_BANDS:
        include["language_dependence"] = {"$in": LANGUAGE_DEPENDENCE_BANDS[language_dependence]}
    if max_min_age is not None:
        # An unknown minimum age is stored as 0, and unknown is not "suitable
        # for toddlers".
        include["min_age"] = {"$gt": 0, "$lte": max_min_age}
    if year_from is not None or year_to is not None:
        year: dict = {"$gt": 0}
        if year_from is not None:
            year["$gte"] = year_from
        if year_to is not None:
            year["$lte"] = year_to
        include["year_published"] = year

    return merge_filters(include, overlap, exclusions)


TAG_PARAMS = {
    "categories": "categories",
    "exclude_categories": "categories",
    "mechanics": "mechanics",
    "exclude_mechanics": "mechanics",
}


async def build_filters_async(**criteria) -> dict:
    """`build_filters`, with tag names translated back to what is stored.

    Filtering matches `categories.name`, which is English, so a Chinese UI
    sending 「卡牌遊戲」 has to be mapped onto "Card Game" here. Doing it with a
    regex over `name_zh` instead would abandon the index and cost ~240 ms per
    request.
    """
    resolved = dict(criteria)
    for param, field in TAG_PARAMS.items():
        value = resolved.get(param)
        if not value:
            continue
        names = await canonical_names(field, _split(value))
        resolved[param] = ",".join(names)
    return build_filters(**resolved)


async def single_tag_filters(category: str | None, mechanic: str | None) -> dict:
    """Legacy single-value `category` / `mechanic` params, canonicalized."""
    fragments = []
    if category:
        fragments.append(await tag_filter("categories", category))
    if mechanic:
        fragments.append(await tag_filter("mechanics", mechanic))
    return merge_filters(*fragments)
