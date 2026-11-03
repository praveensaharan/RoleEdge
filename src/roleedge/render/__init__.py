"""Deterministic rendering: the model writes content, this code decides layout (rule A3)."""

from .browser import HtmlRenderer
from .calendar import build_calendar
from .card import card_html
from .package import render_record

__all__ = ["HtmlRenderer", "build_calendar", "card_html", "render_record"]
