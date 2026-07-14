"""Central configuration for the Lobster Press backend.

Everything comes from environment variables (GitHub Actions secrets in CI, a
local .env / shell when developing). Nothing is hardcoded. `require()` fails
loudly with a clear message so a misconfigured run never silently no-ops.
"""
from __future__ import annotations

import os

# --- Repo root + data files (anchored, not cwd-relative) -----------------------
# Scripts run from scripts/ in CI (working-directory: scripts), so a bare
# relative path would resolve to scripts/data/... and silently load nothing.
# Anchor to the repo root (parent of this file's dir) unless overridden.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_PATH = os.environ.get("POSTS_PATH") or os.path.join(REPO_ROOT, "data", "posts.json")
INBOX_PATH = os.environ.get("INBOX_PATH") or os.path.join(REPO_ROOT, "data", "inbox.json")
IMAGES_DIR = os.environ.get("IMAGES_DIR") or os.path.join(REPO_ROOT, "images")

# --- Intake (Gmail) -----------------------------------------------------------
# NOTE: use `or default`, not get(key, default). GitHub Actions passes empty
# strings for unset repo variables (e.g. INTAKE_SENDER: ${{ vars.INTAKE_SENDER }}),
# and get() only falls back when the key is ABSENT — an empty string would slip
# through and make the query `from:` (no filter), pulling every inbox email.
INTAKE_SENDER = os.environ.get("INTAKE_SENDER") or "socialmedia@tlcnj.com"
GMAIL_LABEL = os.environ.get("GMAIL_LABEL") or "LobsterPress/Processed"
# gmail.modify is required so we can APPLY the processed label (read-only can't).
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
GMAIL_CREDENTIALS_JSON = os.environ.get("GMAIL_CREDENTIALS_JSON", "")  # OAuth client
GMAIL_TOKEN_JSON = os.environ.get("GMAIL_TOKEN_JSON", "")             # authorized token w/ refresh

# --- AI generation (FREE models only — never Claude/Opus/paid GPT-4) ----------
# Provider-agnostic, OpenAI-compatible chat endpoint. Point it at a free tier:
#   Groq:        https://api.groq.com/openai/v1   model e.g. llama-3.3-70b-versatile
#   OpenRouter:  https://openrouter.ai/api/v1     model e.g. meta-llama/llama-3.1-8b-instruct:free
# If unset, generation falls back to deterministic templates (no network).
# Default to Google Gemini's free OpenAI-compatible endpoint, so the ONLY thing
# that has to be provisioned is the LLM_API_KEY secret. Override the URL/model
# via env to switch providers (e.g. Groq) — the code is provider-agnostic.
# Generation stays on templates until LLM_API_KEY is set (safe no-op).
LLM_BASE_URL = os.environ.get("LLM_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL") or "gemini-2.5-flash"

# Models we must never use for generation (cost guardrail). Checked in generate.py.
BANNED_MODEL_MARKERS = ("claude", "opus", "sonnet", "haiku", "gpt-4", "gpt-5", "o1", "o3")

# --- Layer B: generative image editing ("Reimagine") --------------------------
# Optional, opt-in, pay-per-image. The primary engine edits a REAL photo per a
# text instruction; the other is an automatic backup if the primary errors.
# Flip IMAGE_ENGINE to switch the default any time ("gemini" or "openai").
#   Nano Banana = Google's gemini-2.5-flash-image (reuses the Gemini key)
#   OpenAI      = gpt-image-1 via the images API
# Unset keys simply disable that engine (Reimagine stays off until a key exists).
IMAGE_ENGINE = (os.environ.get("IMAGE_ENGINE") or "gemini").lower()
GEMINI_API_BASE = os.environ.get("GEMINI_API_BASE") or "https://generativelanguage.googleapis.com/v1beta"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or LLM_API_KEY  # Nano Banana shares the Gemini key
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1"

# --- Publishing platforms -----------------------------------------------------
# Each business has its OWN Facebook Page. Per-brand secrets:
#   FB_PAGE_ID_TLC / FB_PAGE_TOKEN_TLC     (Tuckerton Lumber)
#   FB_PAGE_ID_SURFBOX / FB_PAGE_TOKEN_SURFBOX
#   FB_PAGE_ID_KELI / FB_PAGE_TOKEN_KELI
# FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN act as a single-page fallback (handy for a
# first test with just one business).
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")
_FB_BRAND_CODES = ("TLC", "SURFBOX", "KELI")


def fb_page(brand_code: str):
    """Return (page_id, page_token) for a brand, falling back to the single
    default page when a per-brand page isn't configured."""
    code = (brand_code or "").upper()
    page_id = os.environ.get(f"FB_PAGE_ID_{code}") or FB_PAGE_ID
    token = os.environ.get(f"FB_PAGE_TOKEN_{code}") or FB_PAGE_ACCESS_TOKEN
    return page_id, token


def fb_any_configured() -> bool:
    """True if at least one Facebook page (default or per-brand) is set."""
    if FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN:
        return True
    return any(
        os.environ.get(f"FB_PAGE_ID_{c}") and os.environ.get(f"FB_PAGE_TOKEN_{c}")
        for c in _FB_BRAND_CODES
    )

IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")

TIKTOK_ACCESS_TOKEN = os.environ.get("TIKTOK_ACCESS_TOKEN", "")

# --- Alerting (Telegram) ------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Base URL for building absolute media URLs from repo-relative image paths.
PAGES_BASE_URL = os.environ.get(
    "PAGES_BASE_URL", "https://roblobsterclaw.github.io/lobster-press"
)


class ConfigError(RuntimeError):
    """Raised when a required setting is missing."""


def require(*names: str) -> None:
    """Fail loudly if any named module-level setting is empty."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise ConfigError(
            "Missing required configuration: "
            + ", ".join(missing)
            + ". Set them as environment variables / GitHub Actions secrets."
        )
