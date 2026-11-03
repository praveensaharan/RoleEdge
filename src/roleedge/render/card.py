"""The illustrated card: line-icon pictograms, 3-5 short steps, a trust badge and a deadline chip."""

from __future__ import annotations

from ..models import Digest, Recipient, is_iso_date
from . import i18n
from .theme import TEMPLATES

# What sits in the corner of each pictogram; None means "use the step number".
MARKERS = {"steps": None, "checklist": "✓", "timeline": "•", "warning": "!"}


def first_deadline(digest: Digest, held: set[int]) -> str | None:
    """Earliest calendar deadline that is not waiting for the sender's review."""
    dates = sorted(a.due_date for i, a in enumerate(digest.actions)
                   if is_iso_date(a.due_date) and a.add_to_calendar and i not in held)
    return dates[0] if dates else None


def card_html(digest: Digest, recipient: Recipient, held: set[int] = frozenset()) -> str:
    warn = digest.illustration.layout == "warning" or digest.is_scam
    deadline = first_deadline(digest, held)
    return TEMPLATES.get_template("card.html").render(
        illustration=digest.illustration,
        warn=warn,
        markers=MARKERS,
        badge=i18n.trust_badge(digest.trust.verdict, recipient.language),
        badge_icon=i18n.BADGE_ICONS[digest.trust.verdict],
        deadline=i18n.deadline_phrase(deadline, recipient.language) if deadline and not warn else None,
        sent_by=i18n.sent_by(recipient.sender_short, recipient.language),
    )
