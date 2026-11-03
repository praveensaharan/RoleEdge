"""Everything the demo web app plays, gathered from saved outputs into one JSON document.

The web app never calls a model: it replays what `roleedge content`, `render` and `checkin` saved.
Missing outputs are listed under "missing" instead of failing, so the page works after a partial run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..checkin import CHECKIN_DIR
from ..content import CONTENT_DIR, load
from ..demo import CONTENT_CASES, FAMILIES, RECIPIENTS
from ..models import DigestRecord

MEDIA = {"card": "card.png", "video": "explainer.mp4", "calendar": "event.ics"}


def build(content_dir: Path = CONTENT_DIR, checkin_dir: Path = CHECKIN_DIR) -> dict[str, Any]:
    families = []
    for family in FAMILIES.values():
        plan, items, calls, missing = family.care_plan, [], [], []
        for case in (c for c in CONTENT_CASES if c.recipient in family.recipients):
            if (content_dir / case.id / "digest.json").exists():
                items.append(_item(load(case.id, content_dir), content_dir))
            else:
                missing.append(f"content/{case.id}")
        for name in family.calls:
            path = checkin_dir / f"{name}.json"
            if path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
                calls.append({"scenario": name, "status": record["report"]["status"], "transcript": record["transcript"],
                              "events": record["events"], "report": record["report"]})
            else:
                missing.append(f"checkin/{name}")
        families.append({
            "id": family.id, "label": family.label,
            "caregiver": {"name": plan.caregiver.name, "relation": plan.caregiver.relation},
            "parent": {"call_name": plan.parent.call_name, "full_name": plan.parent.full_name,
                       "language": plan.parent.language},
            "recipients": [{"key": key, "call_name": RECIPIENTS[key].call_name, "role": RECIPIENTS[key].role,
                            "language": RECIPIENTS[key].language} for key in family.recipients],
            "items": items, "calls": calls, "missing": missing,
        })
    return {"families": families, "metrics": _metrics(content_dir.parent / "costs.json")}


def _metrics(costs_file: Path) -> dict[str, float] | None:
    """Measured model cost per item and per call (from ``roleedge costs``), or None before it has run."""
    if not costs_file.exists():
        return None
    costs = json.loads(costs_file.read_text(encoding="utf-8"))
    return {"cost_per_item_usd": costs["avg_llm_cost_per_content_item_usd"],
            "cost_per_call_usd": costs["avg_llm_cost_per_checkin_logic_usd"]}


def _item(record: DigestRecord, content_dir: Path) -> dict[str, Any]:
    folder = content_dir / record.case
    media = {key: f"/media/content/{record.case}/{name}" for key, name in MEDIA.items() if (folder / name).exists()}
    return {
        "case": record.case, "input": record.input, "recipient": record.recipient, "scam": record.digest.is_scam,
        "digest": record.digest.model_dump(mode="json"), "held_actions": sorted(record.held_action_indexes),
        "held_fields": [issue.path for issue in record.verify_issues if issue.needs_review],
        "voice_note": record.digest.voice_note_script, "media": media,
    }
