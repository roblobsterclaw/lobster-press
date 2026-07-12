"""Publish due posts to every targeted platform.

Run on a cron (see .github/workflows/publisher.yml). A post is "due" when it is
marked Post Now, or it is Scheduled and its time has passed. Each post is sent
to every code in post["platforms"] via that platform's adapter. Facebook is
live; Instagram/TikTok skip cleanly until their adapters are wired.

No silent failures: a hard publish error marks the post `failed` (surfaced in
the dashboard) and alerts via Telegram.

Set DRY_RUN=1 to log what would publish without calling any platform API.
"""
from __future__ import annotations

import datetime
import os

import notify
import store
from platforms import get_adapter

DRY_RUN = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")


def _parse_dt(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def is_due(post: dict, now: datetime.datetime) -> bool:
    status = post.get("status")
    if status == "post_now":
        return True
    if status == "scheduled":
        when = _parse_dt(post.get("scheduledAt"))
        return when is not None and when <= now
    return False


def publish_post(post: dict) -> tuple[bool, list[str], list[str]]:
    """Return (any_success, live_platform_names, hard_errors)."""
    codes = post.get("platforms") or ["FB"]
    live: list[str] = []
    errors: list[str] = []
    first_url = None

    for code in codes:
        adapter = get_adapter(code)
        if adapter is None:
            errors.append(f"{code}: no adapter registered")
            continue
        if not adapter.is_configured():
            notify.log.info("Skipping %s for %s (not configured)", adapter.name, post.get("id"))
            continue
        if DRY_RUN:
            notify.log.info("[dry-run] would publish %s to %s", post.get("id"), adapter.name)
            live.append(adapter.name)
            continue

        result = adapter.publish(post)
        if result.ok:
            live.append(adapter.name)
            first_url = first_url or result.url
        elif result.skipped:
            notify.log.info("Skipped %s for %s: %s", adapter.name, post.get("id"), result.error)
        else:
            errors.append(f"{adapter.name}: {result.error}")

    if live and not DRY_RUN:
        post["status"] = "posted"
        post["postedAt"] = store.now_iso()
        post["postedPlatforms"] = sorted(set((post.get("postedPlatforms") or []) + live))
        if first_url:
            post["postedUrl"] = first_url
            post["publishedUrl"] = first_url
        post["updatedAt"] = store.now_iso()
    elif errors and not DRY_RUN:
        post["status"] = "failed"
        post["failureReason"] = "; ".join(errors)
        post["updatedAt"] = store.now_iso()

    return bool(live), live, errors


def verify_pages() -> None:
    """Read-only check that each brand's Facebook Page token is valid. Logs the
    page name (no posting). Used in DRY_RUN to confirm setup before going live."""
    from platforms import get_adapter

    fb = get_adapter("FB")
    for code in ("TLC", "Surfbox", "Keli"):
        notify.log.info("FB page check — %s", fb.verify_page(code))


def main() -> int:
    with notify.guard("publisher"):
        if DRY_RUN:
            verify_pages()
        data = store.load_posts()
        now = datetime.datetime.now(datetime.timezone.utc)
        due = [p for p in data["posts"] if is_due(p, now)]

        if not due:
            notify.log.info("No posts due to publish.")
            return 0

        published, failed = [], []
        for post in due:
            ok, live, errors = publish_post(post)
            if ok:
                published.append(f"{post.get('id')} → {', '.join(live)}")
            if errors:
                failed.append(f"{post.get('id')}: {'; '.join(errors)}")

        store.save_posts(data)

        if published:
            notify.notify("Published:\n" + "\n".join(published))
        if failed:
            # publish_post already marked them failed; alert so it's never silent.
            notify.alert("Publish failures:\n" + "\n".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
