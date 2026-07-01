"""Network-free smoke test for the Lobster Press backend.

Exercises the pure logic that doesn't need Gmail/Meta/LLM credentials:
brand classification, the posts.json store round-trip, template generation,
the free-model guardrail, due-post detection, and the adapter registry.

Run: python scripts/smoke_test.py
"""
from __future__ import annotations

import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import brand          # noqa: E402
import config         # noqa: E402
import generate       # noqa: E402
import gmail_scan     # noqa: E402
import publisher      # noqa: E402
import store          # noqa: E402
from platforms import all_adapters, get_adapter  # noqa: E402

failures = []


def check(name: str, cond: bool) -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        failures.append(name)


# 1. Brand classifier
check("brand: surfbox dog -> Surfbox",
      brand.classify("surfbox dog on a portable storage container") == "Surfbox")
check("brand: tuckerton lumber -> TLC",
      brand.classify("composite deck at Tuckerton Lumber since 1932") == "TLC")
check("brand: keli -> Keli", brand.classify("Keli Lynch KW Premier under contract") == "Keli")
check("brand: empty -> default", brand.classify("", default="TLC") == "TLC")

# 2. Store round-trip (atomic write to a temp file)
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "posts.json")
    store.save_posts({"posts": [{"id": "x1", "status": "new"}]}, path)
    loaded = store.load_posts(path)
    check("store: round-trip preserves post", loaded["posts"][0]["id"] == "x1")
    check("store: writes meta.lastUpdated", bool(loaded["meta"]["lastUpdated"]))

# 3. Template generation (no LLM env configured -> fallback path)
opts = generate.generate_options("Surfbox", "Spring cleaning", "garage declutter season")
check("generate: returns 3 options", len(opts) == 3)
check("generate: options carry hashtags", all(o.get("hashtags") for o in opts))
check("generate: optionIds A/B/C", [o["optionId"] for o in opts] == ["A", "B", "C"])

# 4. Free-model guardrail
banned = False
try:
    generate.assert_free_model("claude-opus-4-8")
except config.ConfigError:
    banned = True
check("generate: refuses banned (Claude/Opus) model", banned)
generate.assert_free_model("llama-3.3-70b-versatile")  # should not raise
check("generate: allows free model", True)

# 5. Due-post detection
now = datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc)
check("publisher: post_now is due",
      publisher.is_due({"status": "post_now"}, now))
check("publisher: past schedule is due",
      publisher.is_due({"status": "scheduled", "scheduledAt": "2026-06-01T10:00:00Z"}, now))
check("publisher: future schedule not due",
      not publisher.is_due({"status": "scheduled", "scheduledAt": "2026-12-01T10:00:00Z"}, now))
check("publisher: new is not due", not publisher.is_due({"status": "new"}, now))

# 6. Adapter registry
check("registry: FB resolves to Facebook", get_adapter("FB").name == "Facebook")
check("registry: IG resolves to Instagram", get_adapter("IG").name == "Instagram")
check("registry: TT resolves to TikTok", get_adapter("TT").name == "TikTok")
check("registry: legacy 'Facebook' name resolves", get_adapter("Facebook").code == "FB")
check("registry: unknown code -> None", get_adapter("XX") is None)
check("registry: nothing configured without env",
      all(not a.is_configured() for a in all_adapters()))

# 7. Gmail intake attachment handling (pure logic, no network)
check("gmail_scan: safe_slug strips punctuation",
      gmail_scan._safe_slug("IMG 2150 (final)!!.mov") == "img-2150-final-mov")
check("gmail_scan: safe_slug never empty", gmail_scan._safe_slug("...") == "attachment")
check("gmail_scan: attachment without attachmentId -> no image",
      gmail_scan._save_image_attachment(
          service=None, msg_id="m1",
          att={"type": "image", "name": "x.jpg", "attachmentId": None},
          post_id="p1",
      ) is None)
check("gmail_scan: oversized attachment -> no image",
      gmail_scan._save_image_attachment(
          service=None, msg_id="m1",
          att={"type": "image", "name": "x.jpg", "attachmentId": "a1",
               "size": gmail_scan.MAX_IMAGE_BYTES + 1},
          post_id="p1",
      ) is None)
check("gmail_scan: non-image attachment -> no image",
      gmail_scan._save_image_attachment(
          service=None, msg_id="m1",
          att={"type": "video", "name": "x.mov", "attachmentId": "a1"},
          post_id="p1",
      ) is None)

# 8. Publisher dry-run path marks no live platform when FB unconfigured
ok, live, errors = publisher.publish_post({"id": "t", "platforms": ["FB"], "caption": "hi"})
check("publisher: unconfigured FB -> no success, no hard error",
      (not ok) and (not errors))

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("All smoke checks passed.")
