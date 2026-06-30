"""TikTok publishing (stub).

TikTok uses the Content Posting API (video-first): init an upload, transfer the
video, then publish. Fill in publish() once TIKTOK_ACCESS_TOKEN is provisioned.
Until then it reports not-configured and the publisher skips it.
"""
from __future__ import annotations

import config

from .base import PlatformAdapter, PublishResult


class TikTokAdapter(PlatformAdapter):
    code = "TT"
    name = "TikTok"

    def is_configured(self) -> bool:
        return bool(config.TIKTOK_ACCESS_TOKEN)

    def publish(self, post: dict) -> PublishResult:
        # TODO: Content Posting API init -> upload -> publish (video required).
        return PublishResult.skip(self.code, "TikTok adapter not yet implemented")
