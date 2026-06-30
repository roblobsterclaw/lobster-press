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
import time

import config
import generate
import notify
import store


def _service():
    """Build an authorized Gmail API client from the env-provided token."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    config.require("GMAIL_TOKEN_JSON")
    info = json.loads(config.GMAIL_TOKEN_JSON)
    creds = Credentials.from_authorized_user_info(info, config.GMAIL_SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _ensure_label(service) -> str:
    """Return the id of the processed label, creating it if needed."""
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
    out = []
    for part in payload.get("parts", []) or []:
        fname = part.get("filename")
        if fname:
            mime = part.get("mimeType", "")
            kind = "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "file"
            out.append({"name": fname, "type": kind})
        out.extend(_attachments(part))
    return out


def scan() -> int:
    """Process new intake emails. Returns the number of drafts created."""
    with notify.guard("gmail-intake"):
        service = _service()
        label_id = _ensure_label(service)

        query = f'from:{config.INTAKE_SENDER} -label:"{config.GMAIL_LABEL}"'
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

            brand = generate.classify_brand(" ".join([subject, body]))
            options = generate.generate_options(brand, subject, body)
            post_id = f"intake-{msg_id[:12]}"

            posts_data["posts"].insert(0, {
                "id": post_id,
                "status": "new",
                "brand": brand,
                "caption": options[0]["caption"] if options else "",
                "options": options,
                "platforms": ["FB"],
                "imageUrl": None,
                "media": atts,
                "emailSubject": subject,
                "emailBody": body,
                "emailReceivedAt": received,
                "processedAt": store.now_iso(),
                "createdAt": store.now_iso(),
                "updatedAt": store.now_iso(),
                "source": f"Gmail intake — {subject}",
                "notes": "NEEDS IMAGE — attach media before posting." if not atts else "",
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
            service.users().messages().modify(
                userId="me", id=msg_id, body={"addLabelIds": [label_id]},
            ).execute()
            seen_msg_ids.add(msg_id)
            created += 1
            time.sleep(0.1)  # be gentle on the API

        store.save_posts(posts_data)
        store.save_inbox(inbox_data)
        if created:
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
