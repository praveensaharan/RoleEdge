"""The call's status colour is decided here, from what the agent recorded - never by the model's
summary (ARCHITECTURE.md rule S3). In testing, the summariser said "amber" after an urgent flag.

Tool arguments come from a model, so they are read defensively: case and spaces are ignored, a concern
whose severity cannot be read counts as urgent, and a medicine whose status cannot be read counts as
missed - an unreadable value must never turn a call green.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from ..models import CallStatus, Severity, Taken

_SEVERITY: TypeAdapter[str] = TypeAdapter(Severity)
_TAKEN: TypeAdapter[str] = TypeAdapter(Taken)


def escalation_status(events: list[dict[str, Any]]) -> CallStatus:
    """red: any urgent concern. amber: any 'watch' concern or a medicine recorded as not taken. else green."""
    severities = {_read(_SEVERITY, e["args"].get("severity"), "urgent") for e in events if e["tool"] == "flag_concern"}
    missed_medicine = any(_read(_TAKEN, m.get("taken"), "no") == "no"
                          for e in events if e["tool"] == "record_checkin"
                          for m in e["args"].get("medicines") or [] if isinstance(m, dict))
    if "urgent" in severities:
        return "red"
    if "watch" in severities or missed_medicine:
        return "amber"
    return "green"


def _read(adapter: TypeAdapter[str], value: Any, fallback: str) -> str:
    try:
        return adapter.validate_python(value)
    except ValidationError:
        return fallback
