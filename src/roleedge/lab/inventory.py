"""Phases 1 and 2: every reel in the source folder, and its technical quality measured by code.

The technical check uses ffmpeg only (no model): loudness and silence for the audio, sharpness, freezes, brightness and
cuts for the video. Each measure is put in a band (pass, weak or fail) so reels can be compared and a bad source is
known before any agent runs.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import LAB, SOURCE


@dataclass
class Reel:
    id: str
    url: str
    video: str  # path, "" if there is none
    title: str = ""
    creator: str = ""
    caption: str = ""
    duration_s: float = 0.0
    language_hint: str = ""  # from the earlier analysis in the source folder
    category_hint: str = ""
    reference: dict[str, Any] = field(default_factory=dict)  # the earlier (independent) analysis: summary, key points
    skipped: str = ""  # why this reel can't be used, if it can't

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inventory(source: Path = SOURCE) -> list[Reel]:
    """Every reel in reels.json, with its video and metadata; a reel with no video says why."""
    listed = json.loads((source / "reels.json").read_text(encoding="utf-8"))["reels"]
    reels = []
    for entry in listed:
        rid = entry["reel_id"]
        video = next((p for p in (source / "downloads_h264" / f"{rid}.mp4", source / "downloads" / f"{rid}.mp4") if p.exists()), None)
        info_path = source / "downloads" / f"{rid}.info.json"
        info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
        ref_path = source / "analysis" / f"{rid}.json"
        ref = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else {}
        title = info.get("title") or ""
        if not title or title.startswith("Video by "):  # Instagram's generic title names only the creator
            title = ref.get("title") or title
        reel = Reel(id=rid, url=entry["url"], video=str(video or ""), title=title[:200],
                    creator=info.get("uploader") or info.get("channel") or ref.get("creator") or "",
                    caption=(info.get("description") or ref.get("caption") or "")[:2000],
                    duration_s=float(info.get("duration") or ref.get("duration_seconds") or 0),
                    language_hint=str(ref.get("language") or ""), category_hint=str(ref.get("category") or ""),
                    reference={k: ref.get(k) for k in ("title", "summary", "key_points", "spoken_summary", "on_screen_text", "transcript")
                               if ref.get(k)})
        if video is None:
            kind = "an image or carousel post" if info.get("_type") == "playlist" or not info else "a post whose video wasn't downloaded"
            reel.skipped = f"No video file in the source folder ({kind}); nothing to watch or hear."
        reels.append(reel)
    return reels


# ---------------------------------------------------------------- the technical check


def _run(args: list[str], timeout: int = 180) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return result.stdout + result.stderr


def _num(pattern: str, text: str, default: float = 0.0) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else default


def probe(video: Path) -> dict[str, Any]:
    """Measures of one video. Analysis runs on the first 90 seconds at a reduced frame rate, which is plenty to judge it."""
    meta = json.loads(_run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)]) or "{}")
    streams = meta.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float((meta.get("format") or {}).get("duration") or 0)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    fps = round(float(num) / float(den or 1), 2) if num else 0.0
    out: dict[str, Any] = {"duration_s": round(duration, 1), "width": v.get("width", 0), "height": v.get("height", 0), "fps": fps,
                           "video_codec": v.get("codec_name", ""), "audio": a is not None,
                           "audio_codec": (a or {}).get("codec_name", ""), "bitrate_kbps": round(int((meta.get("format") or {}).get("bit_rate") or 0) / 1000)}
    span = ["-t", "90"]
    if a is not None:
        loud = _run(["ffmpeg", "-hide_banner", "-nostats", *span, "-i", str(video), "-vn", "-af", "ebur128=framelog=quiet,silencedetect=n=-45dB:d=0.6",
                     "-f", "null", "-"])
        silence = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", loud))
        out.update(loudness_lufs=_num(r"I:\s+(-?[\d.]+) LUFS", loud, -70.0), loudness_range_lu=_num(r"LRA:\s+([\d.]+) LU", loud),
                   silence_share=round(min(1.0, silence / max(1.0, min(duration, 90))), 2))
    else:
        out.update(loudness_lufs=None, loudness_range_lu=None, silence_share=1.0)
    vid = _run(["ffmpeg", "-hide_banner", "-nostats", *span, "-i", str(video), "-an", "-vf",
                "fps=2,scale=360:-2,blurdetect=block_pct=80:block_height=32:block_width=32,signalstats,metadata=print:file=-,"
                "freezedetect=n=0.003:d=2", "-f", "null", "-"], timeout=300)
    blur = [float(x) for x in re.findall(r"lavfi\.blur=([\d.]+)", vid)]
    yavg = [float(x) for x in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", vid)]
    frozen = sum(float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", vid))
    cuts = _run(["ffmpeg", "-hide_banner", "-nostats", *span, "-i", str(video), "-an", "-vf", "scale=320:-2,scdet=threshold=12", "-f", "null", "-"], timeout=300)
    out.update(blur_mean=round(sum(blur) / len(blur), 2) if blur else None, blurry_share=round(sum(b > 7 for b in blur) / len(blur), 2) if blur else None,
               brightness=round(sum(yavg) / len(yavg), 1) if yavg else None, frozen_share=round(min(1.0, frozen / max(1.0, min(duration, 90))), 2),
               cuts_per_10s=round(10 * len(re.findall(r"lavfi\.scd\.time", cuts)) / max(1.0, min(duration, 90)), 1))
    out["bands"] = bands(out)
    return out


def bands(m: dict[str, Any]) -> dict[str, str]:
    """Each measure as pass / weak / fail, by plain thresholds (documented in docs/REEL_LAB.md)."""
    short = min(m["width"] or 0, m["height"] or 0)
    b = {"resolution": "pass" if short >= 700 else "weak" if short >= 480 else "fail",
         "frame_rate": "pass" if m["fps"] >= 23.9 else "weak" if m["fps"] >= 15 else "fail",  # 23.976 is film rate
         "audio": "fail" if not m["audio"] else "pass"}
    if m["audio"]:
        lufs, silence = m["loudness_lufs"], m["silence_share"]
        b["loudness"] = "pass" if -24 <= lufs <= -8 else "weak" if -34 <= lufs <= -6 else "fail"
        b["silence"] = "pass" if silence <= 0.3 else "weak" if silence <= 0.7 else "fail"
    if m.get("blurry_share") is not None:
        b["sharpness"] = "pass" if m["blurry_share"] <= 0.25 else "weak" if m["blurry_share"] <= 0.6 else "fail"
    b["frozen"] = "pass" if m["frozen_share"] <= 0.3 else "weak" if m["frozen_share"] <= 0.7 else "fail"
    if m.get("brightness") is not None:
        b["brightness"] = "pass" if 40 <= m["brightness"] <= 220 else "weak"
    return b


def _probed(reel: Reel) -> dict[str, Any]:
    row = reel.to_dict()
    cached = LAB / reel.id / "probe.json"
    if reel.video:
        if cached.exists():
            row["probe"] = json.loads(cached.read_text())
            row["probe"]["bands"] = bands(row["probe"])  # thresholds may have changed since it was measured
        else:
            row["probe"] = probe(Path(reel.video))
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(row["probe"], indent=1))
    return row


def save_inventory(workers: int = 4) -> list[dict[str, Any]]:
    """Inventory plus the technical check for every reel (kept per reel, so a re-run is free), stored in
    output/reel-lab/inventory.json."""
    from concurrent.futures import ThreadPoolExecutor

    LAB.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as pool:
        rows = list(pool.map(_probed, inventory()))
    (LAB / "inventory.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return rows
