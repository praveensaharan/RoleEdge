"""The Reel Lab page (``/lab``): every reel the lab ran, its rounds and scores, and the moments made, shown with the
same viewers the phone uses. Read only: it reads what ``python -m roleedge.lab`` stored in ``output/reel-lab/`` and
never calls a model.

The app sits below the lab package in the layers, so this reads the lab's files directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..config import OUTPUT_DIR

LAB = OUTPUT_DIR / "reel-lab"
REEL_ID = re.compile(r"[A-Za-z0-9_-]{6,20}")
MEDIA = re.compile(r"([ft]\d{2}\.jpg|picture-[rk]\d{1,2}\.png)")  # a frame or a timed still of the reel, or a drawn picture
CRITERIA = ("faithful", "clear", "engaging", "useful", "format_fit")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _rounds(rid: str, kind: str = "round") -> dict[int, dict[str, Any]]:
    """A reel's rounds for Linda (``round-N.json``) or for Leo (``kids-N.json``), by number."""
    found = {}
    for path in (LAB / rid).glob(f"{kind}-*.json"):
        try:
            found[int(path.stem.split("-")[1])] = _json(path)
        except ValueError:
            continue
    return dict(sorted(found.items()))


def _score(moment: dict[str, Any]) -> float:
    keys = (*CRITERIA, "natural") if moment.get("natural") else CRITERIA  # judge v4 adds natural
    return round(sum(moment[k] for k in keys) / len(keys), 2)


def _judged(out: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The latest judge's scores: v4 (the family's voice), v3 (the full set), the children's judges, or v2 (rounds 1-3)."""
    for key, name in (("judgement_v4", "v4"), ("judgement_child_v2", "child2"), ("judgement_v3", "v3"), ("judgement_child", "child"),
                      ("judgement_v2", "v2")):
        if out.get(key):
            return name, out[key]
    return "", {}


def _best(out: dict[str, Any]) -> float:
    return max((_score(m) for m in _judged(out)[1].get("moments", [])), default=0.0)


def _summary(n: int, out: dict[str, Any]) -> dict[str, Any]:
    judge, j = _judged(out)
    scores = [_score(m) for m in j.get("moments", [])]
    v2 = [_score(m) for m in (out.get("judgement_v2") or {}).get("moments", [])]
    return {"round": n, "judge": judge, "best": max(scores, default=0.0), "every": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "best_v2": max(v2, default=None), "formats": list((out.get("outputs") or {}).keys())}


def add_lab_routes(app: FastAPI, web_dir: Path) -> None:
    @app.get("/lab", include_in_schema=False)
    def lab_page() -> FileResponse:
        return FileResponse(web_dir / "lab.html")

    @app.get("/api/lab")
    def lab_index() -> dict:
        rows = _json(LAB / "inventory.json") or []
        reels = []
        for row in rows:
            rounds = _rounds(row["id"]) if not row["skipped"] else {}
            latest = rounds[max(rounds)] if rounds else {}
            reels.append({"id": row["id"], "title": row["title"], "skipped": row["skipped"],
                          "duration_s": (row.get("probe") or {}).get("duration_s", row.get("duration_s")),
                          "type": (latest.get("profile") or {}).get("content_type", ""),
                          "topic": (latest.get("profile") or {}).get("topic_en", ""),
                          "rounds": [_summary(n, o) for n, o in rounds.items()],
                          "kids": [_summary(n, o) for n, o in (_rounds(row["id"], "kids") if not row["skipped"] else {}).items()]})
        notion = [_json(p) for p in sorted((LAB / "notion").glob("round-*.json"))]
        return {"reels": reels, "notion": [{"round": n["round"], "passed": n["passed"], "total": n["total"]} for n in notion if n]}

    @app.get("/api/lab/summary")
    def lab_summary() -> dict:
        """The tuning in numbers: every round, every change and what it moved (written by ``python -m roleedge.lab report``)."""
        summary = _json(LAB / "summary.json")
        if summary is None:
            raise HTTPException(404, "No lab summary yet: run python -m roleedge.lab report.")
        return summary

    @app.get("/api/lab/{reel_id}")
    def lab_reel(reel_id: str) -> dict:
        if not REEL_ID.fullmatch(reel_id):
            raise HTTPException(400, "Not a reel id.")
        row = next((r for r in _json(LAB / "inventory.json") or [] if r["id"] == reel_id), None)
        if row is None:
            raise HTTPException(404, "No such reel.")
        frames = [f"/lab-media/{reel_id}/{p.name}" for p in sorted((LAB / reel_id / "frames").glob("*.jpg"))]
        return {**_detail(reel_id, row, frames), "kids": [_one(n, out, frames) for n, out in _rounds(reel_id, "kids").items()]}

    @app.get("/lab-media/{reel_id}/{name}", include_in_schema=False)
    def lab_media(reel_id: str, name: str) -> FileResponse:
        if not REEL_ID.fullmatch(reel_id) or not MEDIA.fullmatch(name):
            raise HTTPException(404)
        path = LAB / reel_id / {"f": "frames", "t": "moments"}.get(name[0], "") / name
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/jpeg" if name.endswith(".jpg") else "image/png")


def _one(n: int, out: dict[str, Any], frames: list[str]) -> dict[str, Any]:
    outputs, rid = out.get("outputs") or {}, out.get("reel", "")
    stills = out.get("stills") or []
    if any(name.startswith("t") for name in stills):  # stills taken at the timeline's moments (round 5 on)
        frames = [f"/lab-media/{rid}/{name}" for name in stills if (LAB / rid / "moments" / name).is_file()]
    picture = outputs.get("picture") or {}
    if str(picture.get("image", "")).startswith("/lab-media/") and not (LAB / rid / picture["image"].rsplit("/", 1)[-1]).is_file():
        outputs["picture"] = {k: v for k, v in picture.items() if k != "image"}  # a copy without the reel media
    research = out.get("research") or {}
    if "video" in outputs and frames:
        outputs["video"]["frames"] = frames
        outputs["video"]["focus"] = research.get("focus") or []
    judge, j = _judged(out)
    judged = {m["format"]: {**m, "score": _score(m)} for m in j.get("moments", [])}
    return {"round": n, "judge": judge, "formats": out.get("formats"), "outputs": outputs, "judged": judged,
            "best_format": j.get("best_format", ""), "missing": j.get("missing_en", []),
            "reading": (out.get("research") or {}).get("reading", {}),
            "fact_check": (out.get("research") or {}).get("fact_check", {}),
            "plan": {k: (out.get("plan") or {}).get(k) for k in ("key_message_en", "content_shape", "safety_notes_en")},
            "stills": frames, "timeline": research.get("timeline"), "items": research.get("items") or [],
            "profile": out.get("profile"), "review": out.get("review"), "gate": out.get("gate"), "guardian": out.get("guardian"),
            "cost": out.get("cost"), "seconds": out.get("seconds"), "error": out.get("error", "")}


def _detail(reel_id: str, row: dict[str, Any], frames: list[str]) -> dict[str, Any]:
    rounds = [_one(n, out, frames) for n, out in _rounds(reel_id).items()]
    latest = _rounds(reel_id)
    transcript = (latest[max(latest)].get("transcript") if latest else None) or {}
    return {"id": reel_id, "title": row["title"], "caption": row["caption"][:800], "skipped": row["skipped"],
            "probe": row.get("probe"), "frames": frames,
            "transcript": {k: transcript.get(k) for k in ("text", "words", "wpm", "agreement", "scripts", "error")},
            "rounds": rounds}
