"""Name matching and relevance ranking for game search.

Three endpoints used to build the same `$or` of case-insensitive regexes and
then sort the hits by `bgg_rating`, so "catan" returned Cities & Knights first
and the base game third: every match was equal, and the tie was broken by
rating alone. Matching now carries a score — exact name beats prefix beats
substring — and expansions are pushed below the game they extend.
"""
import math

from app.core.cjk import expand_query_variants

# Match tiers. The gaps are wide enough that quality can never outrank a
# stronger match type, only order results within one.
SCORE_EXACT = 100.0
SCORE_PREFIX = 60.0
SCORE_WORD = 40.0
SCORE_SUBSTRING = 20.0
SCORE_OTHER = 5.0

EXPANSION_PENALTY = 25.0
QUALITY_WEIGHT = 1.0  # quality_score is 0-10, so this contributes at most 10

# How many matches to pull back for scoring. Name searches almost always return
# far fewer than this; beyond it, results keep the database ordering.
RESCORE_LIMIT = 300

NAME_FIELDS = ("name_en", "name_zh", "aliases")


def build_name_query(query: str | None) -> dict | None:
    """`$or` over every name field and every simplified/traditional variant."""
    if not query or not query.strip():
        return None

    clauses = []
    for variant in expand_query_variants(query.strip()):
        for field in NAME_FIELDS:
            clauses.append({field: {"$regex": variant, "$options": "i"}})
    return {"$or": clauses} if clauses else None


def _candidate_names(doc: dict) -> list[str]:
    names = [doc.get("name_en") or "", doc.get("name_zh") or ""]
    names.extend(alias for alias in doc.get("aliases") or [] if isinstance(alias, str))
    return [name.strip().lower() for name in names if name]


def _match_score(name: str, variant: str) -> float:
    if name == variant:
        return SCORE_EXACT
    if name.startswith(variant):
        return SCORE_PREFIX
    if f" {variant}" in name or f":{variant}" in name:
        return SCORE_WORD
    if variant in name:
        return SCORE_SUBSTRING
    return 0.0


def relevance(doc: dict, query: str) -> float:
    """How well one game answers the query. Higher is better."""
    variants = [variant.strip().lower() for variant in expand_query_variants(query.strip())]
    names = _candidate_names(doc)

    best = max(
        (_match_score(name, variant) for name in names for variant in variants),
        default=0.0,
    ) or SCORE_OTHER

    if doc.get("is_expansion"):
        best -= EXPANSION_PENALTY

    quality = doc.get("quality_score") or doc.get("bgg_rating") or 0
    return best + QUALITY_WEIGHT * quality


def rank_by_relevance(docs: list[dict], query: str) -> list[dict]:
    return sorted(docs, key=lambda doc: relevance(doc, query), reverse=True)


# Cosine similarity alone rewards short documents whose entire text repeats the
# query: over the full 43k index, "cooperative game about curing diseases"
# returned Together, Infection and Joint Efforts while Pandemic fell out of the
# top ten, and "deck building card game" led with a game literally called Deck
# Building: The Deck Building Game. Two priors fix that. Quality separates good
# from bad but is compressed into a 6-8 band, so it cannot outweigh a strong
# match on its own; the audience size behind a game spans five orders of
# magnitude, which is exactly the spread needed to break these ties.
SEMANTIC_SIMILARITY_WEIGHT = 0.65
SEMANTIC_QUALITY_WEIGHT = 0.20
SEMANTIC_POPULARITY_WEIGHT = 0.15

MAX_QUALITY_SCORE = 10.0
# log10 of the most-rated game on the site, near enough: 10^5 = 100,000 ratings.
POPULARITY_DECADES = 5.0


def _popularity(doc: dict) -> float:
    users_rated = doc.get("users_rated") or 0
    if users_rated <= 0:
        return 0.0
    return min(math.log10(1 + users_rated) / POPULARITY_DECADES, 1.0)


def rerank_semantic(docs: list[dict], scores: dict[int, float]) -> list[dict]:
    """Order vector hits by similarity, tempered by quality and audience size."""
    def blended(doc: dict) -> float:
        similarity = scores.get(doc.get("bgg_id"), 0.0)
        quality = (doc.get("quality_score") or 0) / MAX_QUALITY_SCORE
        return (
            SEMANTIC_SIMILARITY_WEIGHT * similarity
            + SEMANTIC_QUALITY_WEIGHT * quality
            + SEMANTIC_POPULARITY_WEIGHT * _popularity(doc)
        )

    return sorted(docs, key=blended, reverse=True)


async def paged_search(collection, filter_query: dict, query: str | None,
                       page: int, per_page: int, sort_key: list,
                       relevance_rank: bool = True) -> tuple[list[dict], int]:
    """Return one page of results plus the total, relevance-ranked when possible.

    With a text query the top `RESCORE_LIMIT` matches are pulled back and
    re-ordered in memory; the ranking depends on comparing candidates against
    each other, which Mongo cannot express in a sort. Without a query, or past
    that many results, the database ordering stands.

    `relevance_rank=False` keeps the caller's sort: re-ranking every search made
    "search for catan, then sort by year" silently do nothing.
    """
    total = await collection.count_documents(filter_query)
    skip = (page - 1) * per_page

    if not relevance_rank:
        docs = await collection.find(filter_query).sort(sort_key).skip(skip).limit(per_page).to_list(length=per_page)
        return docs, total

    if query and total <= RESCORE_LIMIT:
        docs = await collection.find(filter_query).sort(sort_key).limit(RESCORE_LIMIT).to_list(length=RESCORE_LIMIT)
        ranked = rank_by_relevance(docs, query)
        return ranked[skip:skip + per_page], total

    docs = await collection.find(filter_query).sort(sort_key).skip(skip).limit(per_page).to_list(length=per_page)
    if query:
        docs = rank_by_relevance(docs, query)
    return docs, total
