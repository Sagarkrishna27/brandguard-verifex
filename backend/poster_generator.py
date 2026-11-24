
"""
BrandGuard Poster Generator
Professional offline poster composition using Pillow.
No AI APIs, no external services, no invented advertising claims.
"""

import os
import io
import base64
import math

from PIL import Image, ImageDraw, ImageFont, ImageFilter


STYLE_THEMES = {
    "bold_splash": {
        "accent": (255, 193, 7),
        "text": (255, 255, 255),
        "panel": (255, 255, 255, 28),
    },
    "clean_minimal": {
        "accent": (255, 193, 7),
        "text": (255, 255, 255),
        "panel": (255, 255, 255, 24),
    },
    "festive_warm": {
        "accent": (255, 183, 77),
        "text": (255, 248, 225),
        "panel": (255, 255, 255, 25),
    },
    "corporate_trust": {
        "accent": (144, 202, 249),
        "text": (255, 255, 255),
        "panel": (255, 255, 255, 25),
    },
    "eco_natural": {
        "accent": (129, 199, 132),
        "text": (255, 255, 255),
        "panel": (255, 255, 255, 25),
    },
}

SIZES = {
    "square": (1080, 1080),
    "story": (1080, 1920),
    "poster": (1080, 1527),
    "banner": (1200, 628),
}

COLOUR_THEMES = {
    "navy": [(29, 63, 158), (10, 20, 55)],
    "crimson": [(155, 27, 48), (45, 8, 20)],
    "teal": [(15, 107, 79), (3, 38, 34)],
    "royal": [(63, 81, 181), (20, 24, 85)],
    "sunset": [(194, 84, 24), (65, 20, 12)],
    "charcoal": [(43, 47, 74), (10, 12, 23)],
}


def parse_prompt(prompt):
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
    size = max(12, int(size))

    candidates = [
        r"C:\Windows\Fonts\montserrat-bold.ttf" if bold
        else r"C:\Windows\Fonts\montserrat-regular.ttf",

        r"C:\Windows\Fonts\segoeuib.ttf" if bold
        else r"C:\Windows\Fonts\segoeui.ttf",

        r"C:\Windows\Fonts\arialbd.ttf" if bold
        else r"C:\Windows\Fonts\arial.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue

    return ImageFont.load_default()


def make_gradient(width, height, top, bottom):
    """Creates a smooth gradient efficiently."""
    strip = Image.new("RGB", (1, height))
    pixels = []

    for y in range(height):
        blend = y / max(1, height - 1)
        colour = tuple(
            int(top[i] + (bottom[i] - top[i]) * blend)
            for i in range(3)
        )
        pixels.append(colour)

    strip.putdata(pixels)
    return strip.resize((width, height), Image.Resampling.BICUBIC)


def wrap_text(draw, text, font, max_width):
    """Wraps text without changing its wording."""
    words = str(text).split()
    if not words:
        return []

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
    return lines


def draw_text_block(
    draw, text, x, y, max_width, font, fill,
    spacing=1.2, max_lines=None
):
    lines = wrap_text(draw, text, font, max_width)

    if max_lines:
        lines = lines[:max_lines]

    line_height = int(font.size * spacing)

    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height

    return y


def fit_font(draw, text, max_width, starting_size, minimum_size=20,
             bold=True):
    """Reduces font size until the longest line fits."""
    size = starting_size

    while size > minimum_size:
        font = get_font(size, bold)
        lines = wrap_text(draw, text, font, max_width)

        if all(draw.textlength(line, font=font) <= max_width
               for line in lines):
            return font

        size -= 2

    return get_font(minimum_size, bold)


def draw_background(width, height, top, bottom, accent, style):
    poster = make_gradient(width, height, top, bottom).convert("RGBA")

    # Soft glowing accent area
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    glow_draw.ellipse(
        (-width * 0.25, -height * 0.20,
         width * 0.85, height * 0.48),
        fill=accent + (48,)
    )

    glow = glow.filter(ImageFilter.GaussianBlur(max(20, width // 18)))
    poster = Image.alpha_composite(poster, glow)

    # Decorative geometric elements
    shapes = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shapes)

    sd.ellipse(
        (width * 0.68, height * 0.10,
         width * 1.12, height * 0.42),
        outline=accent + (100,),
        width=max(2, width // 180)
    )

    sd.ellipse(
        (width * 0.76, height * 0.16,
         width * 1.04, height * 0.36),
        outline=accent + (65,),
        width=max(2, width // 250)
    )

    sd.polygon(
        [
            (width * 0.78, height),
            (width, height * 0.78),
            (width, height),
        ],
        fill=accent + (24,)
    )

    poster = Image.alpha_composite(poster, shapes)

    return poster.convert("RGB")


def draw_brand(draw, brand, x, y, font, accent):
    draw.text((x, y), brand.upper(), font=font, fill=accent)

    text_width = draw.textlength(brand.upper(), font=font)

    draw.rounded_rectangle(
        (x, y + font.size + 9,
         x + min(text_width, 150), y + font.size + 14),
        radius=3,
        fill=accent
    )


def compose_poster(brief):
    brand = (brief.get("brand_name") or "Your Brand").strip()
    headline = (brief.get("headline") or "").strip()
    description = (brief.get("description") or "").strip()
    offer = (brief.get("offer") or "").strip()
    cta = (brief.get("cta") or "Learn More").strip()
    disclaimer = (brief.get("disclaimer") or "").strip()

    style_key, size_key, theme_key = parse_prompt(
        (brief.get("prompt", "") or "") + " " +
        (brief.get("style", "") or "")
    )

    if brief.get("style") in STYLE_THEMES:
        style_key = brief["style"]

    if brief.get("size") in SIZES:
        size_key = brief["size"]

    if brief.get("colour_theme") in COLOUR_THEMES:
        theme_key = brief["colour_theme"]

    style = STYLE_THEMES[style_key]
    top_colour, bottom_colour = COLOUR_THEMES[theme_key]

    width, height = SIZES[size_key]
    accent = style["accent"]
    text_colour = style["text"]

    poster = draw_background(
        width, height, top_colour, bottom_colour, accent, style_key
    )

    draw = ImageDraw.Draw(poster)

    margin = int(width * 0.085)
    content_width = width - margin * 2

    # Layout adapts to the selected format.
    if size_key == "banner":
        brand_y = int(height * 0.13)
        headline_y = int(height * 0.30)
        content_width = int(width * 0.62)
    elif size_key == "story":
        brand_y = int(height * 0.09)
        headline_y = int(height * 0.24)
    else:
        brand_y = int(height * 0.09)
        headline_y = int(height * 0.25)

    # Brand identity
    brand_font = get_font(width * 0.038, bold=True)
    draw_brand(draw, brand, margin, brand_y, brand_font, accent)

    # Headline
    y = headline_y

    if headline:
        headline_font = fit_font(
            draw, headline, content_width,
            int(width * 0.085), int(width * 0.038)
        )

        y = draw_text_block(
            draw, headline, margin, y, content_width,
            headline_font, text_colour, spacing=1.12
        )

    # Description
    if description:
        y += int(height * 0.025)

        desc_font = get_font(width * 0.030)

        y = draw_text_block(
            draw, description, margin, y, content_width,
            desc_font, text_colour, spacing=1.35
        )

    # Offer card
    if offer:
        y += int(height * 0.045)

        offer_font = fit_font(
            draw, offer, content_width - margin * 0.35,
            int(width * 0.045), int(width * 0.025)
        )

        offer_lines = wrap_text(
            draw, offer, offer_font, content_width - margin * 0.35
        )

        line_height = int(offer_font.size * 1.3)
        padding = int(width * 0.035)
        panel_height = len(offer_lines) * line_height + padding * 2

        # Rounded card with subtle shadow
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)

        shadow_draw.rounded_rectangle(
            (margin + 5, y + 7,
             margin + content_width + 5, y + panel_height + 7),
            radius=22,
            fill=(0, 0, 0, 65)
        )

        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        poster = Image.alpha_composite(
            poster.convert("RGBA"), shadow
        ).convert("RGB")

        draw = ImageDraw.Draw(poster)

        draw.rounded_rectangle(
            (margin, y, margin + content_width, y + panel_height),
            radius=22,
            fill=accent
        )

        text_y = y + padding

        for line in offer_lines:
            draw.text(
                (margin + padding, text_y),
                line,
                font=offer_font,
                fill=(255, 255, 255)
            )
            text_y += line_height

        y += panel_height

    # CTA button
    if cta:
        y += int(height * 0.045)

        cta_font = fit_font(
            draw, cta, content_width - 50,
            int(width * 0.034), int(width * 0.022)
        )

        padding_x = int(width * 0.045)
        padding_y = int(width * 0.023)

        button_width = int(draw.textlength(cta, font=cta_font)) + padding_x * 2
        button_height = cta_font.size + padding_y * 2

        button_width = min(button_width, content_width)

        draw.rounded_rectangle(
            (margin, y, margin + button_width, y + button_height),
            radius=button_height // 2,
            fill=(255, 255, 255)
        )

        draw.text(
            (margin + padding_x, y + padding_y),
            cta,
            font=cta_font,
            fill=bottom_colour
        )

    # Footer divider and disclaimer
    footer_y = int(height * 0.89)

    draw.line(
        (margin, footer_y, width - margin, footer_y),
        fill=accent + (180,),
        width=2
    )

    if disclaimer:
        disc_font = get_font(width * 0.019)

        draw_text_block(
            draw,
            disclaimer,
            margin,
            footer_y + int(height * 0.018),
            content_width,
            disc_font,
            text_colour,
            spacing=1.3,
            max_lines=3
        )

    # Export
    buffer = io.BytesIO()
    poster.save(buffer, format="PNG", optimize=True)

    png_base64 = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return {
        "image_base64": png_base64,
        "width": width,
        "height": height,
        "applied_style": style_key,
        "applied_size": size_key,
        "applied_colour_theme": theme_key,
    }


def generate_poster(brief):
    """Offline poster generator. No AI service is called."""

    result = compose_poster(brief)

    result["ai_enrichment_used"] = False
    result["generator"] = (
        "BrandGuard Professional Offline Poster Engine (Pillow)"
    )

    result["disclaimer"] = (
        "The generator preserves your supplied wording. It does not "
        "invent awards, certifications, prices, discounts, testimonials "
        "or government approvals. Human approval is required before "
        "publishing."
    )

    return result
