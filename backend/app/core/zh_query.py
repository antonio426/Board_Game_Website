"""Turn a Chinese search phrase into the English concepts the index understands.

The vector index is built with `BAAI/bge-small-en-v1.5`, an English retrieval
model, so a Chinese sentence embedded as-is lands nowhere near the games it
describes: 「適合兩人的合作解謎」 returned Just One (a 3-7 player party game)
and Café International before it returned anything cooperative.

The site already owns a bilingual dictionary of exactly the words people search
with — the 85 categories and 196 mechanics in `app/core/vocab.py`, each with a
Chinese name. Reading the query through that dictionary turns 「合作」 into
"Cooperative Game" and 「解謎」 into "Puzzle", which is a query the English model
answers well. `EVERYDAY_TERMS` covers the words that describe a game without
being a tag — player counts, length, weight, mood.

A Chinese query that maps to nothing is not embedded at all. Feeding the model
untranslated Chinese produced plausible-looking noise, which is worse than
saying "this one goes through name matching instead": see `embedding_query`.
"""
import re

from app.core import vocab
from app.core.cjk import expand_query_variants, has_cjk

# Words that describe a game but are not tags. Values are English phrases, not
# single words, because the embedding is of the whole sentence.
EVERYDAY_TERMS = {
    "單人": "solo one player",
    "一個人": "solo one player",
    "兩人": "two player",
    "雙人": "two player",
    "二人": "two player",
    "三人": "three player",
    "四人": "four player",
    "多人": "many players",
    "團體": "large group",
    "情侶": "two player couple",
    "家庭": "family game",
    "親子": "family game with children",
    "小孩": "children",
    "兒童": "children",
    "新手": "beginner friendly",
    "入門": "beginner friendly gateway game",
    "簡單": "simple light",
    "輕鬆": "light easy going",
    "輕度": "light",
    "中度": "medium complexity",
    "重度": "heavy complex",
    "燒腦": "heavy brain burning",
    "複雜": "complex",
    "策略": "strategy",
    "短": "short quick",
    "快": "quick fast",
    "快速": "quick fast",
    "長": "long",
    "派對": "party",
    "聚會": "party",
    "熱鬧": "lively party",
    "安靜": "quiet thoughtful",
    "氣氛": "atmosphere",
    "劇情": "story driven narrative",
    "故事": "story narrative",
    "劇本": "scenario campaign",
    "戰役": "campaign",
    "合作": "cooperative",
    "對抗": "competitive head to head",
    "競爭": "competitive",
    "引擎": "engine building",
    "探索": "exploration",
    "生存": "survival",
    "解謎": "puzzle solving",
    "推理": "deduction",
    "背叛": "traitor hidden roles",
    "說謊": "bluffing",
    "喝酒": "drinking party",
    "動腦": "thinky",
    "運氣": "luck",
    "經典": "classic",
    "好玩": "fun",
    "無聊": "boring",
    "桌遊": "board game",
    "遊戲": "game",
    "擴充": "expansion",
    "主題": "thematic",
    "美術": "artwork",
}

# Particles and connectives that carry no retrieval signal. Stripped so that a
# leftover 「的」 cannot be the reason a query looks untranslatable.
STOPWORDS = ("適合", "的", "或", "和", "跟", "與", "想要", "想", "要", "找",
             "推薦", "有沒有", "什麼", "怎麼", "可以", "玩", "一起")

_ASCII_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'&:\-]*")


async def _dictionary() -> dict[str, str]:
    """Chinese term -> English term, tags first, then the everyday words."""
    terms: dict[str, str] = {}
    for field in vocab.TAG_COLLECTIONS:
        for row in await vocab.vocabulary(field):
            if has_cjk(row["name_zh"]):
                terms[row["name_zh"]] = row["name"]
    terms.update(EVERYDAY_TERMS)
    return terms


def _scan(text: str, terms: dict[str, str], keys: list[str]) -> list[str]:
    """Longest-match left to right, so 卡牌遊戲 never matches as 卡牌 + 遊戲."""
    found: list[str] = []
    index = 0
    while index < len(text):
        for key in keys:
            if text.startswith(key, index):
                found.append(terms[key])
                index += len(key)
                break
        else:
            index += 1
    return found


async def to_english_concepts(query: str) -> str:
    """The English concepts a Chinese query names, in the order it names them."""
    terms = await _dictionary()
    keys = sorted(terms, key=len, reverse=True)

    concepts: list[str] = []
    # Simplified and Traditional both map, so 卡牌游戏 works as well as 卡牌遊戲.
    for variant in expand_query_variants(query):
        stripped = variant
        for stopword in STOPWORDS:
            stripped = stripped.replace(stopword, " ")
        concepts.extend(_scan(stripped, terms, keys))

    # Latin words in a mixed query are already in the model's language.
    concepts.extend(_ASCII_RUN.findall(query))

    seen: set[str] = set()
    ordered = [c for c in concepts if not (c.lower() in seen or seen.add(c.lower()))]
    return " ".join(ordered)


async def embedding_query(query: str | None) -> str | None:
    """What to embed for this query, or None if the vector path cannot serve it.

    English passes through. Chinese is translated. Chinese that translates to
    nothing — a game title, most often — returns None so the caller falls back
    to name matching, which is what actually finds 璀璨寶石.
    """
    if not query or not query.strip():
        return None
    if not has_cjk(query):
        return query
    concepts = await to_english_concepts(query)
    return concepts or None
