"""Instagram publishing (stub).

Instagram uses the same Meta Graph plumbing as Facebook: create a media
container at /{ig-user-id}/media with image_url + caption, then publish it at
/{ig-user-id}/media_publish. Wire this up by filling in publish() once
IG_USER_ID / IG_ACCESS_TOKEN are provisioned. Until then it reports
not-configured and the publisher skips it (no silent drop).
"""
from __future__ import annotations

import config

from .base import PlatformAdapter, PublishResult


class InstagramAdapter(PlatformAdapter):
    code = "IG"
    name = "Instagram"

    def is_configured(self) -> bool:
        return bool(config.IG_USER_ID and config.IG_ACCESS_TOKEN)

    def publish(self, post: dict) -> PublishResult:
        # TODO: two-step container + media_publish flow (mirrors FacebookAdapter).
        return PublishResult.skip(self.code, "Instagram adapter not yet implemented")
