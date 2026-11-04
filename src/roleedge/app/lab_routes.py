"""The Lab page (``/lab``): how the agents were tested and tuned, in aggregate. Read only: it serves the summary that
``python -m roleedge.lab report`` wrote to ``output/reel-lab/summary.json`` and never calls a model.

No single reel is served: not its title, caption, transcript, frames or moments. The reels are other people's posts,
so the page shows only totals and averages.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..config import OUTPUT_DIR

SUMMARY = OUTPUT_DIR / "reel-lab" / "summary.json"


def add_lab_routes(app: FastAPI, web_dir: Path) -> None:
    @app.get("/lab", include_in_schema=False)
    def lab_page() -> FileResponse:
        return FileResponse(web_dir / "lab.html")

    @app.get("/api/lab/summary")
    def lab_summary() -> dict:
        """The tuning in numbers: every round, every change and what it moved."""
        if not SUMMARY.exists():
            raise HTTPException(404, "No lab summary yet: run python -m roleedge.lab report.")
        return json.loads(SUMMARY.read_text(encoding="utf-8"))
