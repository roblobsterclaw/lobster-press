"""Render self-test (needs Pillow). Renders all 5 treatments for each brand
from a repo photo into a temp dir and checks the files come out non-empty.

Kept separate from smoke_test.py so the pure-stdlib CI check stays dependency
free. Run: python scripts/render_selftest.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import render  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = [
    ("Keli", "images/keli-under-contract.jpg"),
    ("Surfbox", "images/surfbox-truck-hero.jpg"),
    ("TLC", "images/tlc-composite-deck.png"),
]
COPY = {
    "headline": "DECK SEASON IS HERE",
    "subhead": "Low-maintenance composite decking built for the shore.",
    "quote": "Bare feet on, splinters gone.",
    "stamp": "IN STOCK", "chip_label": "NEW", "chip_value": "Composite Decking",
    "fun": "Your bare feet just RSVP'd yes",
}

failures = []
with tempfile.TemporaryDirectory() as d:
    for brand, img in CASES:
        src = os.path.join(REPO, img)
        if not os.path.exists(src):
            print(f"SKIP  {brand}: {img} not in repo")
            continue
        out = render.render_treatments(src, brand, COPY, d, f"{brand}_t")
        ok = len(out) == 5 and all(os.path.getsize(r["path"]) > 1000 for r in out)
        print(f"{'PASS' if ok else 'FAIL'}  {brand}: {len(out)} treatments")
        if not ok:
            failures.append(brand)

print()
if failures:
    print(f"FAILED: {failures}")
    sys.exit(1)
print("Render self-test passed.")
