"""The tuned child guard's steps, each started by hand (docs/GUARD.md has the full runbook).

    python -m roleedge.guard_cli estimate          what `data` will do and roughly cost (free, calls nothing)
    python -m roleedge.guard_cli data              Muse Spark writes and checks the training data (Meta, cents)
    python -m roleedge.guard_cli real              adds real lines from Hana's and Leo's packs to the test set (free)
    python -m roleedge.guard_cli spark-eval        today's Muse Spark guardian on the test set (Meta, cents)
    python -m roleedge.guard_cli report [--write]  the comparison table; --write puts it in docs/FINDINGS.md
    python -m roleedge.guard_cli check             one call to the deployed guard (wakes its GPU briefly)
    python -m roleedge.guard_cli modal ...         the Modal CLI, signed in with the Modal token from .env

Training, evaluation and serving on the GPU are `modal run` / `modal deploy` of modal_apps/guard_lora.py through
the `modal` command above. Nothing here runs on its own.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR, REPO_ROOT, get_settings
from .families import CIRCLES
from .guard import Verdict, tuned_guard_from_settings
from .guard import data as guard_data
from .guard.metrics import save_eval, table
from .llm import LLM, get_provider
from .models.studio import ChildCheck
from .store import Store
from .studio.agents import CHILD_GUARD, fields
from .studio.verify import recipient_texts

GUARD_DIR = OUTPUT_DIR / "guard"
DATA_DIR = GUARD_DIR / "data"
EVAL_DIR = GUARD_DIR / "eval"
FINDINGS = REPO_ROOT / "docs" / "FINDINGS.md"
BEGIN, END = "<!-- guard-results:begin -->", "<!-- guard-results:end -->"
PRICE_IN, PRICE_OUT = 0.10, 0.20  # USD per 1M tokens, muse-spark-1.3-contributor (costs.PRICE_BY_MODEL)


def _meta_llm() -> LLM:
    return LLM(get_provider("meta"))  # synthetic lines only, so the contributor model is fine


def _confirm(question: str, yes: bool) -> bool:
    if yes:
        return True
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def cmd_estimate(args: argparse.Namespace) -> int:
    e = guard_data.estimate(args.rounds, args.per)
    usd = e["tokens_in"] / 1e6 * PRICE_IN + e["tokens_out"] / 1e6 * PRICE_OUT
    print(f"Muse Spark calls: {e['write_calls']} to write + about {e['check_calls']} to check")
    print(f"Lines before checks: about {e['lines_before_checks']} (duplicates and lines the blind check disagrees with are dropped)")
    print(f"Tokens: about {e['tokens_in']:,} in, {e['tokens_out']:,} out  ->  about ${usd:.2f} at contributor prices")
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    cmd_estimate(args)
    if not _confirm("Write the training data with Muse Spark now?", args.yes):
        return 1
    splits, stats = guard_data.build(_meta_llm(), rounds=args.rounds, per_request=args.per)
    for name, rows in splits.items():
        guard_data.save_jsonl(DATA_DIR / f"{name}.jsonl", rows)
    (DATA_DIR / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))
    print(f"Wrote {DATA_DIR}/train.jsonl, val.jsonl, test.jsonl")
    return 0


def real_rows(store: Store) -> list[dict[str, Any]]:
    """Lines from finished packs for the demo children that passed review: extra safe test rows."""
    rows = []
    for circle in store.circles():
        children = {c.id: c for c in circle.children}
        for item in store.items(circle.id):
            p = item.payload
            child = children.get(p.get("recipient", ""))
            if item.kind != "studio" or child is None or not p.get("outputs") or not (p.get("guardian") or {}).get("safe_for_child"):
                continue
            lines = [*recipient_texts(p["outputs"]), (p.get("plan") or {}).get("conversation_starter", "")]
            rows += [{"text": " ".join(t.split()), "safe": True, "categories": [], "lang": child.language, "age": child.age,
                      "target": "real", "round": -1, "source": "real"} for t in lines if t.strip()]
    return guard_data.dedupe(rows)


def cmd_real(_: argparse.Namespace) -> int:
    rows = real_rows(Store())
    guard_data.save_jsonl(DATA_DIR / "real.jsonl", rows)
    print(f"{len(rows)} real lines from children's packs -> {DATA_DIR / 'real.jsonl'}")
    return 0


def test_rows() -> list[dict[str, Any]]:
    rows = guard_data.load_jsonl(DATA_DIR / "test.jsonl")
    real = DATA_DIR / "real.jsonl"
    return rows + (guard_data.load_jsonl(real) if real.exists() else [])


def spark_verdict(llm: LLM, row: dict[str, Any]) -> Verdict:
    """Today's Muse Spark guardian (CHILD_GUARD) on one line, exactly as the Studio asks it."""
    circle = CIRCLES["sato" if row.get("lang") == "ja" else "chen"]
    child = circle.children[0]
    messages = [{"role": "system", "content": CHILD_GUARD.system.format(**fields(circle, child))},
                {"role": "user", "content": f"The pack, line by line:\n- {row['text']}"}]
    try:
        result = llm.complete_json(CHILD_GUARD.id, messages, ChildCheck, "child_guardian", effort=CHILD_GUARD.effort)
        return Verdict(safe=ChildCheck.model_validate(result.data).safe_for_child)
    except Exception:
        return Verdict(safe=False, parsed=False)


def cmd_spark_eval(args: argparse.Namespace) -> int:
    rows = test_rows()
    print(f"{len(rows)} test lines, one Muse Spark call each (about ${len(rows) * 900 / 1e6 * PRICE_IN + len(rows) * 120 / 1e6 * PRICE_OUT:.2f})")
    if not _confirm("Run the Muse Spark guardian on the test set now?", args.yes):
        return 1
    llm = _meta_llm()
    with ThreadPoolExecutor(5) as pool:
        verdicts = list(pool.map(lambda r: spark_verdict(llm, r), rows))
    scores = save_eval(EVAL_DIR / "spark.json", "Muse Spark prompt (today)", llm.engine, rows, verdicts)
    print(table({"Muse Spark prompt (today)": scores}))
    return 0


def results() -> dict[str, dict[str, Any]]:
    order = {"base": 0, "spark": 2}
    found = sorted(EVAL_DIR.glob("*.json"), key=lambda p: (order.get(p.stem, 1), p.stem))
    return {json.loads(p.read_text())["name"]: json.loads(p.read_text())["scores"] for p in found}


def cmd_report(args: argparse.Namespace) -> int:
    found = results()
    if not found:
        print(f"No results yet in {EVAL_DIR}: run the evaluations first (docs/GUARD.md).")
        return 1
    text = table(found)
    print(text)
    if args.write:
        doc = FINDINGS.read_text(encoding="utf-8")
        if BEGIN not in doc or END not in doc:
            print(f"No results block in {FINDINGS}.")
            return 1
        head, rest = doc.split(BEGIN, 1)
        FINDINGS.write_text(f"{head}{BEGIN}\n{text}\n{END}{rest.split(END, 1)[1]}", encoding="utf-8")
        print(f"Updated {FINDINGS}")
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    guard = tuned_guard_from_settings()
    if guard is None:
        print("Set ROLEEDGE_GUARD_URL and ROLEEDGE_GUARD_KEY in .env first (docs/GUARD.md, step 6).")
        return 1
    lines = ["Let's count the stars together tonight.", "Tell me your school name and I'll send you a prize!"]
    for line, verdict in zip(lines, guard.classify(lines, 9, "en"), strict=True):
        print(f"{'safe  ' if verdict.safe else 'UNSAFE'} {', '.join(verdict.names):<40} {line}")
    return 0


def cmd_modal(args: argparse.Namespace) -> int:
    """The Modal CLI with this project's token (the CLI doesn't read .env; get_settings puts the token in the
    environment of this process only)."""
    if get_settings().modal is None:
        print("Add MODAL_TOKEN_ID and MODAL_TOKEN_SECRET to .env first.")
        return 1
    modal = str(Path(sys.executable).with_name("modal"))
    os.chdir(REPO_ROOT)
    os.execv(modal, [modal, *args.rest])
    return 0  # not reached


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m roleedge.guard_cli", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("estimate", "data"):
        p = sub.add_parser(name)
        p.add_argument("--rounds", type=int, default=4, help="batches per language and target (default 4)")
        p.add_argument("--per", type=int, default=24, help="lines per batch (default 24)")
        p.add_argument("--yes", action="store_true", help="don't ask before calling Muse Spark")
    sub.add_parser("real")
    sub.add_parser("spark-eval").add_argument("--yes", action="store_true")
    sub.add_parser("report").add_argument("--write", action="store_true")
    sub.add_parser("check")
    sub.add_parser("modal").add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    handlers = {"estimate": cmd_estimate, "data": cmd_data, "real": cmd_real, "spark-eval": cmd_spark_eval,
                "report": cmd_report, "check": cmd_check, "modal": cmd_modal}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
