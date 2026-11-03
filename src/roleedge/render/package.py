"""Render one digest record into everything the recipient receives.

    card.png        illustrated card (1080x1350)
    explainer.mp4   vertical 720x1280 explainer built from the storyboard (silent for now)
    event.ics       calendar events with reminders (only if there are deadlines)
    article.md      the regional-language article
    voice_note.txt  the script a text-to-speech voice will read
"""

from __future__ import annotations

import time
from pathlib import Path

from ..models import DigestRecord, Recipient
from .browser import HtmlRenderer
from .calendar import build_calendar
from .card import card_html
from .video import render_explainer, video_length


def render_record(renderer: HtmlRenderer, record: DigestRecord, recipient: Recipient, case_dir: Path) -> dict:
    """Write all outputs into ``case_dir``; return timings and counts for the report."""
    digest, held = record.digest, record.held_action_indexes
    stats: dict = {}

    started = time.time()
    renderer.screenshot(card_html(digest, recipient, held), case_dir / "card.png", 1080, 1350)
    stats["card_s"] = round(time.time() - started, 2)

    started = time.time()
    seconds = render_explainer(renderer, digest.storyboard, case_dir / "frames", case_dir / "explainer.mp4",
                               warn=digest.is_scam)
    stats["video_s"] = round(time.time() - started, 2)
    stats["video_len_s"] = video_length(seconds)

    ics = build_calendar(digest, uid_prefix=record.case, held=held, timezone=recipient.timezone)
    ics_path = case_dir / "event.ics"
    if ics:
        ics_path.write_bytes(ics)
    else:
        ics_path.unlink(missing_ok=True)
    stats["calendar_events"] = ics.count(b"BEGIN:VEVENT") if ics else 0
    stats["calendar_held_for_review"] = len(held)

    reg = digest.regional
    bullets = "\n".join(f"- {line}" for line in reg.summary)
    (case_dir / "article.md").write_text(f"# {reg.title}\n\n{bullets}\n\n{reg.article}\n", encoding="utf-8")
    (case_dir / "voice_note.txt").write_text(digest.voice_note_script + "\n", encoding="utf-8")
    return stats
