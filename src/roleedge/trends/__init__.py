"""The trend engine: notices when the parent's everyday life drifts from her own normal (the USP, PIVOT.md §2).

Pure code, no model calls (rule A3): the decision to flag a change must be reviewable and repeatable.
"""

from .engine import COUNT_LINES, VOICE_LINES, InsightsMode, build_report

__all__ = ["COUNT_LINES", "VOICE_LINES", "InsightsMode", "build_report"]
