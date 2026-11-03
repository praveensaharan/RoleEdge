"""The way to fine-tune a model on the family's voice: every moment the judge and code approved, as training pairs.

From each round's stored results, a moment goes in only when judge v4 (or the children's judge v2) scored it 4.3 or
more with natural 4 or more, it has no robotic habit (``studio.verify.robotic``), it passed the send gate, and its
reel isn't one the safety review held. Each line is one chat example: the maker's own instructions, the brief the
maker got (the plan and the research), and the approved moment. That is the data for a LoRA on an open Llama model,
the same way the child guard was trained (docs/GUARD.md); nothing is trained here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..families import CIRCLES
from ..studio.agents import FORMAT_NAMES, MAKERS, fields
from ..studio.verify import robotic
from . import LAB
from .report import load, moment_score, moment_texts, rounds

OUT = LAB / "style-dataset.jsonl"
MIN_SCORE, MIN_NATURAL = 4.3, 4


def examples() -> list[dict[str, Any]]:
    found = []
    for kind, key in (("round", "judgement_v4"), ("kids", "judgement_child_v2")):
        for n in rounds(kind):
            for rid, out in load(n, kind).items():
                judged = {m["format"]: m for m in (out.get(key) or {}).get("moments", [])}
                if not judged or not (out.get("gate") or {}).get("passed") or not (out.get("guardian") or {}).get("safe_for_child", True):
                    continue
                brief = (f"Plan:\n{json.dumps(out.get('plan') or {}, ensure_ascii=False)}\n\n"
                         f"Research:\n{json.dumps(out.get('research') or {}, ensure_ascii=False)[:12000]}")
                for fmt, moment in (out.get("outputs") or {}).items():
                    m = judged.get(fmt)
                    if not m or moment_score(m) < MIN_SCORE or m.get("natural", 0) < MIN_NATURAL or robotic(moment_texts(moment)):
                        continue
                    clean = {k: v for k, v in moment.items() if k not in ("image", "frames", "focus", "image_error")}
                    found.append({"reel": rid, "round": f"{kind} {n}", "format": fmt, "score": round(moment_score(m), 2),
                                  "messages": [{"role": "system", "content": _system(fmt, kind)},
                                               {"role": "user", "content": brief},
                                               {"role": "assistant", "content": json.dumps(clean, ensure_ascii=False)}]})
    return found


def _system(fmt: str, kind: str) -> str:
    """The maker's instructions as it got them, for Linda (79) or Leo (9)."""
    circle = CIRCLES["chen"]
    filled = fields(circle, circle.children[0] if kind == "kids" else None)
    return MAKERS[fmt].system.replace("{format_name}", FORMAT_NAMES[fmt]).format(**filled)


def write_dataset(path: Path = OUT) -> dict[str, Any]:
    rows = examples()
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    by_format: dict[str, int] = {}
    for r in rows:
        by_format[r["format"]] = by_format.get(r["format"], 0) + 1
    return {"examples": len(rows), "by_format": by_format, "path": str(path)}
