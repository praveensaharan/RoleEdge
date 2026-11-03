# RoleEdge

RoleEdge helps a grown child care for a parent who lives far away. The child shares a reel, a link, a photo or a few
typed words. A team of agents researches it, checks the facts and turns it into something the parent can take in:
a short note, slides, a mind map, a gentle quiz, an animated video and a picture. The parent's replies come back as a
summary and a weekly trend. Every model call goes to Meta models: Muse Spark, Muse Wonder, Muse Image, SAM 3.1 and
Muse Voice Transcribe.

The app comes with two made-up families:

| Family | Caregiver | Parent | Grandchild |
|---|---|---|---|
| `chen` (English) | Maya, her daughter | "Mom", Linda | Leo, 9 |
| `sato` (Japanese) | Kenji, her son | "Okaasan" | Hana, 8 |

## What you need

- **A Meta Model API key** (dev.meta.ai).
- **Python 3.11 or newer.** Check with `python3 --version`. On a Mac without it: `brew install python@3.12`, or use
  the installer from python.org.
- **ffmpeg**, for videos, reel links and voice recordings: `brew install ffmpeg` (Mac) or `sudo apt install ffmpeg`
  (Linux). Typed messages and web pages work without it.
- An internet connection. The first run installs about 250 MB of Python packages into the folder.

## Start it (Mac or Linux)

1. Unzip, then open a terminal in the `roleedge` folder.
2. Copy the settings file and add your key:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in `META_API_KEY="..."`. Nothing else is required.
3. Run:
   ```bash
   bash run.sh
   ```
   The first run installs the app into `.venv` (a few minutes), checks the key with one tiny call, then starts the
   server. Later runs start in seconds.
4. Open **http://localhost:8100**.

Port 8100 already in use? Run `PORT=8200 bash run.sh` instead.

**Windows** (not tested): install Python 3.11+ and ffmpeg, then in PowerShell, in the `roleedge` folder:

```powershell
copy .env.example .env      # then add your key to .env
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\roleedge serve --port 8100
```

## What to open

Put the caregiver's screen and the parent's phone side by side. The phone updates live.

| Page | What it is |
|---|---|
| http://localhost:8100/ | The home page |
| http://localhost:8100/studio | **The caregiver's workspace**: share something, watch the agents work, approve what goes out |
| http://localhost:8100/phone/chen | **Linda's phone** (English) |
| http://localhost:8100/phone/sato?subs=1 | Okaasan's phone (Japanese; `?subs=1` adds English subtitles) |
| http://localhost:8100/lab | **The tuning lab**: 44 real reels (41 with a video), 7 rounds of tuning, the judges' scores and every change we made |

## Things to try

1. **Share a reel.** In `/studio`, with **Mom** picked under "Explain it to", press **Link** and paste a public
   Instagram, YouTube or TikTok link, or use **Photo or video** to upload a short one. Keep **Research first** and press
   **Research and plan**. The agents watch it, look things up and propose a set of
   moments. Press **Make**, read what they wrote, then **Approve and send**. It arrives on `/phone/chen`. A pack takes
   one to three minutes. If a link won't download (some sites block it), upload the video file instead.
2. **Send a quick message.** Choose **Quick message**, type something like "tell mom I made her soup recipe and ask if
   she wants some on Sunday" and send it. On the card, **Record** lets you say it in your own voice. Code makes the recording
   clearer, and Mom hears you instead of the device voice.
3. **Reply as Mom.** On her phone, tap a reply, or hold the microphone and talk ("I didn't sleep well, and we're out
   of rice"). The caregiver gets a short summary, her needs and today's signals.
4. **Ask her assistant.** On her phone, ask "when is my doctor's appointment?" or "what goes in my chicken soup?".
   It answers from the prefilled demo calendar, mail and notes.
5. **A grandchild.** Share something for Leo instead of Mom. The same content comes back as a picture story and a
   quiz game, checked for a 9-year-old.

To start over with clean demo families, stop the server and run `.venv/bin/roleedge serve --reset`.

## What it costs on your key

Every call is logged in `output/usage.jsonl` with its price. The Studio panel shows a running total.

| Action | Muse Spark 1.3 (default) | Muse Spark 1.3 contributor |
|---|---|---|
| A full Studio pack (research, five moments, verification, picture) | about $0.15 | about $0.04 |
| A quick message or a reply | under $0.01 | under $0.01 |
| A minute of voice transcribed | $0.003 | $0.003 |

New Studio shares stop at $10 of spend. Change `ROLEEDGE_STUDIO_SPEND_CAP_USD` in `.env` to raise it. The
contributor model is cheaper because Meta trains on what is sent to it. That is acceptable for these made-up families,
but not for real ones, so the app only uses it when you also set `ALLOW_CONTRIBUTOR_MODELS="1"`.

## Good to know

- **Voice.** The device voice reads the messages. The organisers ruled that only Meta models may run at runtime, and
  Meta has no text-to-speech model. Edge's "Natural" voices sound best. Browsers only speak after a first tap on the
  page. A caregiver's own recording is played as recorded.
- **Gmail, Calendar and Notion.** Without your own Google OAuth client or Notion token in `.env`, the prefilled demo
  accounts answer.
- **The lab page** shows the results of our tuning rounds. The reels themselves, their stills and the product photos
  found online are other people's content, so they are not included. Re-running the lab needs those reels.
- **Your data stays on your machine.** It is kept in `output/` (SQLite and uploads). The server only listens on
  `localhost`.

## Something went wrong

| You see | Do this |
|---|---|
| `Add your Meta Model API key ...` | Put the key in `.env` as `META_API_KEY="..."` |
| `The Meta key didn't work` | Check the key at dev.meta.ai, and that it can use `muse-spark-1.3` |
| `Address already in use` | `PORT=8200 bash run.sh` |
| A video or voice note fails | Install ffmpeg |
| No sound on the phone | Tap the page once, check the volume, or try Edge |

## Where things are

- `src/roleedge/`: the app. `studio/` holds the research swarm and makers, `app/` the server, `errands/` the
  assistant, `trends/` the trend engine, `lab/` the tuning lab.
- `web/app/`: the screens.
- `tests/`: `.venv/bin/python -m pip install -e ".[dev]"`, then `.venv/bin/python -m pytest`.
- `docs/`: the design (`PIVOT.md`, `HACKATHON.md`), the tuning log (`REEL_LAB.md`, `reel-lab/`), what we found
  (`FINDINGS.md`) and the connections (`reel-lab/INTEGRATIONS.md`).
