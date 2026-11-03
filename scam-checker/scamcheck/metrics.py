"""Scoring any model's answers on a test set, the same way for Glimmer, Muse Spark, GPT and Claude.

"Positive" means scam. The two numbers that matter most:

- **catch rate**: of the real scams, how many were caught (a missed scam can cost someone their savings);
- **false alarms**: of the genuine messages, how many were wrongly flagged (too many and people stop listening,
  and miss real notices such as a genuine refund from the city).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .policy import Answer, flags_in, normalise, parse_answer


def score(rows: Sequence[dict[str, Any]], answers: Sequence[Answer]) -> dict[str, Any]:
    if len(rows) != len(answers):
        raise ValueError(f"{len(rows)} rows but {len(answers)} answers")
    pairs = list(zip(rows, answers, strict=True))
    tp = sum(1 for r, a in pairs if r["scam"] and a.scam)
    fn = sum(1 for r, a in pairs if r["scam"] and not a.scam)
    fp = sum(1 for r, a in pairs if not r["scam"] and a.scam)
    tn = sum(1 for r, a in pairs if not r["scam"] and not a.scam)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    caught = [(r, a) for r, a in pairs if r["scam"] and a.scam]
    typed = [(r, a) for r, a in caught if r.get("type") not in ("", "none", "other")]
    flagged = [(r, a) for r, a in caught if r.get("red_flags")]
    predicted_flags = [(r["text"], f) for r, a in caught for f in a.red_flags]
    return {
        "n": len(pairs), "scams": tp + fn, "genuine": fp + tn,
        "catch_rate": recall, "false_alarms": fp / (fp + tn) if fp + tn else 0.0,
        "precision": precision, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "accuracy": (tp + tn) / len(pairs) if pairs else 0.0,
        "type_match": sum(r["type"] == a.type for r, a in typed) / len(typed) if typed else None,
        "flag_match": sum(_overlaps(r["red_flags"], a.red_flags) for r, a in flagged) / len(flagged) if flagged else None,
        "flags_copied": (sum(bool(flags_in(t, [f])) for t, f in predicted_flags) / len(predicted_flags)
                         if predicted_flags else None),
        "unparsed": sum(1 for _, a in pairs if not a.parsed),
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
    }


def _overlaps(gold: Sequence[str], predicted: Sequence[str]) -> bool:
    """At least one predicted red flag overlaps a gold one (either contains the other)."""
    g, p = [normalise(x) for x in gold], [normalise(x) for x in predicted]
    return any(a and b and (a in b or b in a) for a in g for b in p)


def table(results: dict[str, dict[str, dict[str, Any]]]) -> str:
    """Markdown: one row per (model, test set). ``results[model][test_set] = score(...)``."""
    pct = lambda x: "n/a" if x is None else f"{x:.0%}"  # noqa: E731
    lines = ["| Model | Test set | n | Catch rate | False alarms | Precision | F1 | Type match | Flag match | Unparsed |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for model, sets in results.items():
        for name, s in sets.items():
            lines.append(f"| {model} | {name} | {s['n']} | {pct(s['catch_rate'])} | {pct(s['false_alarms'])} | "
                         f"{pct(s['precision'])} | {pct(s['f1'])} | {pct(s['type_match'])} | {pct(s['flag_match'])} | "
                         f"{s['unparsed']} |")
    return "\n".join(lines)


def save(path: Path, model: str, sets: dict[str, tuple[list[dict[str, Any]], list[str]]]) -> dict[str, dict[str, Any]]:
    """Score raw answers per test set and write scores plus every prediction (to read the mistakes)."""
    scores, predictions = {}, {}
    for name, (rows, raws) in sets.items():
        answers = [parse_answer(raw) for raw in raws]
        scores[name] = score(rows, answers)
        predictions[name] = [{"text": r["text"], "scam": r["scam"], "type": r["type"], "red_flags": r.get("red_flags", []),
                              "pred_scam": a.scam, "pred_type": a.type, "pred_flags": a.red_flags,
                              "pred_advice": a.advice, "raw": raw} for r, a, raw in zip(rows, answers, raws, strict=True)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model, "at": datetime.now(UTC).isoformat(timespec="seconds"),
                                "scores": scores, "predictions": predictions}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return scores
