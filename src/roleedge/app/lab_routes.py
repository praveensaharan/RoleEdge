"""The Lab page (``/lab``): how the agents were tested and tuned, in aggregate. Read only: it serves the summary that
``python -m roleedge.lab report`` wrote to ``data/lab/summary.json`` (shipped with the app) and never calls a model.

No single reel is served: not its title, caption, transcript, frames or moments. The reels are other people's posts,
so the page shows only totals and averages.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..config import LAB_SUMMARY as SUMMARY


def add_lab_routes(app: FastAPI, web_dir: Path) -> None:
    @app.get("/lab", include_in_schema=False)
    def lab_page() -> FileResponse:
        return FileResponse(web_dir / "lab.html")

    @app.get("/api/lab/summary")
    def lab_summary() -> dict:
        """The tuning in numbers: every round, every change and what it moved."""
        if not SUMMARY.exists():  # a visitor sees this, so no command line in it (see docs/REEL_LAB.md)
            raise HTTPException(404, "The lab results are not available on this server.")
        return json.loads(SUMMARY.read_text(encoding="utf-8"))
