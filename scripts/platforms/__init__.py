"""Platform adapter registry.

Map the short codes stored in post["platforms"] (FB / IG / TT) to adapters.
Register a new channel by adding one line here.
"""
from __future__ import annotations

from .base import NotConfigured, PlatformAdapter, PublishResult
from .facebook import FacebookAdapter
from .instagram import InstagramAdapter
from .tiktok import TikTokAdapter

# Some legacy data uses "Facebook"/"Instagram"; accept both the code and name.
_ADAPTERS: list[PlatformAdapter] = [FacebookAdapter(), InstagramAdapter(), TikTokAdapter()]

_BY_CODE: dict[str, PlatformAdapter] = {}
for _a in _ADAPTERS:
    _BY_CODE[_a.code.upper()] = _a
    _BY_CODE[_a.name.upper()] = _a


def get_adapter(code: str) -> PlatformAdapter | None:
    return _BY_CODE.get((code or "").upper())


def all_adapters() -> list[PlatformAdapter]:
    return list(_ADAPTERS)


__all__ = [
    "PlatformAdapter", "PublishResult", "NotConfigured",
    "FacebookAdapter", "InstagramAdapter", "TikTokAdapter",
    "get_adapter", "all_adapters",
]
