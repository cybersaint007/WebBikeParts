from __future__ import annotations

from difflib import SequenceMatcher


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()

