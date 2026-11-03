"""The Japanese scam checker's prompt and answer format, as the app uses them. The data, training on Modal and
scoring live in the self-contained kit in scam-checker/ (its README.md is the plan and runbook)."""

from .policy import CHANNELS, SCAM_TYPES, Answer, messages, parse_answer, target

__all__ = ["CHANNELS", "SCAM_TYPES", "Answer", "messages", "parse_answer", "target"]
