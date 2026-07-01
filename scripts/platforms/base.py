"""Platform adapter contract.

Adding a new channel (Instagram, TikTok, ...) means writing one class that
implements `code`, `name`, `is_configured()`, and `publish()`. The publisher
and the queue/approval logic never change. This is the extensibility seam:
Facebook ships now; Instagram and TikTok are stubs that light up when their
adapters are configured.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class PublishResult:
    platform: str            # adapter code, e.g. "FB"
    ok: bool = False
    skipped: bool = False    # configured-but-not-applicable / not yet wired
    url: str | None = None
    platform_post_id: str | None = None
    error: str | None = None

    @classmethod
    def success(cls, code: str, url: str, post_id: str | None = None) -> "PublishResult":
        return cls(platform=code, ok=True, url=url, platform_post_id=post_id)

    @classmethod
    def skip(cls, code: str, reason: str) -> "PublishResult":
        return cls(platform=code, skipped=True, error=reason)

    @classmethod
    def failure(cls, code: str, reason: str) -> "PublishResult":
        return cls(platform=code, ok=False, error=reason)


class NotConfigured(RuntimeError):
    """Raised by an adapter that has no credentials yet."""


class PlatformAdapter(abc.ABC):
    code: str = "BASE"   # the short code used in post["platforms"]
    name: str = "Base"   # human label

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True when this adapter has the credentials to publish."""

    @abc.abstractmethod
    def publish(self, post: dict) -> PublishResult:
        """Publish `post` to this platform and return the outcome."""
