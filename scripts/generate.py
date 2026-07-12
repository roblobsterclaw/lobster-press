"""Generate 3 post-caption options for a piece of intake.

Hard rule: AI generation uses FREE models only — never Claude/Opus/paid GPT-4.
We talk to any OpenAI-compatible endpoint (Groq, OpenRouter free tier, ...) set
via LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, and refuse banned model ids. If no
endpoint is configured (or the call fails), we fall back to deterministic
templates so intake still produces usable drafts — never a silent blank.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os

import brand as brandmod
import brands as brand_charter
import config
from notify import log

TONES = ["Professional", "Punchy", "Community"]
OPTION_IDS = ["A", "B", "C"]


def assert_free_model(model: str) -> None:
    lowered = (model or "").lower()
    for marker in config.BANNED_MODEL_MARKERS:
        if marker in lowered:
            raise config.ConfigError(
                f"Refusing to generate with non-free model '{model}'. "
                "Lobster Press generation must use a FREE model."
            )


def generate_options(brand: str, subject: str, body: str, image_url: str | None = None) -> list[dict]:
    options = _llm_options(brand, subject, body) if config.LLM_BASE_URL and config.LLM_API_KEY else None
    if not options:
        options = _template_options(brand, subject, body)
    # normalize shape the dashboard expects
    tags = brand_charter.get(brand)["hashtags"]
    for i, opt in enumerate(options):
        opt.setdefault("optionId", OPTION_IDS[i % 3])
        opt.setdefault("tone", TONES[i % 3])
        opt.setdefault("hashtags", tags)
        opt["imageUrl"] = image_url
        opt["videoUrl"] = None
        opt["platform"] = "Facebook"
    return options[:3]


def _template_options(brand: str, subject: str, body: str) -> list[dict]:
    tags = " ".join(brand_charter.get(brand)["hashtags"])
    context = " ".join(x for x in (subject, body) if x).strip()[:220] or "a fresh update from the team"
    openers = {
        "TLC": [
            "Tuckerton Lumber has helped local builders and homeowners get it done since 1932.",
            "Project in motion? TLC has the materials and local know-how to keep it on track.",
            "Another look at the work happening around Tuckerton and LBI.",
        ],
        "Surfbox": [
            "Surfbox makes portable storage simple for Jersey Shore projects.",
            "Need room fast? Surfbox drops clean, secure storage right where the work is.",
            "Local moves, renovations, and job sites get easier with Surfbox on site.",
        ],
        "Keli": [
            "Keli Lynch brings steady local guidance to every real estate conversation.",
            "The market moves fast. Keli helps buyers and sellers decide with confidence.",
            "Buying or selling starts with someone who knows the neighborhood.",
        ],
    }.get(brand, [])
    return [
        {"caption": f"{openers[i]}\n\nFrom the team: {context}.\n\n{tags}"}
        for i in range(min(3, len(openers)))
    ]


def _llm_options(brand: str, subject: str, body: str) -> list[dict] | None:
    """Call a free OpenAI-compatible chat endpoint. Returns None on any failure."""
    model = config.LLM_MODEL or "llama-3.3-70b-versatile"
    try:
        assert_free_model(model)
    except config.ConfigError as exc:
        log.error("%s", exc)
        return None

    b = brand_charter.get(brand)
    prompt = (
        f"You write social captions for {b['display_name']}, a Jersey Shore small business.\n"
        f"VOICE (follow strictly): {brand_charter.VOICE}\n"
        f"GOAL of every post: {b['goal']}\n"
        f"TIMING: {_date_context()}\n"
        f"Always end with this call to action: {b['primary_cta']}\n"
        f"Write 3 caption options (Professional, Punchy, Community tones). "
        f"Return ONLY JSON: "
        f'{{"options":[{{"tone":"Professional","caption":"..."}},'
        f'{{"tone":"Punchy","caption":"..."}},{{"tone":"Community","caption":"..."}}]}}.\n'
        f"Subject: {subject}\nDetails: {body}"
    )
    try:
        data = _post_chat({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        }, timeout=60)
        content = data["choices"][0]["message"]["content"]
        options = json.loads(content).get("options", [])
        cleaned = [{"tone": o.get("tone"), "caption": o["caption"]} for o in options if o.get("caption")]
        return cleaned or None
    except Exception as exc:
        log.error("LLM generation failed, using templates: %s", exc)
        return None


# --- Treatment copy (caption + the short strings render.py overlays) ----------

COPY_KEYS = ("caption", "headline", "subhead", "quote", "stamp", "chip_label",
             "chip_value", "fun")


def generate_treatment_copy(brand: str, subject: str, body: str,
                            image_path: str | None = None) -> dict:
    """Produce the copy render.py needs for the 5 treatments.

    With a FREE vision model configured, the model actually LOOKS at the photo
    and writes an on-brand caption + short overlay strings. Otherwise it falls
    back to deterministic templates (never a blank).
    """
    b = brand_charter.get(brand)
    copy = None
    if config.LLM_BASE_URL and config.LLM_API_KEY:
        copy = _vision_copy(b, subject, body, image_path)
    if not copy:
        copy = _template_copy(b, subject, body)

    copy.setdefault("cta", b["primary_cta"])
    copy.setdefault("attribution", f"— {b['display_name']}")
    # Append the brand's hashtags to the caption (once).
    tags = " ".join(b["hashtags"])
    caption = (copy.get("caption") or "").rstrip()
    if tags and "#" not in caption:
        caption = f"{caption}\n\n{tags}".strip()
    copy["caption"] = caption
    return copy


def _date_context() -> str:
    """Give the model today's date + a gentle nudge to use timely hooks when they
    genuinely fit — so a photo taken on the 4th naturally gets a 4th-of-July angle."""
    import datetime

    today = datetime.date.today()
    parts = [f"Today's date is {today.strftime('%A, %B %d, %Y')}."]
    if today.year == 2026:
        parts.append("2026 is the United States' 250th anniversary (the Semiquincentennial) "
                     "— a strong hook whenever patriotic or American-made themes fit.")
    parts.append("Only work in a holiday, season, or timely angle when it genuinely fits "
                 "the photo and the moment; otherwise ignore it.")
    return " ".join(parts)


def _template_copy(b: dict, subject: str, body: str) -> dict:
    context = " ".join(x for x in (subject, body) if x).strip()[:180] or "a fresh update from the team"
    opener = {
        "Tuckerton Lumber Company": "Tuckerton Lumber Company has helped local builders and homeowners get it done since 1932.",
        "Surfbox Storage": "Surfbox makes portable storage simple across the Jersey Shore.",
        "Keli Lynch · Keller Williams": "Keli Lynch brings steady local guidance to every real estate move.",
    }.get(b["display_name"], f"An update from {b['display_name']}.")
    short = b["short_name"].upper()
    return {
        "caption": f"{opener}\n\n{b['primary_cta']}",
        "headline": short,
        "subhead": context,
        "quote": opener,
        "stamp": short,
        "chip_label": "LOCAL",
        "chip_value": b["short_name"],
        "fun": f"Stop by and say hi — {b['short_name']}.",
    }


def _post_chat(payload: dict, timeout: int = 90) -> dict:
    """POST to the OpenAI-compatible chat endpoint with retries on transient
    errors (429/5xx/network). Free-tier Gemini occasionally returns 503, and a
    single miss would otherwise leave a draft stuck on the template caption."""
    import time

    import requests

    url = f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"}
    last = None
    for attempt in range(4):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last = f"{resp.status_code} {resp.reason}"
                log.warning("LLM %s (attempt %d/4), retrying...", last, attempt + 1)
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last = str(exc)
            log.warning("LLM request error (attempt %d/4): %s", attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LLM request failed after retries: {last}")


def _vision_copy(b: dict, subject: str, body: str, image_path: str | None) -> dict | None:
    """Ask a FREE vision model to look at the photo and write copy. None on failure."""
    model = config.LLM_MODEL or "gemini-2.5-flash"
    try:
        assert_free_model(model)
    except config.ConfigError as exc:
        log.error("%s", exc)
        return None

    prompt = (
        f"You write social posts for {b['display_name']}, a Jersey Shore small business.\n"
        f"VOICE (follow strictly): {brand_charter.VOICE}\n"
        f"GOAL of the post: {b['goal']}\n"
        f"TIMING: {_date_context()}\n"
        f"Look at the attached photo (if any) and the email context, then write post copy.\n"
        f"Return ONLY JSON with EXACTLY these keys:\n"
        f'{{"caption": "2-4 short paragraphs in the brand voice, ending with this exact '
        f'call to action: {b["primary_cta"]} — no hashtags",'
        f'"headline": "punchy 2-4 word hook",'
        f'"subhead": "one short sentence",'
        f'"quote": "one short quotable line, max ~12 words",'
        f'"stamp": "1-3 word badge",'
        f'"chip_label": "1-2 word label like IN STOCK or STATUS",'
        f'"chip_value": "2-4 word value",'
        f'"fun": "one playful casual one-liner"}}\n'
        f"Email subject: {subject}\nEmail notes: {(body or '')[:800]}"
    )

    content = [{"type": "text", "text": prompt}]
    data_url = _image_data_url(image_path)
    if data_url:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    try:
        data = _post_chat({
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        })
        raw = json.loads(data["choices"][0]["message"]["content"])
        copy = {k: str(raw[k]).strip() for k in COPY_KEYS if raw.get(k)}
        return copy if copy.get("caption") else None
    except Exception as exc:
        log.error("Vision copy generation failed, using templates: %s", exc)
        return None


def _image_data_url(image_path: str | None) -> str | None:
    if not (image_path and os.path.exists(image_path)):
        return None
    try:
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except OSError:
        return None


def classify_brand(text: str) -> str:
    return brandmod.classify(text, default="TLC")


def classify_email(subject: str, body: str) -> str:
    """Subject-weighted brand classification for intake emails."""
    return brandmod.classify_email(subject, body, default="TLC")
