"""Turning a game document into what a client renders.

Both the games router and the collection endpoint answer with games, and a
game's Chinese name, its tag translations and its image paths have to be
decided the same way in both places — locale handling belongs here rather than
in each component, and the tag vocabulary comes from `app.core.vocab`, never
from the copy inside the document.
"""
from app.core import vocab


def format_game(doc: dict, locale: str = "en", translations: dict | None = None) -> dict:
    """Locale-aware game formatting: zh → name_zh priority, local images.

    `translations` is the tag vocabulary, hoisted by `format_games` so a page
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


async def tag_translations() -> dict[str, dict[str, str]]:
    return {field: await vocab.zh_map(field) for field in vocab.TAG_COLLECTIONS}


async def format_games(docs: list[dict], locale: str = "en") -> list[dict]:
    translations = await tag_translations()
    return [format_game(doc, locale, translations) for doc in docs]
