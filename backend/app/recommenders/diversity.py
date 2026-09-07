"""Diversity re-ranking for recommendation lists.

Pure similarity ranking answers "most like this game" with six versions of the
same game: search for something like Catan and the top results were Catan:
Starfarers, Catan: Ancient Egypt, Catan: Dawn of Humankind. Maximal Marginal
Relevance keeps a candidate only if it adds something the already-chosen ones
do not, and hard caps stop one series or designer from owning the list.
"""
LAMBDA = 0.7            # 1.0 = pure relevance, 0.0 = pure novelty
MAX_PER_SERIES = 2
MAX_PER_DESIGNER = 2
CANDIDATE_MULTIPLIER = 4


def _tags(doc: dict) -> set[str]:
    values = set()
    for field in ("categories", "mechanics"):
        for item in doc.get(field) or []:
            name = item.get("name") if isinstance(item, dict) else item
            if name:
                values.add(f"{field}:{name}")
    return values


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _series(doc: dict) -> str | None:
    series = doc.get("series")
    if isinstance(series, dict):
        return series.get("name")
    if isinstance(series, list) and series:
        first = series[0]
        return first.get("name") if isinstance(first, dict) else str(first)
    return series or None


def _designers(doc: dict) -> list[str]:
    names = []
    for item in doc.get("designers") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if name:
            names.append(name)
    return names


def diversify(games: list[dict], top_k: int, lambda_: float = LAMBDA) -> list[dict]:
    """Greedy MMR over already-scored games, with per-series/designer caps."""
    if len(games) <= 1:
        return games[:top_k]

    highest = max(game.get("recommendation_score", 0) for game in games) or 1.0
    remaining = list(games)
    tag_cache = {id(game): _tags(game) for game in remaining}

    selected: list[dict] = []
    selected_tags: list[set[str]] = []
    series_used: dict[str, int] = {}
    designer_used: dict[str, int] = {}

    while remaining and len(selected) < top_k:
        best_game = None
        best_value = None

        for game in remaining:
            series = _series(game)
            if series and series_used.get(series, 0) >= MAX_PER_SERIES:
                continue
            if any(designer_used.get(name, 0) >= MAX_PER_DESIGNER for name in _designers(game)):
                continue

            relevance = (game.get("recommendation_score", 0) or 0) / highest
            redundancy = max(
                (_similarity(tag_cache[id(game)], chosen) for chosen in selected_tags),
                default=0.0,
            )
            value = lambda_ * relevance - (1 - lambda_) * redundancy

            if best_value is None or value > best_value:
                best_game, best_value = game, value

        if best_game is None:
            # Every candidate left is capped out; fall back to plain relevance.
            remaining.sort(key=lambda game: game.get("recommendation_score", 0), reverse=True)
            selected.extend(remaining[: top_k - len(selected)])
            break

        selected.append(best_game)
        selected_tags.append(tag_cache[id(best_game)])
        remaining.remove(best_game)

        series = _series(best_game)
        if series:
            series_used[series] = series_used.get(series, 0) + 1
        for name in _designers(best_game):
            designer_used[name] = designer_used.get(name, 0) + 1

    return selected[:top_k]
