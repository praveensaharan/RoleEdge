"""Phase 9: the reports, written from what the lab stored (no model calls).

* ``docs/reel-lab/REPORT.md``: the summary, the rounds compared, every change and its effect, Notion, the demo apps,
  and the costs;
* ``docs/reel-lab/REELS.md``: the structured evaluation of every reel (technical, transcription, visual reading,
  content, formats chosen, scores per round, what still falls short);
* ``docs/reel-lab/OUTPUTS.md``: the moments made for every reel in the latest round, as text.

Creators' handles are left out; reels are named by id and title. No token or page id is written.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..costs import PRICE_BY_MODEL, UNKNOWN_PRICE, dollars
from ..llm.types import Usage
from . import LAB, REPORT_DIR
from .budget import spent
from .changes import CHANGES

CRITERIA = ("faithful", "clear", "engaging", "useful", "format_fit")
BAR = 4.2


# ---------------------------------------------------------------- reading what is stored


def inventory() -> list[dict[str, Any]]:
    return json.loads((LAB / "inventory.json").read_text(encoding="utf-8"))


def rounds(kind: str = "round") -> list[int]:
    """Rounds for Linda (``round``) or for Leo (``kids``)."""
    found = {int(p.stem.split("-")[1]) for p in LAB.glob(f"*/{kind}-*.json") if p.parent.name not in ("notion", "apps")}
    return sorted(found)


def load(n: int, kind: str = "round") -> dict[str, dict[str, Any]]:
    return {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
            for p in LAB.glob(f"*/{kind}-{n}.json") if p.parent.name not in ("notion", "apps")}


JUDGE_KEY = "judgement_v2"  # the judge the tables use; set per table (v2: rounds 1-3, v3: the full set, child: Leo)


def judged(out: dict[str, Any]) -> dict[str, Any]:
    """The judgement the current table uses (v2 for rounds 1-3; round 1 was scored again with it)."""
    return out.get(JUDGE_KEY) or {}


def using(key: str) -> None:
    global JUDGE_KEY
    JUDGE_KEY = key


def latest_key(out: dict[str, Any]) -> str:
    """The newest judge that scored this round: v4 (the family's voice), v3 (the full set), the children's judges, or v2."""
    return next((k for k in ("judgement_v4", "judgement_child_v2", "judgement_v3", "judgement_child", "judgement_v2") if out.get(k)),
                "judgement_v2")


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def fmt_key(name: str) -> str:
    """The judge sometimes names a moment its own way ("Quiz (askme)", "Steps/slides"): back to the format id."""
    low = name.lower()
    for key, words in (("askme", ("askme", "ask me")), ("steps", ("steps", "slides")), ("map", ("map",)), ("video", ("video",)),
                       ("picture", ("picture",)), ("note", ("note",)), ("card", ("card",)), ("story", ("story",)),
                       ("quiz", ("quiz",)), ("relay", ("relay", "ask grandma"))):
        if any(w in low for w in words):
            return key
    return low


def moment_score(m: dict[str, Any]) -> float:
    """The mean of the judge's scores; judge v4 adds a sixth, natural (sounds like the family, not a report)."""
    keys = (*CRITERIA, "natural") if m.get("natural") else CRITERIA
    return sum(m[k] for k in keys) / len(keys)


def moment_texts(output: dict[str, Any]) -> list[str]:
    """What she sees or hears in one moment (the English summaries and file names left out)."""
    found: list[str] = []

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, str):
            if not key.endswith("_en") and key not in ("icon", "image", "frames", "format"):
                found.append(value)
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)

    walk(output)
    return found


def robotic_rate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Share of moments with a robotic habit (code, studio.verify.robotic): introducing the sender, narrating the
    reel, disclaimers she doesn't need, labels about the reel. The user's own complaint, measured the same way in
    every round, with no judge."""
    from ..studio.verify import robotic

    moments = hit = habits = 0
    for o in rows.values():
        for output in (o.get("outputs") or {}).values():
            found = robotic(moment_texts(output))
            moments += 1
            hit += bool(found)
            habits += len(found)
    return {"moments": moments, "with_habit": hit, "rate": round(hit / moments, 3) if moments else 0.0, "habits": habits}


def best(out: dict[str, Any]) -> float:
    return max((moment_score(m) for m in judged(out).get("moments", [])), default=0.0)


def pack(out: dict[str, Any]) -> float:
    """The mean of every moment made: with a full set, every moment has to be good, not just the best one."""
    scores = [moment_score(m) for m in judged(out).get("moments", [])]
    return sum(scores) / len(scores) if scores else 0.0


def weakest(out: dict[str, Any]) -> float:
    return min((moment_score(m) for m in judged(out).get("moments", [])), default=0.0)


def majors(out: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**p, "format": m["format"]} for m in judged(out).get("moments", []) for p in m["problems"] if p["severity"] == "major"]


def unsafe(out: dict[str, Any]) -> list[str]:
    """Major findings about unsafe advice that still passed the send gate."""
    words = ("unsafe", "injur", "dangerous", "risky", "hurt", "medical advice", "financial advice", "money advice")
    if not (out.get("gate") or {}).get("passed"):
        return []
    return [p["problem_en"] for p in majors(out) if any(w in p["problem_en"].lower() for w in words)]


def round_cost(out: dict[str, Any]) -> float:
    c = out.get("cost") or {}
    return c.get("usd", 0.0) + c.get("transcribe_usd", 0.0) + c.get("image_usd", 0.0) + sum(v for k, v in c.items() if k.startswith("rejudge"))


def summary(n: int, data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    outs = [o for o in data.values() if judged(o)]
    bests = [best(o) for o in outs]
    by_format: dict[str, list[float]] = defaultdict(list)
    causes: Counter[str] = Counter()
    for o in outs:
        made = list((o.get("outputs") or {}).keys())
        named = [fmt_key(m["format"]) for m in judged(o)["moments"]]
        for k, m in enumerate(judged(o)["moments"]):
            # a judge that names a moment its own way ("all faces are different"): the made format it left out
            key = named[k] if named[k] in made else next((f for f in made if f not in named), named[k])
            by_format[key].append(moment_score(m))
        for p in majors(o):
            causes[p["cause"]] += 1
    return {"round": n, "reels": len(data), "judged": len(outs), "mean_best": mean(bests), "at_bar": sum(b >= BAR for b in bests),
            "pack_mean": mean([pack(o) for o in outs]), "weakest": mean([weakest(o) for o in outs]),
            "moments": sum(len(judged(o)["moments"]) for o in outs),
            "held_for_child": sum(not (o.get("guardian") or {}).get("safe_for_child", True) for o in outs),
            "majors": sum(len(majors(o)) for o in outs), "unsafe_passed": sum(len(unsafe(o)) for o in outs),
            "gate_held": sum(not (o.get("gate") or {}).get("passed", True) for o in outs),
            "scam_verdicts": sum((o.get("research") or {}).get("fact_check", {}).get("verdict") == "likely_scam_or_misleading" for o in outs),
            "errors": sum(bool(o.get("error")) for o in data.values()),
            "by_format": {f: (len(v), mean(v)) for f, v in sorted(by_format.items())}, "causes": dict(causes),
            "cost": round(sum(round_cost(o) for o in data.values()), 3),
            "seconds": mean([o.get("seconds", 0) for o in data.values()])}


# ---------------------------------------------------------------- moments as text


def moment_text(fmt: str, o: dict[str, Any], pictures: list[str]) -> list[str]:
    if fmt == "note":
        return [f"**{o.get('title', '')}**", *o.get("lines", []), f"*Question:* {o.get('question', '')}"]
    if fmt in ("steps", "story"):
        return [f"**{o.get('title', '')}**", *(f"{k + 1}. **{p['big_text']}**: {p['line']}" for k, p in enumerate(o.get("pages", [])))]
    if fmt == "card":
        return [f"**{o.get('title', '')}**", *(f"- {line['text']}" for line in o.get("lines", [])),
                f"*Remember:* {o.get('remember') or '(empty)'}", f"*Ask:* {o.get('ask', '')}"]
    if fmt in ("askme", "quiz"):
        lines = [f"**{o.get('title', '')}**"]
        for q in o.get("questions", []):
            choices = " / ".join(f"**{c}**" if i == q.get("answer") else c for i, c in enumerate(q.get("choices", [])))
            lines.append(f"- {q['question']} ({choices}). {q.get('explain', '')}")
        return lines
    if fmt == "map":
        return [f"**{o.get('root', '')}**", *(f"- {b['label']}: {', '.join(b.get('leaves', []))}" for b in o.get("branches", []))]
    if fmt == "video":
        lines = [f"**{o.get('title', '')}**"]
        for k, sc in enumerate(o.get("scenes", [])):
            frame = sc.get("frame", -1)
            still = f" *(the reel's still: {pictures[frame]})*" if 0 <= frame < len(pictures) else ""
            lines.append(f"{k + 1}. **{sc['big_text']}**: {sc['narration']}{still}")
        return lines
    if fmt == "picture":
        return [f"**{o.get('title', '')}**", o.get("caption", ""), f"*Drawn from:* {o.get('prompt_en', '')}"]
    return [json.dumps(o, ensure_ascii=False)[:600]]


# ---------------------------------------------------------------- the three files


def _short(text: str, n: int = 70) -> str:
    text = " ".join((text or "").split()).replace("|", "/")
    return text if len(text) <= n else text[: n - 1] + "…"


def _bands(probe: dict[str, Any]) -> str:
    weak = [f"{k} {v}" for k, v in probe.get("bands", {}).items() if v != "pass"]
    return ", ".join(weak) or "all pass"


def _agreement(t: dict[str, Any]) -> str:
    if t.get("agreement") is not None:
        return f"{t['agreement']:.2f}"
    scripts = t.get("scripts") or ["", ""]
    if not scripts[1]:
        return "no reference"
    if scripts[0] != scripts[1]:
        return f"not comparable ({scripts[0] or 'none'} vs {scripts[1]})"
    return "n/a"


def write_report() -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    inv = inventory()
    ns = rounds()
    data = {n: load(n) for n in ns}
    using("judgement_v2")
    sums = [summary(n, data[n]) for n in ns if any(o.get("judgement_v2") for o in data[n].values())]
    v1 = [o for o in data.get(1, {}).values() if o.get("judgement")]
    last = ns[-1] if ns else 0
    (REPORT_DIR / "REPORT.md").write_text(_report(inv, ns, data, sums, v1, last), encoding="utf-8")
    (REPORT_DIR / "REELS.md").write_text(_reels(inv, ns, data), encoding="utf-8")
    kids = rounds("kids")
    text = _outputs(inv, data.get(last, {}), last)
    if kids:
        text += "\n" + _outputs(inv, load(kids[-1], "kids"), kids[-1], who="Leo (9)")
    (REPORT_DIR / "OUTPUTS.md").write_text(text, encoding="utf-8")
    (LAB / "summary.json").write_text(json.dumps(summary_data(inv, ns, data), ensure_ascii=False, indent=1), encoding="utf-8")
    return f"wrote {REPORT_DIR}/REPORT.md, REELS.md, OUTPUTS.md and {LAB}/summary.json (rounds {ns})"


def _criteria(rows: dict[str, dict[str, Any]]) -> dict[str, float]:
    per: dict[str, list[int]] = defaultdict(list)
    for o in rows.values():
        for m in judged(o).get("moments", []):
            for k in (*CRITERIA, "natural"):
                if m.get(k):
                    per[k].append(m[k])
    return {k: mean(per[k]) for k in (*CRITERIA, "natural") if per[k]}


def _rows(key: str, kind: str, ns: list[int], data: dict[int, dict[str, dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Round by round on one judge: the headline numbers, scores by format and by criterion."""
    using(key)
    out = []
    for n in ns:
        rows = data[n] if data is not None else load(n, kind)
        if not any(o.get(key) for o in rows.values()):
            continue
        x = summary(n, rows)
        out.append({k: x[k] for k in ("round", "judged", "moments", "mean_best", "at_bar", "pack_mean", "weakest", "majors",
                                      "unsafe_passed", "gate_held", "held_for_child", "cost")}
                   | {"by_format": {f: {"count": c, "score": v} for f, (c, v) in x["by_format"].items()}, "criteria": _criteria(rows)})
    using("judgement_v2")
    return out


def summary_data(inv: list[dict[str, Any]], ns: list[int], data: dict[int, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """Everything the /lab page shows about the tuning, from the stored rounds (no model calls)."""
    usable = [r for r in inv if not r["skipped"]]
    kid_ns = rounds("kids")
    all_rows = [o for n in ns for o in data[n].values()] + [o for n in kid_ns for o in load(n, "kids").values()]
    judgements = sum(1 for o in all_rows for k in ("judgement", "judgement_v2", "judgement_v3", "judgement_child") if o.get(k))
    moments = sum(len(o.get("outputs") or {}) for o in all_rows)
    calls = 0
    for path in LAB.glob("**/ledger-*.jsonl"):
        calls += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and '"replayed_from_cache": false' in line)
    notion = [json.loads(p.read_text()) for p in sorted((LAB / "notion").glob("round-*.json"))]
    links = json.loads((LAB / "links" / "results.json").read_text()) if (LAB / "links" / "results.json").exists() else None
    apps = [json.loads(p.read_text()) for p in sorted((LAB / "apps").glob("e2e-*.json"))]
    collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=REPORT_DIR.parent.parent,
                               capture_output=True, text=True, timeout=120, check=False).stdout
    tests = sum(1 for line in collected.splitlines() if "::" in line)  # the automated tests in the repository
    return {
        "reels": len(inv), "usable": len(usable), "skipped": len(inv) - len(usable),
        "rounds_linda": len(ns), "rounds_leo": len(kid_ns), "reel_runs": len(all_rows), "moments": moments,
        "judgements": judgements, "model_calls": calls, "changes": len(CHANGES), "code_tests": tests,
        "v2": _rows("judgement_v2", "round", ns, data), "v3": _rows("judgement_v3", "round", ns, data),
        "kids": _rows("judgement_child", "kids", kid_ns),
        "v4": _rows("judgement_v4", "round", ns, data), "kids_v2": _rows("judgement_child_v2", "kids", kid_ns),
        "robotic": [{"round": n, "who": "Linda", **robotic_rate(data[n])} for n in ns]
                   + [{"round": n, "who": "Leo", **robotic_rate(load(n, "kids"))} for n in kid_ns],
        "v1_mean_best": mean([max((moment_score(m) for m in o["judgement"]["moments"]), default=0)
                              for o in data.get(1, {}).values() if o.get("judgement")]),
        "notion": [{"round": x["round"], "label": "right after creating the pages" if i == 0 else "",
                    "passed": x["passed"], "total": x["total"], "pages_seen": x["pages_seen"]} for i, x in enumerate(notion)],
        "links": {"passed": links["passed"], "total": links["total"]} if links else None,
        "apps": {"answered": sum(1 for a in apps[-1]["answers"] if a.get("kind") in ("schedule", "delivery", "none")),
                 "total": len(apps[-1]["answers"])} if apps else None,
        "change_log": CHANGES, "spend": spent(),
    }


def _report(inv: list[dict[str, Any]], ns: list[int], data: dict[int, dict[str, dict[str, Any]]], sums: list[dict[str, Any]],
            v1: list[dict[str, Any]], last: int) -> str:
    usable = [r for r in inv if not r["skipped"]]
    money = spent()
    out = ["# Reel Lab report", "",
           "*Generated by `python -m roleedge.lab report` from `output/reel-lab/`. The plan, the method and the log are in "
           "[../REEL_LAB.md](../REEL_LAB.md); every reel's evaluation is in [REELS.md](REELS.md) and the moments made "
           "are in [OUTPUTS.md](OUTPUTS.md).*", "",
           "## In short", "",
           f"- **{len(inv)} reels** in the source folder: **{len(usable)} usable**, {len(inv) - len(usable)} have no video "
           "(image or carousel posts), recorded with the reason.",
           f"- **{len(ns)} rounds** of the Studio's own agents on every usable reel, for Linda (79, English), each moment "
           f"scored 1-5 on five criteria by a Muse Wonder judge. The bar: a moment at {BAR} or more."]
    if sums:
        first, final = sums[0], sums[-1]
        out.append(f"- Rounds {first['round']}-{final['round']} (one to three moments per reel, judge v2): best moment per reel "
                   f"**{first['mean_best']} → {final['mean_best']}**, reels at the bar **{first['at_bar']} → {final['at_bar']}** "
                   f"of {final['judged']}, major findings **{first['majors']} → {final['majors']}**.")
    using("judgement_v3")
    full = [summary(n, data[n]) for n in ns if any(o.get("judgement_v3") for o in data[n].values())]
    using("judgement_v2")
    if len(full) >= 2:
        before, after = full[0], full[1:]
        out.append(f"- The full set from round 4 (a mind map, slides, a quiz, a video and a picture for every reel; judge v3): best "
                   f"moment per reel **{before['mean_best']} (round {before['round']}) → "
                   + " / ".join(f"{x['mean_best']} (round {x['round']})" for x in after)
                   + f"**, reels at the bar **{before['at_bar']} → " + " / ".join(str(x["at_bar"]) for x in after)
                   + f"**, every moment {' / '.join(str(x['pack_mean']) for x in after)}.")
    kid_rounds = [n for n in rounds("kids") if len(load(n, "kids")) == len(usable)]
    if kid_rounds:
        using("judgement_child")
        ks = [summary(n, load(n, "kids")) for n in kid_rounds]
        using("judgement_v2")
        out.append(f"- For Leo (9), the children's set: best moment per reel **{' → '.join(str(k['mean_best']) for k in ks)}**, "
                   f"reels at the bar **{' → '.join(str(k['at_bar']) for k in ks)}**; packs the safety review held for Maya: "
                   f"{' → '.join(str(k['held_for_child']) for k in ks)} (see below).")
    if v1:
        b = [max((moment_score(m) for m in o["judgement"]["moments"]), default=0) for o in v1]
        out.append(f"- The first judge was too harsh in ways that were its own fault (see J2): on the same round 1 moments it gave "
                   f"{mean(b)} where judge v2 gives {sums[0]['mean_best'] if sums else '-'}. Rounds 1-3 use judge v2, the full set judge v3 (J3), Leo's sets the children's judge.")
    out += [f"- Spent on the whole lab: **${money['total_usd']:.2f}** of the ${money['limit_usd']:.0f} limit "
            "(Meta tokens from the usage ledger, which includes the app's own earlier calls, plus Muse Voice Transcribe and "
            "Muse Image).", ""]

    out += ["## Rounds compared", "",
            "Best = the best moment of each reel; every moment = the mean over all moments made (from round 4 the full "
            "set: lead, mind map, slides, quiz, video, picture); weakest = the lowest moment of each reel.", "",
            "| Round | Reels | Moments | Mean best | At the bar | Every moment | Weakest | Major findings | Unsafe passed | Held by the gate | Called misleading | Cost | Mean time |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in sums:
        out.append(f"| {s['round']} | {s['judged']} | {s['moments']} | {s['mean_best']} | {s['at_bar']} | {s['pack_mean']} | {s['weakest']} | "
                   f"{s['majors']} | {s['unsafe_passed']} | {s['gate_held']} | {s['scam_verdicts']} | ${s['cost']:.2f} | {s['seconds']:.0f} s |")
    out += ["", "**Score by format** (moments made, mean of the five criteria):", "",
            "| Format | " + " | ".join(f"Round {s['round']}" for s in sums) + " |", "|---|" + "---|" * len(sums)]
    for f in sorted({f for s in sums for f in s["by_format"]}):
        cells = [f"{s['by_format'][f][1]} ({s['by_format'][f][0]})" if f in s["by_format"] else "-" for s in sums]
        out.append(f"| {f} | " + " | ".join(cells) + " |")
    out += ["", "**Major findings by cause** (where the fix belongs):", "",
            "| Cause | " + " | ".join(f"Round {s['round']}" for s in sums) + " |", "|---|" + "---|" * len(sums)]
    for c in ("prompt", "model", "tool", "workflow", "data"):
        out.append(f"| {c} | " + " | ".join(str(s["causes"].get(c, 0)) for s in sums) + " |")

    if len(ns) >= 2:
        a, b = data[ns[0]], data[ns[-1]]
        rows = []
        for rid in sorted(set(a) & set(b)):
            rows.append((rid, best(a[rid]), best(b[rid]), len(majors(a[rid])), len(majors(b[rid]))))
        up = sum(r[2] > r[1] for r in rows)
        down = sum(r[2] < r[1] for r in rows)
        out += ["", f"## Before and after, reel by reel (round {ns[0]} → round {ns[-1]})", "",
                f"{up} reels improved, {down} got worse, {len(rows) - up - down} unchanged.", "",
                "| Reel | Title | Best before | Best after | Majors before | Majors after |", "|---|---|---|---|---|---|"]
        titles = {r["id"]: r["title"] for r in inv}
        for rid, x, y, mx, my in rows:
            out.append(f"| {rid} | {_short(titles.get(rid, ''), 48)} | {x:.1f} | {y:.1f} | {mx} | {my} |")

    out += _full_set(data)
    out += _voice(ns, data)
    out += _kids()
    out += ["", "## Every change, and why", "",
            "| Id | Round | Cause | Where | Weakness found | Change |", "|---|---|---|---|---|---|"]
    for c in CHANGES:
        out.append(f"| {c['id']} | {c['round']} | {c['cause']} | {c['where']} | {c['weakness']} | {c['change']} |")

    out += ["", *_notion(), "", *_links(), "", *_apps(), "", *_costs(ns, data)]
    return "\n".join(out) + "\n"


def _full_set(data: dict[int, dict[str, dict[str, Any]]]) -> list[str]:
    """Round 3 (rescored with judge v3) against round 4, the full set, on the same judge."""
    using("judgement_v3")
    ns = [n for n in sorted(data) if any(o.get("judgement_v3") for o in data[n].values())]
    if not ns:
        using("judgement_v2")
        return []
    sums = [summary(n, data[n]) for n in ns]
    out = ["", "## The full set, as on the home page (judge v3)", "",
           "From round 4 every reel gets the whole set the home page shows: the moment its shape calls for, then a mind "
           "map, slides, a quiz, an animated video (with the reel's own stills) and a picture drawn by Muse Image. Judge "
           "v3 asks whether each moment uses its own format well; round 3 was scored again with it.", "",
           "| Round | Reels | Moments | Mean best | At the bar | Every moment | Weakest | Major findings | Unsafe passed | Held by the gate | Cost |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in sums:
        out.append(f"| {x['round']} | {x['judged']} | {x['moments']} | {x['mean_best']} | {x['at_bar']} | {x['pack_mean']} | {x['weakest']} | "
                   f"{x['majors']} | {x['unsafe_passed']} | {x['gate_held']} | ${x['cost']:.2f} |")
    out += ["", "| Format | " + " | ".join(f"Round {x['round']}" for x in sums) + " |", "|---|" + "---|" * len(sums)]
    for f in sorted({f for x in sums for f in x["by_format"]}):
        out.append(f"| {f} | " + " | ".join(f"{x['by_format'][f][1]} ({x['by_format'][f][0]})" if f in x["by_format"] else "-" for x in sums) + " |")
    crit: dict[int, dict[str, list[int]]] = {}
    for x in sums:
        per: dict[str, list[int]] = defaultdict(list)
        for o in data[x["round"]].values():
            for m in judged(o).get("moments", []):
                for k in CRITERIA:
                    per[k].append(m[k])
        crit[x["round"]] = per
    out += ["", "| Criterion | " + " | ".join(f"Round {x['round']}" for x in sums) + " |", "|---|" + "---|" * len(sums)]
    for k in CRITERIA:
        out.append(f"| {k} | " + " | ".join(str(mean(crit[x['round']][k])) for x in sums) + " |")
    using("judgement_v2")
    return out


def _voice(ns: list[int], data: dict[int, dict[str, dict[str, Any]]]) -> list[str]:
    """The family's voice: the user's review (2026-11-03) asked for the family talking, not a report about a reel.
    Measured twice: by code (robotic habits in every round) and by judge v4's sixth score, natural."""
    out = ["", "## The family's voice (the user's review, judge v4 and code)", "",
           "The moments sounded like a report about a reel (\"Mom, I am Maya, and I saved this for you. The reel says...\"), "
           "with disclaimers nobody needed. Round 6 rewrote the voice (C29-C33), round 7 taught it to explain like a person "
           "(C34). Two measures: code counts the robotic habits "
           "in every moment of every round (introducing the sender, narrating the reel, disclaimers, labels about the reel); "
           "judge v4 adds a sixth score, natural, and round 5 was scored again with it.", "",
           "| Round | Moments | With a robotic habit | Share |", "|---|---|---|---|"]
    for n in ns:
        r = robotic_rate(data[n])
        out.append(f"| {n} | {r['moments']} | {r['with_habit']} | {r['rate']:.0%} |")
    using("judgement_v4")
    v4 = [n for n in ns if any(o.get("judgement_v4") for o in data[n].values())]
    if v4:
        sums = [summary(n, data[n]) for n in v4]
        crits = {n: _criteria(data[n]) for n in v4}
        out += ["", "| Round (judge v4) | Reels | Mean best | At the bar | Every moment | Natural | Major findings |", "|---|---|---|---|---|---|---|"]
        for x in sums:
            out.append(f"| {x['round']} | {x['judged']} | {x['mean_best']} | {x['at_bar']} | {x['pack_mean']} | "
                       f"{crits[x['round']].get('natural', '-')} | {x['majors']} |")
    using("judgement_v2")
    return out


def _kids() -> list[str]:
    ns = rounds("kids")
    if not ns:
        return []
    using("judgement_child")
    out = ["", "## The same reels for a child (Leo, 9)", "",
           "The full children's set from each reel (a picture story, a quiz game, an animated video, a mind map and a "
           "picture), made by the same agents for Leo and scored by a children's judge (Muse Wonder, safety first). "
           "Every pack also went through the child-safety review; a pack it doesn't pass is held for Maya.", "",
           "| Round | Reels | Moments | Mean best | At the bar | Every moment | Weakest | Major findings | Held for Maya by the safety review | Cost |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for n in ns:
        s = summary(n, load(n, "kids"))
        out.append(f"| {n} | {s['judged']} | {s['moments']} | {s['mean_best']} | {s['at_bar']} | {s['pack_mean']} | {s['weakest']} | "
                   f"{s['majors']} | {s['held_for_child']} | ${s['cost']:.2f} |")
    last = summary(ns[-1], load(ns[-1], "kids"))
    out += ["", "| Format | Moments | Score |", "|---|---|---|"]
    for f, (count, score) in last["by_format"].items():
        out.append(f"| {f} | {count} | {score} |")
    using("judgement_v2")
    return out


def _notion() -> list[str]:
    d = LAB / "notion"
    out = ["## Notion"]
    inspect = json.loads((d / "inspect.json").read_text()) if (d / "inspect.json").exists() else {}
    if inspect:
        out += ["", f"**The integration** (inspected through the API, counts only): token valid (HTTP {inspect.get('auth')}), "
                f"an internal integration owned by a user; it can see {inspect.get('pages')} pages and "
                f"{inspect.get('databases')} databases. {inspect.get('pages_in_reels_db')} pages are rows of the reels "
                f"database; {inspect.get('pages_elsewhere')} belongs to another database, which the lab did not read. "
                f"No plain page is shared with it ({inspect.get('plain_pages')}), so the three test pages were created as "
                "rows of the reels database, titled \"[RoleEdge test]\", with synthetic data only. Creating them succeeded, "
                "so the integration has insert permission as well as read."]
    for path in sorted(d.glob("round-*.json")):
        r = json.loads(path.read_text())
        label = path.stem.replace("round-", "Round ").replace("-search-lag", " (right after creating the pages: search had not listed them yet)")
        out += ["", f"**{label}**: {r['passed']}/{r['total']} passed, {r['pages_seen']} pages seen, ${r['cost']['usd']:.4f}.", "",
                "| Scenario | Kind | Passed | Pages it used | Answer |", "|---|---|---|---|---|"]
        for s in r["results"]:
            out.append(f"| {s['id']} | {s['kind']} | {'yes' if s['passed'] else 'no'} | {_short(', '.join(s.get('picked') or []), 60)} | "
                       f"{_short((s.get('answer') or {}).get('answer_en', s.get('error', '')), 110)} |")
    out += ["", "Every answer is checked by code: the found flag, the expected terms, the pages cited, and every quote found "
            "word for word in the page it cites (an invented quote fails). The two \"isn't there\" questions (a hotel "
            "Wi-Fi password, a return train) must come back as not found, with nothing invented."]
    return out


def _links() -> list[str]:
    path = LAB / "links" / "results.json"
    if not path.exists():
        return []
    r = json.loads(path.read_text())
    out = ["## Reel and post links", "",
           f"A reel shared as a link is downloaded with its caption (`content/social.py`) and then watched like an attached "
           f"video. On the source folder's links: **{r['passed']}/{r['total']}** behaved as expected (a video for a reel; for a "
           "photo post, the message to attach the pictures). No login, no browser imitation, only the video sites' own "
           "extractors.", "", "| Link | Expected | Video | Size | Codec | Caption matches | Message |", "|---|---|---|---|---|---|---|"]
    for x in r["results"]:
        out.append(f"| {x['id']} | {x['expected']} | {'yes' if x['video'] else 'no'} | {x['mb']} MB | {x['codec'] or '-'} | "
                   f"{'yes' if x['caption_matches'] else 'no'} | {x['problem'] or '-'} |")
    return out


def _apps() -> list[str]:
    out = ["## Demo Gmail, Slack, Zoom and Google Calendar you can add to", "",
           "Items added in the Studio's Apps panel (Add) are stored per circle and picked up by the agents like anything "
           "already there. Tested end to end on a test server with real Meta calls:"]
    for path in sorted((LAB / "apps").glob("e2e-*.json")):
        r = json.loads(path.read_text())
        out += ["", "| Her question | Answered by | What she heard | From |", "|---|---|---|---|"]
        for a in r["answers"]:
            used = ", ".join(u.get("title") or u.get("subject", "") for u in a.get("used") or [])
            out.append(f"| {a['q']} | {a.get('kind')} | {_short(a.get('said', ''), 100)} | {_short(used, 50)} |")
    out += ["", "The work event added (\"Performance review with HR about my promotion\") reached the model only as "
            "\"busy\" with its time: its title and room never left code. The dentist question had no calendar entry; the "
            "router left it for Maya instead of guessing. Real sign-in: see [INTEGRATIONS.md](INTEGRATIONS.md)."]
    return out


def _costs(ns: list[int], data: dict[int, dict[str, dict[str, Any]]]) -> list[str]:
    out = ["## Costs", "",
           "Per call from the usage ledgers (Muse Spark contributor $0.10 / $0.20 per 1M tokens in / out, Muse Wonder $4 / "
           "$20), plus Muse Voice Transcribe at $0.18 an audio hour. Calls replayed from the cache cost nothing and are not "
           "counted; a round only pays for the agents whose input changed.", "",
           "| Reel | " + " | ".join([*(f"Round {n}" for n in ns), *(f"Leo {n}" for n in rounds("kids"))]) + " | Total |",
           "|---|" + "---|" * (len(ns) + len(rounds("kids")) + 1)]
    columns = [*(data[n] for n in ns), *(load(n, "kids") for n in rounds("kids"))]
    ids = sorted({rid for column in columns for rid in column})
    totals = [0.0] * len(columns)
    for rid in ids:
        cells = []
        for k, column in enumerate(columns):
            c = round_cost(column[rid]) if rid in column else 0.0
            totals[k] += c
            cells.append(f"${c:.3f}")
        out.append(f"| {rid} | " + " | ".join(cells) + f" | ${sum(float(x[1:]) for x in cells):.3f} |")
    out.append("| **All reels** | " + " | ".join(f"**${t:.2f}**" for t in totals) + f" | **${sum(totals):.2f}** |")
    by_agent: Counter[str] = Counter()
    for path in LAB.glob("*/ledger-*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if not row.get("replayed_from_cache"):
                by_agent[row["task"]] += dollars(Usage.from_dict(row), PRICE_BY_MODEL.get(row.get("model", ""), UNKNOWN_PRICE))
    out += ["", "**By agent** (all lab ledgers):", "", "| Agent | Cost |", "|---|---|"]
    for task, usd in by_agent.most_common():
        out.append(f"| {task} | ${usd:.3f} |")
    money = spent()
    out += ["", f"**Whole lab so far:** ${money['total_usd']:.2f} (Meta tokens ${money['meta_usd']:.2f}, transcription "
            f"${money['transcribe_usd']:.2f}, pictures ${money['images_usd']:.2f}) of the ${money['limit_usd']:.0f} limit."]
    return out


def _reels(inv: list[dict[str, Any]], ns: list[int], data: dict[int, dict[str, dict[str, Any]]]) -> str:
    out = ["# Every reel, evaluated", "",
           "*Generated by `python -m roleedge.lab report`. Technical measures come from ffmpeg (first 90 seconds); bands "
           "are defined in [../REEL_LAB.md](../REEL_LAB.md). Scores are judge v2, the best moment of each round.*", ""]
    for row in inv:
        out.append(f"## {row['id']}: {_short(row['title'], 80)}")
        out.append("")
        if row["skipped"]:
            out += [f"**Skipped:** {row['skipped']}", ""]
            continue
        p = row.get("probe", {})
        latest = data[ns[-1]].get(row["id"], {}) if ns else {}
        t = latest.get("transcript") or {}
        prof = latest.get("profile") or {}
        reading = (latest.get("research") or {}).get("reading") or {}
        out += [f"- **Video:** {p.get('duration_s')} s, {p.get('width')}x{p.get('height')}, {p.get('fps')} fps; sharpness "
                f"{p.get('blurry_share')} of frames blurry, brightness {p.get('brightness')}, frozen {p.get('frozen_share')}, "
                f"{p.get('cuts_per_10s')} cuts per 10 s.",
                f"- **Audio:** {'yes' if p.get('audio') else 'none'}, {p.get('loudness_lufs')} LUFS, silence {p.get('silence_share')}. "
                f"Bands: {_bands(p)}.",
                f"- **Transcription:** {t.get('words', 0)} words ({t.get('wpm', 0)} a minute), agreement with the earlier "
                f"transcript: {_agreement(t)}." + (f" Error: {t['error']}" if t.get("error") else ""),
                f"- **What it is:** {prof.get('content_type', '-')}: {prof.get('topic_en', '')}. "
                f"{'Worth explaining' if prof.get('worth_explaining') else 'Little to explain'}: {prof.get('reason_en', '')}"
                + (f" Risks: {'; '.join(prof['risks_en'])}." if prof.get("risks_en") else ""),
                f"- **Visual reading:** {_short(reading.get('summary_en', ''), 300)} ({len(reading.get('facts_en', []))} facts"
                + (f", {len(reading['pictures_en'])} frames described" if reading.get("pictures_en") else "") + ")",
                ""]
        out += ["| Round | Judge | Fact check | Formats made | Judge's best format | Best | Majors | Gate | Cost |",
                "|---|---|---|---|---|---|---|---|---|"]
        for n in ns:
            o = data[n].get(row["id"])
            if not o:
                continue
            using(latest_key(o))
            j = judged(o)
            scores = ", ".join(f"{m['format']} {moment_score(m):.1f}" for m in j.get("moments", []))
            out.append(f"| {n} | {JUDGE_KEY.split('_')[-1]} | {(o.get('research') or {}).get('fact_check', {}).get('verdict', '-')} | {scores or ', '.join(o.get('formats') or [])} | "
                       f"{j.get('best_format', '-')} | {best(o):.1f} | {len(majors(o))} | "
                       f"{'passed' if (o.get('gate') or {}).get('passed') else 'held'} | ${round_cost(o):.3f} |")
        using(latest_key(latest))
        left = majors(latest)
        using("judgement_v2")
        if left:
            out += ["", "Still falling short (latest round, major):"]
            out += [f"- {p['format']} ({p['cause']}): {_short(p['problem_en'], 220)}" for p in left[:5]]
        if latest.get("error"):
            out += ["", f"Error: {latest['error']}"]
        out.append("")
    return "\n".join(out) + "\n"


def _outputs(inv: list[dict[str, Any]], data: dict[str, dict[str, Any]], n: int, who: str = "Linda (79)") -> str:
    out = [f"# The moments made for {who}, reel by reel", "",
           f"*Round {n}. Generated by `python -m roleedge.lab report`; see them drawn at `/lab`; the full JSON is in "
           "`output/reel-lab/<reel id>/`. A picture is drawn by Muse Image from its description when the caregiver makes "
           "it in the Studio; a video scene marked with a still shows that frame of the reel behind its words.*", ""]
    for row in inv:
        o = data.get(row["id"])
        if not o or not o.get("outputs"):
            continue
        pictures = ((o.get("research") or {}).get("reading") or {}).get("pictures_en", [])
        scores = {m["format"]: moment_score(m) for m in (o.get(latest_key(o)) or {}).get("moments", [])}
        out += [f"## {row['id']}: {_short(row['title'], 80)}", ""]
        for fmt, moment in o["outputs"].items():
            out.append(f"### {fmt}" + (f" (judge {scores[fmt]:.1f})" if fmt in scores else ""))
            out.append("")
            out += [line for line in moment_text(fmt, moment, pictures)]
            out.append("")
    return "\n".join(out) + "\n"


def paths() -> list[Path]:
    return [REPORT_DIR / name for name in ("REPORT.md", "REELS.md", "OUTPUTS.md")]
