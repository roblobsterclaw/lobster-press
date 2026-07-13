"""Production image renderer — turns one photo into 5 on-brand treatments.

This is the engine behind Step 2's "5 choices." It's deterministic (Pillow,
free, no AI image cost) and reads every brand detail — color, display name,
CTA — from brands.py so the look stays consistent across all three businesses.

Treatments (each auto-sized to its placement):
  clean_feed     1:1   photo + brand footer bar
  headline_story 9:16  big hook headline + subhead + CTA (Stories/Reels)
  quote_card     4:5   blurred photo behind a pull-quote (testimonials)
  badge_callout  1:1   angled status stamp + info chip (helps reader "get it")
  fun_casual     1:1   playful caption bar, lighter tone

Public API:
  render_treatments(src_path, brand_code, copy, out_dir, post_id) -> list[dict]
  each dict: {"treatment", "format", "path"}

`copy` supplies the words (in production, written by the vision/caption model):
  headline, subhead, cta, quote, attribution, stamp, chip_label, chip_value, fun
Missing keys fall back to brand defaults so a render never crashes on absence.
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

import brands

_FONT_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REG = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
WHITE = (255, 255, 255)
INK = (17, 19, 24)


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    for path in (_FONT_BOLD if bold else _FONT_REG):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# --- geometry helpers ---------------------------------------------------------

def _fill(src: Image.Image, w: int, h: int) -> Image.Image:
    """Resize + center-crop so the photo fills w×h without distortion."""
    src = src.convert("RGB")
    scale = max(w / src.width, h / src.height)
    resized = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))))
    left, top = (resized.width - w) // 2, (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _scrim(w: int, h: int, top_a: int, bot_a: int) -> Image.Image:
    grad = Image.new("L", (1, h))
    for y in range(h):
        grad.putpixel((0, y), int(top_a + (bot_a - top_a) * (y / max(1, h - 1))))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    overlay.putalpha(grad.resize((w, h)))
    return overlay


def _fit(draw, text, bold, max_w, start, min_size=28):
    size = start
    while size > min_size:
        f = _font(bold, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(bold, min_size)


def _wrap(draw, text, f, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw_wrapped(draw, x, y, text, f, fill, max_w, leading=None):
    """Draw wrapped text; return the y just below the block."""
    leading = leading if leading is not None else f.size + 12
    for line in _wrap(draw, text, f, max_w):
        draw.text((x, y), line, font=f, fill=fill)
        y += leading
    return y


# --- treatments (each returns a PIL RGBA image) -------------------------------

def _clean_feed(src, b, copy):
    W = H = 1080
    img = _fill(src, W, H).convert("RGBA")
    # Slimmer footer + smaller type so it sits low and doesn't crop the subject
    # (a napping dog's nose was disappearing behind the old 132px bar).
    bar = 92
    fs = 29
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, H - bar, W, H), radius=0, fill=INK + (235,))
    d.rectangle((0, H - bar, W, H - bar + 6), fill=b["color_rgb"])
    ty = H - bar + (bar - fs) // 2 + 2  # vertically centered in the slim bar
    d.text((48, ty), b["display_name"].upper(), font=_font(True, fs), fill=WHITE)
    contact = b.get("contact", "")
    if contact:
        cf = _font(True, fs)
        d.text((W - 48 - d.textlength(contact, font=cf), ty), contact, font=cf, fill=b["color_rgb"])
    return img


def _headline_story(src, b, copy):
    W, H = 1080, 1920
    img = _fill(src, W, H).convert("RGBA")
    img.alpha_composite(_scrim(W, 640, 215, 0))
    img.alpha_composite(_scrim(W, 720, 0, 235), dest=(0, H - 720))
    d = ImageDraw.Draw(img)
    d.rectangle((72, 120, 192, 132), fill=b["color_rgb"])
    hf = _fit(d, copy["headline"], True, W - 144, 150)
    y = _draw_wrapped(d, 72, 168, copy["headline"], hf, WHITE, W - 144, hf.size + 6)
    _draw_wrapped(d, 72, y + 18, copy.get("subhead", ""), _font(False, 46), (235, 238, 245), W - 144, 58)
    # CTA — now wraps/fits instead of running off the edge (the old bug)
    cta = copy.get("cta") or b["primary_cta"]
    cf = _fit(d, cta, True, W - 144, 52, min_size=34)
    cta_lines = _wrap(d, cta, cf, W - 144)
    cta_y = H - 210 - (len(cta_lines) - 1) * (cf.size + 8)
    _draw_wrapped(d, 72, cta_y, cta, cf, WHITE, W - 144, cf.size + 8)
    d.rectangle((72, H - 150, 202, H - 138), fill=b["color_rgb"])
    d.text((72, H - 120), b["display_name"].upper(), font=_font(True, 32), fill=WHITE)
    if b.get("contact"):
        d.text((72, H - 74), b["contact"], font=_font(True, 38), fill=b["color_rgb"])
    return img


def _quote_card(src, b, copy):
    W, H = 1080, 1350
    base = _fill(src, W, H).filter(ImageFilter.GaussianBlur(6)).convert("RGBA")
    base.alpha_composite(Image.new("RGBA", (W, H), (10, 12, 16, 165)))
    d = ImageDraw.Draw(base)
    d.text((80, 120), "“", font=_font(True, 240), fill=b["color_rgb"])
    quote = copy.get("quote") or copy.get("subhead", "")
    qf = _fit(d, quote.split("\n")[0], True, W - 160, 92, min_size=48)
    y = _draw_wrapped(d, 80, 430, quote, qf, WHITE, W - 160, qf.size + 18)
    d.rectangle((80, y + 22, 170, y + 32), fill=b["color_rgb"])
    attribution = copy.get("attribution") or f"— {b['display_name']}"
    d.text((80, y + 54), attribution, font=_font(True, 38), fill=(235, 238, 245))
    d.text((80, H - 90), b["display_name"].upper(), font=_font(True, 28), fill=(180, 186, 196))
    return base


def _badge_callout(src, b, copy):
    W = H = 1080
    img = _fill(src, W, H).convert("RGBA")
    d = ImageDraw.Draw(img)
    stamp = copy.get("stamp", "")
    if stamp:
        sw, sh = 620, 150
        layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        sd = ImageDraw.Draw(layer)
        sd.rounded_rectangle((6, 6, sw - 6, sh - 6), radius=14, fill=b["color_rgb"] + (235,), outline=WHITE, width=8)
        sf = _fit(sd, stamp, True, sw - 60, 92)
        sd.text(((sw - sd.textlength(stamp, font=sf)) / 2, (sh - sf.size) / 2 - 6), stamp, font=sf, fill=WHITE)
        layer = layer.rotate(-8, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(layer, dest=(70, 70))
    label, value = copy.get("chip_label", ""), copy.get("chip_value", "")
    if label or value:
        cw, ch = 540, 150
        cx, cy = 60, H - ch - 60
        d.rounded_rectangle((cx, cy, cx + cw, cy + ch), radius=20, fill=INK + (238,))
        d.rounded_rectangle((cx, cy, cx + 12, cy + ch), radius=6, fill=b["color_rgb"])
        d.text((cx + 40, cy + 30), label.upper(), font=_font(True, 30), fill=(170, 176, 188))
        vf = _fit(d, value, True, cw - 70, 52, min_size=32)
        d.text((cx + 40, cy + 70), value, font=vf, fill=WHITE)
    return img


def _fun_casual(src, b, copy):
    W = H = 1080
    img = _fill(src, W, H).convert("RGBA")
    # Shorter, lighter scrim + smaller caption sitting lower on the frame, so a
    # subject in the lower third (a dog's face) stays fully visible above it.
    img.alpha_composite(_scrim(W, 360, 0, 200), dest=(0, H - 360))
    d = ImageDraw.Draw(img)
    line = copy.get("fun") or copy.get("headline", "")
    f = _fit(d, line.split("\n")[0], True, W - 120, 56, min_size=34)
    lines = _wrap(d, line, f, W - 120)
    y = H - 38 - len(lines) * (f.size + 12)
    for ln in lines:
        d.text((60, y), ln, font=f, fill=WHITE)
        y += f.size + 12
    d.rectangle((60, H - 28, 196, H - 20), fill=b["color_rgb"])
    return img


TREATMENTS = [
    ("clean_feed", "1:1", _clean_feed),
    ("headline_story", "9:16", _headline_story),
    ("quote_card", "4:5", _quote_card),
    ("badge_callout", "1:1", _badge_callout),
    ("fun_casual", "1:1", _fun_casual),
]


def render_treatments(src_path: str, brand_code: str, copy: dict,
                      out_dir: str, post_id: str) -> list[dict]:
    """Render all 5 treatments for one photo. Returns metadata per output."""
    b = brands.get(brand_code)
    src = Image.open(src_path)
    src = ImageOps.exif_transpose(src)  # respect phone-photo orientation (no more sideways)
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for name, fmt, fn in TREATMENTS:
        img = fn(src, b, copy)
        path = os.path.join(out_dir, f"{post_id}_{name}.jpg")
        img.convert("RGB").save(path, quality=92)
        results.append({"treatment": name, "format": fmt, "path": path})
    return results
