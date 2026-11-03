"""Command line: ``roleedge <command>`` (or ``python -m roleedge <command>``).

    check                 confirm each configured provider's key works (tiny request)
    ask QUESTION [--file] one-off question, optionally about the start of a text/CSV file
    chat                  run the chat playground at http://127.0.0.1:8000
    samples [--force]     create the synthetic media samples
    content [CASE ...]    shared item -> digest -> checker      (output/content/<case>/digest.json)
    render [CASE ...]     digest -> card, explainer video, calendar, article
    checkin [SCENARIO ...] simulate daily check-in calls        (output/checkin/)
    mock                  caregiver view + "what Mummy sees" mock (output/mock/screens.png)
    costs                 measured cost per item / per call     (output/costs.json)
    all                   samples -> content -> render -> checkin -> mock -> costs

Model calls are cached in .cache/llm, so re-running is free and repeatable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, get_settings


def cmd_check(_: argparse.Namespace) -> int:
    from .llm import ProviderError, configured_providers

    providers = configured_providers()
    if not providers:
        print("No providers configured. Copy .env.example to .env and fill it in.")
        return 1
    ok = True
    for name, provider in providers.items():
        try:
            reply = provider.check()
            print(f"OK    {name:6s} model={reply.model} reply={reply.text!r} usage={reply.usage.to_dict()}")
        except ProviderError as exc:
            ok = False
            print(f"FAIL  {name:6s} {exc}")
    settings = get_settings()
    if not settings.meta:
        print("info  meta   not configured (META_API_KEY unset) - skipped")
    return 0 if ok else 1


def cmd_ask(args: argparse.Namespace) -> int:
    from .llm import get_provider

    provider = get_provider(args.provider or get_settings().pipeline_provider)
    prompt = args.question
    if args.file:
        sample = Path(args.file).read_text(encoding="utf-8")[: args.max_chars]
        sample = sample[: sample.rfind("\n") + 1] or sample  # cut at the last full line
        prompt = f"Here is the start of the file '{Path(args.file).name}':\n\n{sample}\n\nQuestion: {args.question}"
    reply = provider.chat([{"role": "user", "content": prompt}], model=args.model, effort=args.effort,
                          max_output_tokens=args.max_output_tokens)
    print(f"--- {provider.name} {reply.model} | usage: {reply.usage.to_dict()}" + (f" | {reply.note}" if reply.note else ""))
    print(reply.text)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("roleedge.chat.app:create_app", factory=True, host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_samples(args: argparse.Namespace) -> int:
    from .samples import ensure_samples

    made = ensure_samples(force=args.force)
    print("\n".join(str(p) for p in made) or "samples already present (use --force to rebuild)")
    return 0


def _pipeline_llm():
    from .llm import LLM, pipeline_provider

    return LLM(pipeline_provider())


def cmd_content(args: argparse.Namespace) -> int:
    from . import content
    from .demo import CONTENT_CASES, RECIPIENTS, TODAY

    llm = _pipeline_llm()
    for case in CONTENT_CASES:
        if args.cases and case.id not in args.cases:
            continue
        record = content.transform(llm, case.id, case.description, case.build(), case.recipient,
                                   RECIPIENTS[case.recipient], TODAY)
        content.save(record)
        print(content.summary_line(record))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from .content import CONTENT_DIR, load
    from .demo import RECIPIENTS
    from .render import HtmlRenderer, render_record

    stats_file = CONTENT_DIR.parent / "render_timings.json"
    stats = json.loads(stats_file.read_text()) if stats_file.exists() else {}
    with HtmlRenderer() as renderer:
        for case_dir in sorted(d for d in CONTENT_DIR.iterdir() if (d / "digest.json").exists()):
            if args.cases and case_dir.name not in args.cases:
                continue
            record = load(case_dir.name)
            stats[record.case] = render_record(renderer, record, RECIPIENTS[record.recipient], case_dir)
            print(record.case, stats[record.case])
    stats_file.write_text(json.dumps(stats, indent=2))
    return 0


def cmd_checkin(args: argparse.Namespace) -> int:
    from . import checkin
    from .demo import FAMILIES

    llm = _pipeline_llm()
    for family in FAMILIES.values():
        for name, scenario in family.calls.items():
            if args.scenarios and name not in args.scenarios:
                continue
            record = checkin.run_call(llm, family.care_plan, name, scenario)
            checkin.save(record)
            print(checkin.summary_line(record))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.reset:
        from .families import CIRCLES, history
        from .store import Store

        Store().reset(CIRCLES.values(), history)
    print(f"roleEdge: http://{args.host}:{args.port}/  (parent's phone: /phone/sato or /phone/chen)")
    uvicorn.run("roleedge.app.server:create_app", factory=True, host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_avatar(args: argparse.Namespace) -> int:
    from .avatar import build_avatar
    from .config import get_settings
    from .llm.meta_media import MetaMedia

    meta = get_settings().meta
    if meta is None:
        raise ConfigError("Building an avatar needs META_API_KEY (Muse Image and SAM 3.1).")
    base = Path(args.photo).read_bytes() if args.photo else None
    result = build_avatar(MetaMedia(meta), args.person, base_image=base, style=args.style,
                          folder_name=args.person if args.style == "character" else f"{args.person}-{args.style}")
    for step in result["steps"]:
        print(f"{step['s']:>5.1f}s  {step['engine']:<22} {step['step']}")
    return 0


def cmd_mock(_: argparse.Namespace) -> int:
    from .demo import RECIPIENTS
    from .mock import build

    print(build(RECIPIENTS["mummy"]))
    return 0


def cmd_costs(_: argparse.Namespace) -> int:
    from .costs import build_report

    print(json.dumps(build_report(), indent=2))
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    empty = argparse.Namespace(cases=[], scenarios=[], force=False)
    for step in (cmd_samples, cmd_content, cmd_render, cmd_checkin, cmd_mock, cmd_costs):
        print(f"\n== {step.__name__.removeprefix('cmd_')}")
        if step(empty):
            return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="roleedge", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="check provider keys").set_defaults(func=cmd_check)

    ask = sub.add_parser("ask", help="one-off question")
    ask.add_argument("question")
    ask.add_argument("--file", help="text/CSV file; its first --max-chars characters are included")
    ask.add_argument("--max-chars", type=int, default=10000)
    ask.add_argument("--provider", choices=["azure", "meta"])
    ask.add_argument("--model")
    ask.add_argument("--effort", default="low")
    ask.add_argument("--max-output-tokens", type=int, default=2000)
    ask.set_defaults(func=cmd_ask)

    chat = sub.add_parser("chat", help="run the chat playground")
    chat.add_argument("--host", default="127.0.0.1")
    chat.add_argument("--port", type=int, default=8000)
    chat.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    chat.set_defaults(func=cmd_chat)

    serve = sub.add_parser("serve", help="run the roleEdge app (caregiver workspace and the parent's phone)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8100)
    serve.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    serve.add_argument("--reset", action="store_true", help="reload the demo circles and their six-week history")
    serve.set_defaults(func=cmd_serve)

    avatar = sub.add_parser("avatar", help="build a talking avatar with Muse Image and SAM 3.1")
    avatar.add_argument("person", help="member id, e.g. kenji or maya")
    avatar.add_argument("--photo", help="animate this portrait (with the person's consent) instead of drawing one")
    avatar.add_argument("--style", choices=["character", "photo"], default="character",
                        help="character = stylized 3D-look avatar (default); photo = photorealistic portrait")
    avatar.set_defaults(func=cmd_avatar)

    samples = sub.add_parser("samples", help="create synthetic media samples")
    samples.add_argument("--force", action="store_true")
    samples.set_defaults(func=cmd_samples)

    for name, func, help_text in (("content", cmd_content, "run the content transformer"),
                                  ("render", cmd_render, "render digests into cards, videos, calendars")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("cases", nargs="*", help="case ids (default: all)")
        p.set_defaults(func=func)

    checkin = sub.add_parser("checkin", help="simulate check-in calls")
    checkin.add_argument("scenarios", nargs="*", help="scenario names (default: all)")
    checkin.set_defaults(func=cmd_checkin)

    sub.add_parser("mock", help="build the mock screens").set_defaults(func=cmd_mock)
    sub.add_parser("costs", help="compute costs from outputs").set_defaults(func=cmd_costs)
    sub.add_parser("all", help="run every feasibility step").set_defaults(func=cmd_all)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
