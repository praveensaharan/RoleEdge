"""python -m roleedge.lab inventory | round N [reel ids...] | kids N [reel ids...] | rejudge N [judge version] [round|kids] | notion inspect|create|run N|trash | links | dataset | report"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> None:
    command = argv[0] if argv else "report"
    if command == "inventory":
        from .inventory import save_inventory

        rows = save_inventory()
        print(f"{len(rows)} reels, {sum(1 for r in rows if r['skipped'])} without a video")
    elif command in ("round", "kids"):
        from .rounds import run_all

        n, ids = int(argv[1]), argv[2:] or None
        for out in run_all(n, ids, kids=command == "kids"):
            judged = (out.get("judgement_v4") or out.get("judgement_child_v2") or out.get("judgement_v3") or out.get("judgement_child")
                      or out.get("judgement_v2") or out.get("judgement") or {})
            scores = judged.get("moments", [])
            best = max((sum(m[k] for k in ("faithful", "clear", "engaging", "useful", "format_fit")) / 5 for m in scores), default=0)
            print(f"{out['reel']}: {','.join(out.get('formats') or [])} best {best:.1f} ${out['cost']['usd']:.3f} "
                  f"{out['seconds']}s {out.get('error') or out.get('skipped') or ''}", flush=True)
    elif command == "rejudge":
        from .rounds import rejudge

        version = argv[2] if len(argv) > 2 else "2"
        kind = argv[3] if len(argv) > 3 else "round"
        for line in rejudge(int(argv[1]), int(version) if version.isdigit() else version, kind=kind):
            print(line, flush=True)
    elif command == "notion":
        from . import notion

        step = argv[1] if len(argv) > 1 else "inspect"
        if step == "inspect":
            print(notion.inspect())
        elif step == "create":
            print(notion.create_test_pages())
        elif step == "run":
            out = notion.run_scenarios(int(argv[2]), limit=int(argv[3]) if len(argv) > 3 else 100)
            print(f"{out['passed']}/{out['total']} passed, {out['pages_seen']} pages seen, ${out['cost']['usd']:.4f}")
            for r in out["results"]:
                print(f"  {r['id']}: {'pass' if r['passed'] else 'FAIL'} {r.get('checks') or r.get('error')}")
        elif step == "trash":
            print(notion.trash_test_pages())
    elif command == "links":
        from .links import run_links

        out = run_links(argv[1:] or None)
        print(f"{out['passed']}/{out['total']} links behaved as expected")
        for r in out["results"]:
            print(f"  {r['id']} {r['expected']}: {'ok' if r['passed'] else 'FAIL'} {r['mb']} MB {r['codec']} {r['problem']}")
    elif command == "dataset":
        from .dataset import write_dataset

        print(write_dataset())
    elif command == "report":
        from .report import write_report

        print(write_report())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
