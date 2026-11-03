"""Phases 3-6: understand each reel, then run rounds of the Studio's agents on it and judge every moment.

A round runs the product's own swarm (reader, web search, fact checker, audience, context, planner, one maker per
moment, the verifier) exactly as the Studio does, for the English parent (Linda, 79). The moments it makes are the
planner's recommended ones plus the profiler's first choice, so every content type is tested in the format it should
get. Every call goes through the shared cache (an unchanged prompt costs nothing the second time) and a ledger of its
own, so each reel's cost is known per round.
"""

from __future__ import annotations

import copy
import difflib
import json
import re
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..app.audio import file_to_wav
from ..app.studio_routes import PARENT_PICTURE_STYLE
from ..config import LEDGER_FILE, get_settings
from ..content.ingest import spread_frames
from ..costs import PRICE_BY_MODEL, UNKNOWN_PRICE, dollars
from ..families import CIRCLES
from ..llm import LLM
from ..llm.meta_media import MetaMedia
from ..llm.providers import pipeline_provider
from ..llm.types import Usage
from ..models.studio import PARENT_FORMATS, Research
from ..studio import Source, Swarm, check_pack
from ..studio.relay import PICTURE_STYLE as CHILD_PICTURE_STYLE
from . import LAB
from .agents import (
    JUDGE,
    JUDGE_CHILD,
    JUDGE_CHILD_V2,
    JUDGE_V2,
    JUDGE_V3,
    JUDGE_V4,
    PROFILER,
    ContentProfile,
    Judgement,
)
from .budget import STOP_AT_USD, TRANSCRIBE_USD_PER_HOUR, can_spend, lab_rows, spent

REQUEST = "I saw this reel and want Mom to understand it. Make it simple and warm for her."
KIDS_REQUEST = "I saw this reel and want Leo to learn from it in a fun way. Keep it right for a 9-year-old."
IMAGE_USD = 0.01  # one Muse Image picture
FULL_SET_FROM = 4  # from round 4 every reel gets the full set of moments, as on the home page
WATCH_FROM = 5  # from round 5 (and every children's round after the first) the video is watched whole
JUDGES = {1: JUDGE, 2: JUDGE_V2, 3: JUDGE_V3, 4: JUDGE_V4, "child": JUDGE_CHILD, "child2": JUDGE_CHILD_V2}
JUDGEMENT_KEY = {1: "judgement", 2: "judgement_v2", 3: "judgement_v3", 4: "judgement_v4", "child": "judgement_child",
                 "child2": "judgement_child_v2"}
NATURAL_FROM = 6  # round 6 (and Leo's round 4): the family's voice (the user's review), judged by v4
USD_PER_REEL = 0.10  # a round on one reel, as measured in round 1 ($0.07), with room
CIRCLE = CIRCLES["chen"]  # Linda, 79: the English parent


def ledger_cost(path: Path) -> dict[str, float]:
    """Dollars and calls in one ledger file (calls replayed from the cache cost nothing)."""
    usd, calls, replayed = 0.0, 0, 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("replayed_from_cache"):
                replayed += 1
                continue
            calls += 1
            usd += dollars(Usage.from_dict(row), PRICE_BY_MODEL.get(row.get("model", ""), UNKNOWN_PRICE))
    return {"usd": round(usd, 5), "calls": calls, "replayed": replayed}


def words(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower())


SCRIPTS = {"latin": ((0x41, 0x24F),), "devanagari": ((0x900, 0x97F),), "arabic": ((0x600, 0x6FF), (0x750, 0x77F)),
           "japanese": ((0x3040, 0x30FF), (0x4E00, 0x9FFF)), "hangul": ((0xAC00, 0xD7AF),)}


def script(text: str) -> str:
    """The writing system most of the letters are in."""
    counts = {name: sum(1 for ch in text if any(lo <= ord(ch) <= hi for lo, hi in spans)) for name, spans in SCRIPTS.items()}
    best = max(counts, key=counts.__getitem__)
    return best if counts[best] else ""


def agreement(ours: str, theirs: str) -> float | None:
    """How closely two transcripts agree, 0..1 (word sequence similarity). None if there is no reference, or if the
    two are in different writing systems (Hindi in Devanagari against the same words in Urdu script, or against an
    English translation), where word overlap measures nothing."""
    if not theirs or not ours or script(ours) != script(theirs):
        return None
    a, b = words(ours)[:1500], words(theirs)[:1500]
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 2) if a and b else 0.0


# ---------------------------------------------------------------- prepare: frames and the transcript (once per reel)


def prepare(row: dict[str, Any], media: MetaMedia) -> dict[str, Any]:
    folder = LAB / row["id"]
    folder.mkdir(parents=True, exist_ok=True)
    video = Path(row["video"])
    frames_dir = folder / "frames"
    frames = sorted(frames_dir.glob("*.jpg")) if frames_dir.exists() else []
    if len(frames) < 8:
        frames = spread_frames(video, frames_dir, 8)
    tpath = folder / "transcript.json"
    if tpath.exists():
        transcript = json.loads(tpath.read_text(encoding="utf-8"))
    else:
        started = time.time()
        try:
            heard = media.transcribe(file_to_wav(video))
            transcript = {"text": heard.text, "duration_s": heard.duration_s, "latency_s": round(time.time() - started, 2), "error": ""}
        except Exception as exc:  # recorded, never silent: the reel is judged on its pictures alone
            transcript = {"text": "", "duration_s": 0, "latency_s": round(time.time() - started, 2), "error": str(exc)[:200]}
        tpath.write_text(json.dumps(transcript, ensure_ascii=False, indent=1), encoding="utf-8")
    duration = row.get("probe", {}).get("duration_s") or row.get("duration_s") or 0
    n_words = len(words(transcript["text"]))
    transcript["words"] = n_words
    transcript["wpm"] = round(n_words / max(1.0, min(duration, 600)) * 60) if duration else 0
    reference = (row.get("reference") or {}).get("transcript") or ""
    transcript["agreement"] = agreement(transcript["text"], reference)
    transcript["scripts"] = [script(transcript["text"]), script(reference)]
    transcript["cost_usd"] = round(min(duration, 600) / 3600 * TRANSCRIBE_USD_PER_HOUR, 5)
    return {"frames": [str(f) for f in frames], "transcript": transcript}


# ---------------------------------------------------------------- one round for one reel


def source_for(row: dict[str, Any], prep: dict[str, Any], caption: bool, request: str = REQUEST) -> Source:
    """What the Studio would get: the request, the transcript and the frames; from round 2 also the reel's caption, as
    a caregiver pastes it with the video (Instagram links can't be opened without a login, so the caption is lost
    unless it is pasted)."""
    text = prep["transcript"]["text"]
    parts = [request]
    if caption and row.get("caption"):
        parts.append(f"The reel's caption, pasted by Maya: {row['caption'][:1500]}")
    parts.append(f"Spoken in it: {text}" if text else "(no speech could be transcribed)")
    return Source(kind="video", text="\n\n".join(parts), images=[Path(f) for f in prep["frames"]], request=request)


def choose(plan_recommended: list[str], profile_best: list[str]) -> list[str]:
    """Rounds 2-3: the planner's first two, then the profiler's first choice (so the content's best format is always
    made), then any other the planner recommended; at most three."""
    chosen = [*plan_recommended[:2], *profile_best[:1], *plan_recommended[2:]]
    return [f for f in dict.fromkeys(chosen) if f in PARENT_FORMATS][:3]


def draw(media: MetaMedia, folder: Path, name: str, picture: dict[str, Any], child: bool) -> float:
    """The picture moment drawn by Muse Image, as the Studio draws it; returns what it cost."""
    style = CHILD_PICTURE_STYLE if child else PARENT_PICTURE_STYLE
    try:
        data = media.generate_image(style.format(scene=picture.get("prompt_en", "")[:600]))
    except Exception as exc:
        picture["image_error"] = str(exc)[:200]
        return 0.0
    (folder / name).write_bytes(data)
    picture["image"] = f"/lab-media/{folder.name}/{name}"
    return IMAGE_USD


def run_round(row: dict[str, Any], n: int, media: MetaMedia, kids: bool = False) -> dict[str, Any]:
    """One round on one reel: for Linda (``round-N.json``), or for Leo, 9 (``kids-N.json``)."""
    folder = LAB / row["id"]
    prep = prepare(row, media)
    tag = f"k{n}" if kids else f"r{n}"
    ledger = folder / f"ledger-{tag}.jsonl"
    ledger.unlink(missing_ok=True)
    llm = LLM(pipeline_provider(), ledger_file=ledger)
    watched = (kids and n >= 2) or (not kids and n >= WATCH_FROM)  # from round 5: the video watched whole, stills at its moments, lookups, SAM
    swarm = Swarm(llm, CIRCLE, f"lab-{row['id']}-{tag}", recipient=CIRCLE.children[0] if kids else None,
                  media=media if watched else None)
    swarm.tuned_guard = None  # the lab never wakes the GPU guard on Modal; Muse Spark reviews children's packs
    request = KIDS_REQUEST if kids else REQUEST
    started = time.time()
    full_set = kids or n >= FULL_SET_FROM
    judge_version = (("child2" if n >= 4 else "child") if kids else 4 if n >= NATURAL_FROM else 3 if full_set else 2 if n >= 2 else 1)
    settings = {"caption": kids or n >= 2, "judge": judge_version, "full_set": full_set,
                "for": "Leo, 9" if kids else "Linda, 79"}
    out: dict[str, Any] = {"round": n, "kids": kids, "reel": row["id"], "settings": settings, "transcript": prep["transcript"]}
    image_usd = 0.0
    try:
        source = source_for(row, prep, settings["caption"], request)
        if watched:
            source.video, source.moments_dir = Path(row["video"]), folder / "moments"
        if (kids and n >= 4) or (not kids and n >= NATURAL_FROM):
            source.files_dir = folder / "found"  # product pictures from the shops' pages
        research: Research = swarm.research(source, request, "No earlier packs yet.", "Recent conversation: (none)")
        plan = swarm.plan(research, request)
        profile = ContentProfile.model_validate(swarm.run(PROFILER, (
            f"Title: {row.get('title', '')}\nCaption: {row.get('caption', '')[:800]}\n"
            f"Transcript: {prep['transcript']['text'][:4000] or '(none)'}\n\nReading of the frames and speech:\n"
            f"{json.dumps(research.reading.model_dump(), ensure_ascii=False)}")).model_dump())
        recommended = [f.format for f in plan.formats if f.recommended]
        if full_set:  # what the Studio now makes from one share: the whole set the plan recommends
            chosen = recommended
        elif n == 1:  # the round 1 rule: the planner's picks first, so the profiler's choice was often cut by the cap
            chosen = [f for f in dict.fromkeys([*recommended, *profile.best_formats[:1]]) if f in PARENT_FORMATS][:3]
        else:
            chosen = choose(recommended, profile.best_formats)
        out.update(research=research.model_dump(), plan=plan.model_dump(), profile=profile.model_dump(), formats=chosen,
                   stills=[p.name for p in source.images])
        outputs = swarm.make(research, plan, chosen)
        if full_set and "picture" in outputs:
            image_usd = draw(media, folder, f"picture-{tag}.png", outputs["picture"], kids)
        review = swarm.verify(research, plan, outputs)
        warning = research.fact_check.verdict == "likely_scam_or_misleading"
        gate = check_pack(outputs, source.text, research.reading.dates_and_numbers,
                          also_shown=[plan.conversation_starter], warning=warning)
        out.update(outputs=outputs, review=review.model_dump(), gate=gate.model_dump(),
                   failed_makers=[f for f in chosen if f not in outputs])
        if kids:
            out["guardian"] = swarm.guard(outputs, [plan.conversation_starter]).model_dump()
        out[JUDGEMENT_KEY[settings["judge"]]] = judge(swarm, row, prep, research, outputs, version=settings["judge"]).model_dump()
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    out["seconds"] = round(time.time() - started, 1)
    out["cost"] = ledger_cost(ledger)
    out["cost"]["transcribe_usd"] = prep["transcript"]["cost_usd"]
    out["cost"]["image_usd"] = image_usd
    (folder / f"{'kids' if kids else 'round'}-{n}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if ledger.exists():  # the app's spend meter counts the lab too
        with open(LEDGER_FILE, "a", encoding="utf-8") as fh:
            fh.write(lab_rows(ledger))
    return out


def key_points(row: dict[str, Any], research: Research) -> list[str]:
    """The reel's key points: the independent earlier analysis when there is one, else our reader's facts."""
    ref = (row.get("reference") or {}).get("key_points") or []
    return [str(p) for p in ref][:10] or research.reading.facts_en[:10]


def shown_to_judge(outputs: dict[str, Any], research: Research, version: int) -> dict[str, Any]:
    """The moments as she sees them. v1 hid every *_en field (so a picture was only its caption); v2 shows what a
    picture will draw and, for a video scene, which still of the reel is behind it."""
    shown = {f: {k: copy.deepcopy(v) for k, v in o.items() if not k.endswith("_en") and k not in ("image", "frames")}
             for f, o in outputs.items()}  # a deep copy: the scenes below are changed for the judge, not in the moment
    if version >= 2:
        if "picture" in outputs:
            shown["picture"]["picture_to_draw"] = outputs["picture"].get("prompt_en", "")
        stills = research.reading.pictures_en
        for scene in (shown.get("video") or {}).get("scenes", []):
            frame = scene.pop("frame", -1)
            if 0 <= frame < len(stills):
                scene["shown_picture"] = stills[frame]
    return shown


def judge(swarm: Swarm, row: dict[str, Any], prep: dict[str, Any], research: Research, outputs: dict[str, Any],
          version: int | str = 2) -> Judgement:
    points = key_points(row, research)
    shown = shown_to_judge(outputs, research, 1 if version == 1 else 2)
    if research.links or research.products:  # what the app adds itself, by code, under the moments
        shown["added_by_the_app"] = {"links": [link.model_dump() for link in research.links],
                                     "products": [{"name": p.name, "good_for": p.good_for_en, "has_picture": bool(p.image)}
                                                  for p in research.products]}
    check = research.fact_check
    brief = (f"Reel title: {row.get('title', '')}\nCaption: {row.get('caption', '')[:600]}\n"
             f"Transcript: {prep['transcript']['text'][:3500] or '(none)'}\n\nReading of the frames and speech: "
             f"{json.dumps(research.reading.model_dump(), ensure_ascii=False)}\n\n"
             + (f"Fact check: {check.verdict}. {check.note_en}\n\n" if version != 1 else "")
             + (f"Timeline of the whole video (watched with its sound): {json.dumps(research.timeline.model_dump(), ensure_ascii=False)}\n\n"
                if research.timeline else "")
             + (f"Each named item, looked up on the web: {json.dumps([i.model_dump() for i in research.items], ensure_ascii=False)}\n\n"
                if research.items else "")
             + "Key points:\n" + "\n".join(f"{k + 1}. {p}" for k, p in enumerate(points))
             + f"\n\nMoments made, by format:\n{json.dumps(shown, ensure_ascii=False)}")
    return Judgement.model_validate(swarm.run(JUDGES[version], brief).model_dump())


def rejudge(n: int, version: int | str = 2, workers: int = 4, kind: str = "round") -> list[str]:
    """Score round ``n``'s stored moments again with judge ``version`` (its ledger: ledger-r{n}-judge{version}.jsonl)."""
    rows = {r["id"]: r for r in json.loads((LAB / "inventory.json").read_text(encoding="utf-8"))}
    key = JUDGEMENT_KEY[version]

    def one(path: Path) -> str:
        out = json.loads(path.read_text(encoding="utf-8"))
        if "outputs" not in out or key in out:
            return f"{out['reel']}: skipped"
        ledger = path.parent / f"ledger-{kind[0]}{n}-judge{version}.jsonl"
        child = CIRCLE.children[0] if kind == "kids" else None
        swarm = Swarm(LLM(pipeline_provider(), ledger_file=ledger), CIRCLE, f"lab-{out['reel']}-{kind[0]}{n}-judge{version}", recipient=child)
        research = Research.model_validate(out["research"])
        out[key] = judge(swarm, rows[out["reel"]], {"transcript": out["transcript"]}, research, out["outputs"],
                         version=version).model_dump()
        out["cost"][f"rejudge{version}_usd"] = ledger_cost(ledger)["usd"]
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        with open(LEDGER_FILE, "a", encoding="utf-8") as fh:
            fh.write(lab_rows(ledger))
        return f"{out['reel']}: rejudged"

    paths = [p for p in sorted(LAB.glob(f"*/{kind}-{n}.json")) if p.parent.name != "notion"]
    if not can_spend(len(paths) * 0.06):
        raise SystemExit("Rejudging could pass the lab's spending stop line; not started.")
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, paths))


def run_all(n: int, ids: list[str] | None = None, workers: int = 4, kids: bool = False) -> Iterator[dict[str, Any]]:
    """Round ``n`` for every usable reel (or the given ones), each result as soon as it is ready, in inventory order."""
    rows = json.loads((LAB / "inventory.json").read_text(encoding="utf-8"))
    todo = [r for r in rows if not r["skipped"] and (ids is None or r["id"] in ids)]
    per_reel = USD_PER_REEL * (1.15 if kids or n >= FULL_SET_FROM else 1)  # a full set: rounds 4-6 cost $0.09-0.12 a reel
    if not can_spend(len(todo) * per_reel):  # as many reels as the stop line allows, in inventory order
        room = int(max(0.0, STOP_AT_USD - spent()["total_usd"]) / per_reel)
        if room < 1:
            raise SystemExit(f"Round {n}: no room under the lab's spending stop line; not started.")
        print(f"Round {n}: the stop line allows {room} of {len(todo)} reels; running those.", flush=True)
        todo = todo[:room]
    media = MetaMedia(get_settings().meta)
    with ThreadPoolExecutor(workers) as pool:
        yield from pool.map(lambda r: run_round(r, n, media, kids), todo)
