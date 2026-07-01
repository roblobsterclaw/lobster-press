"""Logging + Telegram alerting.

Rule for the whole backend: no silent failures. Every error path goes through
`alert()`, which logs AND pings Telegram. `guard()` wraps a stage so any
uncaught exception is reported before it propagates and fails the job.
"""
from __future__ import annotations

import contextlib
import logging
import sys

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("lobster-press")


def send_telegram(text: str) -> bool:
    """Best-effort Telegram message. Returns True if delivered."""
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        log.warning("Telegram not configured; skipping alert: %s", text)
        return False
    try:
        import requests

        resp = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # never let alerting itself crash the job
        log.error("Failed to send Telegram alert: %s", exc)
        return False


def alert(message: str, exc: BaseException | None = None) -> None:
    """Log an error and push it to Telegram."""
    detail = f"{message}: {exc}" if exc else message
    log.error(detail)
    send_telegram(f"🦞⚠️ Lobster Press\n{detail}")


def notify(message: str) -> None:
    """Informational ping (e.g. 'published 2 posts'). Logs + Telegram."""
    log.info(message)
    send_telegram(f"🦞 Lobster Press\n{message}")


@contextlib.contextmanager
def guard(stage: str):
    """Wrap a stage so any exception is alerted, then re-raised."""
    try:
        yield
    except Exception as exc:
        alert(f"[{stage}] failed", exc)
        raise
