"""Reel and post links, tested: the product's own downloader (``content.social``) on the source folder's URLs.

No model is called. For each link: did a video come down, how big, which codec, does the caption match the one in the
source folder, and for a photo post, does the caregiver get the right message. Links are fetched one at a time with a
pause, as a person sharing them would.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ..content.social import PHOTOS, fetch_social
from . import LAB

DIR = LAB / "links"


def _codec(video: Path) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True, timeout=30, check=False)
    return out.stdout.strip()


def run_links(ids: list[str] | None = None, reels: int = 8) -> dict[str, Any]:
    rows = json.loads((LAB / "inventory.json").read_text(encoding="utf-8"))
    posts = [r for r in rows if r["skipped"]]
    videos = [r for r in rows if not r["skipped"]][:reels]
    todo = [r for r in rows if ids is None or r["id"] in ids] if ids else posts + videos
    results = []
    for row in todo:
        started = time.time()
        got = fetch_social(row["url"], DIR / row["id"])
        caption = (row.get("caption") or "").strip()
        results.append({"id": row["id"], "url": row["url"], "expected": "photos" if row["skipped"] else "video",
                        "video": bool(got.video), "mb": round(got.video.stat().st_size / 1e6, 1) if got.video else 0,
                        "codec": _codec(got.video) if got.video else "", "caption_matches": bool(caption) and got.caption.strip()[:80] == caption[:80],
                        "problem": got.problem, "seconds": round(time.time() - started, 1),
                        "passed": (bool(got.video) if not row["skipped"] else got.problem == PHOTOS)})
        time.sleep(2)
    out = {"passed": sum(r["passed"] for r in results), "total": len(results), "results": results}
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
