"""Facebook Page publishing via the Graph API.

Image posts go to /{page-id}/photos; text-only posts go to /{page-id}/feed.
Video upload is not handled here yet (returns a clear skip so the publisher
alerts rather than silently dropping it).
"""
from __future__ import annotations

import config

from .base import PlatformAdapter, PublishResult


class FacebookAdapter(PlatformAdapter):
    code = "FB"
    name = "Facebook"

    def is_configured(self) -> bool:
        return config.fb_any_configured()

    def publish(self, post: dict) -> PublishResult:
        import requests

        page_id, token = config.fb_page(post.get("brand"))
        if not (page_id and token):
            return PublishResult.skip(self.code, f"No Facebook page configured for brand {post.get('brand')}")
        base = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{page_id}"
        caption = (post.get("editedCaption") or post.get("caption") or "").strip()
        image_url = _image_url(post)

        # Video (e.g. testimonial Video.mov) needs the video endpoint + a hosted
        # file; not wired yet. Skip loudly instead of posting a broken caption.
        if post.get("videoAttachment") or post.get("videoUrl"):
            return PublishResult.skip(self.code, "Video posts not yet supported on Facebook adapter")

        try:
            if image_url:
                resp = requests.post(
                    f"{base}/photos",
                    data={"url": image_url, "caption": caption, "access_token": token},
                    timeout=60,
                )
            else:
                resp = requests.post(
                    f"{base}/feed",
                    data={"message": caption, "access_token": token},
                    timeout=60,
                )
            payload = resp.json() if resp.content else {}
            if resp.status_code >= 400 or "error" in payload:
                err = payload.get("error", {}).get("message") or f"HTTP {resp.status_code}"
                return PublishResult.failure(self.code, f"Graph API: {err}")
            post_id = payload.get("post_id") or payload.get("id")
            url = f"https://www.facebook.com/{post_id}" if post_id else None
            return PublishResult.success(self.code, url=url, post_id=post_id)
        except Exception as exc:
            return PublishResult.failure(self.code, str(exc))


def _selected_option(post: dict) -> dict:
    sel = post.get("selectedOption")
    if isinstance(sel, dict):
        return sel
    options = post.get("options") or []
    if isinstance(sel, str):
        return next((o for o in options if o.get("optionId") == sel), {})
    return {}


def _image_url(post: dict) -> str | None:
    """Resolve an absolute, publicly reachable image URL. Prefer the approved
    treatment's rendered image over the raw source photo."""
    url = _selected_option(post).get("imageUrl") or post.get("imageUrl")
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    # repo-relative path like images/foo.png -> GitHub Pages absolute URL
    return f"{config.PAGES_BASE_URL.rstrip('/')}/{url.lstrip('/')}"
