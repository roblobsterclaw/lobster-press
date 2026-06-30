"""Read/write the JSON data files that the dashboard and backend share.

`data/posts.json` is the single source of truth for the queue. Writes are
atomic (temp file + replace) and always refresh `meta.lastUpdated` so a partial
write can never corrupt the file the dashboard reads.
"""
from __future__ import annotations

import datetime
import json
import os
import tempfile
from typing import Any

import config

VERSION = "3.0.0"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_posts(path: str | None = None) -> dict[str, Any]:
    data = _read_json(path or config.POSTS_PATH)
    if "posts" not in data or not isinstance(data["posts"], list):
        data = {"posts": [], "meta": {}}
    return data


def save_posts(data: dict[str, Any], path: str | None = None) -> None:
    path = path or config.POSTS_PATH
    data.setdefault("meta", {})
    data["meta"]["lastUpdated"] = now_iso()
    data["meta"]["version"] = VERSION
    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_inbox(path: str | None = None) -> dict[str, Any]:
    data = _read_json(path or config.INBOX_PATH)
    if "items" not in data or not isinstance(data["items"], list):
        data = {"items": []}
    return data


def save_inbox(data: dict[str, Any], path: str | None = None) -> None:
    _atomic_write(path or config.INBOX_PATH,
                  json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _atomic_write(path: str, text: str) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# --- helpers ------------------------------------------------------------------

def index_by_id(posts: list[dict]) -> dict[str, dict]:
    return {p["id"]: p for p in posts if p.get("id")}


def has_post(posts: list[dict], post_id: str) -> bool:
    return any(p.get("id") == post_id for p in posts)


def inbox_already_used(inbox_items: list[dict], inbox_id: str) -> bool:
    """True if an inbox item has already produced a post (dedupe guard)."""
    for it in inbox_items:
        if it.get("id") == inbox_id and (it.get("usedInPost") or it.get("status") == "used"):
            return True
    return False
