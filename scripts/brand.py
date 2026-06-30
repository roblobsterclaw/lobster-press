"""Weighted-keyword brand classifier (TLC / Surfbox / Keli).

Mirrors the dashboard's classifyBrand() in index.html so the email-intake
backend and the browser agree on how a draft gets tagged. Strong, unambiguous
signals (names, phones, domains) score far above generic shared terms (lumber,
storage, real estate, LBI), so a Surfbox post never gets tagged TLC just
because both mention the Jersey Shore.
"""
from __future__ import annotations

import re

# (regex, weight) per brand. Patterns are matched case-insensitively.
BRAND_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "Surfbox": [
        (r"\bsurfbox\b", 10), (r"surfboxstorage", 10), (r"855[\s).-]*surfbox", 8),
        (r"787[\s.-]*3269", 8), (r"portable storage", 4), (r"\bcontainers?\b", 3),
        (r"we deliver\.? you fill it", 6), (r"\bron ?jon", 2),
    ],
    "Keli": [
        (r"\bkeli\b", 10), (r"\blynch\b", 6), (r"kw premier", 8), (r"kwpremier", 8),
        (r"609[\s.-]*273[\s.-]*5747", 9), (r"\brealtor\b", 5), (r"real estate", 4),
        (r"under contract", 4), (r"\blisting\b", 3), (r"closing day", 3),
        (r"buyers? (?:and|&) sellers?", 3), (r"long beach island", 1),
    ],
    "TLC": [
        (r"tuckerton lumber", 10), (r"\btlcnj\b", 9), (r"\btlc\b", 6),
        (r"benjamin moore", 6), (r"\breeb\b", 5), (r"\bweber\b", 4),
        (r"composite deck|trex|wolf decking", 5), (r"since 1932", 5),
        (r"\blumber\b", 4), (r"surf city", 3), (r"smart lock", 3),
    ],
}

_COMPILED = {
    brand: [(re.compile(pat, re.IGNORECASE), weight) for pat, weight in signals]
    for brand, signals in BRAND_SIGNALS.items()
}


def score(text: str) -> dict[str, int]:
    haystack = text or ""
    return {
        brand: sum(len(rx.findall(haystack)) * weight for rx, weight in signals)
        for brand, signals in _COMPILED.items()
    }


def classify(text: str, default: str | None = None) -> str | None:
    """Return the best-scoring brand, or `default` when nothing matches."""
    if not (text or "").strip():
        return default
    scores = score(text)
    brand, best = max(scores.items(), key=lambda kv: kv[1])
    return brand if best > 0 else default


if __name__ == "__main__":  # quick manual check
    samples = {
        "surfbox dog napping on a portable storage container": "Surfbox",
        "Composite deck samples just arrived at Tuckerton Lumber": "TLC",
        "Keli Lynch | KW Premier — under contract!": "Keli",
    }
    for text, expected in samples.items():
        got = classify(text)
        print(f"{'ok' if got == expected else 'XX'}  {got:<8} <- {text}")
