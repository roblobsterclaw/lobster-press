"""Validate (and optionally normalize) data/posts.json.

This is the guardrail that makes "silently missing posts" impossible. The
original bug was vocabulary drift: the generator wrote status "pending" while
the dashboard filtered on "new", so 13 posts matched no tab and vanished. Run
this in CI so any such drift fails the build instead of hiding a post.

  python validate.py            # check only; exit 1 on any problem
  python validate.py --fix      # normalize legacy values in place, then check

Checks: canonical status, unique ids, required fields, known brand.
"""
from __future__ import annotations

import argparse
import sys

import store

# The one canonical status vocabulary. Everything else is drift.
CANONICAL_STATUSES = {
    "new", "approved", "scheduled", "post_now", "posted", "failed", "rejected",
}
# Legacy / alias -> canonical. Extend here when a value is renamed.
STATUS_ALIASES = {
    "pending": "new",
    "creating": "new",
    "draft": "new",
    "published": "posted",
}
KNOWN_BRANDS = {"TLC", "Surfbox", "Keli"}
REQUIRED_FIELDS = ("id", "status", "brand")


def normalize(posts: list[dict]) -> int:
    """Apply status aliases in place. Returns the number of posts changed."""
    changed = 0
    for p in posts:
        s = p.get("status")
        if s in STATUS_ALIASES:
            p["status"] = STATUS_ALIASES[s]
            changed += 1
    return changed


def validate(posts: list[dict]) -> list[str]:
    problems: list[str] = []
    seen: dict[str, int] = {}
    for i, p in enumerate(posts):
        pid = p.get("id", f"<index {i}>")
        for field in REQUIRED_FIELDS:
            if not p.get(field):
                problems.append(f"{pid}: missing required field '{field}'")
        if p.get("id"):
            seen[p["id"]] = seen.get(p["id"], 0) + 1
        status = p.get("status")
        if status and status not in CANONICAL_STATUSES:
            hint = f" (alias of '{STATUS_ALIASES[status]}'? run --fix)" if status in STATUS_ALIASES else ""
            problems.append(f"{pid}: unknown status '{status}'{hint}")
        brand = p.get("brand")
        if brand and brand not in KNOWN_BRANDS:
            problems.append(f"{pid}: unknown brand '{brand}'")
    for pid, count in seen.items():
        if count > 1:
            problems.append(f"duplicate id '{pid}' appears {count} times")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="normalize legacy values in place")
    args = ap.parse_args()

    data = store.load_posts()
    posts = data["posts"]

    if args.fix:
        n = normalize(posts)
        if n:
            store.save_posts(data)
            print(f"Normalized {n} post(s).")
        else:
            print("Nothing to normalize.")

    problems = validate(posts)
    if problems:
        print(f"\n{len(problems)} validation problem(s):", file=sys.stderr)
        for prob in problems:
            print(f"  - {prob}", file=sys.stderr)
        return 1
    print(f"OK: {len(posts)} posts valid (statuses, ids, fields, brands).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
