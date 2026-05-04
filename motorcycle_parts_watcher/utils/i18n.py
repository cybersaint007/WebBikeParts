"""Tiny i18n layer for multi-language part search.

Used by services/crawl.py to translate the user's typed query into each
adapter's preferred language before dispatch (e.g. an English "exhaust"
becomes "排氣管" for the Webike TW adapter and "マフラー" for Yahoo Auctions
JP / Monotaro). Unknown words pass through unchanged so brand names and
part numbers ("Brembo", "GW71A") survive intact.

Detection is a character-class heuristic; translation is a curated parts
dictionary (no LLM, no network call). Extend PARTS_DICT as gaps surface.
"""
from __future__ import annotations

import re
from typing import Any


LANG_EN = "en"
LANG_ZH = "zh-TW"
LANG_JA = "ja"


PARTS_DICT: list[dict[str, str]] = [
    {"en": "exhaust",      "zh-TW": "排氣管",   "ja": "マフラー"},
    {"en": "muffler",      "zh-TW": "消音器",   "ja": "サイレンサー"},
    {"en": "brake",        "zh-TW": "煞車",     "ja": "ブレーキ"},
    {"en": "brake pad",    "zh-TW": "煞車片",   "ja": "ブレーキパッド"},
    {"en": "brake disc",   "zh-TW": "煞車盤",   "ja": "ブレーキディスク"},
    {"en": "fairing",      "zh-TW": "整流罩",   "ja": "カウル"},
    {"en": "tank",         "zh-TW": "油箱",     "ja": "タンク"},
    {"en": "fuel tank",    "zh-TW": "油箱",     "ja": "燃料タンク"},
    {"en": "mirror",       "zh-TW": "後視鏡",   "ja": "ミラー"},
    {"en": "handlebar",    "zh-TW": "把手",     "ja": "ハンドル"},
    {"en": "seat",         "zh-TW": "座墊",     "ja": "シート"},
    {"en": "chain",        "zh-TW": "鏈條",     "ja": "チェーン"},
    {"en": "sprocket",     "zh-TW": "齒盤",     "ja": "スプロケット"},
    {"en": "tire",         "zh-TW": "輪胎",     "ja": "タイヤ"},
    {"en": "wheel",        "zh-TW": "輪框",     "ja": "ホイール"},
    {"en": "shock",        "zh-TW": "避震器",   "ja": "ショック"},
    {"en": "suspension",   "zh-TW": "避震器",   "ja": "サスペンション"},
    {"en": "fork",         "zh-TW": "前叉",     "ja": "フォーク"},
    {"en": "headlight",    "zh-TW": "大燈",     "ja": "ヘッドライト"},
    {"en": "battery",      "zh-TW": "電池",     "ja": "バッテリー"},
    {"en": "oil filter",   "zh-TW": "機油濾芯", "ja": "オイルフィルター"},
    {"en": "air filter",   "zh-TW": "空氣濾芯", "ja": "エアフィルター"},
    {"en": "spark plug",   "zh-TW": "火星塞",   "ja": "スパークプラグ"},
    {"en": "piston",       "zh-TW": "活塞",     "ja": "ピストン"},
    {"en": "clutch",       "zh-TW": "離合器",   "ja": "クラッチ"},
    {"en": "carburetor",   "zh-TW": "化油器",   "ja": "キャブレター"},
    {"en": "engine",       "zh-TW": "引擎",     "ja": "エンジン"},
    {"en": "cylinder",     "zh-TW": "汽缸",     "ja": "シリンダー"},
    {"en": "gasket",       "zh-TW": "墊片",     "ja": "ガスケット"},
    {"en": "bolt",         "zh-TW": "螺絲",     "ja": "ボルト"},
    {"en": "bearing",      "zh-TW": "軸承",     "ja": "ベアリング"},
    {"en": "cable",        "zh-TW": "拉線",     "ja": "ケーブル"},
    {"en": "grip",         "zh-TW": "握把",     "ja": "グリップ"},
    {"en": "lever",        "zh-TW": "拉桿",     "ja": "レバー"},
    {"en": "clamp",        "zh-TW": "夾具",     "ja": "クランプ"},
    {"en": "windscreen",   "zh-TW": "風鏡",     "ja": "スクリーン"},
    {"en": "rim",          "zh-TW": "鋼圈",     "ja": "リム"},
    {"en": "tail light",   "zh-TW": "尾燈",     "ja": "テールランプ"},
    {"en": "turn signal",  "zh-TW": "方向燈",   "ja": "ウインカー"},
    {"en": "horn",         "zh-TW": "喇叭",     "ja": "ホーン"},
    {"en": "frame",        "zh-TW": "車架",     "ja": "フレーム"},
    {"en": "swing arm",    "zh-TW": "後搖臂",   "ja": "スイングアーム"},
]


# Reverse indexes: phrase-length → {lower-cased source phrase: row}.
# For English the "length" is the number of whitespace-separated words.
# For CJK languages it's the number of characters. Built once at import.
def _is_cjk_lang(lang: str) -> bool:
    return lang in (LANG_ZH, LANG_JA)


def _phrase_len(phrase: str, lang: str) -> int:
    return len(phrase) if _is_cjk_lang(lang) else len(phrase.split())


def _build_index(lang: str) -> dict[int, dict[str, dict[str, str]]]:
    by_len: dict[int, dict[str, dict[str, str]]] = {}
    for row in PARTS_DICT:
        phrase = row[lang]
        by_len.setdefault(_phrase_len(phrase, lang), {})[_norm(phrase)] = row
    return by_len


def _norm(s: str) -> str:
    return s.strip().lower()


_INDEX: dict[str, dict[int, dict[str, dict[str, str]]]] = {
    LANG_EN: _build_index(LANG_EN),
    LANG_ZH: _build_index(LANG_ZH),
    LANG_JA: _build_index(LANG_JA),
}


_HIRAGANA_RE = re.compile(r"[぀-ゟ]")
_KATAKANA_RE = re.compile(r"[゠-ヿ]")
_CJK_RE      = re.compile(r"[一-鿿]")


def detect_lang(text: str) -> str:
    """Cheap script-class detection. Tuned for short search queries.

    Hiragana or katakana → Japanese (even if mixed with kanji, since only
    Japanese routinely mixes kana with han characters). Han-only → Traditional
    Chinese. Otherwise English.
    """
    if not text:
        return LANG_EN
    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        return LANG_JA
    if _CJK_RE.search(text):
        return LANG_ZH
    return LANG_EN


def translate(text: str, target_lang: str) -> str:
    """Translate `text` into `target_lang` token by token.

    - No-op when source and target lang match.
    - Phrase-greedy: "oil filter" matches as one entry, not as ["oil", "filter"].
    - Unknown tokens pass through verbatim (proper nouns, model numbers, …).
    """
    text = (text or "").strip()
    if not text:
        return text
    src = detect_lang(text)
    if src == target_lang:
        return text

    # Tokenise: English splits on whitespace; CJK is per-character.
    tokens: list[str] = list(text) if _is_cjk_lang(src) else text.split()
    src_index = _INDEX[src]
    out: list[str] = []
    i = 0
    while i < len(tokens):
        matched = False
        # Try the longest phrase length present in the index, then descend.
        for n in sorted(src_index.keys(), reverse=True):
            if i + n > len(tokens):
                continue
            window = "".join(tokens[i:i + n]) if _is_cjk_lang(src) else " ".join(tokens[i:i + n])
            row = src_index[n].get(_norm(window))
            if row is not None:
                out.append(row[target_lang])
                i += n
                matched = True
                break
        if not matched:
            out.append(tokens[i])
            i += 1

    # Preserve the SOURCE language's separator structure: English input keeps
    # its spaces (so "Brembo brake" → "Brembo ブレーキ" with the space intact);
    # CJK input has no separator (so "排氣管" → "マフラー", no spaces injected).
    sep = "" if _is_cjk_lang(src) else " "
    return sep.join(out).strip()


def translate_for_adapter(query: str, adapter: Any) -> str | None:
    """Translate `query` into `adapter.preferred_query_lang`, if any.

    Returns the original query unchanged when the adapter has no preference
    (preferred_query_lang is None or missing) or when source == target.
    """
    target = getattr(adapter, "preferred_query_lang", None)
    if not target or not query:
        return query
    return translate(query, target)
