"""Gates that run in code before anything reaches the parent (PIVOT.md T5, T8)."""

from .mail import MailVerdict, check_sender
from .send import HARD_RULES, check_outgoing

__all__ = ["HARD_RULES", "MailVerdict", "check_outgoing", "check_sender"]
