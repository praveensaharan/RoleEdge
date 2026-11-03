# roleEdge at the Meta Global AI Developer Hackathon: build plan

*Draft v0.1, 2026-10-31. Product brief: [PIVOT.md](PIVOT.md). Hackathon window: Oct 26, 12:00 PM EST → **Nov 4,
9:00 PM EST** (that is Nov 5, 02:00 UTC / 07:30 IST / 11:00 JST). Track: **Build for Your World**.*

---

## 1. What the judges score, and our answer

| Stage / criterion | Weight | What it asks | Our answer |
|---|---|---|---|
| Stage 1 (pass/fail) | — | Fits a track; really uses Meta models | "Build for Your World": caring for parents far away. **Every model call in the shipped app goes to Meta**, except voice and avatar, which Meta does not offer (section 2). |
| Impact | 30% | Real problem, real users | Japan's older people living alone and their busy children; early notice of change, not just "is she active?" |
| Use of Meta AI tooling | 25% | Creative, beyond basic integration | Seven Meta models, each doing a job the others can't (section 2) |
| Technical depth | 20% | Sound engineering, craft | A team of agents where code makes the decisions; gates against injected instructions and fake mail; the trend engine; tests |
| Demo | 25% | Works live; a video worth watching | Two working prototypes (English and Japanese) at a public URL, and a 3-minute story (section 5) |

**Two rules that can disqualify us** (participant guide):
1. **"Only highlight what you built during the Hackathon."** Everything shown working must really work. Parts that
   are simulated (checkout, the doctor booking) are labelled "simulated" on screen. Roadmap items (children) are
   labelled "coming soon".
2. **Anti-project: "AI that gives medical advice."** roleEdge never tells anyone what condition she may have or
   what to take or eat. It **notices changes and gets people talking**: you, Mom, her doctor. The video says this
   in so many words.

## 2. Meta tooling map

| Meta model | Job in roleEdge | Why it is more than a basic integration |
|---|---|---|
| **Muse Spark 1.3** | Every agent: composer, check-in (tool calling), gates, signal extraction (structured output), shopper | A team of agents behind code gates; tool calling with our own tools |
| **Muse Spark 1.3, built-in `web_search`** | The shopper finds where to buy and at what price, within your limit | "Finds things and buys them", the Muse pattern you asked for (verify that `web_search` is enabled for our key) |
| **Muse Spark 1.3, video input** | Watches a shared reel (curry recipe, scam warning) and turns it into simple steps | Reads the reel itself instead of sampled frames |
| **Muse Spark 1.2, audio input** | Listens to *how* Mom sounds (tired, breathless, flat), alongside the measured voice features | 1.3 does not fully support audio yet; 1.2 does (Meta docs) |
| **Muse Voice Transcribe** | Mom's voice replies and check-ins | Realtime WebSocket; test Japanese |
| **SAM 3.1** | Mom shows her fridge or pantry. SAM picks out each item, Spark names them, and code works out what's missing for tonight's curry. | Physical world → shopping list. This connects to the "Push the Frontier" spirit. |
| **Muse Image** | Illustrated step cards and diagrams for Mom (text drawn by code on top) | Visual explanations, not text walls |
| **Muse Wonder** | The weekly review: reads 4 weeks of signals and drafts the doctor summary in plain words (code chooses what goes in) | Used rarely, for the hardest writing job |
| Stretch: **Muse Glimmer** (open weights, 30B) | Private extraction of health signals on our own GPU. In the product: on-device (ExecuTorch) and fine-tuned for the child guardian | Needs an 80 GB GPU in bf16 (about $4/hour on Modal), so only if time allows |

**Not Meta (Meta has no equivalent):**
- Qwen3-TTS for your cloned voice and the assistant voice;
- MuseTalk for the avatar.

Both run on Modal, and the README says so plainly.

## 3. Scope

| Priority | Feature | Meta models used |
|---|---|---|
| **Must** | Closed circle with QR pairing; your chat next to a live mirror of Mom's phone | — |
| **Must** | Compose → Mom gets your avatar and voice (voice switch, small "assistant" icon) | Spark |
| **Must** | Mom replies by voice → summary for you, needs list, today's signals | Transcribe, Spark 1.3 + 1.2 |
| **Must** | Check-in playbook (the existing agent loop, moved to Meta) with voice | Spark (tools) |
| **Must** | **Trend engine** on 6 weeks of synthetic history → trend card → weekly summary → doctor summary → support-centre pointer | Spark, Wonder |
| **Must** | Shopper: three lanes, spending limit, simulated one-time-card checkout | Spark + `web_search` |
| **Should** | Answer Mom from Gmail, Notion and Slack, with the gates (verified senders, disclosure table, injection guard, Slack approval) | Spark |
| **Should** | Reel → simple steps plus an illustrated card; a scam reel → a warning | Spark (video), Image |
| **Should** | Japanese prototype (a second circle with Japanese on Mom's side) | all |
| **Could** | Fridge photo → missing ingredients | **SAM 3.1** + Spark |
| **Could** | Children "coming soon" page with a held-message example | Spark |
| **Stretch** | Muse Glimmer for private signal extraction | Glimmer |

**If we fall behind, cut in this order:**
1. Glimmer;
2. Slack reading (keep Slack sign-in);
3. Notion;
4. per-message live avatar (use pre-rendered clips instead);
5. polish of the Japanese prototype;
6. the fridge photo.

The USP (trends) and the avatar message are never cut.

## 4. Day plan

| Day | Goal | Done when |
|---|---|---|
| **Fri Oct 31 (today)** | **Foundations and Meta spikes.** Public GitHub repo with history from today. Implement `MetaProvider.call_tools` (the flat Responses format from the docs). Probe structured output, video input, 1.2 audio input, Voice Transcribe (EN/JA), SAM 3.1, Muse Image and `web_search`. Create the Modal account. **You record a 60 s video and 2 min of voice.** | Each Meta model returns a correct result once; the existing check-in calls run on Meta with the same status colours |
| **Sat Nov 1** | **The avatar path end to end.** FastAPI app, SQLite, sign-in, circle and QR pairing, chat, Mom's phone mirror over WebSocket. Qwen3-TTS and MuseTalk on Modal. Composer on Spark. | You type a message and Mom's screen plays your avatar saying it |
| **Sun Nov 2** | **The USP.** Mom's voice reply → Transcribe → reply reader → today signals. Check-in playbook with voice. Trend engine plus synthetic history, trend card, weekly summary, doctor summary (PDF). Shopper. | The full health story runs from a fresh start |
| **Mon Nov 3** | **Sources and reach.** Gmail (RoleSpace's Google project, test users), Notion, Slack; T8 checks, disclosure table, injection guard, Slack approval. Reel explainer and Image cards. Japanese circle. Fridge (SAM). Children page. | Every "Should" item works on the live URL |
| **Tue Nov 4** | **Ship.** HTTPS deployment, feature freeze at 12:00 EST. Record and edit the video. README with the "built during the hackathon" section. **Submit by 18:00 EST**, leaving 3 hours of buffer. | The submission is in; the repo is public; the video link opens in a private window |

## 5. The 3-minute video

| Time | Scene | What it shows |
|---|---|---|
| 0:00–0:20 | The problem | Japan: a parent living alone, a child in Tokyo meetings. Today's services only ask "is she active?" |
| 0:20–0:50 | **Kenji messages from a meeting** | "What are you cooking tonight?" → Mom's phone shows Kenji's avatar and voice |
| 0:50–1:20 | **Mom answers by voice** | "Curry, but no onions… and I didn't sleep well." → Kenji sees a 2-line summary, "slept badly" today, and onions within his limit → approve → one-time card (simulated) |
| 1:20–1:45 | **Mom asks while he's busy** | "When does my parcel come?" → answered from a verified Yamato mail; a fake Sagawa mail is blocked; a work-trip question goes to Kenji in Slack |
| 1:45–2:30 | **The USP** | 4 weeks: more skipped meals, slower speech, the same question twice, not going out → trend card → weekly summary → doctor summary → support centre → Kenji calls her |
| 2:30–2:45 | Reels | A scam reel becomes a warning in Kenji's voice; a recipe reel becomes illustrated steps |
| 2:45–3:00 | What's next and what's Meta | Children coming soon; one slide naming every Meta model and its job; "built during the hackathon" |

## 6. Compliance checklist

- [ ] **The repository is public.** It contains no `.env`, no keys, no face or voice recordings and no real
  personal data. Demo data is synthetic (rule S7).
- [ ] **The README has a "Built during the hackathon" section.** All code here was written from Oct 27, inside the
  window. That includes the CareCircle prototype, which is committed first and labelled as such.
- [ ] **The README lists what is pre-existing:**
  - RoleSpace's design tokens (our own, from before Oct 26);
  - RoleSpace's Google Cloud project, used for Gmail sign-in;
  - the licences of third-party models (Qwen3-TTS: Apache-2.0; MuseTalk: MIT, with the licences of its face models
    checked).
- [ ] **Prompts and on-screen text are reviewed for medical advice:** observations only, people as the next step.
- [ ] **Simulated parts are labelled on screen** (checkout, doctor booking); children are labelled "coming soon".
- [ ] **Every team member is listed** on the submission.

## 7. Risks

| Risk | Plan |
|---|---|
| Meta tool calling or audio input behaves differently from the docs | Test today. Azure gpt-5-mini stays wired as a fallback through `llm/`, but the demo must run on Meta to pass Stage 1. |
| The avatar render is too slow or looks wrong | Pre-render the clips used in the video; live render stays in the app |
| A Modal cold start during the live demo | Keep the two GPU containers warm only while judges may test (scheduled), and show a "preparing" state |
| Gmail test users | Add judges' emails if the organisers share them; otherwise the demo account path |
| Running out of time | The cut order in section 3 |
