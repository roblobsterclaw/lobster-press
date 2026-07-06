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

# Market areas differ per business — do NOT blanket-tag everyone the same:
#
#   Surfbox:   the coast from Rehoboth, DE up to Seaside Heights, NJ, plus
#              ~25-30 miles inland. Coastal-heavy, reaches furthest south.
#   Tuckerton: Central Jersey coast+inland — Atlantic City up to Seaside and
#              inland toward Trenton. NOT south of AC (competitors there; nobody
#              drives that far for a lumber yard).
#   Keli/KW:   the Central Jersey "square" — Trenton / Princeton / Red Bank /
#              down to Atlantic City / over to Morristown. Same core as Tuckerton.
#
# These tags seed local discovery; the paid boost tools do the precise geo
# targeting (you draw the actual circle/region there).
GEO_TAGS_SURFBOX = ["#JerseyShore", "#LBI", "#OceanCounty", "#TomsRiver",
                    "#AtlanticCity", "#OceanCityNJ", "#Wildwood", "#CapeMay",
                    "#Rehoboth", "#BethanyBeach", "#DelawareBeaches", "#SouthJersey"]
GEO_TAGS_CENTRAL_NJ = ["#JerseyShore", "#LBI", "#OceanCounty", "#CentralJersey",
                       "#AtlanticCity", "#Trenton", "#Princeton", "#RedBank",
                       "#MonmouthCounty"]

BRANDS = {
    "TLC": {
        "display_name": "Tuckerton Lumber Company",
        "short_name": "Tuckerton Lumber",
        "color_hex": "#C41E2A",              # red — their identity color
        "color_rgb": (196, 30, 42),
        "goal": "TWO audiences: (1) retail/walk-in — drive foot traffic to the stores; "
                "(2) contractors — win call-in LUMBER orders we deliver across a wide area.",
        "primary_cta": "Stop in — Tuckerton & Surf City.",
        "audiences": {
            "retail": {
                "who": "Homeowners / DIY / walk-in customers.",
                "area": "Tight local — LBI, Manahawkin, Tuckerton, Ship Bottom / Surf City. "
                        "They won't travel far for a hardware store.",
                "cta": "Stop in — Tuckerton & Surf City.",
            },
            "contractor": {
                "who": "Contractors & builders (existing relationships well beyond LBI).",
                "area": "Wide DELIVERY zone — Mercer (Trenton, Princeton, Bordentown) & "
                        "Burlington (Mt Holly) through all of Ocean County to Atlantic "
                        "City. Bounded only by driver/truck capacity.",
                "cta": "Call your order in — we deliver lumber across the region.",
            },
        },
        "contact": "tlcnj.com",
        "hashtags": ["#TuckertonLumber", "#ShopLocal", "#Since1932", "#ContractorSupply",
                     "#LumberDelivery"] + GEO_TAGS_CENTRAL_NJ,
        "service_area": "Retail core: LBI / Manahawkin / Tuckerton. Lumber DELIVERY: Mercer "
                        "& Burlington (Trenton–Princeton, Bordentown, Mt Holly) through "
                        "Ocean County to Atlantic City.",
    },
    "Surfbox": {
        "display_name": "Surfbox Storage",
        "short_name": "Surfbox",
        "color_hex": "#1C7BD6",              # blue
        "color_rgb": (28, 123, 214),
        "goal": "Drive phone calls, emails, and website sign-ups.",
        "primary_cta": "Call (855) SURFBOX or book at surfboxstorage.com.",
        "contact": "(855) SURFBOX",
        "hashtags": ["#Surfbox", "#PortableStorage", "#StorageMadeSimple"] + GEO_TAGS_SURFBOX,
        "service_area": "The whole coast — Delaware beaches (Lewes/Rehoboth/Bethany) up "
                        "through Cape May, Wildwood, Ocean City, Atlantic City, LBI to "
                        "Toms River/Seaside — plus inland South Jersey (Vineland, "
                        "Hammonton, Medford, Mt Holly, Pemberton, Lakewood), ~25-30 mi in.",
    },
    "Keli": {
        "display_name": "Keli Lynch · Keller Williams",
        "short_name": "Keli Lynch",
        "color_hex": "#E8562A",              # orange
        "color_rgb": (232, 86, 42),
        "goal": "Generate real-estate leads — calls and messages to Keli.",
        "primary_cta": "Call Keli Lynch, Keller Williams · 609.273.5747.",
        "contact": "609.273.5747",
        "hashtags": ["#KeliLynch", "#KellerWilliams", "#NJRealEstate"] + GEO_TAGS_CENTRAL_NJ,
        "service_area": "The Central Jersey square: Trenton / Princeton / Red Bank / down "
                        "to Atlantic City / over to Morristown.",
    },
}


def get(code: str) -> dict:
    return BRANDS.get(code, BRANDS["TLC"])
