"""Generate 3 post-caption options for a piece of intake.

Hard rule: AI generation uses FREE models only — never Claude/Opus/paid GPT-4.
We talk to any OpenAI-compatible endpoint (Groq, OpenRouter free tier, ...) set
via LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, and refuse banned model ids. If no
endpoint is configured (or the call fails), we fall back to deterministic
templates so intake still produces usable drafts — never a silent blank.
"""
from __future__ import annotations

import json

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
        f"Always end with this call to action: {b['primary_cta']}\n"
        f"Write 3 caption options (Professional, Punchy, Community tones). "
        f"Return ONLY JSON: "
        f'{{"options":[{{"tone":"Professional","caption":"..."}},'
        f'{{"tone":"Punchy","caption":"..."}},{{"tone":"Community","caption":"..."}}]}}.\n'
        f"Subject: {subject}\nDetails: {body}"
    )
    try:
        import requests

        resp = requests.post(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        options = json.loads(content).get("options", [])
        cleaned = [{"tone": o.get("tone"), "caption": o["caption"]} for o in options if o.get("caption")]
        return cleaned or None
    except Exception as exc:
        log.error("LLM generation failed, using templates: %s", exc)
        return None


def classify_brand(text: str) -> str:
    return brandmod.classify(text, default="TLC")
