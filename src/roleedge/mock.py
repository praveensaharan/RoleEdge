"""Mock of the core screen, built from real pipeline outputs: the caregiver's chat next to a live
mirror of what the parent's phone shows. Writes output/mock/screens.html and screens.png."""

from __future__ import annotations

from pathlib import Path

from .checkin import CHECKIN_DIR, CallRecord
from .config import OUTPUT_DIR
from .content import load
from .models import Recipient
from .render import HtmlRenderer
from .render.i18n import deadline_phrase
from .render.theme import COLORS, TEMPLATES

MOCK_DIR = OUTPUT_DIR / "mock"
STATUS_COLORS = {"red": COLORS["danger"], "amber": "#d08a00", "green": COLORS["ok"]}


def build(recipient: Recipient, mock_dir: Path = MOCK_DIR) -> Path:
    """``recipient`` is the parent whose phone is mirrored (their language drives the labels)."""
    pension, scam = load("pension_reel").digest, load("scam_reel").digest
    call = CallRecord.model_validate_json((CHECKIN_DIR / "concerning_day.json").read_text(encoding="utf-8"))
    due = next(a for a in pension.actions if a.due_date)
    language = recipient.language
    html = TEMPLATES.get_template("mock_screens.html").render(
        pension=pension, scam=scam, due=due, report=call.report,
        status_color=STATUS_COLORS[call.report["status"]],
        due_phrase=deadline_phrase(due.due_date, language),
        reminder_phrase=" और ".join(f"{d} दिन" for d in sorted(due.remind_days_before)) + " पहले",
    )
    mock_dir.mkdir(parents=True, exist_ok=True)
    page = mock_dir / "screens.html"
    page.write_text(html, encoding="utf-8")
    with HtmlRenderer() as renderer:
        renderer.screenshot_file(page, mock_dir / "screens.png", 1440, 1000)
    return mock_dir / "screens.png"
