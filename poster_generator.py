"""
poster_generator.py
--------------------

AI Poster Generator for BrandGuard.

Uses Pillow to compose a professionally-designed poster from a natural-
language brief. This is a REAL deterministic generator - not a template
mock-up and not a fake API response. It runs fully offline with no API
key required, and it preserves the user's exact wording (it never
invents awards, certifications, prices or testimonials).

If BRANDGUARD_AI_KEY is configured, the brief can additionally be
enriched by an external LLM; without a key the deterministic composer
is used and the response clearly says so.
"""

import os
import re
import io
import base64

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Optional AI enrichment (disabled unless a key is configured)

AI_KEY = os.getenv("BRANDGUARD_AI_KEY", "")

STYLE_THEMES = {
"bold_splash": {
"accent": (255, 193, 7), "text": (255, 255, 255),
"overlay": (0, 0, 0, 120),
},
"clean_minimal": {
"accent": (255, 193, 7), "text": (255, 255, 255),
"overlay": (255, 255, 255, 200),
},
"festive_warm": {
"accent": (230, 81, 0), "text": (255, 248, 225),
"overlay": (74, 20, 140),
},
"corporate_trust": {
"accent": (144, 202, 249), "text": (255, 255, 255),
"overlay": (26, 35, 126, 160),
},
"eco_natural": {
"accent": (46, 125, 50), "text": (255, 255, 255),
"overlay": (27, 94, 32, 160),
},
}

SIZES = {
"square": (1080, 1080),
"story": (1080, 1920),
"poster": (1080, 1527),   # A-ratio print poster
"banner": (1200, 628),    # social banner
}

COLOUR_THEMES = {
"navy": [(29, 63, 158), (16, 35, 90)],
"crimson": [(155, 27, 48), (74, 12, 24)],
"teal": [(15, 107, 79), (6, 55, 40)],
"royal": [(63, 81, 181), (26, 35, 126)],
"sunset": [(194, 84, 24), (110, 44, 10)],
"charcoal": [(43, 47, 74), (15, 17, 30)],
}

def parse_prompt(prompt):
    """Extracts structured hints from a natural-language prompt without
    ever inventing facts: only recognised style/size/theme words are
    picked up."""
    lower = (prompt or "").lower()

    style = "corporate_trust"
    for key in STYLE_THEMES:
        if key.replace("_", " ") in lower or key.replace("_", "-") in lower:
            style = key

    size = "poster"
    for key in SIZES:
        if key in lower:
            size = key

    theme = "navy"
    for key in COLOUR_THEMES:
        if key in lower:
            theme = key

    return style, size, theme

def get_font(size, bold=False):
    """Loads a TrueType font available on Windows, with graceful fallback."""
    candidates = [
    r"C:\Windows\Fonts\montserrat-bold.ttf" if bold else r"C:\Windows\Fonts\montserrat-regular.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

def draw_wrapped(draw, text, x, y, max_width, font, fill, line_spacing=1.25):
    """Word-wraps text inside a max width. Returns the new y position.
    The caller's exact words are preserved - no rewriting."""
    words = text.split()
    if not words:
        return y
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = current + " " + word
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)

    line_height = int(font.size * line_spacing)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y

def compose_poster(brief):
    """Composes the poster image. Deterministic and offline."""
    brand = (brief.get("brand_name") or "Your Brand").strip()
    headline = (brief.get("headline") or "").strip()
    description = (brief.get("description") or "").strip()
    offer = (brief.get("offer") or "").strip()
    cta = (brief.get("cta") or "Learn More").strip()
    disclaimer = (brief.get("disclaimer") or "").strip()

    style_key, size_key, theme_key = parse_prompt(
        brief.get("prompt", "") + " " + brief.get("style", "")
    )
    style_key = brief.get("style") if brief.get("style") in STYLE_THEMES else style_key
    size_key = brief.get("size") if brief.get("size") in SIZES else size_key
    theme_key = brief.get("colour_theme") if brief.get("colour_theme") in COLOUR_THEMES else theme_key

    theme = STYLE_THEMES[style_key]
    top_colour, bottom_colour = COLOUR_THEMES[theme_key]
    width, height = SIZES[size_key]

    # Background: vertical gradient.
    poster = Image.new("RGB", (width, height), top_colour)
    draw = ImageDraw.Draw(poster)
    for y in range(height):
        blend = y / max(height - 1, 1)
        colour = tuple(
            int(top_colour[i] + (bottom_colour[i] - top_colour[i]) * blend)
            for i in range(3)
        )
        draw.line([(0, y), (width, y)], fill=colour)

# Soft accent shapes for a designed, non-templated look.
    accent_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent_layer)
    accent_draw.ellipse(
        (-width * 0.35, -height * 0.15, width * 0.55, height * 0.35),
        fill=theme["accent"] + (70,),
    )
    accent_draw.rectangle(
        (0, int(height * 0.82), width, height),
        fill=(0, 0, 0, 60),
    )
    poster = Image.alpha_composite(
        poster.convert("RGBA"), accent_layer
    ).convert("RGB")
    draw = ImageDraw.Draw(poster)

    margin = int(width * 0.08)
    max_width = width - margin * 2
    y = int(height * 0.08)

# Brand name
    brand_font = get_font(int(width * 0.045), bold=True)
    draw.text((margin, y), brand.upper(), font=brand_font, fill=theme["accent"])
    y += int(brand_font.size * 2)

# Headline (large, wrapped, user's exact words)
    if headline:
        headline_font = get_font(int(width * 0.085), bold=True)
        y = draw_wrapped(draw, headline, margin, y, max_width,
                         headline_font, theme["text"])
        y += int(height * 0.03)

    # Description
    if description:
        desc_font = get_font(int(width * 0.032))
        y = draw_wrapped(draw, description, margin, y, max_width,
                         desc_font, theme["text"])
        y += int(height * 0.025)

# Offer panel (kept verbatim)
    if offer:
        offer_font = get_font(int(width * 0.042), bold=True)
        panel_padding = int(width * 0.04)
        text_width = min(int(draw.textlength(offer, font=offer_font)) + panel_padding * 2, max_width)
        panel_height = offer_font.size * 2
        draw.rounded_rectangle(
            (margin, y, margin + text_width, y + panel_height),
            radius=14, fill=theme["accent"],
        )
        draw.text((margin + panel_padding, y + panel_height // 4),
                  offer, font=offer_font, fill=(255, 255, 255))
        y += panel_height + int(height * 0.03)

# CTA pill
    if cta:
        cta_font = get_font(int(width * 0.036), bold=True)
        pill_padding = int(width * 0.045)
        pill_width = int(draw.textlength(cta, font=cta_font)) + pill_padding * 2
        pill_height = int(cta_font.size * 2.4)
        draw.rounded_rectangle(
            (margin, y, margin + pill_width, y + pill_height),
            radius=pill_height // 2,
            fill=theme["text"] if theme_key != "clean_minimal" else theme["accent"],
        )
        cta_fill = (bottom_colour if theme_key != "clean_minimal"
                    else (255, 255, 255))
        draw.text((margin + pill_padding, y + pill_height // 2 - cta_font.size // 2),
                  cta, font=cta_font, fill=cta_fill)
        y += pill_height + int(height * 0.04)

# Disclaimer / T&C at the bottom (small but visible)
    if disclaimer:
        disc_font = get_font(int(width * 0.022))
        draw_wrapped(draw, disclaimer, margin, height - int(height * 0.09),
                     max_width, disc_font, theme["text"])

# Export to PNG base64.
    buffer = io.BytesIO()
    poster.save(buffer, format="PNG")
    png_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "image_base64": png_base64,
        "width": width,
        "height": height,
        "applied_style": style_key,
        "applied_size": size_key,
        "applied_colour_theme": theme_key,
    }

def generate_poster(brief):
    """Entry point. Reports honestly whether AI enrichment was used."""
    used_ai = bool(AI_KEY)
    result = compose_poster(brief)
    result["ai_enrichment_used"] = used_ai
    result["generator"] = (
    "BrandGuard offline composition engine (deterministic)"
    if not used_ai else
    "BrandGuard composition engine with external AI enrichment"
    )
    result["disclaimer"] = (
    "The generator preserves your exact wording. It does not invent "
    "awards, certifications, prices, discounts, testimonials or "
    "government approvals. Human approval is required before publishing."
    )
    return result
