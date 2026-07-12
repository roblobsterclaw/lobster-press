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

    def verify_page(self, brand_code: str) -> str:
        """Read-only token check: fetch the page name. No posting."""
        import requests

        page_id, token = config.fb_page(brand_code)
        if not (page_id and token):
            return f"{brand_code}: no page configured"
        try:
            resp = requests.get(
                f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{page_id}",
                params={"fields": "name", "access_token": token},
                timeout=30,
            )
            payload = resp.json() if resp.content else {}
            if resp.status_code >= 400 or "error" in payload:
                err = payload.get("error", {}).get("message") or f"HTTP {resp.status_code}"
                return f"{brand_code}: ERROR — {err}"
            return f"{brand_code}: OK → '{payload.get('name')}' (page {page_id})"
        except Exception as exc:
            return f"{brand_code}: ERROR — {exc}"

    def publish(self, post: dict) -> PublishResult:
        caption = (post.get("editedCaption") or post.get("caption") or "").strip()
        image_url = _image_url(post)

        # Video (e.g. testimonial Video.mov) needs the video endpoint + a hosted
        # file; not wired yet. Skip loudly instead of posting a broken caption.
        if post.get("videoAttachment") or post.get("videoUrl"):
            return PublishResult.skip(self.code, "Video posts not yet supported on Facebook adapter")

        # A post can target several brand Pages at once (crossposting). A dog in
        # a SurfBox hat sitting in the Tuckerton yard belongs on both walls.
        targets = _target_brands(post)
        already = set(post.get("postedPages") or [])
        remaining = [b for b in targets if b not in already]
        if not remaining:
            return PublishResult.skip(self.code, "Already posted to every target page")

        posted_now: list[str] = []
        errors: list[str] = []
        first_url = None
        first_id = None
        for brand in remaining:
            ok, url, pid, err = self._post_to_page(brand, caption, image_url)
            if ok:
                posted_now.append(brand)
                first_url = first_url or url
                first_id = first_id or pid
            else:
                errors.append(f"{brand}: {err}")

        # Record which Pages actually took the post so a retry never double-posts
        # to a Page that already succeeded — only the failed Pages are re-tried.
        if posted_now:
            post["postedPages"] = sorted(already | set(posted_now))

        if errors:
            detail = "; ".join(errors)
            if posted_now:
                detail = f"posted to {', '.join(posted_now)}; FAILED — {detail}"
            return PublishResult(
                platform=self.code, ok=False, url=first_url,
                platform_post_id=first_id, error=detail,
            )
        return PublishResult.success(self.code, url=first_url, post_id=first_id)

    def _post_to_page(self, brand_code, caption, image_url):
        """Publish to one brand's Page. Returns (ok, url, post_id, error)."""
        import requests

        page_id, token = config.fb_page(brand_code)
        if not (page_id and token):
            return False, None, None, "no Page configured"
        base = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{page_id}"
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
                return False, None, None, f"Graph API: {err}"
            post_id = payload.get("post_id") or payload.get("id")
            url = f"https://www.facebook.com/{post_id}" if post_id else None
            return True, url, post_id, None
        except Exception as exc:
            return False, None, None, str(exc)


def _target_brands(post: dict) -> list[str]:
    """Which brand Pages this post should go to. `crosspostBrands` (a list of
    brand codes) lets one approved item hit several Pages; absent that, it goes
    to the post's own `brand`. Order preserved, duplicates dropped, blanks
    ignored."""
    raw = post.get("crosspostBrands")
    codes = raw if isinstance(raw, list) and raw else [post.get("brand")]
    seen: set[str] = set()
    out: list[str] = []
    for code in codes:
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


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
