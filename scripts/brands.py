"""Brand charter — the single source of truth for who each business is.

Both the caption AI (generate.py) and the image renderer (render.py) read from
here, so voice, color, goal, and CTA stay consistent across every post and
every platform. Keyed by internal code ("TLC" / "Surfbox" / "Keli"); the
customer-facing name is `display_name` (never the code).

Shared voice for ALL THREE (per owner, 2026-07-06):
  Mom-and-pop warmth with an edge. NOT corporate. Smart, dedicated, and openly
  the best in our space and our towns. Customer-service first. Real, local,
  human. Word of mouth is king — write posts people want to share and repeat.
"""
from __future__ import annotations

VOICE = (
    "Warm, local, mom-and-pop feel but with an edge and confidence. Never "
    "corporate or stiff. Smart, dedicated, proud to be the best in our area. "
    "Customer-service first. Plain-spoken and human — the kind of post someone "
    "screenshots and sends to a friend. No jargon, no hype-speak."
)

# Geo focus: strong in Ocean County / LBI today; GROWING south — Atlantic City
# down through Cape May County to Rehoboth, DE. Seed local discovery tags so the
# southern towns start surfacing this content.
GEO_TAGS_CORE = ["#LBI", "#JerseyShore", "#OceanCounty"]
GEO_TAGS_SOUTH = ["#SouthJersey", "#CapeMay", "#Wildwood", "#Avalon",
                  "#StoneHarbor", "#OceanCityNJ", "#Rehoboth", "#CapeMayCounty"]

BRANDS = {
    "TLC": {
        "display_name": "Tuckerton Lumber Company",
        "short_name": "Tuckerton Lumber",
        "color_hex": "#C41E2A",              # red — their identity color
        "color_rgb": (196, 30, 42),
        "goal": "Drive people into the physical stores (foot traffic). No online mail-order.",
        "primary_cta": "Stop in — Tuckerton & Surf City.",
        "contact": "tlcnj.com",
        "hashtags": ["#TuckertonLumber", "#ShopLocal", "#Since1932"] + GEO_TAGS_CORE,
        "service_area": "LBI, Tuckerton, Manahawkin, Mystic Islands — and south.",
    },
    "Surfbox": {
        "display_name": "Surfbox Storage",
        "short_name": "Surfbox",
        "color_hex": "#1C7BD6",              # blue
        "color_rgb": (28, 123, 214),
        "goal": "Drive phone calls, emails, and website sign-ups.",
        "primary_cta": "Call (855) SURFBOX or book at surfboxstorage.com.",
        "contact": "(855) SURFBOX",
        "hashtags": ["#Surfbox", "#PortableStorage", "#StorageMadeSimple"] + GEO_TAGS_CORE,
        "service_area": "Ocean County → Cape May County → Rehoboth, DE.",
    },
    "Keli": {
        "display_name": "Keli Lynch · Keller Williams",
        "short_name": "Keli Lynch",
        "color_hex": "#E8562A",              # orange
        "color_rgb": (232, 86, 42),
        "goal": "Generate real-estate leads — calls and messages to Keli.",
        "primary_cta": "Call Keli Lynch, Keller Williams · 609.273.5747.",
        "contact": "609.273.5747",
        "hashtags": ["#KeliLynch", "#KellerWilliams", "#NJRealEstate"] + GEO_TAGS_CORE,
        "service_area": "Burlington County, Crosswicks, and the Jersey Shore.",
    },
}


def get(code: str) -> dict:
    return BRANDS.get(code, BRANDS["TLC"])
