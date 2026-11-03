"""Brand tokens (from docs/design.md) and the Jinja environment used by every template.

Colours, fonts and the icon/emoji filters live here so cards, video frames and mocks always match the app.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .icons import icon_svg

COLORS = {  # "refined red": a deep brand red used sparingly, warm neutrals, separate status colours
    "primary": "#b4232c",  # brand: primary actions and the brand mark, never large fills
    "primary_deep": "#8f1a22",
    "ink": "#2b2a33",  # headers, dark bands and body text
    "canvas": "#ffffff",
    "canvas_soft": "#f7f6f4",  # page background, icon tiles
    "line": "#e7e4e0",  # hairlines
    "body": "#6e6a66",  # secondary text
    "text_muted": "#4f4b48",
    "danger": "#b42318",  # scams and urgent status only
    "ok": "#1e7b4b",
    "warn": "#9a5b00",
}

# Indic and Japanese scripts need Noto fonts; without them they render as empty boxes.
FONT_LINK = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
             "&family=Noto+Sans+Devanagari:wght@400;600;700&family=Noto+Sans+JP:wght@400;500;700&display=block")
FONT_STACK = "'Inter','Noto Sans Devanagari','Noto Sans JP',sans-serif"

# Emoji and pictographic symbols; the model is told not to use them, and anything that slips through is removed.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u231A\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\uFE0F\u200D]")


def strip_emoji(text: str | None) -> str:
    """Model text without emoji (words in every script, numbers and punctuation stay)."""
    return re.sub(r"\s{2,}", " ", EMOJI.sub("", text or "")).strip()


TEMPLATES = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                        autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
TEMPLATES.filters["plain"] = strip_emoji
TEMPLATES.filters["icon"] = icon_svg
# font_stack goes inside <style>, where HTML escaping would break the quotes, so mark it safe.
TEMPLATES.globals.update(colors=COLORS, font_link=FONT_LINK, font_stack=Markup(FONT_STACK))
