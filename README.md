<p align="center"><img src="web/app/favicon.svg" width="72" height="72" alt="RoleEdge"></p>

<h1 align="center">RoleEdge</h1>

<p align="center"><b>Care for a parent far away, in the family's own voice.</b><br>
Share a reel, a link or a few words. A team of agents on Meta models turns it into something your parent can follow,
checks it before she sees it, and tells you how she is doing.</p>

<p align="center">
  <img alt="Runs on Meta models" src="https://img.shields.io/badge/runs%20on-Meta%20models-0a0a0a">
  <img alt="175 tests" src="https://img.shields.io/badge/tests-175%20passing-0a0a0a">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-0a0a0a">
  <img alt="macOS, Ubuntu, Windows" src="https://img.shields.io/badge/runs%20on-macOS%20%C2%B7%20Ubuntu%20%C2%B7%20Windows-0a0a0a">
</p>

---

## By the numbers

Measured on 41 real reels, round after round, by a Muse Wonder judge (1 to 5) and by code. The details are on the
`/lab` page.

| | Before | After |
|---|---:|---:|
| Best moment per reel (for Linda, 79) | 3.61 | **4.31** |
| How natural it sounds ("sounds like family") | 2.07 | **3.82** |
| Moments with a robotic habit | 85% | **5%** |
| Reels with a moment at 4.2 or more | 4 of 41 | **25 of 41** |
| Problems the judge found | 233 | **91** |
| A grandchild's set (Leo, 9): best moment per reel | | **4.45** (31 of 41 at 4.2+) |
| Unsafe findings that got past the checks, latest rounds | | **0** |
| Questions answered right from a real Notion workspace | 7/10 | **10/10** |

*Before and after are rounds 5 and 7 under the same judge, except Notion (the first and last test runs once search listed the pages).*

| Scale of the tuning | |
|---|---|
| Runs through the agents | **418** |
| Moments made and scored | **1,883** |
| Model calls | **5,322** |
| Measured changes to agents, tools and workflow | **43** |
| Cost per reel per round, judge included | **about $0.11** |
| Automated tests | **175** |

## Contents

[Product](#product) · [Architecture](#architecture) · [Models](#models) · [Quick start](#quick-start) ·
[Configuration](#configuration) · [Demo guide](#demo-guide) · [Quality and evaluation](#quality-and-evaluation) ·
[Security and privacy](#security-and-privacy) · [Cost](#cost) · [Troubleshooting](#troubleshooting) ·
[Project layout](#project-layout)

## Product

| For | What RoleEdge does |
|---|---|
| **The caregiver** (the Studio) | Share anything: a reel or a link, a photo, a voice note or typed words. Agents research it, check its claims and suggest the best moment for her: a note, slides, a mind map, a quiz, an animated video, a picture or a fridge card. Nothing reaches her until you approve it. **Behind the scenes** shows every agent at work. |
| **The parent** (her phone) | Large type, a talking avatar, the device's voice or your own recording. She taps or holds the microphone to reply, and asks her assistant about her day: "when is my appointment?". |
| **A grandchild** | The same content as a picture story, a quiz game, a mind map or "ask Grandma", checked by a child-safety review. |
| **Everyone** | Her replies become a two-line summary, her needs and today's signals. A trend engine compares her last two weeks with her usual weeks. It reports observations only and never gives medical advice. |

Two made-up families come with it: **chen** (English; Maya, her mother Linda, Leo, 9) and **sato** (Japanese; Kenji,
his mother, Hana, 8).

## Architecture

![RoleEdge architecture: the caregiver's Studio and Mom's phone talk to one server, where four pipelines run on Meta models and every message to her passes a final code check](docs/img/architecture.svg)

- **Studio share:**
  - **Read.** A watcher sees the whole video; a reader and web search check what it says.
  - **Understand.** A fact check runs, every film, product or song named is looked up, and the agents ask how she
    takes things in.
  - **Plan.** The planner picks the best moment for her.
  - **Make.** Each moment you pick gets its own maker.
  - **Verify.** Muse Wonder reads everything before you do.
  - **Send gate.** Code runs the final check.
- **Typed news:** a quick intent check, then one rewrite in her words. A message to pass on doesn't need research.
- **Her replies:** transcription, a reply reader, and a trend engine (code).
- **Her questions:** a router, then her calendar, mail or notes (her own accounts, or prefilled demo ones). The answer
  uses only what was read, and code checks its quotes.

Built with FastAPI and WebSockets for live updates, SQLite, and plain HTML, CSS and JavaScript (no build step).
three.js draws the 3D avatar.

## Models

Every model called at runtime is a Meta model.

| Model | Job in RoleEdge | Price |
|---|---|---|
| `muse-spark-1.3` | Every agent. Watches whole videos (video input) and reads photos, searches the web, returns strict JSON for each agent's schema, and writes in her language | $1.25 / $4.25 per million tokens in / out (contributor variant: $0.10 / $0.20) |
| `muse-wonder-1.0` | The verifier, and the judge in the tuning lab | $4 / $20 per million tokens |
| `muse-image-1.0` | The picture moment, and the avatar's portrait with its mouth and blink frames | $0.01 per image |
| `sam-3.1` | What to watch in each still, the avatar's mouth and eyes, product cut-outs | $2.50 per 1,000 images |
| `muse-voice-transcribe-1.0` | Her voice replies, and captions for your own recordings | $0.18 per hour |

There is no text-to-speech model: the device's own voice speaks, and Meta has no voice model to use instead. The
child-safety model we fine-tuned, [Llama-Garvit-1.0](https://huggingface.co/pra40109/Llama-Garvit-1.0), is research
only. It is not run here, because Llama doesn't count as a Meta model in this hackathon.

## Quick start

You need a **Meta Model API key** (dev.meta.ai), **Python 3.11+** and **ffmpeg** (for video and voice).

```bash
cp .env.example .env        # 1. add your key: META_API_KEY="..."
bash run.sh                 # 2. the first run installs into .venv (a few minutes, about 250 MB), then starts
                            # 3. open http://localhost:8100
```

<details>
<summary><b>macOS</b></summary>

```bash
brew install python@3.12 ffmpeg
cp .env.example .env && open -e .env     # add your key
bash run.sh
```
</details>

<details>
<summary><b>Ubuntu and other Linux</b></summary>

```bash
sudo apt install python3 python3-venv ffmpeg     # Ubuntu 22.04: python3.11 python3.11-venv
cp .env.example .env && nano .env                # add your key
bash run.sh
```
</details>

<details>
<summary><b>Windows 10 and 11 (PowerShell)</b></summary>

```powershell
winget install Python.Python.3.12 Gyan.FFmpeg     # then open a new PowerShell window
copy .env.example .env; notepad .env              # add your key
powershell -ExecutionPolicy Bypass -File run.ps1
```

The Windows script hasn't been tested on Windows yet. The same steps by hand:
`$env:PYTHONUTF8 = "1"`, then `py -3.12 -m venv .venv`, `.venv\Scripts\python -m pip install -e .` and
`.venv\Scripts\roleedge serve --port 8100`.
</details>

To use another port, run `PORT=8200 bash run.sh` (on Windows: `$env:PORT=8200` first). To start over with clean demo
families, run `.venv/bin/roleedge serve --reset` (Windows: `.venv\Scripts\roleedge serve --reset`), or press
**Reset demo** in the Studio.

## Configuration

Everything goes in `.env`. Only the key is required.

| Variable | Default | What it does |
|---|---|---|
| `META_API_KEY` | (required) | Your Meta Model API key |
| `ROLEEDGE_PROVIDER` | `meta` | The provider for every agent |
| `META_MODEL` | `muse-spark-1.3` | The agents' model. `muse-spark-1.3-contributor` costs about a tenth as much, but Meta trains on what is sent; it also needs `ALLOW_CONTRIBUTOR_MODELS="1"`. Use it only with the made-up demo families |
| `ROLEEDGE_STUDIO_SPEND_CAP_USD` | `10` in `.env.example` | No new model call past this spend (estimated from the usage ledger), even in the middle of a run |
| `ROLEEDGE_LEDGER_BACKUP` | (empty) | A file on lasting storage (on Cloud Run, a mounted Cloud Storage bucket) that keeps the spend across restarts and deploys |
| `NOTION_TOKEN` | (empty) | A Notion internal integration's secret, for real notes |
| `ROLEEDGE_GOOGLE_CLIENT_ID`, `ROLEEDGE_GOOGLE_CLIENT_SECRET` | (empty) | A Google OAuth client, for real Gmail and Calendar (read-only) |
| `ROLEEDGE_VAULT_KEY` | generated | The key that encrypts connected accounts' tokens |

When the optional values are left empty, the prefilled demo mail, calendar and notes answer instead.

## Demo guide

Put the Studio and her phone side by side; the phone updates live.

| Open | For |
|---|---|
| `/studio` | The caregiver's Studio |
| `/phone/chen` | Linda's phone (English) |
| `/phone/sato?subs=1` | Okaasan's phone (Japanese, with English subtitles) |
| `/lab` | How the agents were tested and tuned |
| `/` | The product page |

1. **Share a reel.** In the Studio, press **Link** and paste a public Instagram, YouTube or TikTok link (or upload the
   video), then **Research and plan**. The best moment is picked; press **Make**, then **Approve and send**. Add
   another moment from the card at any time. If she already has the pack, the new moment waits for your approval.
2. **Send typed news.** "Tell mom I'll call after my meeting at 6" takes the fast way: one rewrite in about 5
   seconds. **Record** lets you say it in your own voice instead.
3. **Reply as her.** Tap a reply, or hold the microphone ("I didn't sleep well, and we're out of rice"). You get a
   summary, her needs and today's signals.
4. **Ask her assistant.** On her phone: "when is my doctor's appointment?".
5. **A grandchild.** Pick **Leo** under "Explain it to".

## Quality and evaluation

- **Method.** 41 of 44 real reels went through the Studio's own agents in 7 rounds for a parent and 4 for a child (the
  other 3 were photo posts with no video).
  - A Muse Wonder judge scored every moment on faithfulness, clarity, engagement, usefulness, format fit and how
    natural it sounds.
  - Code counted the rest: robotic habits, gate holds and unsafe findings.
  - Each weakness was traced to its cause (instructions, workflow, tool, judge or model) and changed. Every change but
    the latest was measured again in a later round.
- **Where to look.** The `/lab` page shows the aggregate results (no reel is shown or named). The full log is in
  [docs/REEL_LAB.md](docs/REEL_LAB.md).
- **Fine-tuning.**
  - 117 approved moments are kept as a training set in the family's voice (`python -m roleedge.lab dataset`).
  - The child-safety LoRA caught 99.6% of unsafe lines on held-out data, against 52% before training.
- **Tests.** 175 automated tests: `.venv/bin/python -m pip install -e ".[dev]"`, then `.venv/bin/python -m pytest`.

## Security and privacy

- **Nothing reaches her unchecked.** Every word she sees or hears passes a send gate written in code: no money,
  codes, card numbers, links or secrecy, and every date must be in what you shared. Your shares wait for your
  approval. A grandchild's set gets a child-safety review.
- **Keys stay in `.env`.** Connected accounts' tokens are encrypted at rest. Google access is read-only.
- **Local by default.** The server listens on `localhost` only, and data stays in `output/` (SQLite and uploads).
- **No real people.** The demo families are made up. The reels used for tuning are other people's content, so they
  are not included.
- **No medical advice.** The app reports observations with dates; people decide what to do.

## Cost

| Action | Default model | Contributor model |
|---|---|---|
| A reel's research and its best moment | a few cents | about a cent |
| A full set of five moments (research, makers, verification, picture) | about $0.15 | about $0.04 |
| A quick message or a reply | under $0.01 | under $0.01 |
| A minute of voice transcribed | $0.003 | $0.003 |

Every call is logged with its price in `output/usage.jsonl`. The Studio shows a running total.

## Troubleshooting

| You see | Do this |
|---|---|
| `Add your Meta Model API key ...` | Put the key in `.env` as `META_API_KEY="..."` |
| `The Meta key didn't work` | Check the key at dev.meta.ai, and that it can use `muse-spark-1.3` |
| `ensurepip is not available` (Ubuntu) | `sudo apt install python3-venv` (or `python3.12-venv`) |
| `running scripts is disabled` (Windows) | Start it with `powershell -ExecutionPolicy Bypass -File run.ps1` |
| `Address already in use` | Use another port (see Quick start) |
| A video, link or voice note fails | Install ffmpeg. If a site blocks the link, upload the video file |
| No sound on her phone | Tap the page once, check the volume, or try Edge (its "Natural" voices sound best) |

## Project layout

```
src/roleedge/
  app/        the server: routes, live updates, the send gate's use, your own voice
  studio/     the research swarm, the planner, one maker per moment, the verifier
  compose/    the fast way: intent and one rewrite
  errands/    her assistant: schedule, mail, notes, prices
  trends/     the trend engine (code)
  lab/        the tuning lab: rounds, judges, reports, the dataset
web/app/      the screens: home, Studio, her phone, the lab (no build step)
data/lab/     the lab's results in aggregate, which /lab shows (python -m roleedge.lab report)
tests/        175 automated tests
docs/         design, findings, the tuning log, the architecture diagram
```

---

<p align="center"><sub>© 2026 Role Enterprise. All rights reserved. Third-party code keeps its own licence
(<a href="web/app/vendor/LICENSES.md">web/app/vendor/LICENSES.md</a>).</sub></p>
