"""The Reel Lab: every reel is a test case for the agents (docs/REEL_LAB.md).

* ``inventory``: what is in the source folder, and why a reel can't be used;
* ``probe``: the technical check, by code (ffmpeg): audio and video quality, in bands;
* ``understand``: transcript, visual reading, content type and the formats it suits;
* ``rounds``: one round makes the moments for every usable reel and scores them, so rounds can be compared;
* ``report``: the markdown report from everything stored, and the aggregate for the /lab page (``data/lab/summary.json``).

The source folder is read only. What the lab makes goes to ``output/reel-lab/<reel id>/``; costs are logged per
reel and per round in their own usage ledgers.
"""

from __future__ import annotations

from pathlib import Path

from ..config import OUTPUT_DIR, REPO_ROOT

SOURCE = Path("/home/azureuser/insta-analyze")
LAB = OUTPUT_DIR / "reel-lab"
REPORT_DIR = REPO_ROOT / "docs" / "reel-lab"
