# CareCircle

A family-care chat app with an AI helper, **Saathi**. Saathi turns what you share into simple, illustrated,
regional-language content for your parents and kids, and makes a daily check-in call when you can't.

This repository holds the **feasibility stage**: four things you can run, for two synthetic families, one in
India (Hindi) and one in Japan (Japanese, a parent who lives alone).
- **Content transformer:** a reel, photo or long message becomes a card, an explainer video, an article and a calendar entry.
- **Check-in call simulator.**
- **Chat playground:** talk to any configured model and see the tokens sent and cached.
- **Product demo:** an animated web app that plays the saved outputs as five flows (see below).

- How the code is organised, and the rules for changing it: **[ARCHITECTURE.md](ARCHITECTURE.md)**
- What was tested and learned: [docs/FINDINGS.md](docs/FINDINGS.md)
- The product plan: [docs/PLAN.md](docs/PLAN.md)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium     # used to render cards and video frames
cp .env.example .env                        # then fill in at least the Azure values
```

You also need `ffmpeg` on the system to build the video.

## Commands

```bash
.venv/bin/carecircle check              # do the API keys work?
.venv/bin/carecircle chat               # chat playground at http://127.0.0.1:8000, demo at /demo
.venv/bin/carecircle all                # run every feasibility step; outputs land in output/
.venv/bin/carecircle content school_notice      # one step, one case
.venv/bin/carecircle ask "Summarise this" --file data.csv
.venv/bin/carecircle --help
```

Each pipeline step on its own:

| Command | Writes |
|---|---|
| `samples` | `data/samples/` synthetic reel video and bill photo (only if missing) |
| `content [case…]` | `output/content/<case>/digest.json` |
| `render [case…]` | `card.png`, `explainer.mp4`, `event.ics`, `article.md`, `voice_note.txt` next to it |
| `checkin [scenario…]` | `output/checkin/<scenario>.md` and `.json` |
| `mock` | `output/mock/screens.png` (your chat next to "what Mummy sees") |
| `costs` | `output/costs.json` |

Model calls are cached in `.cache/llm/`, so re-running costs nothing and gives the same output. Delete that
folder to force fresh calls.

## Product demo

Run `carecircle all` once (or at least `content`, `render` and `checkin`), then `carecircle chat` and open
<http://127.0.0.1:8000/demo>. It never calls a model: it replays what the pipeline saved in `output/`, served
as one JSON document at `/api/demo/story`. Switch between the India and Japan families and pick a flow:
share and simplify, scam held back, deadline to reminder, daily check-in call, see what they see.

Links can open a flow directly: `/demo?family=japan&flow=call`; add `&end=1` to jump to its last step.

To change it, edit one file in `web/demo/`:

| To change | Edit |
|---|---|
| Any words on the page | `js/copy.js` |
| The steps of a flow, their order and timing | `js/flows.js` (guide at the top) |
| How a kind of step is drawn | `js/stage.js` (`RENDER`) and `js/pieces.js` |
| Colours, fonts, radii | `css/tokens.css` (same values as `render/theme.py`) |
| Icons (shared with the cards and videos) | `src/carecircle/render/icons.py` |
| Animations | `css/motion.css` |

## Development

```bash
.venv/bin/python -m pytest              # unit tests (no network, no .env needed)
.venv/bin/ruff check src tests          # lint
.venv/bin/carecircle chat --reload      # playground that restarts on code changes
```

Before you change anything, read [ARCHITECTURE.md](ARCHITECTURE.md): the layering (§3), the rules (§5–6) and
the definition of done (§12).
