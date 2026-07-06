"""One-time Gmail authorization helper for Lobster Press.

Run this ONCE on a computer with a browser (your Mac mini). It opens a Google
login, you approve access to the socialmedia@tlcnj.com mailbox, and it prints a
token you paste into GitHub as the GMAIL_TOKEN_JSON secret. After that the
intake cron runs on its own — you never do this again unless access is revoked.

Prereqs:
  1. In Google Cloud Console: create a project, enable the Gmail API, and make
     an OAuth client of type "Desktop app". Download its JSON.
  2. pip install google-auth-oauthlib google-api-python-client
  3. python gmail_auth.py /path/to/that/client_secret.json

It requests the gmail.modify scope (read messages + apply the Processed label).
"""
from __future__ import annotations

import json
import sys

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python gmail_auth.py /path/to/client_secret.json", file=sys.stderr)
        return 2
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    token_json = creds.to_json()
    with open("token.json", "w", encoding="utf-8") as fh:
        fh.write(token_json)

    # Sanity: confirm it actually reads the mailbox before you trust it.
    try:
        from googleapiclient.discovery import build
        profile = build("gmail", "v1", credentials=creds).users().getProfile(userId="me").execute()
        who = profile.get("emailAddress", "?")
    except Exception as exc:
        who = f"(could not verify: {exc})"

    print("\n" + "=" * 70)
    print(f"Authorized mailbox: {who}")
    print("Saved token.json. Copy the ENTIRE line below into the GitHub secret")
    print("named GMAIL_TOKEN_JSON (Settings -> Secrets and variables -> Actions):")
    print("=" * 70)
    print(json.dumps(json.loads(token_json)))
    print("=" * 70)
    print("Also add the client_secret.json contents as the secret GMAIL_CREDENTIALS_JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
