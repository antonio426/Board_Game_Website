"""CJK normalization helpers.

Project policy (board game Chinese names):
- If Traditional Chinese exists, store Traditional Chinese (繁體).
- If no Chinese name exists, English is used.
- Source data may be Simplified; convert via OpenCC s2t on write.

Uses `opencc-python-reimplemented` (pure-Python, no native dependency).
"""
from __future__ import annotations

import re

try:
    import opencc  # opencc-python-reimplemented

    # s2tw, not s2t: the site is zh-TW and plain s2t produces the mainland
    # variant forms, so "为" came back as 爲 rather than 為. s2tw stops at
    # character variants; s2twp would also swap vocabulary (網絡 -> 網路),
    # which is more editing than a game description asked for.
    try:
        _S2T = opencc.OpenCC("s2tw")
    except Exception:  # pragma: no cover - older opencc builds
        _S2T = opencc.OpenCC("s2t")
    _T2S = opencc.OpenCC("t2s")
    _OPENCC_OK = True
except Exception:  # pragma: no cover
    _S2T = None
    _T2S = None
    _OPENCC_OK = False


_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def has_cjk(text: str | None) -> bool:
    """True if text contains any CJK Unified Ideograph (basic + ext-A planes)."""
    return bool(text and _CJK_RE.search(text))


_KANA_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")

# Shinjitai forms that exist in Japanese but not in Chinese of either register.
# Kana catches most Japanese titles; these catch the kanji-only ones, such as
# Ticket to Ride's 乗車券 (Chinese would write 乘車券).
_SHINJITAI = "乗変図実対発県円歩帰穂桜駅覚営絵両単価届囲売読楽気従"
_SHINJITAI_RE = re.compile(f"[{_SHINJITAI}]")


def is_chinese(text: str | None) -> bool:
    """True for Chinese text, false for Japanese.

    BGG lists every CJK alternate name together, so the enrichers used to store
    カタン スタンダード版 as Catan's Chinese name. Kana is the giveaway for most
    of them; kanji-only Japanese titles are caught by the shinjitai characters
    that Chinese never uses.
    """
    if not text or not has_cjk(text):
        return False
    return not _KANA_RE.search(text) and not _SHINJITAI_RE.search(text)


def to_traditional(text: str | None) -> str:
    """Convert Simplified Chinese to Traditional. Idempotent on Traditional.

    - None / empty -> "" (or original falsy passthrough)
    - Non-CJK -> returned unchanged
    - CJK input -> s2t conversion (Traditional passes through unchanged)
    - OpenCC unavailable or conversion error -> returned unchanged
    """
    if not text:
        return text or ""
    if not _OPENCC_OK or not has_cjk(text):
        return text
    try:
        return _S2T.convert(text)
    except Exception:  # pragma: no cover
        return text


def expand_query_variants(q: str | None) -> list[str]:
    """Return the query plus its s2t and t2s variants (deduped, sorted).

    Useful for $or regex matching against name_en/name_zh where stored names
    may be either script. For ASCII-only queries returns just [q].
    """
    if not q:
        return [""]
    variants: set[str] = {q}
    if _OPENCC_OK and has_cjk(q):
        try:
            variants.add(_S2T.convert(q))
            variants.add(_T2S.convert(q))
        except Exception:  # pragma: no cover
            pass
    return sorted(v for v in variants if v)
