# Lobster Press — Build Log

Social media content pipeline for three businesses — **Tuckerton Lumber Company (TLC)**,
**Surfbox Storage**, and **Keli Lynch (KW Premier)**. Email intake → AI draft options →
Joe approves on his iPhone → publisher posts to Facebook. Designed to expand to Instagram
and TikTok next.

This log records the targeted rebuild work. It is appended to over time — newest entry on top.

---

## 2026-07-11 — Gemini vision + renderer wired into intake

Intake now produces the full "5 choices" experience for photo emails:
- `generate.generate_treatment_copy(brand, subject, body, image_path)` — with a FREE
  vision model configured, the model **looks at the actual photo** and writes an on-brand
  caption + the short overlay strings (headline/subhead/quote/stamp/chip/fun). Falls back to
  deterministic templates otherwise. Sends the image as a base64 data URL (OpenAI vision
  format), so it works with any OpenAI-compatible vision endpoint.
- `gmail_scan._build_options()` — for a photo email, renders the 5 treatments via
  `render.py` and attaches them as the draft's options (New-tab swipe carousel). `render` is
  imported lazily so the pure-stdlib `smoke_test.py` / `validate.yml` CI stays dependency-free.
  Text-only fallback for emails without a usable image.
- `config.py` — defaults the LLM to **Gemini's free OpenAI-compatible endpoint**
  (`gemini-2.5-flash`), so the only thing to provision is the `LLM_API_KEY` secret. Provider
  is overridable via env (e.g. Groq) — the code is provider-agnostic. Generation stays on
  templates until the key is set (safe no-op).

Verified: compiles, smoke green, template-copy path produces valid fields, and the full
`_build_options` path renders all 5 treatments locally.

---

## 2026-07-07 — Live intake, classifier fix for forwarded email, UI cleanup

- **Email intake is LIVE.** Gmail auth fixed (honor the token's own scope; label best-effort)
  and the empty-`INTAKE_SENDER` bug fixed (`get() or default`, since Actions passes empty
  strings for unset repo vars — it had pulled 25 arbitrary inbox emails). Intake now correctly
  ingests only `socialmedia@tlcnj.com` and runs on the 30-min cron.
- **Brand classifier fix for forwarded email.** Forwarded emails carry a `tlcnj.com`
  footer/signature that skewed every draft to TLC. Added `classify_email(subject, body)` that
  weights the subject 3× over the body, plus Keller Williams signals for Keli. Mirrored in the
  dashboard (`classifyBrand` + subject weighting in auto-detect/generation). Re-tagged existing
  drafts (surfbox subjects now correctly → Surfbox).
- **Dashboard readability.** Removed the tall hero/summary block (it duplicated the tab counts
  and pushed every draft below the fold). Widened the container to `min(1600px, 96vw)`, made
  the treatment carousel show two options side-by-side on desktop, and capped slide media at
  `46vh` — so drafts and their options are visible without scrolling past filler. Verified with
  desktop + phone screenshots.

Known follow-up: template captions currently echo the raw forwarded email body (signature/tel
links) — this cleans up automatically once the free vision/caption model (Gemini) is wired into
intake.

---

## 2026-07-06 — Production renderer + swipe carousel + Sign of the Week

- **`scripts/render.py`** — production image renderer. 5 treatments (clean_feed,
  headline_story, quote_card, badge_callout, fun_casual), all pulling color / display
  name / CTA from `brands.py`. Fixed the CTA-overflow bug (wraps/fits now).
  `render_selftest.py` verifies 3 brands × 5 treatments; `smoke_test.py` stays pure-stdlib.
- **Dashboard swipe carousel** — the New tab now shows a post's treatments as a native
  touch-swipe carousel (CSS scroll-snap, no library): one design at a time, "‹ Prev /
  Design N of M / Next ›", "Use this" to approve that design. Falls back cleanly to a
  single slide for posts without treatments. Verified with a headless-Chromium screenshot
  at iPhone size (`keli-listing-001` seeded with 5 real rendered treatments).
- **`scripts/signs.py`** — "Sign of the Week" generator for the store marquees
  (Surf City 200 N Long Beach Blvd, Tuckerton 249 N Green St). ~10 candidate lines/store,
  enforces the physical limit (≤60 chars, ≤2 lines), free-model when configured else a
  curated evergreen+seasonal bank. `generate_candidates(..., context=)` powers the
  "type a direction → 10 more" flow. Surf City leans into the island general-store angle.

**Market areas locked in `brands.py`:** Surfbox = full coast (DE beaches → Toms River) +
inland South Jersey; Tuckerton = retail tight (LBI/Manahawkin) + contractor lumber delivery
across Mercer/Burlington/Ocean/Atlantic; Keli = same Central Jersey footprint as Tuckerton.

---

## 2026-07-06 — Step 2 creative-treatment direction + brand kit + Gmail auth

Prototyped a big presentation upgrade for Step 2: instead of text-only caption options,
each piece of intake produces **5 finished, on-brand treatments** from the photo (or a
video's cover frame) — Clean Feed (1:1), Headline Story (9:16), Quote Card (4:5),
Badge/Callout (1:1), Fun/Casual (1:1). Built with Pillow (free, deterministic, no AI image
cost). Validated on three real photos across all three brands.

**Brand kit locked (customer-facing):**
- Surfbox → **blue**
- Keli / Keller Williams → **orange**
- Tuckerton Lumber → **red** (their identity color)
- Tuckerton is always written **"Tuckerton Lumber Company"** on customer art — never "TLC"
  ("TLC" stays only as an internal brand code in the software).

**Still to wire in (production):** promote the prototype to `scripts/render.py`; call it from
intake; show the 5 mockups in the New tab; hook up a free vision model (Gemini) so captions
are written from the actual photo. Known polish item: long CTA lines need auto-fit/wrap.

**Gmail authorization:** added `scripts/gmail_auth.py` — a one-time local OAuth helper
(gmail.modify scope) that produces the `GMAIL_TOKEN_JSON` secret so the intake cron can read
`socialmedia@tlcnj.com` and apply the Processed label. This is the step that turns the
"send email → auto pickup" automation on.

---

## 2026-07-01 — Intake now downloads image attachments

Previously `gmail_scan.py` only recorded attachment metadata (`{name, type}`) — the actual
image bytes were never fetched, so any post created from an image-bearing email was
permanently stuck flagged "NEEDS IMAGE" even though the photo was sitting right there in
the email. Fixed:

- `_save_image_attachment()` downloads the attachment via the Gmail API
  (`messages.attachments.get`), decodes it, and writes it into `images/` with a
  collision-safe name derived from the post id + a slugified original filename.
  Oversized (>8MB) or non-image attachments are skipped with a logged reason — never a
  crash, never a silent drop.
- The first successfully-downloaded image attachment becomes the post's `imageUrl`
  (resolved to an absolute GitHub Pages URL) and is passed into `generate_options()` so
  every caption option carries it too. `notes` only says "NEEDS IMAGE" when there truly
  is no image to attach.
- `config.py` now exposes `IMAGES_DIR` (repo-root-anchored, same fix as `POSTS_PATH`).
- `intake.yml` commits `images/` alongside `data/` so downloaded photos actually land in
  the repo (and on GitHub Pages) instead of staying local to the runner.
- Smoke test extended to 26 checks (filename slugging, oversized/non-image/no-attachment-id
  guards — all pure logic, no network).

---

## 2026-06-30 — Root-cause the "missing posts" + add drift guardrails

The owner reported posts missing from the live dashboard. **Root cause: silent status
drift, not data loss.** The generator wrote `status:"pending"`; the original dashboard's
New tab filtered on `"new"`. `"pending"` matched no tab, so **13 posts were invisible on
the live site** (all real, all intact in `data/posts.json`). Confirmed by counting:
8 posted, 13 pending (hidden), 2 rejected = 23 total.

Made this class of bug impossible going forward:

1. **Dashboard never hides a post.** Replaced the per-tab `includes()` filter with a single
   `tabForStatus()` that resolves every post to exactly one tab and **falls back to New for
   any unknown/legacy status** — nothing can silently disappear again. Verified: all 23
   posts map to a tab (13 New, 8 Posted, 2 Rejected).
2. **One canonical status vocabulary + normalizer.** `scripts/validate.py` defines the
   canonical statuses and legacy aliases (`pending→new`, `creating→new`, `published→posted`).
   `--fix` normalizes in place; ran it → 13 posts moved `pending→new`, data now canonical.
3. **CI fails on drift.** `.github/workflows/validate.yml` runs `validate.py` (canonical
   status, unique ids, required fields, known brand) **and** the backend smoke test on every
   push/PR. A duplicate id or unknown status now fails the build instead of hiding a post.

Also fixed a **real backend path bug** found while wiring this: scripts run with
`working-directory: scripts` in CI, so the bare relative `data/posts.json` would have
resolved to `scripts/data/posts.json` and silently loaded an empty file. `config.py` now
anchors `POSTS_PATH`/`INBOX_PATH` to the repo root regardless of cwd.

**Complete inventory at this point** (also given to the owner): TLC 7 (4 sent / 3 pending),
Surfbox 10 (2 sent / 7 pending / 1 rejected), Keli 6 (2 sent / 3 pending / 1 rejected).
Inbox fully reconciled except `inbox-001` (FW: Video) — blocked, the referenced video
attachment was never in the export.

---

## 2026-06-30 — Backend built into the repo (intake + publisher)

Built the email-intake and Facebook-publisher tier directly into this repo, running
free on GitHub Actions cron and reading/writing `data/posts.json` — the same file the
dashboard uses. New layout under `scripts/`:

```
scripts/
  config.py        env/secrets loading + require() (fails loudly, no silent no-ops)
  notify.py        logging + Telegram alerts; guard() wraps stages — no silent failures
  store.py         atomic posts.json / inbox.json read·write·dedupe
  brand.py         weighted-keyword classifier (mirrors the dashboard)
  generate.py      3 caption options via a FREE OpenAI-compatible model; refuses
                   Claude/Opus/paid GPT; deterministic template fallback
  gmail_scan.py    Gmail intake — gmail.modify scope + LobsterPress/Processed label + dedupe
  publisher.py     publishes due posts (Post Now + past-schedule) across platforms
  platforms/
    base.py        PlatformAdapter contract + PublishResult
    facebook.py    Facebook Graph API adapter (LIVE)
    instagram.py   stub — lights up when IG creds are set
    tiktok.py      stub — lights up when TikTok creds are set
    __init__.py    registry: FB/IG/TT -> adapter (add a channel in one line)
  smoke_test.py    network-free test (23 checks, all green)
.github/workflows/
  intake.yml       cron */30 — scan email, create drafts, commit data/
  publisher.yml    cron */15 — publish due posts, commit data/
requirements.txt
```

**Spec issues this closes (the backend half):**
- **Gmail read-only → gmail.modify.** `gmail_scan.py` requests the `gmail.modify`
  scope, creates the `LobsterPress/Processed` label if missing, and applies it to every
  processed message — so the `-label:` query actually excludes handled mail. Dedupe is
  double-guarded by the Gmail message id recorded on each inbox item.
- **Extensible publisher.** One adapter per channel behind a shared `PlatformAdapter`
  contract; the queue/approval logic never changes. Facebook ships now; Instagram and
  TikTok are stubs that activate the moment their credentials exist. The publisher
  iterates `post.platforms`, records `postedPlatforms`/`postedUrl`, and on a hard error
  marks the post `failed` (shown in the dashboard) **and** alerts via Telegram.
- **Free models only.** `generate.py` talks to any OpenAI-compatible free endpoint and
  **refuses** banned model ids (`claude`, `opus`, `sonnet`, `haiku`, `gpt-4`, …). With no
  endpoint configured it falls back to templates — never a silent blank draft.
- **No silent failures.** Every stage runs inside `notify.guard()`; all errors log AND
  ping Telegram.

**Verification:** `python scripts/smoke_test.py` → 23/23 pass (brand, store round-trip,
template generation, free-model guardrail, due-post detection, adapter registry, publisher
partial-success path). All modules byte-compile. Network paths (Gmail/Graph/LLM) are guarded
behind credential checks and weren't exercised here (no secrets in this sandbox).

**Secrets / vars to set in the repo (Settings → Secrets and variables → Actions):**

| Secret | Purpose |
| --- | --- |
| `GMAIL_CREDENTIALS_JSON` | Gmail OAuth client JSON |
| `GMAIL_TOKEN_JSON` | Authorized Gmail token JSON (must contain a refresh_token) |
| `LLM_API_KEY` | Free LLM provider key (Groq / OpenRouter free tier) |
| `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN` | Facebook Page publishing |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram (when ready) |
| `TIKTOK_ACCESS_TOKEN` | TikTok (when ready) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Alerting |

| Variable | Example |
| --- | --- |
| `INTAKE_SENDER` | `socialmedia@tlcnj.com` |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |

Test before going live: run the **Publisher** workflow via *Run workflow* with **dry_run = true**.

> Note on missing TLC posts (flagged 2026-06-30): the repo's full git history was searched —
> no TLC posts were ever dropped here (only a Surfbox and a Keli reject). The additional TLC
> posts the owner remembers live on the Mac mini / Google Drive, neither reachable from the
> sandboxed session (Drive needs re-authorization). Pending hand-off of those files.

---

## 2026-06-29 — Targeted rebuild

Scope note: the live repository (`roblobsterclaw/lobster-press`) is the **static dashboard +
data** half of the system — `index.html`, `data/posts.json`, `data/inbox.json`, `images/`,
and the GitHub Pages plumbing. The backend intake/publisher scripts referenced in the task
brief (`scripts/gmail-scan.py`, `scripts/publisher.py`, `processed-ids.json`,
`CODEX-SPEC.md`) are **not present in this repo snapshot**, so the issues that targeted them
were addressed at the level this repo actually exposes. See "Backend not in this repo" below.

### 1. Dashboard tabs now match the spec — New / Scheduled / Posted / Rejected
- Old tabs were Pending / Approved / Scheduled / Posted, and **Reject sent items back into
  Pending** — the `renderRejected()` function existed but was never reachable.
- Rebuilt the tab/state model around a single `TAB_STATUSES` map:
  - **New** ← statuses `new`, `pending` (legacy data used `pending`; it now renders as New)
  - **Scheduled** ← `approved`, `scheduled`, `post_now`, `failed` (the approve→schedule
    pipeline lives here; "approved" is the ready-to-schedule step)
  - **Posted** ← `posted`
  - **Rejected** ← `rejected`
- `renderByStatus()` now routes `rejected` to `renderRejected()`. Rejecting a draft moves it
  to the **Rejected** tab (not Pending) and switches the view there.
- **Rejected items never disappear.** "Regenerate" no longer mutates the rejected draft —
  it clones a fresh `*-rework-*` draft into **New** and leaves the rejected original (with
  its feedback) parked in **Rejected**. This mirrors the existing rework pattern in the data
  (e.g. `surfbox-team-001` rejected, `surfbox-team-002` reworked).
- Reject modal now captures optional free-text rework notes alongside the reason.
- Hero panel, summary cards, status line, and empty states all relabeled to the new model.

### 2. Brand classifier
- Added a weighted-keyword `classifyBrand(text)` to the dashboard. Strong, unambiguous
  signals (brand names, phone numbers, web domains, `since 1932`, `kw premier`) score far
  higher than generic shared terms (`lumber`, `portable storage`, `real estate`, `LBI`), so
  a Surfbox post can't get mis-tagged TLC just because both mention the Jersey Shore.
- Wired in two places: an **"Auto-detect brand"** button on every New draft, and as the
  brand fallback inside `generateClientOptions()` when a draft has no brand set.
- Verified against all 23 posts in `data/posts.json`: **23/23 agree with the existing
  (correct) brand tags, 0 mismatches.** Spot checks: a "surfbox dog" caption → Surfbox; a
  bare "composite deck at Tuckerton Lumber" caption → TLC.

### 3. Gmail scope (backend — not in this repo)
- The `gmail.modify` scope + `LobsterPress/Processed` label change applies to
  `scripts/gmail-scan.py`, which is not part of this repo snapshot. Documented here so the
  fix is carried forward when the backend lands. See "Backend not in this repo".

### 4. Branch
- Repo default and all dashboard GitHub calls already target **`main`** (reads use
  `?ref=main`, writes use `branch: "main"`). No stale `master` exists in this clone. Working
  branch for this rebuild: `claude/lobster-press-rebuild-ixyqec`.

### 5. Data drift fixed
- `data/posts.json` contained **two different posts sharing `id: keli-lbi-rework-002`**. The
  second was unreachable because every handler uses `posts.find(p => p.id === postId)`, which
  always returns the first match — so that draft could never be approved, rejected, or edited.
- Renamed the newer text-only rework to **`keli-lbi-rework-003`**. Both drafts are preserved.
- Re-validated: 23 posts, **0 duplicate ids**, valid JSON.

### 6. Cruft removed
- Deleted **`dashboard.html`** (99 KB stale "Command Center" version, superseded by
  `index.html`). The other files named in the brief (`posts-sample.json`, `auto-creator.py`,
  `make_it_doc.py`, a root `publisher.py` wrapper) do not exist in this repo.

### 7. Hardcoded password — noted, intentionally kept
- `PASSWORD = "soccer12"` is a client-side gate in `index.html`. Acceptable for this threat
  model: the queue holds no sensitive data and the real write-guard is the GitHub token kept
  in each browser's `localStorage` (the dashboard never stores Meta page tokens). Added an
  inline code comment so the next reader knows it's deliberate, not an oversight.

---

## Architecture — extensible publisher (Facebook now, Instagram + TikTok next)

The data model is already platform-aware: each post carries a `platforms` array
(`["FB"]`, `["FB","IG"]`, …) and `postedPlatforms` records where it actually went live.
The intended publisher shape, to be honored when the backend script is (re)added here:

- A small **platform-adapter interface** — one adapter per channel, each exposing the same
  contract: `publish(post) -> { url, platformPostId }`. Facebook (Graph API) is the first
  adapter; Instagram (Graph API, same Meta token plumbing) and TikTok (Content Posting API)
  drop in as additional adapters without touching the queue/approval logic.
- The publisher iterates `post.platforms`, dispatches to each adapter, and writes results
  back to `postedPlatforms` / `postedUrl`. A failure on one platform marks the post `failed`
  with a `failureReason` (already surfaced in the dashboard) **and** alerts — no silent
  failures.
- All AI draft generation must use **free models only** — never Claude/Opus.
- Every error must both **log and alert via Telegram**.

## Backend not in this repo

The task brief describes intake/publisher Python (`scripts/gmail-scan.py`,
`scripts/publisher.py`), `processed-ids.json`, `CLAUDE.md`, and `CODEX-SPEC.md`. None are
present in this repository snapshot — it is the dashboard/data tier only. The fixes that
depend on those files (Gmail `gmail.modify` scope + `LobsterPress/Processed` label;
publisher token checks; cron env vars) are documented above and should be applied to the
backend repo/tier when it is connected. Flag to the owner if you expected those files here.

## 2026-07-12 — Orientation fix + crossposting

- **Sideways photos fixed.** Phone cameras store the sensor frame plus an EXIF
  orientation flag instead of rotating pixels; Pillow was ignoring the flag, so
  a portrait photo (EXIF orientation 6) rendered rotated 90°. The surf-dog draft
  came out lying on its side. `render.py` and `gmail_scan.py` now call
  `ImageOps.exif_transpose` (idempotent — a no-op once an image carries no EXIF
  tag, so there is no double-rotation).
- **Crossposting.** A post can now carry `crosspostBrands` (a list of brand
  codes); the Facebook adapter posts the one approved item to each brand's Page
  and records `postedPages`, so a retry only re-hits Pages that haven't
  succeeded — never a double-post. Absent `crosspostBrands`, behavior is
  unchanged (post → its own brand's Page). The surf-dog draft is set to
  crosspost to Surfbox + Tuckerton Lumber.

## 2026-07-13 — First live posts + app UX pass

- **First automated posts went live**: surf-dog → Surfbox, and the 250th
  flag/truck → Tuckerton Lumber, both via the approve → Post Now flow.
- **Facebook Preview** button (New/Approved/Scheduled) with two modes:
  "while scrolling" (Facebook overlays page name + caption on tall images) and
  "tapped open" (clean). Catches overlay collisions before posting.
- **Headline Story** reworked: text lives top-only (FB owns the bottom of tall
  feed images); wide/landscape photos keep the whole scene (blurred backdrop +
  full photo) instead of cropping the sides.
- **Crossposting** (`crosspostBrands`) with idempotent per-Page tracking.
- **Light/dark theme toggle** (persisted) via CSS variables + `data-theme`.
- **Gallery** New-tab layout: swipe edge-to-edge designs, dot indicators,
  peek of the next design, slim action pills.
- **Clear queued/scheduled status** so Post Now is unmistakable.
- **Stale-save fix**: `savePosts` now reconciles against the live server list
  before writing — a browser tab loaded before a publish can no longer clobber
  a "posted" status (which had briefly re-queued the flag for a duplicate) or
  drop new email drafts.
- **Next**: Step 2 — talk-to-the-app reimagine (Nano Banana / OpenAI images).
