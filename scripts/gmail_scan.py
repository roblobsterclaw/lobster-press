"""Email intake from socialmedia@tlcnj.com into the draft queue.

Uses the Gmail API with the **gmail.modify** scope so it can APPLY the
`LobsterPress/Processed` label after handling a message — that label is what
keeps the `-label:` query from re-processing the same email (the read-only
scope could never do this, which was the original bug). Dedupe is also enforced
locally by the Gmail message id recorded on each inbox item.

For every new message: record an inbox item, classify the brand, generate 3
caption options (free model), create a `new` draft post, then label the email.

Credentials come from secrets:
  GMAIL_CREDENTIALS_JSON  OAuth client (installed-app) JSON
  GMAIL_TOKEN_JSON        authorized token JSON containing a refresh_token
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time

import config
import generate
import notify
import store

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # Graph API photo upload practical ceiling


def _service():
    """Build an authorized Gmail API client from the env-provided token.

    We intentionally do NOT force a scope here. Forcing gmail.modify onto a
    token that was granted a different scope makes the refresh fail with
    'invalid_scope'. Instead we honor whatever scope the token already carries;
    applying the Processed label is attempted best-effort (see _ensure_label /
    scan), and dedupe always works via the recorded Gmail message id.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    config.require("GMAIL_TOKEN_JSON")
    info = json.loads(config.GMAIL_TOKEN_JSON)
    creds = Credentials.from_authorized_user_info(info)
    if not creds.valid:
        if not creds.refresh_token:
            raise config.ConfigError(
                "Gmail token has no refresh_token — re-run scripts/gmail_auth.py."
            )
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _ensure_label(service) -> str | None:
    """Return the id of the processed label, creating it if needed. Returns
    None (best-effort) if the token can't create/read labels — dedupe still
    works via the recorded message id."""
    try:
        existing = service.users().labels().list(userId="me").execute().get("labels", [])
        for lab in existing:
            if lab["name"] == config.GMAIL_LABEL:
                return lab["id"]
        created = service.users().labels().create(
            userId="me",
            body={"name": config.GMAIL_LABEL,
                  "labelListVisibility": "labelShow",
                  "messageListVisibility": "show"},
        ).execute()
        return created["id"]
    except Exception as exc:
        notify.log.warning(
            "Could not ensure label '%s' (token may lack gmail.modify); "
            "relying on message-id dedupe instead: %s", config.GMAIL_LABEL, exc)
        return None


def _header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _plain_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        text = _plain_body(part)
        if text:
            return text
    return ""


def _attachments(payload: dict) -> list[dict]:
    """Walk MIME parts, returning attachment metadata including the Gmail
    attachmentId needed to fetch the actual bytes."""
    out = []
    for part in payload.get("parts", []) or []:
        fname = part.get("filename")
        if fname:
            mime = part.get("mimeType", "")
            kind = "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "file"
            out.append({
                "name": fname,
                "type": kind,
                "mimeType": mime,
                "size": part.get("body", {}).get("size", 0),
                "attachmentId": part.get("body", {}).get("attachmentId"),
            })
        out.extend(_attachments(part))
    return out


def _safe_slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug or "attachment")[:max_len]


def _save_image_attachment(service, msg_id: str, att: dict, post_id: str) -> str | None:
    """Download an image attachment and save it under images/. Returns the
    repo-relative path (e.g. 'images/intake-abc123-0.jpg') or None on any
    problem — callers must treat None as 'no image', never raise."""
    if att["type"] != "image" or not att.get("attachmentId"):
        return None
    if att.get("size") and att["size"] > MAX_IMAGE_BYTES:
        notify.log.warning("Skipping oversized attachment %s (%s bytes)", att["name"], att["size"])
        return None
    try:
        blob = service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=att["attachmentId"],
        ).execute()
        raw = base64.urlsafe_b64decode(blob["data"])
    except Exception as exc:
        notify.log.error("Failed to download attachment %s: %s", att["name"], exc)
        return None

    ext = os.path.splitext(att["name"])[1] or mimetypes.guess_extension(att.get("mimeType", "")) or ".jpg"
    filename = f"{post_id}-{_safe_slug(os.path.splitext(att['name'])[0])}{ext}"
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    dest = os.path.join(config.IMAGES_DIR, filename)
    try:
        # Auto-orient via EXIF so phone photos aren't stored sideways. Fall back
        # to the raw bytes if it isn't a Pillow-decodable image.
        try:
            import io

            from PIL import Image, ImageOps

            ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB").save(dest, quality=92)
        except Exception:
            with open(dest, "wb") as fh:
                fh.write(raw)
    except OSError as exc:
        notify.log.error("Failed to write attachment %s: %s", filename, exc)
        return None
    return f"images/{filename}"


_TREATMENT_LABELS = {
    "clean_feed": "Clean Feed", "headline_story": "Headline Story",
    "quote_card": "Quote Card", "badge_callout": "Badge / Callout",
    "fun_casual": "Fun / Casual",
}
_OPTION_IDS = ["A", "B", "C", "D", "E"]


def _build_options(brand: str, post_id: str, subject: str, body: str,
                   image_local: str | None, image_url: str | None) -> list[dict]:
    """Build the draft's option list. With a photo, generate on-brand copy
    (vision model → caption + overlay strings) and render the 5 treatments so
    the New tab shows the swipe carousel. Without a photo, fall back to
    text-only caption options."""
    if image_local and os.path.exists(image_local):
        copy = generate.generate_treatment_copy(brand, subject, body, image_local)
        try:
            import render  # lazy: keeps the pure-stdlib smoke test dependency-free

            results = render.render_treatments(image_local, brand, copy, config.IMAGES_DIR, post_id)
            base = config.PAGES_BASE_URL.rstrip("/")
            options = []
            for i, r in enumerate(results):
                fname = os.path.basename(r["path"])
                options.append({
                    "optionId": _OPTION_IDS[i % 5],
                    "treatment": r["treatment"],
                    "tone": _TREATMENT_LABELS.get(r["treatment"], r["treatment"]),
                    "format": r["format"],
                    "caption": copy["caption"],
                    "imageUrl": f"{base}/images/{fname}",
                    "hashtags": [],
                    "platform": "Facebook",
                })
            return options
        except Exception as exc:
            notify.log.error("Treatment render failed for %s; using text options: %s", post_id, exc)

    return generate.generate_options(brand, subject, body, image_url=image_url)


def scan() -> int:
    """Process new intake emails. Returns the number of drafts created."""
    with notify.guard("gmail-intake"):
        service = _service()
        label_id = _ensure_label(service)

        query = f'from:{config.INTAKE_SENDER}'
        if label_id:
            query += f' -label:"{config.GMAIL_LABEL}"'
        listing = service.users().messages().list(userId="me", q=query, maxResults=25).execute()
        messages = listing.get("messages", [])
        if not messages:
            notify.log.info("No new intake emails.")
            return 0

        posts_data = store.load_posts()
        inbox_data = store.load_inbox()
        seen_msg_ids = {it.get("gmailMessageId") for it in inbox_data["items"]}

        created = 0
        for ref in messages:
            msg_id = ref["id"]
            if msg_id in seen_msg_ids:
                continue
            msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = msg.get("payload", {})
            subject = _header(payload, "Subject")
            body = _plain_body(payload).strip()
            atts = _attachments(payload)
            received = _epoch_iso(msg.get("internalDate"))

            brand = generate.classify_email(subject, body)
            post_id = f"intake-{msg_id[:12]}"

            # Download the first image attachment (if any) and commit it into
            # images/ so the post has a real, publicly reachable imageUrl
            # instead of getting stuck flagged "NEEDS IMAGE" forever.
            image_path = None
            for att in atts:
                image_path = _save_image_attachment(service, msg_id, att, post_id)
                if image_path:
                    break
            image_url = f"{config.PAGES_BASE_URL.rstrip('/')}/{image_path}" if image_path else None
            image_local = os.path.join(config.REPO_ROOT, image_path) if image_path else None

            options = _build_options(brand, post_id, subject, body, image_local, image_url)

            posts_data["posts"].insert(0, {
                "id": post_id,
                "status": "new",
                "brand": brand,
                "caption": options[0]["caption"] if options else "",
                "options": options,
                "platforms": ["FB"],
                "imageUrl": image_url,
                "media": atts,
                "emailSubject": subject,
                "emailBody": body,
                "emailReceivedAt": received,
                "processedAt": store.now_iso(),
                "createdAt": store.now_iso(),
                "updatedAt": store.now_iso(),
                "source": f"Gmail intake — {subject}",
                "notes": "" if image_url else (
                    "NEEDS IMAGE — no image attachment found; attach media before posting."
                    if atts else "NEEDS IMAGE — attach media before posting."
                ),
            })
            inbox_data["items"].insert(0, {
                "id": f"gmail-{msg_id[:12]}",
                "gmailMessageId": msg_id,
                "receivedAt": received,
                "subject": subject,
                "sender": config.INTAKE_SENDER,
                "status": "used",
                "attachments": atts,
                "emailBody": body,
                "usedInPost": post_id,
            })

            # Apply the processed label so this email is never re-ingested.
            # Best-effort: if the token lacks gmail.modify, dedupe still works
            # via seen_msg_ids (the recorded Gmail message id).
            if label_id:
                try:
                    service.users().messages().modify(
                        userId="me", id=msg_id, body={"addLabelIds": [label_id]},
                    ).execute()
                except Exception as exc:
                    notify.log.warning("Could not label message %s: %s", msg_id, exc)
            seen_msg_ids.add(msg_id)
            created += 1
            time.sleep(0.1)  # be gentle on the API

        # Only write (and thus commit) when something actually changed —
        # otherwise every cron run would commit a no-op meta.lastUpdated bump.
        if created:
            store.save_posts(posts_data)
            store.save_inbox(inbox_data)
            notify.notify(f"Intake created {created} new draft(s).")
        return created


def _epoch_iso(internal_date: str | None) -> str:
    if not internal_date:
        return store.now_iso()
    import datetime
    secs = int(internal_date) / 1000
    return datetime.datetime.fromtimestamp(secs, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(0 if scan() >= 0 else 1)
