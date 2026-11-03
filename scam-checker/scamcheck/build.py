"""Merge every data file into the final training and test sets, checking each row.

Reads (files whose name starts with ``_`` are templates and are skipped):

- ``data/synthetic/*.jsonl``  messages written by Muse Spark (``python -m scamcheck generate``)
- ``data/cases/*.csv|jsonl``  your own cases; they go into training unless the row says ``split=test``
- ``data/real/*.csv|jsonl``   real messages labelled by where they were published: **test only, never trained on**

Writes ``data/final/train.jsonl``, ``val.jsonl``, ``test.jsonl``, ``real_test.jsonl`` and ``stats.json``.

A row with a problem (an unknown type, a red flag that isn't in the message, ...) is skipped and reported with its
file and line, so you can fix it. Duplicates are removed (real beats cases beats synthetic), and anything that also
appears in the real test set is removed from training, so the scores aren't inflated.
"""

from __future__ import annotations

import csv
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .policy import CHANNELS, SCAM_TYPES, flags_in, foreign_hanzi

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRUE, FALSE = {"true", "yes", "y", "1", "scam", "詐欺"}, {"false", "no", "n", "0", "genuine", "none", "本物"}


def key(text: str) -> str:
    """For finding duplicates: full-width forms unified, case, spaces and punctuation ignored."""
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        k = key(row["text"])
        if k and k not in seen:
            seen.add(k)
            out.append(row)
    return out


def read_file(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """(line number, raw row) for a .jsonl or .csv file."""
    if path.suffix == ".jsonl":
        return [(n, json.loads(line)) for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                if line.strip()]
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [(n, row) for n, row in enumerate(csv.DictReader(fh), 2) if any((v or "").strip() for v in row.values())]


def clean(raw: dict[str, Any], kind: str) -> tuple[dict[str, Any] | None, list[str]]:
    """One row in the common format, or None and the problems found. ``kind`` is synthetic, cases or real."""
    problems: list[str] = []
    text = str(raw.get("text") or "").strip()
    scam_raw = raw.get("scam")
    scam = scam_raw if isinstance(scam_raw, bool) else (
        True if str(scam_raw).strip().lower() in TRUE else False if str(scam_raw).strip().lower() in FALSE else None)
    kind_ = str(raw.get("type") or "").strip() or ("none" if scam is False else "")
    flags = raw.get("red_flags") or []
    if isinstance(flags, str):
        flags = [f.strip() for f in flags.split("|") if f.strip()]
    advice = str(raw.get("advice") or "").strip()
    channel = str(raw.get("channel") or "").strip().lower()
    split = str(raw.get("split") or "").strip().lower()

    if not 5 <= len(text) <= 3000:
        problems.append("text is empty or longer than 3000 characters")
    if scam is None:
        problems.append(f"scam must be true or false, got {scam_raw!r}")
    if channel and channel not in CHANNELS:
        problems.append(f"channel {channel!r} is not one of {', '.join(CHANNELS)}")
    if split not in ("", "train", "test"):
        problems.append(f"split must be train, test or empty, got {split!r}")
    if kind == "real" and not str(raw.get("source_url") or raw.get("source") or "").strip():
        problems.append("a real message needs source_url (where it was published)")
    if scam:
        if kind_ not in SCAM_TYPES:
            problems.append(f"type {kind_!r} is not one of {', '.join(SCAM_TYPES)}")
        missing = [f for f in flags if f not in flags_in(text, flags)]
        if missing:
            problems.append(f"red flags not found in the text: {missing}")
        if kind != "real" and not flags:
            problems.append("a scam needs at least one red flag (a phrase copied from the text)")
        if kind != "real" and not advice:
            problems.append("a scam needs advice (one calm sentence)")
    elif scam is False and kind_ != "none":
        problems.append(f"a genuine message has type none, got {kind_!r}")
    if kind == "synthetic" and foreign_hanzi(text):
        problems.append(f"Chinese characters not used in Japanese: {foreign_hanzi(text)}")
    if problems:
        return None, problems
    row = {"text": text, "channel": channel, "sender": str(raw.get("sender") or "").strip(), "scam": scam,
           "type": kind_ if scam else "none", "red_flags": flags if scam else [], "advice": advice if scam else "",
           "target": raw.get("target") or f"{kind}:{kind_ if scam else 'none'}", "origin": kind,
           "source": str(raw.get("source_url") or raw.get("source") or kind)}
    if split:
        row["split"] = split
    return row, []


def load(data: Path = DATA) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    rows: dict[str, list[dict[str, Any]]] = {"synthetic": [], "cases": [], "real": []}
    problems: list[str] = []
    for kind, folder, patterns in (("synthetic", "synthetic", ("*.jsonl",)), ("cases", "cases", ("*.jsonl", "*.csv")),
                                   ("real", "real", ("*.jsonl", "*.csv"))):
        for path in sorted(p for pattern in patterns for p in (data / folder).glob(pattern) if not p.name.startswith("_")):
            for line, raw in read_file(path):
                row, found = clean(raw, kind)
                if row is None:
                    problems += [f"{path.relative_to(data.parent)}:{line}: {p}" for p in found]
                else:
                    rows[kind].append(row)
    return rows, problems


def split(rows: list[dict[str, Any]], seed: int = 7) -> dict[str, list[dict[str, Any]]]:
    """80/10/10 per target, so every split has every kind of message; rows marked split=test go to test."""
    out: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("split") == "test":
            out["test"].append(row)
        else:
            groups[row["target"]].append(row)
    rng = random.Random(seed)
    for target in sorted(groups):
        group = groups[target][:]
        rng.shuffle(group)
        n = max(1, len(group) // 10) if len(group) >= 5 else 0
        out["test"] += group[:n]
        out["val"] += group[n:2 * n]
        out["train"] += group[2 * n:]
    for part in out.values():
        rng.shuffle(part)
    return out


def build(data: Path = DATA) -> tuple[dict[str, Any], list[str]]:
    rows, problems = load(data)
    real = dedupe(rows["real"])
    real_keys = {key(r["text"]) for r in real}
    pool = [r for r in dedupe(rows["cases"] + rows["synthetic"]) if key(r["text"]) not in real_keys]
    leaks = len(dedupe(rows["cases"] + rows["synthetic"])) - len(pool)
    splits = {**split(pool), "real_test": real}
    final = data / "final"
    final.mkdir(parents=True, exist_ok=True)
    for name, part in splits.items():
        (final / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part),
                                            encoding="utf-8")
    stats = {"read": {k: len(v) for k, v in rows.items()}, "rows_with_problems": len(problems),
             "removed_because_in_real_test": leaks,
             "splits": {name: {"rows": len(part), "scam_share": round(sum(r["scam"] for r in part) / max(1, len(part)), 2)}
                        for name, part in splits.items()},
             "train_types": dict(Counter(r["type"] for r in splits["train"]).most_common())}
    (final / "stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    return stats, problems
