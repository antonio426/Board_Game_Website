"""Which fields each kind of response needs from a game document.

A game document is large — the English description alone runs to a few
kilobytes — and a grid of cards reads none of it. Keeping the field list in one
place stops the list endpoint, the search endpoint and the collection endpoint
from drifting into three different answers to the same question.
"""

# What a card renders, plus the three fields ranking reads but nobody displays:
# `aliases`, `is_expansion` and `quality_score` feed `app.core.search.relevance`.
LIST_FIELDS = (
    "bgg_id", "name_en", "name_zh", "aliases",
    "image", "thumbnail", "local_image", "local_thumbnail",
    "min_players", "max_players", "best_players", "recommended_players",
    "min_playtime", "max_playtime", "min_age", "player_age",
    "year_published", "language_dependence",
    "bgg_rating", "bgg_avg_rating", "bgg_rank", "bgg_weight", "users_rated",
    "quality_score", "is_expansion", "series",
    "categories", "mechanics", "designers",
)
LIST_PROJECTION = {field: 1 for field in LIST_FIELDS}

# Comparison is a table of the numbers people decide on, so it needs the card
# fields and nothing more — the descriptions are what the detail page is for.
COMPARE_PROJECTION = LIST_PROJECTION
