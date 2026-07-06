"""Marquee "Sign of the Week" generator for the changeable store signs.

Both stores have high-traffic changeable letter signs out front (thousands of
cars/pedestrians daily). This produces ~10 short candidate lines each week for
Joe to pick from — catchy, sometimes edgy, timely, and ALWAYS within the
physical limits of the sign:

  <= 60 characters, at most 2 short lines.

Surf City leans into the "island general store — we have it, just ask, skip the
bridge" positioning. When a free model is configured it writes fresh lines from
the store's voice + the week's context; otherwise it draws from a curated
evergreen bank so there's always a good option. Every candidate is validated
against the sign limits before it's offered.
"""
from __future__ import annotations

MAX_CHARS = 60
MAX_LINES = 2

STORES = {
    "surf_city": {
        "name": "Tuckerton Lumber — Surf City",
        "address": "200 N Long Beach Blvd, Surf City, NJ",
        "angle": "The island's general store & hardware. We carry (almost) everything — "
                 "just ask, and if we don't have it we'll get it. Skip the bridge and the "
                 "big-box drive. Neighborly, a little edgy, LBI-proud.",
        "evergreens": [
            "Skip the bridge. We've got it.",
            "Need it? Just ask. We've got it.",
            "The island's general store. Just ask.",
            "If we don't carry it, we'll get it.",
            "Everything the island needs. Right here.",
            "Don't cross the bridge. Cross our threshold.",
            "Forgot something? We've got it.",
            "Big-box selection. Small-town service.",
            "Nuts, bolts & everything else. Just ask.",
            "One more thing off your list. Stop in.",
            "Another island shop closed. We're still here.",
            "Save the bridge traffic for the tourists.",
            "Your island hardware store since 1932.",
        ],
    },
    "tuckerton": {
        "name": "Tuckerton Lumber — Tuckerton",
        "address": "249 N Green St, Tuckerton, NJ 08087",
        "angle": "The original since 1932. Lumber + hardware + paint. Retail walk-ins and "
                 "contractors (call it in, we deliver). Proud, local, dependable.",
        "evergreens": [
            "Your project starts here. Since 1932.",
            "Paint, lumber, hardware — one stop.",
            "Contractors: call it in, we deliver.",
            "90+ years on Green Street.",
            "Everything for the job. Since 1932.",
            "Local since 1932. Still going strong.",
        ],
    },
}

# Seasonal nudges the generator can time (evergreen fallback rotates these in).
SEASONAL = [
    "Deck season's here. So's your lumber.",
    "Grill's calling. We've got the propane.",
    "Storm prep starts here.",
    "Beach house to-do list? Start here.",
    "Summer's coming. Beat the rush.",
    "Cold snap? Grab it before you need it.",
]

VOICE = (
    "Short, punchy, memorable. Catchy and sometimes edgy, never corporate. "
    "Local and LBI-proud. Each line must be <= 60 characters and fit on at most "
    "two short lines. Some should tie to the season or the week."
)


def validate(line: str) -> bool:
    """True if a line fits the physical sign (<= 60 chars, <= 2 lines)."""
    if not line or len(line) > MAX_CHARS:
        return False
    return line.count("\n") + 1 <= MAX_LINES


def _fallback(store: str, n: int) -> list[str]:
    cfg = STORES[store]
    pool = list(cfg["evergreens"])
    if store == "surf_city" or store == "tuckerton":
        pool += SEASONAL
    out, seen = [], set()
    for line in pool:
        if validate(line) and line not in seen:
            out.append(line)
            seen.add(line)
        if len(out) >= n:
            break
    return out


def generate_candidates(store: str, n: int = 10, context: str = "") -> list[str]:
    """Return up to n validated sign lines. Uses a free model when configured,
    otherwise the curated evergreen/seasonal bank. Never returns a line that
    won't fit the sign."""
    if store not in STORES:
        raise ValueError(f"unknown store '{store}'")
    lines = _model_candidates(store, n, context)
    if not lines:
        lines = _fallback(store, n)
    # enforce the physical limit no matter the source
    return [ln for ln in lines if validate(ln)][:n]


def _model_candidates(store: str, n: int, context: str) -> list[str] | None:
    """Free-model generation (OpenAI-compatible). None on any failure."""
    try:
        import config
        if not (config.LLM_BASE_URL and config.LLM_API_KEY):
            return None
        import json
        import requests
        cfg = STORES[store]
        prompt = (
            f"Write {n} marquee sign lines for {cfg['name']}.\n"
            f"Positioning: {cfg['angle']}\nStyle: {VOICE}\n"
            f"This week's context: {context or 'general'}\n"
            f'Return ONLY JSON: {{"lines":["...", "..."]}}. '
            f"Every line MUST be <= {MAX_CHARS} characters."
        )
        resp = requests.post(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={"model": config.LLM_MODEL or "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.9, "response_format": {"type": "json_object"}},
            timeout=60,
        )
        resp.raise_for_status()
        return json.loads(resp.json()["choices"][0]["message"]["content"]).get("lines")
    except Exception:
        return None


if __name__ == "__main__":
    for store in STORES:
        print(f"\n== {STORES[store]['name']} ==")
        for i, line in enumerate(generate_candidates(store, 10), 1):
            print(f"{i:2}. [{len(line):2}] {line}")
