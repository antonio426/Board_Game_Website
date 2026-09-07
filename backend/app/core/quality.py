"""Single source of truth for "which games are worth showing".

Before this module the gate `{"description_en": {"$exists": True, "$ne": ""}}`
was copy-pasted across games.py, recommendations.py and chat.py, and the
zh-locale gate queried a field (`num_ratings`) that does not exist in the
collection — the real field is `users_rated`.

Coverage as of the last data health run (180,401 docs total):
    description_en non-empty   43,401
    users_rated >= 50          25,457
    bgg_rating > 0             43,474   (Bayesian, ranked games only)
    bgg_avg_rating > 0        140,604   (raw average)
"""

# A doc without an English description is a stub row from the BGG id sweep,
# not a game we can render.
QUALITY_FILTER: dict = {"description_en": {"$exists": True, "$ne": ""}}

# zh locale additionally hides games nobody has rated and that score poorly,
# because the Chinese audience has no BGG context to judge them by.
ZH_MIN_RATING = 6.0
ZH_MIN_USERS_RATED = 50


def quality_gate(locale: str = "en", min_users_rated: int = 0) -> dict:
    """Mongo filter fragment selecting games that are safe to show."""
    gate: dict = dict(QUALITY_FILTER)

    if min_users_rated > 0:
        gate["users_rated"] = {"$gte": min_users_rated}

    if locale and locale.startswith("zh"):
        gate["$or"] = [
            {"bgg_rating": {"$gte": ZH_MIN_RATING}},
            {"users_rated": {"$gte": ZH_MIN_USERS_RATED}},
        ]

    return gate


def is_low_quality(doc: dict, locale: str = "en") -> bool:
    """Document-level equivalent of the zh half of `quality_gate`."""
    if not locale or not locale.startswith("zh"):
        return False
    rating = doc.get("bgg_rating") or 0
    users_rated = doc.get("users_rated") or 0
    return rating < ZH_MIN_RATING and users_rated < ZH_MIN_USERS_RATED


def merge_filters(*fragments: dict | None) -> dict:
    """Combine Mongo filter fragments without one clobbering another.

    Two fragments may legitimately both carry `$or` (the quality gate and a
    name query, say). Colliding keys are pushed into `$and` instead of being
    overwritten, which is what a plain `dict.update` would do.
    """
    merged: dict = {}
    conflicts: list[dict] = []

    for fragment in fragments:
        if not fragment:
            continue
        for key, value in fragment.items():
            if key in merged and merged[key] != value:
                conflicts.append({key: value})
            else:
                merged[key] = value

    if conflicts:
        return {"$and": [merged, *conflicts]}
    return merged
