"""Save a call record as JSON (for code) and Markdown (for people)."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import OUTPUT_DIR
from .call import CallRecord

CHECKIN_DIR = OUTPUT_DIR / "checkin"


def save(record: CallRecord, out_dir: Path = CHECKIN_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{record.scenario}.json").write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    md = out_dir / f"{record.scenario}.md"
    md.write_text(to_markdown(record), encoding="utf-8")
    return md


def to_markdown(record: CallRecord) -> str:
    lines = [f"# Check-in call: {record.scenario}\n", "| Speaker | Line |", "|---|---|"]
    lines += [f"| {who} | {text.replace('|', '/')} |" for who, text in record.transcript]
    lines += ["\n## Tool events\n"]
    lines += [f"- turn {e['turn']}: `{e['tool']}` {json.dumps(e['args'], ensure_ascii=False)}" for e in record.events]
    lines += ["\n## Caregiver report\n", "```json", json.dumps(record.report, ensure_ascii=False, indent=2), "```"]
    return "\n".join(lines)


def summary_line(record: CallRecord) -> str:
    latencies = sorted(t["latency_s"] for t in record.metrics["agent_turns"])
    tools = [e["tool"] for e in record.events]
    return (f"{record.scenario}: {len(record.transcript)} lines, tools={tools}, status={record.report['status']}, "
            f"ended={record.ended_cleanly}, agent calls={len(latencies)}, "
            f"agent latency median={latencies[len(latencies) // 2]}s max={latencies[-1]}s")
