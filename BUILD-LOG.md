# Lobster Press — Build Log

Social media content pipeline for three businesses — **Tuckerton Lumber Company (TLC)**,
**Surfbox Storage**, and **Keli Lynch (KW Premier)**. Email intake → AI draft options →
Joe approves on his iPhone → publisher posts to Facebook. Designed to expand to Instagram
and TikTok next.

This log records the targeted rebuild work. It is appended to over time — newest entry on top.

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
