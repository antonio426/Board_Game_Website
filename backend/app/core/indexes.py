"""Index definitions for `board_games`, applied at startup.

The collection held 180k documents with only the default `_id` index, so every
list, search and count was a collection scan. `create_index` is idempotent, so
running this on each boot is cheap once the indexes exist.
"""
import logging

from pymongo import ASCENDING, DESCENDING, TEXT

from app.core.database import mongo_db

logger = logging.getLogger(__name__)

GAME_INDEXES: list[tuple[list[tuple[str, object]], dict]] = [
    ([("bgg_id", ASCENDING)], {"name": "bgg_id_unique", "unique": True}),
    ([("bgg_rank", ASCENDING)], {"name": "bgg_rank_asc"}),
    ([("bgg_rating", DESCENDING)], {"name": "bgg_rating_desc"}),
    ([("users_rated", DESCENDING)], {"name": "users_rated_desc"}),
    ([("year_published", DESCENDING)], {"name": "year_published_desc"}),
    # sort=name and sort=weight had no index; the TEXT index cannot serve an
    # ascending sort on name_en.
    ([("name_en", ASCENDING)], {"name": "name_en_asc"}),
    ([("bgg_weight", DESCENDING)], {"name": "bgg_weight_desc"}),
    ([("designers", ASCENDING)], {"name": "designers_name"}),
    ([("publishers", ASCENDING)], {"name": "publishers_name"}),
    ([("categories.name", ASCENDING)], {"name": "categories_name"}),
    ([("mechanics.name", ASCENDING)], {"name": "mechanics_name"}),
    ([("min_players", ASCENDING), ("max_players", ASCENDING)], {"name": "player_range"}),
    # quality_score is written by scripts/compute_quality_score.py (Phase 2).
    ([("quality_score", DESCENDING)], {"name": "quality_score_desc"}),
    (
        [("name_en", TEXT), ("name_zh", TEXT), ("aliases", TEXT)],
        {"name": "name_text", "default_language": "none"},
    ),
]


async def ensure_indexes() -> list[str]:
    """Create any missing index. Returns the names that now exist."""
    created: list[str] = []
    for keys, options in GAME_INDEXES:
        name = options.get("name")
        try:
            await mongo_db.board_games.create_index(keys, **options)
            created.append(name)
        except Exception as exc:
            # A pre-existing index with the same keys but a different name, or a
            # unique violation on dirty data, must not stop the app from booting.
            logger.warning("index %s not created: %s", name, exc)
    return created
