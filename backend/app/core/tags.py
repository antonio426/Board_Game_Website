"""Canonical category / mechanic names for filtering.

A case-insensitive `$regex` on `categories.name` cannot use the
`categories_name` index, so tag filtering degraded into a 43k-document scan
(~240 ms). Names come from `app.core.vocab`, whose canonical map is keyed by
both the English and the Chinese name — which is how a Chinese UI can send
「卡牌遊戲」 and still get an indexed equality match on the stored English name.
"""
from app.core import vocab

_FIELDS = vocab.TAG_PATHS


async def canonical_name(field: str, value: str) -> str | None:
    return await vocab.canonical(field, value)


async def canonical_names(field: str, values: list[str]) -> list[str]:
    """Map a caller's list onto stored names, keeping anything unrecognised."""
    mapping = await vocab.canonical_map(field)
    return [mapping.get(value.strip().lower(), value) for value in values]


async def tag_filter(field: str, value: str) -> dict:
    """Mongo fragment matching one category or mechanic.

    Exact (index-friendly) match when the value is a known tag, case-insensitive
    regex otherwise so partial input still finds something.
    """
    path = _FIELDS[field]
    canonical = await vocab.canonical(field, value)
    if canonical:
        return {path: canonical}
    return {path: {"$regex": value, "$options": "i"}}
