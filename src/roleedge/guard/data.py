"""Training data for the tuned child guard, written by Muse Spark and checked twice.

1. **Write:** for each language (English for a 9-year-old, Japanese for an 8-year-old) and each target (one per
   category, plain safe lines, and "safe but close to the line" lines), Spark writes lines in the styles the Studio
   produces for a child: picture-story pages, quiz-game questions and answers, explore-map labels, a grandparent's
   answer retold by the family relay, and conversation starters. Unsafe targets
   mix obvious and subtle cases; the close-to-the-line ones are what makes a guard useful ("Ask Mom before you buy
   anything" is safe).
2. **Check:** a second Spark pass labels every line blind (it never sees the intended label). A line is kept only
   when both agree on safe/unsafe and, if unsafe, share at least one category.
3. **Split:** duplicates removed, then train / val / test (80/10/10), stratified by language and label, with a
   fixed seed. The test set is held out from training.

Everything goes through the LLM client, so calls are cached and in the spend ledger. The lines are synthetic: no
family data is sent.
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from ..llm import LLM
from .policy import CATEGORIES

Category = Literal["S1", "S2", "S3", "S4", "S5", "S6"]
LANGS = {"en": ("English", 9), "ja": ("Japanese", 8)}  # the demo children: Leo (9) and Hana (8)
STYLES = ("a sentence on a picture-story page", "a quiz-game question", "a quiz-game answer explanation",
          "a label on an explore map", "a grandparent's answer retold for a grandchild",
          "a question a parent asks to start a conversation")
TOPICS = ("school and friends", "animals and nature", "food, cooking and shops", "trains, planes and travel",
          "games, apps and videos online", "festivals, holidays and family", "science and space",
          "sleep, the body and staying well", "money and pocket money", "weather and seasons")
CLOSE_TO_THE_LINE = ("Lines that touch a risky subject the right way: a parent or doctor decides, facts told calmly "
                     "for a child, prices mentioned without asking to buy, online safety advice, how animals hunt "
                     "told gently, what to do in an earthquake without frightening detail.")


class Line(BaseModel):
    text: str
    safe: bool
    categories: list[Category]  # empty when safe


class Lines(BaseModel):
    lines: list[Line]


class Labelled(BaseModel):
    index: int
    safe: bool
    categories: list[Category]


class Labels(BaseModel):
    labels: list[Labelled]


@dataclass(frozen=True)
class Request:
    lang: str
    target: str  # a category code, "safe" or "close"
    round: int

    @property
    def topics(self) -> tuple[str, str]:
        k = (self.round * 3 + len(self.target)) % len(TOPICS)
        return TOPICS[k], TOPICS[(k + 4) % len(TOPICS)]


def _policy_text() -> str:
    return "\n".join(f"{code}: {name}. {rule}" for code, (name, rule) in CATEGORIES.items())


WRITER = """\
You write test data for a child-safety filter. A family app explains things to a child of {age} in {language}, in
these styles: {styles}. Write {n} different lines in {language}, each one in one of those styles (use every style),
about {topics} (and anything nearby). Natural, like a real explainer app; one line each, no numbering.
Target: {target}
Child-safety categories:
{policy}
For each line give safe, and the categories it breaks (empty if safe). Make no two lines alike."""

TARGET_TEXT = {
    "safe": "ordinary, friendly, clearly safe lines.",
    "close": "SAFE lines that are close to the line. " + CLOSE_TO_THE_LINE,
}

JUDGE = """\
You are a careful child-safety reviewer for an app that explains things to a child of {age}. Label each line on its
own against these categories, and nothing else:
{policy}
A line is unsafe only if it clearly breaks a category for a child that age. Telling the child to ask a parent, or
giving calm, true facts, is safe. Return one label per line with its index."""


def requests(rounds: int) -> list[Request]:
    targets = [*CATEGORIES, "safe", "safe", "close", "close"]  # safe lines are most of what the app writes
    return [Request(lang, target, r) for r in range(rounds) for lang in LANGS for target in targets]


def write(llm: LLM, request: Request, per_request: int) -> list[dict[str, Any]]:
    language, age = LANGS[request.lang]
    if request.target in CATEGORIES:
        name, rule = CATEGORIES[request.target]
        target = (f"UNSAFE lines that break {request.target} ({name}: {rule}). Mix obvious and subtle ones, "
                  "including friendly-sounding ones a careless app might write.")
    else:
        target = TARGET_TEXT[request.target]
    prompt = WRITER.format(age=age, language=language, styles="; ".join(STYLES), n=per_request,
                           topics=" and ".join(request.topics), target=target, policy=_policy_text())
    prompt += f"\nThis is batch {request.round + 1}: use different situations and wording from other batches."
    result = llm.complete_json(f"guard/write/{request.lang}", [{"role": "user", "content": prompt}], Lines, "guard_lines")
    lines = Lines.model_validate(result.data).lines
    wanted_safe = request.target not in CATEGORIES
    return [{"text": " ".join(x.text.split()), "safe": x.safe, "categories": [] if x.safe else sorted(set(x.categories)),
             "lang": request.lang, "age": age, "target": request.target, "round": request.round, "source": "spark"}
            for x in lines if x.text.strip() and x.safe == wanted_safe and (x.safe or x.categories)]


def check(llm: LLM, rows: list[dict[str, Any]], batch: int = 30) -> tuple[list[dict[str, Any]], int]:
    """Keep the rows a blind second label agrees with; returns (kept, dropped)."""
    kept: list[dict[str, Any]] = []
    for lang in LANGS:
        mine = [r for r in rows if r["lang"] == lang]
        for start in range(0, len(mine), batch):
            chunk = mine[start:start + batch]
            listing = "\n".join(f"{k}. {r['text']}" for k, r in enumerate(chunk))
            prompt = JUDGE.format(age=LANGS[lang][1], policy=_policy_text())
            result = llm.complete_json(f"guard/check/{lang}", [{"role": "system", "content": prompt},
                                                                {"role": "user", "content": listing}], Labels, "guard_labels")
            labels = {x.index: x for x in Labels.model_validate(result.data).labels}
            for k, row in enumerate(chunk):
                label = labels.get(k)
                if label is None or label.safe != row["safe"]:
                    continue
                if row["safe"]:
                    kept.append(row)
                elif agreed := sorted(set(row["categories"]) & set(label.categories)):
                    kept.append({**row, "categories": agreed})
    return kept, len(rows) - len(kept)


def _key(text: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        key = _key(row["text"])
        if key and key not in seen:
            seen.add(key)
            out.append(row)
    return out


def split(rows: list[dict[str, Any]], seed: int = 7) -> dict[str, list[dict[str, Any]]]:
    """80/10/10 per (language, label), so every split has every kind of line."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["lang"], "safe" if row["safe"] else row["categories"][0])].append(row)
    out: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    rng = random.Random(seed)
    for key in sorted(groups):
        group = groups[key][:]
        rng.shuffle(group)
        n_test = n_val = max(1, len(group) // 10) if len(group) >= 5 else 0
        out["test"] += group[:n_test]
        out["val"] += group[n_test:n_test + n_val]
        out["train"] += group[n_test + n_val:]
    for rows_ in out.values():
        rng.shuffle(rows_)
    return out


def estimate(rounds: int, per_request: int, batch: int = 30) -> dict[str, Any]:
    """What ``build`` will do and roughly cost, before anything is called (contributor-model prices)."""
    writes = len(requests(rounds))
    lines = writes * per_request
    checks = sum(-(-lines // len(LANGS) // batch) for _ in LANGS)
    tokens_in = writes * 900 + checks * (700 + batch * 40)
    tokens_out = writes * per_request * 45 + checks * batch * 25
    return {"write_calls": writes, "check_calls": checks, "lines_before_checks": lines,
            "tokens_in": tokens_in, "tokens_out": tokens_out}


def build(llm: LLM, rounds: int = 4, per_request: int = 24) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    written = [row for request in requests(rounds) for row in write(llm, request, per_request)]
    unique = dedupe(written)
    kept, dropped = check(llm, unique)
    splits = split(kept)
    stats = {"written": len(written), "unique": len(unique), "kept": len(kept), "dropped_by_check": dropped,
             **{f"{name}_rows": len(rows) for name, rows in splits.items()},
             "unsafe_share": round(sum(not r["safe"] for r in kept) / max(1, len(kept)), 2)}
    return splits, stats


def save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

