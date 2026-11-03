"""The scam checker's local steps. Each one is started by hand; README.md has the full runbook.

    python -m scamcheck estimate [--rounds N]        what `generate` will do and cost (free)
    python -m scamcheck generate [--rounds N]        Muse Spark writes and checks messages (Meta, cents per round)
    python -m scamcheck build                        merge synthetic + your cases + real -> data/final (free)
    python -m scamcheck report                       the comparison table from results/*.json (free)
"""

from __future__ import annotations

import argparse
import json
import re

from . import build as build_
from . import generate as gen
from .meta_api import MetaAPI, spend
from .metrics import table

DATA, RESULTS = build_.DATA, build_.ROOT / "results"


def _next_round() -> int:
    """The first round not generated yet, so each `generate` adds new batches instead of repeating old ones."""
    ends = [int(m.group(1)) for p in (DATA / "synthetic").glob("spark_rounds_*.jsonl")
            if (m := re.search(r"-(\d+)\.jsonl$", p.name))]
    return max(ends) + 1 if ends else 0


def cmd_estimate(args: argparse.Namespace) -> int:
    e = gen.estimate(args.rounds, args.per)
    print(f"Rounds {args.start if args.start is not None else _next_round()} onwards: {e['write_calls']} calls to write "
          f"+ about {e['check_calls']} to check, {args.workers} at a time")
    print(f"About {e['messages_before_checks']:,} messages before checks; about ${e['usd']:.2f} "
          f"({e['tokens_in']:,} tokens in, {e['tokens_out']:,} out)")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    cmd_estimate(args)
    if not args.yes and input("Call Muse Spark now? [y/N] ").strip().lower() not in ("y", "yes"):
        return 1
    start = args.start if args.start is not None else _next_round()
    path, stats = gen.run(MetaAPI(), DATA / "synthetic", args.rounds, start, args.per, args.workers)
    print(json.dumps(stats, indent=1))
    print(f"Wrote {path}. Spent so far: {spend()}")
    print("Next: python -m scamcheck build")
    return 0


def cmd_build(_: argparse.Namespace) -> int:
    stats, problems = build_.build()
    for p in problems[:50]:
        print("SKIPPED", p)
    if len(problems) > 50:
        print(f"... and {len(problems) - 50} more")
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    print(f"Wrote {DATA / 'final'}")
    return 0


def cmd_report(_: argparse.Namespace) -> int:
    found = sorted(RESULTS.glob("*.json"))
    if not found:
        print(f"No results yet in {RESULTS}: run an evaluation first (README.md, step 7).")
        return 1
    print(table({(d := json.loads(p.read_text(encoding="utf-8")))["model"]: d["scores"] for p in found}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scamcheck", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("estimate", "generate"):
        p = sub.add_parser(name)
        p.add_argument("--rounds", type=int, default=5, help="rounds to add; each is 21 batches (default 5)")
        p.add_argument("--start", type=int, help="first round number (default: after the last one generated)")
        p.add_argument("--per", type=int, default=20, help="messages per batch (default 20)")
        p.add_argument("--workers", type=int, default=8, help="Muse Spark calls at a time (default 8)")
        p.add_argument("--yes", action="store_true", help="don't ask before calling Muse Spark")
    sub.add_parser("build")
    sub.add_parser("report")
    args = parser.parse_args(argv)
    return {"estimate": cmd_estimate, "generate": cmd_generate, "build": cmd_build, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
