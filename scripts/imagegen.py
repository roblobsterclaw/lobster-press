"""Layer B — generative image editing ("Reimagine").

Turns one real photo + a plain-English instruction ("brighten it and put him on
the beach") into a NEW image, which the deterministic renderer then dresses into
the 5 branded treatments. This is the opt-in, pay-per-image step that sits on
top of the free Pillow pipeline — nothing here runs unless a user asks for it
AND a key is configured.

Engines (config.IMAGE_ENGINE picks the default; the other is an automatic
backup if the primary errors):
  gemini  → Nano Banana (gemini-2.5-flash-image) — edits the real photo
  openai  → gpt-image-1 via the images API

Public API:
  reimagine(src_path, instruction, out_path, engine=None) -> {"path", "engine"}
  available_engines() -> ["gemini", "openai"]  (only those with a key)

No silent failures: every engine attempt is logged; if all fail, ImageGenError
is raised with each engine's reason so the caller can alert.
"""
from __future__ import annotations

import base64
import mimetypes
import os
import time

import config
from notify import log

_ENGINES = ("gemini", "openai")


class ImageGenError(RuntimeError):
    """Raised when reimagining fails (no engine configured, or all engines errored)."""


def available_engines() -> list[str]:
    """Engines that actually have a key set (so the UI can show/hide Reimagine)."""
    out = []
    if config.GEMINI_API_KEY:
        out.append("gemini")
    if config.OPENAI_API_KEY:
        out.append("openai")
    return out


def _order(preferred: str | None) -> list[str]:
    """Preferred engine first, the other as backup — keeping only configured ones."""
    primary = (preferred or config.IMAGE_ENGINE or "gemini").lower()
    if primary not in _ENGINES:
        primary = "gemini"
    ordered = [primary] + [e for e in _ENGINES if e != primary]
    return [
        e for e in ordered
        if (e == "gemini" and config.GEMINI_API_KEY) or (e == "openai" and config.OPENAI_API_KEY)
    ]


def reimagine(src_path: str, instruction: str, out_path: str, engine: str | None = None) -> dict:
    """Edit `src_path` per `instruction`, writing the result to `out_path`.

    Tries the preferred engine, then the other as backup. Returns
    {"path", "engine"} on success; raises ImageGenError if all engines fail.
    """
    if not (src_path and os.path.exists(src_path)):
        raise ImageGenError(f"source image not found: {src_path}")
    instruction = (instruction or "").strip()
    if not instruction:
        raise ImageGenError("empty instruction — nothing to reimagine")

    order = _order(engine)
    if not order:
        raise ImageGenError(
            "No image engine configured — set GEMINI_API_KEY (Nano Banana) "
            "or OPENAI_API_KEY to enable Reimagine."
        )

    with open(src_path, "rb") as fh:
        img = fh.read()
    mime = mimetypes.guess_type(src_path)[0] or "image/jpeg"

    errors = []
    for eng in order:
        try:
            out = _gemini_image(img, mime, instruction) if eng == "gemini" else _openai_image(img, mime, instruction)
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as fh:
                fh.write(out)
            log.info("Reimagined via %s -> %s", eng, out_path)
            return {"path": out_path, "engine": eng}
        except Exception as exc:  # noqa: BLE001 — surface every engine's reason
            log.warning("Image engine '%s' failed: %s", eng, exc)
            errors.append(f"{eng}: {exc}")
    raise ImageGenError("All image engines failed — " + "; ".join(errors))


# --- engines ------------------------------------------------------------------

def _gemini_image(img_bytes: bytes, mime: str, instruction: str) -> bytes:
    """Nano Banana (gemini-2.5-flash-image) native generateContent image edit."""
    if not config.GEMINI_API_KEY:
        raise ImageGenError("GEMINI_API_KEY not set")
    url = f"{config.GEMINI_API_BASE.rstrip('/')}/models/{config.GEMINI_IMAGE_MODEL}:generateContent"
    payload = {
        "contents": [{
            "parts": [
                {"text": instruction},
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(img_bytes).decode("ascii")}},
            ]
        }],
    }
    data = _post_json(url, {"x-goog-api-key": config.GEMINI_API_KEY}, payload)
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inline_data") or part.get("inlineData")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise ImageGenError("Gemini returned no image data")


def _openai_image(img_bytes: bytes, mime: str, instruction: str) -> bytes:
    """OpenAI gpt-image-1 edit: real photo + prompt -> new image."""
    if not config.OPENAI_API_KEY:
        raise ImageGenError("OPENAI_API_KEY not set")
    ext = (mime.split("/")[-1] or "png").replace("jpeg", "jpg")
    resp = _post_multipart(
        "https://api.openai.com/v1/images/edits",
        {"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        {"image": (f"source.{ext}", img_bytes, mime)},
        {"model": config.OPENAI_IMAGE_MODEL, "prompt": instruction, "size": "auto"},
    )
    items = resp.get("data") or []
    if items and items[0].get("b64_json"):
        return base64.b64decode(items[0]["b64_json"])
    raise ImageGenError("OpenAI returned no image data")


# --- transport (retry transient 429/5xx/network) ------------------------------

def _post_json(url: str, headers: dict, payload: dict, timeout: int = 120) -> dict:
    import requests

    last = None
    for attempt in range(3):
        try:
            resp = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                                 json=payload, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last = f"{resp.status_code} {resp.reason}"
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last = str(exc)
            time.sleep(2 * (attempt + 1))
    raise ImageGenError(f"request failed after retries: {last}")


def _post_multipart(url: str, headers: dict, files: dict, data: dict, timeout: int = 120) -> dict:
    import requests

    last = None
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last = f"{resp.status_code} {resp.reason}"
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last = str(exc)
            time.sleep(2 * (attempt + 1))
    raise ImageGenError(f"request failed after retries: {last}")
