# Pivot brief: from CareCircle to roleEdge

*Draft v0.4, 2026-10-31. Sources: `hello.md` and your answers in it. Nothing here is built yet. "Verify" marks a
claim that still needs a primary source or a test. Earlier research: [PLAN.md](PLAN.md), [FINDINGS.md](FINDINGS.md).*

> **This is being built for the Meta Global AI Developer Hackathon, due Nov 4, 9:00 PM EST.** The hackathon scope,
> day plan, video and rules are in [HACKATHON.md](HACKATHON.md). This brief describes the full product the demo
> points towards.

---

## 1. Decisions so far

| Topic | Decision | What it means for the build |
|---|---|---|
| Why pivot | CareCircle was too basic, with no strong USP | The USP is health and behaviour trends, with an early step to a doctor (section 2) |
| Name | **roleEdge** (final) | Not "Muse X / Muse Edge": Muse is now Meta's own agent product (muse.ai) |
| Look | **Professional and productive first,** in roleEdge's own enterprise design system (Geist, black for the brand and actions, colour only for status); muse.ai is only a loose reference | Section 12 |
| Market | **Japan first, then global** | APPI, the PMD Act (medical devices) and Japanese partners first. Every language string is translatable from day one |
| Build language | English while building. **The final output has two prototypes people can try: English and Japanese** | Two demo circles; the circle sets the language |
| Who can message | **Closed circle.** Both people approve the link once, in person, and nobody else can message | No phone-number messaging |
| Agent instructions | **Preset playbooks**, or a confirmation from you in the middle of a task | Section 4 (T2) |
| Cloned voice and avatar | Used **both** for your approved words **and** when the agent speaks on its own; only inside the app | Section 4. The face is shown as an avatar |
| Whose voice is sent | **A switch on each message:** your cloned voice or an assistant voice | Section 8. A real celebrity's voice or face is not an option (section 9, C1) |
| Sources for answering Mom | **Gmail, Notion and Slack.** Each user is asked for consent to connect each one at sign-in. The video presents it as "connect any app" | Section 4 and section 9, C2 |
| T4 label | **Agreed:** a small, quiet icon on messages the agent spoke, which Mom agrees to at setup | Section 4 |
| Spending limit | **¥3,000 per order, ¥20,000 per month**; simulated checkout in the demo | F2 |
| Demo audience | **Gmail test users** (up to 100); the demo account for anyone else, such as judges | Section 9, C2 |
| Mail from companies | **Allowed** from verified senders (for example "parcel arrives Monday") | Verified senders only (T8) |
| Shopping | Tonight's ingredients, staples, **medicine and daily items**; the **agent spends within a limit you set** | Section 5, F2 and section 9, C6 |
| Kids | **"Coming soon"** in the demo, with a walkthrough of how the safety layer works | Section 11 |
| Health story | **Go deep:** trend → next step → **connect to a doctor** | Section 2 |
| Models while building | You asked for Azure gpt-5-mini first, then Meta. **For the hackathon I recommend Meta from day 1** (HACKATHON.md §1, §7) | Section 7; to confirm |
| Budget | Meta $100, Modal $100 (this already includes Modal's $30 free credit), Azure gpt-5-mini credits | Section 7 |
| Grandparent and child messaging directly | Later | Every message goes through you for now |

## 2. The USP: notice the change early, and act

Existing *mimamori* (watching-over) services answer **"Is she active?"** roleEdge answers **"How is she changing,
and what should we do about it?"**

1. **Warm everyday conversation** in her child's voice and face, so she wants to talk.
2. **A personal baseline** of how she sounds and behaves:
   - **voice:** speaking rate, pauses, pitch range, loudness;
   - **language:** word-finding pauses, repeating herself, shorter answers;
   - **routine:** how fast she replies, missed check-ins;
   - **what she reports:** meals, sleep, pain, medicine, mood;
   - **social:** who she talked to, whether she went out.
3. **Code spots a sustained drift**: at least two signals outside her normal range for about a week. The model
   only extracts the signals; it never makes the decision (rule A3).
4. **A next step that scales with the change:**

| Level | What you get | Who acts |
|---|---|---|
| Small change | A trend card after the check-in: "She has mentioned skipping lunch 4 times this week (usually once)" | You: call her tonight |
| Sustained change in several signals | A weekly summary, plus suggested steps | You: visit; ask about her week |
| Change worth a professional's eyes | A **doctor summary**: one page of observed changes with dates, no interpretation, for her family doctor (*kakaritsuke-i*) or an online consultation | Mom and her doctor (only with her consent) |
| Care or support need | A pointer to her area's **Community General Support Centre** (*chiiki hōkatsu shien sentā*), Japan's official first stop for older people's care questions | You or Mom |
| Emergency signs in a call | The existing red path: tell her to sit down safely, call 119, alert you at once | Code (rule S3) |

**The line we never cross:** we report changes we observed. We never say what they mean medically (section 9, C4).
This also keeps us clear of the hackathon's banned "AI medical advice" projects.

### 2.1 Wellbeing signals, at two speeds

**Today** means one conversation is enough to tell you, in the summary after it. **Trend** means it only counts
when it lasts.

| Area | Today (one conversation) | Trend (weeks) | Heard from | Red flags (immediate alert, advise 119) |
|---|---|---|---|---|
| Eating and drinking | Skipped a meal; not hungry; little water on a hot day | More skipped meals; "not hungry" more often; fewer food needs on the list | What she says; the shopping list | — |
| Sleep | Slept badly; napped a lot | More bad nights | What she says | — |
| Medicine | Missed a dose, or isn't sure (amber, rule S3) | Missed doses per week | What she says; reminder taps | — |
| Body | Pain, dizziness, a cold or cough, "not feeling well", low energy | More mentions; less energy in her voice | What she says; her voice | A fall, chest pain, breathlessness, fainting, sudden confusion, slurred speech |
| Mood | Low, lonely, worried | Mood words over time; loneliness | What she says; her tone (Muse Spark 1.2 listening) | — |
| Memory and orientation | Unsure of the day or date; forgot a plan; asked the same question twice in one call | More repeated questions and stories; more missed plans | Transcript | — |
| Social and going out | Stayed in; talked to no one | More days without contact | What she says (`social_contact`) | — |
| Voice | Not used for a single day (too noisy) | Slower speech, longer pauses, smaller pitch range, quieter | Measured audio features | — |
| Routine | Late first reply; missed a check-in | Replies getting slower; more missed check-ins | App events | A missed check-in plus no reply for hours → call you |
| Home and season (Japan) | A very hot day and little water; a cold bathroom in winter | — | What she says, plus the local weather | — |

**What happens next:**
- **Today signals:** the summary you get after each conversation, and a ready action ("order her lunch", "call her
  tonight").
- **Trend signals:** a trend card, then the weekly summary, then the doctor summary and the support-centre pointer
  (the table above).
- **Every signal is stored with its date and the exact words or measurement behind it.** Then the doctor summary
  can quote evidence instead of interpreting it.

## 3. People, screens and language

| Person | Screen | Language |
|---|---|---|
| You | Text summaries, approvals, trend cards, a live pane showing what Mom sees | English |
| Mom | Your avatar video, voice messages, simple diagrams, big reply buttons | English while building; **Japanese in the Japan demo** |
| Child (coming soon) | Cartoon-style explainers behind the safety layer | English or Japanese |

## 4. Trust model

| # | Rule | How it is enforced |
|---|---|---|
| T1 | **Closed circle.** You and Mom link once with both sides approving: a QR code scanned in person, or a confirmed invite. Then it works anywhere. | Server rejects messages from non-members |
| T2 | **Instructions come from you, not from content.** The agent follows **playbooks** you set (daily check-in, weekly summary, "answer schedule questions", "watch staples") and **asks you to confirm** anything outside them. Text it reads in Gmail, Notion, reels or messages is data, never instructions. | Code: playbooks are stored settings; confirmations are signed events from your session |
| T3 | **Your voice and avatar appear only inside the app.** We teach Mom: "Kenji's voice outside roleEdge, for example a phone call, may be fake." | Onboarding, with a monthly reminder |
| T4 | **She can tell your words from your agent's.** A small, quiet icon marks agent-spoken messages; Mom agrees to its meaning at setup | Renderer and client |
| T5 | **The final send gate.** Before anything reaches Mom, code blocks requests for money, codes, card numbers or links, "do it now" pressure, and anything a child's policy forbids. | Code, as the last step of every send |
| T6 | **Family code word** for any real money request. | Onboarding |
| T7 | **Consent.** You consent for your own voice and face. Mom opts in to receiving them, to voice analysis, and (separately) to sharing summaries with a doctor. Inferred health information and handing it to a third party both need her prior consent under APPI. | Consent records |
| T8 | **Verified company mail.** Mail from companies counts only if it **passes sender authentication** (SPF/DKIM/DMARC) **and** comes from a domain on an allowlist (Yamato, Sagawa, Japan Post, Amazon, Rakuten and so on). Only facts are taken (date, time window); **never links or instructions**. | Code checks the mail's authentication headers and the allowlist |

T8 matters for a specific reason: **fake delivery notices pretending to be Sagawa, Yamato or Japan Post are among
the most common scams in Japan.** A courier mail that fails authentication must never reach Mom as "your parcel
comes Monday".

**What can be shared from your sources:**

| Category | Default |
|---|---|
| Schedule, whereabouts at city level, travel plans, family events, deliveries | Share |
| Work details, health, money, other people's information | **Ask me first** (one tap in Slack or the app) |
| Passwords, finances, confidential work | Never |

If you don't answer, Mom hears "I'll ask him and get back to you."

## 5. Core flows

| # | Flow | What happens |
|---|---|---|
| F1 | Compose and approve | You type or speak and choose the voice (yours or the assistant's). The agent turns it into Mom's format. You preview her screen, then approve, or it is sent at once if you turned that on. |
| F2 | **Needs and shopping** | Mom's replies become a needs list in three lanes. **Tonight** (onions for the curry): order now. **Staples and daily items** (rice, curry roux, tissues): watched, and bought when the price is good. **Medicine**: refill reminders and suggestions (section 9, C6). Everything stays **within the spending limit you set**, and anything over it asks you first. |
| F3 | Check-in on your behalf | A playbook runs the check-in in your voice, records it, and gives you a summary plus a trend card. |
| F4 | Answer Mom while you are busy | From Gmail, Notion, calendar and verified company mail, through the gates in section 4 |
| F5 | Reel with a personal note | A curry recipe or a scam warning becomes simple steps, with your note, in your voice |
| F7 | **Trends to a doctor (USP)** | Section 2 |
| F8 | See what they see | A live mirror of Mom's screen |
| F6 | Child channel | **Coming soon** (section 11) |

## 6. The agents

Code routes everything and makes every decision that must not be wrong. Models fill in text and structured fields.

| Agent | Job | Kind | Exists today? |
|---|---|---|---|
| Router | Sends each event to the right agent | Code | — |
| Playbook runner | Runs your preset routines; asks you to confirm anything outside them (T2) | Code + LLM | — |
| Composer | Your words → Mom's format and style | LLM | Partly (content transformer) |
| Explainer | Reel, notice or photo → steps, diagram data, narration | LLM | **Yes** (`content/`) |
| Trust checker | Scam check; dates and names against the source | LLM + code | **Yes**, including Japanese dates |
| Source reader | Gmail, Notion and calendar search; returns quoted facts with their source; runs the T8 checks | Connectors + code | — |
| Disclosure gate | Puts each fact in a category; the table in section 4 decides | LLM + code | — |
| Injection guard | Checks drafts for planted instructions | LLM | — |
| Final send gate | T5 | **Code** | — |
| Check-in agent | Conversation and follow-ups; status set by code | LLM + code | **Yes**, including loneliness |
| Reply reader | Mom's voice → transcript, needs, summary | STT + LLM | — |
| Shopper | Needs → product search → price watch → buy within your limit | LLM + code + shop APIs | Partly (order-pending rule) |
| Signal extractor | Voice and language features per conversation | Signal processing + LLM | — |
| Trend engine | Baselines, drift, trend cards, doctor summary | **Code** | — |
| Voice and avatar studio | Cloned or assistant voice; lip-synced avatar video | GPU services (Modal) | — |
| Child guardian | Coming soon | Guard model + code | — |

## 7. Models and budget

**Plan:** build on **Azure gpt-5-mini** (free credits; tool calling, strict JSON and prompt caching are already
verified). Switch agents to **Meta muse-spark-1.3** once everything works. The switch is one setting per agent
through `llm/`.

| Job | Where | Price | Notes |
|---|---|---|---|
| All agents, building phase | **Azure** `gpt5mini` | $0.25 / $0.025 cached / $2.00 per 1M tokens | Uses the free credits. Retires 2027-02-09. |
| All agents, after the switch | **Meta** `muse-spark-1.3` (not `-contributor`, rule S1) | $1.25 / $4.25 per 1M | About 1,500–3,000 messages for $100 (estimate). Check tool calling first (FINDINGS §6). |
| Speech to text | Azure (if transcription is deployed) or Whisper on Modal; Meta `muse-voice-transcribe` later | Meta $0.18 per hour | Meta does not confirm Japanese yet |
| Voice (clone and assistant) | **Modal**: Qwen3-TTS on an L4 or A10 | $0.80–1.10 per GPU hour | A few cents per message |
| Avatar video | **Modal**: MuseTalk on an A10 or L40S | $1.10–1.95 per GPU hour | Roughly 1–3 cents per 15 s clip (estimate) |
| Experiments | Modal | — | Keep $30–40 aside |

**The Modal rule:** everything scales to zero, and containers stay warm only during demos. One L40S left on
overnight costs about $47 a day, which is half the budget in two days.

## 8. Voice and avatar

**The voice switch on each message:**

| Option | How | Notes |
|---|---|---|
| **My voice** | Qwen3-TTS **Base**, cloned from 1–3 minutes of your clean audio | Your clone speaking Japanese is "cross-lingual". Qwen reports English-to-Japanese results, but the accent quality is ours to test. |
| **Assistant voice** | Qwen3-TTS **CustomVoice** (9 preset voices) or **VoiceDesign** (a voice made from a text description, for example "warm, calm Japanese woman in her 40s") | Not a real person's voice, so there are no consent issues. This is the natural choice for the Japanese demo, since you don't speak Japanese. |

All Qwen3-TTS variants are Apache-2.0 licensed and support streaming.

**Changed (Nov 3), after the organisers' ruling** that every model called at runtime must be a Meta model ("an
Apache-2.0 TTS model from another provider can't be used as the voice; a built-in system or browser voice that isn't
an AI model call is fine"), and since no Meta model clones a voice:

- **My voice** is your *real* recording. On a quick message you tap Record (or pick an audio or video file). Code
  makes it clearer (ffmpeg filters, no model: level to -18 LUFS, rumble and steady noise down, long pauses
  shortened, silence trimmed). Muse Voice Transcribe writes down what you said for her captions, and the final send
  gate checks those words. Her phone plays the recording with the avatar's mouth following its loudness
  (`app/voice_routes.py`).
- **Otherwise**, the device voice (`web/app/js/voice.js`) reads the text: the most natural voice the browser has,
  whole sentences with pauses between them.
- **Qwen3-TTS** stays a build-time comparison only (`/compare`).

**The avatar switch follows the voice switch:**

| Option | How |
|---|---|
| **My avatar** | MuseTalk re-draws the mouth on a 30–60 s video of you |
| **Assistant avatar** | The same MuseTalk pipeline on a generated face of a person who does not exist, or a simple animated mark |

**Recording guide for your video:**
- 30–60 s, 1080p, even light, facing the camera;
- natural blinks and small head movements;
- mouth mostly relaxed, hands away from the face.

**Your recordings never go in the repository** (rule S7). They live in a private Modal Volume.

## 9. Challenges

### C1. No real celebrity voices or faces
"Use some Japanese idol" is not possible:
- Japanese courts recognise **publicity rights** for celebrities, and talent agencies enforce them.
- Every voice and avatar vendor forbids cloning without the person's consent.
- It breaks the product's promise that **the only cloned voice in the circle is a real family member who agreed**.

The assistant voice in section 8 covers the same need.

### C2. Real Gmail and Notion for demo users
- **Gmail:** reading mail is a *restricted* Google scope. Until Google verifies the app (including a paid security
  assessment, which takes weeks), it works only for **up to 100 test users you add by email**. Those users see an
  "unverified app" warning, and their sign-ins expire after 7 days (verify). Google's Limited Use policy also
  applies: data is used only for the user's own feature and never for training models.
- **Notion:** OAuth integration. The user picks which pages to share. Easy.
- **Slack:** sign-in plus reading the user's own messages and search, with a user token, once they consent. Slack's
  2025 API terms limit storing message data, so we read when needed and keep nothing.
- **We use RoleSpace's existing Google Cloud project** for the Gmail consent screen. It is pre-existing, so it is
  listed as such for the hackathon. Unless that project is verified for Gmail's restricted scopes, the 100 test-user
  limit still applies.
- **What the demo needs:** consent to connect each source at sign-in for invited test users, plus **a "use the demo
  account" button** for everyone else, including judges whose emails we don't have.
- **Data handling:** tokens are stored encrypted, and demo data is deleted after the session.

### C3. Fine-tuning for children
- **The hosted models can't be changed inside.** We cannot alter the attention layers of Meta's or Azure's hosted
  models.
- **What works is a guard layer around them:** small open safety models that we host on Modal and **fine-tune on
  our own policy** (LoRA), plus code rules and a final gate.
- **Japanese still needs testing:** Llama Guard does not officially list Japanese (verify).
- **For the real app, fine-tuning is possible on Meta's own open models.** Muse Glimmer and Muse Spark Open both
  support supervised and RL fine-tuning (Meta docs). So the product path is a **child guardian fine-tuned from Muse
  Glimmer on our policy**, hosted by us.
- **Children are "coming soon"** in the demo, so this is phase 2 work.

### C4. Health trends must stay observations
- Under the PMD Act, software that diagnoses is a medical device. The doctor summary lists observed changes with
  dates, never a condition or a probability.
- Get a legal check before real users.

### C5. A trend needs history
- A new user has no baseline for about 4 weeks.
- The demo needs **4–8 weeks of synthetic history**, plus a few real recordings to show live features.

### C6. Medicine, money and payment
- **Medicine in Japan:**
  - Prescription medicine needs a prescription. Online, that means a consultation plus online guidance from a
    pharmacist.
  - Some over-the-counter medicines (first class) need a pharmacist's confirmation even online.
  - **So for medicine, the agent reminds and suggests, and never buys.** It also never advises a dose (rule S5
    carries over).
- **Agent spending:**
  - Muse (Meta) has no developer API, so we can't hand shopping to it. We copy its pattern instead: approval
    before purchase, **a one-time card number at checkout**, and a spending limit.
  - In the demo, checkout is simulated. Product search uses the **Rakuten Ichiba** public API for real Japanese
    prices.
- **Fresh food:** tonight's onions can't wait for a sale; only staples are price-watched.

### C7. Speed of a live check-in
- Below 1.5 s per turn is needed.
- The demo runs check-ins as a **voice-message exchange** first, and a live call second.

### C8. Name and look
- "Muse" is Meta's agent product, so the name and Meta's brand assets (including its "Optimistic" typeface) are
  off limits.
- roleEdge with its own mark and design system avoids this. A trademark search is still needed before going public.

## 10. What to find out first (week 1 spikes)

| # | Spike | Pass condition | Cost |
|---|---|---|---|
| 1 | **Voice:** Qwen3-TTS Base cloning your voice (30 s and 2 min references) in English and Japanese, plus one designed Japanese assistant voice | A blind listen says "sounds like you"; the assistant voice sounds natural to a Japanese speaker; first audio in under 0.5 s when warm | Modal about $5 |
| 2 | **Avatar:** MuseTalk with your 60 s video, driven by spike 1's audio | A 15 s clip looks real at phone size and renders in under 30 s | Modal about $5–10 |
| 3 | **Gmail and Notion connect-on-demand**, with a test user, plus the T8 checks on real courier mail | The agent answers "When does my parcel come?" from an authenticated courier mail and refuses a spoofed one | $0 |
| 4 | **Trend engine** on 6 weeks of synthetic history | It flags the planted drift, and stays quiet on a normal history | Azure, cents |
| 5 | **Voice features** (openSMILE / Praat) on the same person, normal vs tired | The features move in the expected direction | $0 |
| 6 | **Japanese speech to text** (Whisper on Modal vs Meta) | Readable transcripts of 5 recordings | about $1 |

The Meta tool-calling test moves to the end of the build, at the switch.

## 11. Demo scope

**Live:**
- sign-in with Slack, and the closed circle;
- composing with the voice switch;
- Mom's screen (Japanese demo, or English);
- reel explanations;
- answers from Gmail and Notion (connected on demand, or the demo account);
- the gates, shown as an activity log;
- the shopper with real Rakuten prices and a spending limit;
- the trend engine and the doctor summary.

**Pre-made:**
- long avatar clips for the scripted story;
- Mom's recorded voice replies;
- 4–8 weeks of synthetic history.

**Simulated:**
- checkout with a one-time card;
- delivery;
- the doctor booking.

**Coming soon, children:** a page that walks through the safety layer step by step:
1. what the AI generates;
2. what people send;
3. grooming signs;
4. the final gate.

It includes one example of a held message and the reason shown to the parent.

## 12. Look and name

**Layout: professional and productive first.**
- The product itself is the page: your workspace (chat, approvals, trend cards) next to the live mirror of Mom's
  phone.
- A short landing section is enough for the hackathon.
- muse.ai is only a loose reference for showing approvals up front. We use no Meta assets, logo or typeface.

**Colours and type: roleEdge's own system** (`web/app/css/tokens.css`; replaced the RoleSpace tokens on
2026-11-02, which made roleEdge look like a copy of our earlier project and, with a pastel colour per format, like a
personal project rather than an enterprise product):

| Role | Token |
|---|---|
| Brand black (top bar, the mark, primary buttons, selection, progress, the caregiver's own bubbles) | `#0a0a0a` |
| Ink, body, muted | `#0a0a0a`, `#3f3f46`, `#71717a` |
| Page, panels, hairlines, input borders | `#fafafa`, `#ffffff`, `#e4e4e7`, `#d4d4d8` |
| Status only | passed `#079455`, needs you `#dc6803`, held or urgent `#d92d20` |
| Type | **Geist** for English, **Noto Sans JP** for Japanese; Geist Mono only for identifiers such as an order number; **Doto** (dot-matrix) only as an accent on the wordmark and the spend meter's numbers in the Studio, never for anything she reads or anything about her |
| Corners | 4–8 px in the Studio, 10–14 px on the phones (big targets) |

- **Nothing is colour-coded by content type:** every moment has the same quiet icon tile; colour says only
  passed, needs you, held or urgent; black means "you can tap this". Red still means only "urgent" or "held" (rule S3).
- Labels are sentence case in the body font (no uppercase monospace labels).
- **The mark:** a black tile with three people (roles) linked by lines (edges), the caregiver on top joining the two
  generations (white tile on the black top bar); the wordmark is "role**Edge**" in Geist, "role" light and "Edge"
  semibold. *(Blue and IBM Plex were tried first the same day; the user chose black and a more refined font.)*
- **This replaces the Vodafone-style red tokens** in `docs/design.md` and the RoleSpace tokens used until
  2026-11-02.

**Name:** **roleEdge** (decided). A trademark search is needed before any launch beyond the hackathon.

## 13. Still open

All five questions from v0.3 are answered (section 1). Open questions for the hackathon build are in
[HACKATHON.md](HACKATHON.md) and in the latest chat reply.
