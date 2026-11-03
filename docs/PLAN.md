# CareCircle: product and feasibility draft

*Working name. Draft v0.1, 2026-10-28. Prices are USD list prices excluding GST and were checked on 2026-10-28.
Items marked UNVERIFIED could not be confirmed from a primary source.*

---

## 1. Summary

CareCircle is a WhatsApp-style family app (chat, photos, video, voice notes, voice and video calls) with an AI
helper, **Saathi**, that works for the busy adult child:

- **Makes things easy to understand.** Anything you send to your parents or kids, such as a reel, a photo of a
  bill or a long school notice, is turned into something they can take in at a glance. That means a big-picture
  card, a 20-second explainer video, a voice note and an article in their own language.
- **Catches deadlines and scams.** It spots deadlines and turns them into reminders. It also spots scams before
  they reach your parents.
- **Calls when you can't.** When you are in a meeting, Saathi makes the daily check-in call. It asks about
  medicines, meals and pain, can order food (with your approval), and alerts you immediately if something is
  wrong.
- **Shows you their screen.** You can see exactly what your parent or child is seeing in the chat.

**Feasibility verdict:**

- **Proven tonight on Azure gpt-5-mini.**
  - **Content transformer.** Works for reels, photos and long text at about **$0.01 per item**.
  - **Check-in conversation logic.** Works at about **$0.015 per call**, and it safely escalated a planted "dizzy
    and missed BP pill" scenario.
  - **Calendar, cards, explainer video and the live mirror** are all ordinary engineering.
- **Needs work.**
  - **Language accuracy.** I saw one real date mistranslation and one invented name. Approve-before-send must be
    the default for now.
  - **Voice calls need a realtime speech model.** A text model's 5–7 s per turn is too slow.
- **Not possible on Meta alone today.** Meta's API has no text-to-speech, no realtime voice and no video
  generation (per dev.meta.ai docs). So **voice notes and AI phone calls need one extra provider**, or on-device
  speech.
- **Constrained by partners.**
  - **Food ordering** is realistic only through Swiggy's Builders Club, which needs approval and uses
    cash on delivery.
  - **Automated phone calls in India** carry TRAI rules and "International call" labelling issues. WhatsApp
    Calling looks like the easiest route.
- **Rough running cost: $4–13 per family per month** (about ₹350–1,300), plus about $40/month for a pilot or
  $115–155/month at small scale in fixed platform costs.

---

## 2. Who it's for

| Person | What they need | What they get |
|---|---|---|
| **Caregiver** (you; adult child, often busy) | Peace of mind without hours on the phone; to share useful information without explaining it | One chat per parent or child, a daily status (green/amber/red), previews of what Saathi will send, approve/decline cards, call reports |
| **Parent** (60–85; may read slowly; regional language; possibly a basic smartphone) | Big, simple, spoken; nothing to learn | Large-type chat, a play button for everything, voice notes, big one-tap replies ("Call me"), reminders, a daily friendly call |
| **Child** (6–14) | Clear, fun explanations; safe space | Kid-level explainers (homework, school notices), cartoon cards, voice notes, no ads, no strangers |

---

## 3. Features and priorities

**P0 = MVP · P1 = next · P2 = later**

### 3.1 Messaging and calls (the "WhatsApp" part)
- **P0** Family circles (you plus parent(s) plus kid(s)), 1:1 and group chat; text, photo, video, voice notes; read and played receipts.
- **P0** Voice and video calls in the app (WebRTC via LiveKit). **P1** CallKit on iOS so calls ring like real calls.
- **P0** Share-to-CareCircle from Instagram and YouTube. This works through the phone's share sheet. Reels are
  sent as a link or as a downloaded file (see §7, legal).

### 3.2 "See what they see"
- **P0** Mirror view. Because our app renders the parent's or child's chat, the caregiver can open an exact
  live view of their screen: font size, the cards and videos, and what has been played or tapped
  ("Mummy watched the video twice and tapped *Call me*").
- **Not possible:** seeing their whole phone screen or other apps without them pressing *Start*. iOS needs a
  ReplayKit broadcast the user has to start themselves. An assisted screen-share ("press the red button and I'll
  guide you") can be **P2**.

### 3.3 Saathi content transformer (tested tonight)
For anything shared into a parent's or child's chat:
1. **Understand.**
   - **Video:** sample frames and transcribe the audio.
   - **Photos and bills:** use vision.
   - **Text:** read it directly.
2. **Digest.** Produce a 3-sentence summary and key points for you, and a **trust verdict** (genuine /
   unverified / likely scam).
3. **Recipient pack**, in their language and reading level:
   - **Illustrated card:** big emoji pictograms, 3–5 steps and a deadline chip.
   - **Explainer video:** 15–20 s and vertical, built from a storyboard (not AI video generation, which is cheap
     and reliable).
   - **Voice note:** about 70 words, read by text-to-speech.
   - **Short article:** in the regional language.
   - **Quick replies:** big one-tap buttons.
4. **Deadlines → reminders.** Calendar events with alarms (.ics, Google Calendar, in-app). Voice reminder calls
   are **P1**.
5. **Safety net.**
   - A verify pass checks the recipient text against the source.
   - **Dates are never changed automatically.**
   - **You approve before it is sent** (P0 default). **P2:** auto-send for trusted content types.
- **P1:** apply the same treatment to your own long text messages (auto-suggested when a message is long or
  contains dates or instructions), so that *every important message* arrives as a picture and a voice note.

### 3.4 Daily check-in call (logic tested tonight)
- **P0** Scheduled daily call, for example 1:30 pm. **P1:** call automatically only if your work calendar shows
  you are busy; otherwise remind *you* to call.
- **Script:**
  1. It always opens with "I'm Saathi, Rohit's AI helper". **No pretending to be you, no voice cloning.**
  2. It asks about mood and sleep, each medicine due so far, meals and water, and pain.
  3. It mentions one upcoming item.
- **Escalation rules:**
  - **Red flags** (chest pain, breathlessness, fainting, a fall, dizziness, confusion, slurred speech, low-sugar
    signs): tell her to sit or lie down safely, **alert you immediately** by push and SMS, and advise calling 112.
  - **A missed medicine** is at least "watch". **Never** advise a dose change.
  - **Secrecy requests** ("don't tell my son") are kindly refused for health matters.
- **After the call:** a report card (green/amber/red, medicines, food, concerns, *your* next steps) and a
  one-tap Hindi voice-note reply. **The status colour is computed by code from what was recorded**, not written
  by the model.
- **P1** Order food during the call ("you haven't eaten, shall I get khichdi?"). This produces a pending order
  card you approve with one tap.

### 3.5 Kids mode
- **P0** The same transformer at the child's age level (school notices, homework help, "why is the sky blue"),
  plus reminders for school deadlines.
- **P1** Parental controls: which contacts, what content, quiet hours. No ads, no tracking (required by law for
  under-18s in India; see §7).

---

## 4. How it works

```
 Caregiver app ─┐                          ┌─ Parent app (big-type mode) / WhatsApp fallback
 (web → iOS)    │                          │
                ▼                          ▼
        ┌────────────────────── API + realtime chat ──────────────────────┐
        │  Postgres (Supabase) · auth · circles · messages · consent log  │
        │  Media: R2 / Blob storage + CDN · Push: APNs / FCM              │
        └───────────┬───────────────────────┬──────────────────────────────┘
                    │ job queue             │ calls
         ┌──────────▼──────────┐   ┌────────▼─────────────────────────────┐
         │ Saathi workers       │   │ LiveKit (WebRTC rooms)               │
         │  ingest: frames, STT │   │  · family voice/video calls          │
         │  digest  (LLM)       │   │  · Saathi voice agent joins as a     │
         │  verify  (LLM)       │   │    participant (LiveKit Agents)      │
         │  render: card, video │   │  · SIP → phone / WhatsApp Calling    │
         │  TTS voice note      │   └────────┬─────────────────────────────┘
         │  calendar (.ics/API) │            │
         └──────────┬───────────┘   ┌────────▼────────┐
                    │               │ tools: record,  │  → caregiver report,
                    ▼               │ alert, order,   │    alerts, approvals
         ┌──────────────────────┐   │ reminders       │
         │ Model adapter         │◄──┴─────────────────┘
         │ prod: Meta  · dev: Azure │  (one interface: json(), tools();
         │ + TTS/STT provider     │    switch by config)
         └──────────────────────┘
```

**Design rules learned tonight:**
- **The LLM fills the content; code does the layout.** Cards and video frames are HTML templates rendered by
  headless Chromium and ffmpeg, so the layout never breaks, and Hindi and other Indic scripts render correctly
  with Noto fonts. An AI image model is optional (for example muse-image at $0.01 per image) for custom
  illustrations. Text should never be drawn by the image model.
- **Anything that matters (dates, escalation status, order state) is decided by code**, not by model prose.
- **Everything is asynchronous.** A content item takes about 30–45 s to prepare. You see "Saathi is preparing…",
  then a preview.

**Suggested stack:**
- **Web/PWA first:** Next.js or SvelteKit.
- **iOS:** native SwiftUI, needed for CallKit/PushKit and the Share Extension. Or React Native/Expo to share code
  with Android. Choose this before writing the iOS app.
- **Backend:** Python (FastAPI) workers. The feasibility code in `src/carecircle/` is a starting point; see [../ARCHITECTURE.md](../ARCHITECTURE.md) §11 for how it splits into services.

---

## 5. "Meta agents/API only": a reality check

What the Meta developer API offers (dev.meta.ai docs, checked 2026-10-28):

| Need | Meta model | Status |
|---|---|---|
| Understanding and writing (text, images, video, PDF in; text out) | muse-spark-1.1 / 1.2 / 1.3, muse-wonder-1.0 | ✅ Responses, Chat Completions and Messages formats. Text and image input were verified on 2026-10-27. The docs say audio and video input are supported, but my 2026-10-27 audio probe was ignored (the model replied "NO AUDIO"), so the right format still needs finding. If video input works, reels can be sent directly. **Tool calling on Meta is not yet verified.** |
| Image generation and editing | muse-image-1.0 ($0.01/image) | ✅ (not yet tested) |
| Speech-to-text | muse-voice-transcribe-1.0 ($0.18/audio hour; realtime WebSocket) | ✅ Hindi, Tamil, Telugu, Bengali, Marathi, Kannada. ❌ **No Punjabi, Gujarati or Malayalam.** My REST probes returned 404, so it probably needs the WebSocket. |
| **Text-to-speech** (voice notes, narration, call voice) | none | ❌ **Missing** |
| **Realtime voice agent** (speech-to-speech) | none | ❌ **Missing** |
| Video generation | none | ❌ Missing. Not needed, because our explainer videos are template-rendered. |

**What this means:** "Meta only" works for the *thinking* (all the agents) and for transcription in 6 languages.
Voice needs one more piece. Options:

1. **Recommended: Meta for all LLM work plus an Indian TTS provider.** For example Sarvam Bulbul (about $10 per
   1M characters, all 9 major Indian languages) or Azure Speech ($15 per 1M characters, 9 languages). The voice
   call is then a streaming pipeline: Meta STT → Muse Spark → TTS. Expect about $0.01–0.02 per minute plus
   transport. It needs careful tuning to reach about 1 s response time.
2. **On-device TTS for voice notes.** iOS and Android ship Hindi voices, at a cost of $0. They sound robotic
   compared with Sarvam or Azure, and this does not solve phone calls.
3. **A realtime speech model for calls only.** For example gpt-realtime-2.1-mini, at about $0.02–0.05 per minute
   (third-party estimate). This gives the most natural calls, but it is not Meta.

> ⚠️ **Privacy:** the `-contributor` Meta models (e.g. `muse-spark-1.3-contributor`, the default in our earlier
> scripts) are very cheap **because Meta trains on what you send**. Family conversations, health details and
> children's data must use the non-contributor models (`muse-spark-1.3`: $1.25 / $0.15 / $4.25 per 1M tokens,
> which is about 5× gpt-5-mini on input).

---

## 6. APIs and costs

### 6.1 Components

| Component | Recommended | Price (list, USD) | Notes |
|---|---|---|---|
| LLM (prod) | Meta muse-spark-1.3 | $1.25 in / $0.15 cached / $4.25 out per 1M tokens | 3,000 requests/min |
| LLM (dev, tonight) | Azure gpt-5-mini | $0.25 / $0.025 / $2.00 per 1M | Retires 2027-02-09. Newer and cheaper Azure models exist (e.g. gpt-6-luna at $0.10/$0.50 per the pricing API). |
| Speech-to-text | Meta muse-voice-transcribe | $0.18 per audio hour | Azure fast transcription is $0.36/hour ($0.10 promo); Sarvam about ₹29/hour |
| Text-to-speech | Sarvam Bulbul v4 Flash, or Azure Neural | about $10, or $15, per 1M characters | Hindi plus 8 more Indian languages |
| Realtime voice (calls) | Pipeline (above), or gpt-realtime-2.1-mini | about $0.01–0.02/min, or $0.02–0.05/min | Per-minute figures are estimates |
| Image generation (optional) | Meta muse-image-1.0 | $0.01 per image | Overlay the text in code |
| Calls (WebRTC) | LiveKit Cloud | Build $0 (5k participant-min, 1k agent-min); Ship $50/mo, then $0.0005/participant-min and $0.01/agent-min | Agents join calls natively and SIP is supported |
| AI call to parent's phone | **WhatsApp Business Calling** (available in India), or Plivo/Exotel via SIP | about ₹0.39/min (reseller rate, UNVERIFIED); Plivo ₹0.38/min + ₹200/mo per number | Twilio numbers show up as "International call" in India, which is bad for elders |
| Delivery to parents without the app | WhatsApp Cloud API | Utility ₹0.115 / marketing ₹0.86 per message + 18% GST; 1,000 free service messages per month | Templates outside the 24-hour window; 16 MB video limit |
| Chat backend | Supabase Pro (or Stream Chat, free to 1k MAU) | $25/mo + usage | |
| Media | Cloudflare R2 | $0.015 per GB-month, free egress | |
| Calendar | Google Calendar API + .ics fallback | Free | Google verifies apps that ask for the sensitive scope. Use `calendar.app.created`. |
| Food | Swiggy Builders Club (MCP) | API free | **Needs approval.** OTP login on the parent's account and cash on delivery only. No apps that hide Swiggy's brand. Zomato's MCP is personal-use only. |
| Stores | Apple Developer; Google Play | $99/yr; $25 once | |

### 6.2 Monthly cost per family (1 parent + 1 child)

Assumptions:
- 90 content items a month (parent 2/day, child 1/day), each about 500 characters of speech.
- 60 reels transcribed, about 1 minute each.
- A daily 5-minute check-in call (150 min/month).
- About 10 hours of human family calls (about 600 participant-minutes).

| Line | Low | High | Basis |
|---|---|---|---|
| Content LLM (digest + verify) | $0.74 | $1.80 | Measured $0.0082 per item on gpt-5-mini. Meta 1.3 is projected at about $0.02 per item. |
| Voice notes and narration (TTS) | $0 | $0.68 | On-device, or Azure Speech, for 45k characters |
| Reel transcription | $0.18 | $0.36 | 1 audio hour |
| Check-in voice AI | $1.50 | $7.50 | 150 min × $0.01–0.05/min |
| Check-in conversation logic | $0.42 | $1.05 | Measured $0.014 per call on gpt-5-mini. Included in the "High" realtime option. |
| Call transport | $0.65 | $1.50 | WhatsApp Calling, or LiveKit agent-minutes |
| Human calls, storage, rendering | $0.40 | $0.60 | LiveKit overage, R2, about 15 s of CPU per item |
| **Total variable** | **≈ $4** | **≈ $13.5** | ≈ ₹350–1,300 per family per month, at ₹88–96 per $ |

**Fixed costs:**
- **Pilot:** about $40/month (LiveKit Build free tier, Supabase free or Pro, one small VM).
- **Small scale:** about $115–155/month (LiveKit Ship $50, Supabase $25, workers $30–70, Apple $8/month).
- **What this suggests for pricing:** a ₹299–499 per month family plan covers costs with margin. Voice minutes
  are the only line that grows a lot with usage, so cap or tier them.

---

## 7. Safety, privacy and legal (must-dos)

- **DPDP Act 2023 and DPDP Rules 2025 (India):**
  - The rules were notified on 13 Nov 2025. Consent-manager rules apply from **13 Nov 2026**; the core
    obligations apply from **13 May 2027**. Breaches must be reported within 72 hours.
  - **Parents give their own consent.** You cannot consent for them. Build a simple voice-guided consent step.
  - **Children under 18** need **verifiable parental consent**, with no tracking and no targeted ads.
  - Penalties run up to ₹200–250 crore.
- **AI disclosure:**
  - Every AI call opens by saying it is an AI helper. This is required in the EU from Aug 2026 and under the
    US TCPA, and it is the right thing to do in India.
  - Under India's Feb 2026 IT Rules amendment, AI-made audio and video must be labelled. Mark explainers and
    voice notes "made by Saathi (AI)".
  - **Don't clone your voice** for calls to your parents. It is a trust risk, and elderly people are already
    targeted by voice-clone scams.
- **Not a medical device.** No diagnosis and no dose advice. A doctor should review the call script and the
  red-flag list. Emergency means alerting the caregiver plus advising 112, never "wait".
- **Reels:** Instagram's terms forbid scraping and oEmbed is display-only. Process only what the user shares
  (a link to show, plus the file they downloaded for AI processing).
- **Phone calls (TRAI):** commercial calls need 140/1600-series numbers and DLT registration. A consented family
  check-in is *arguably* not commercial (UNVERIFIED; get a legal opinion). WhatsApp Calling avoids most of this.
- **App Store:**
  - Rule 5.1.2(i): explicit consent before sending data to a third-party AI.
  - Indicate when a call is recorded.
  - Avoid the "Kids" category, which bans third-party analytics.
- **Encryption trade-off:** the AI must read what it transforms, so chats it processes cannot be end-to-end
  encrypted from the server. Make this explicit. Offer "private" messages that Saathi never reads.

---

## 8. Roadmap

| Phase | Time | Scope | Exit test |
|---|---|---|---|
| **0. Feasibility** (started tonight) | 1–2 weeks | ✅ Content pipeline and check-in logic on Azure. Next: deploy Azure TTS/STT/realtime (needs `az login` or portal), test Hindi voice quality and call latency; when the Meta keys return, verify Meta tool calling, muse-image and muse-voice-transcribe, and re-run all cases on Meta. | A Hindi voice note sounds natural to your parents. Call turns take under 1.5 s. Meta passes the same cases. |
| **1. Web MVP** (PWA) | 4–6 weeks | Circles, chat and media, Saathi digest with approve-before-send, mirror view, reminders, LiveKit calls, daily check-in (in-app or WhatsApp call), caregiver report | 3–5 real families use it daily for 2 weeks |
| **2. iOS app** | 6–8 weeks | Native calls (CallKit/PushKit), Share Extension for reels, Google Calendar, kids mode, food ordering (if Swiggy approves) | TestFlight with pilot families |
| **3. Scale and polish** | ongoing | More languages, auto-send trust levels, assisted screen share, Android, billing | Retention, and caregiver NPS |

---

## 9. Decisions I need from you

1. **Voice under "Meta only".** Do you accept a separate TTS provider (Sarvam or Azure) for voice notes and calls?
   Or on-device voices for notes and wait on calls?
2. **Parents' channel for phase 1.** Our own app, or **WhatsApp first** (no install; Meta-native; WhatsApp
   Calling for check-ins) with our app for caregivers?
3. **Approve-before-send.** Keep it on by default? (Recommended until the accuracy numbers are better.)
4. **Languages for launch.** Hindi plus which others? Meta STT lacks Punjabi, Gujarati and Malayalam.
5. **Clinical advisor and legal.** Who reviews the check-in script, the red-flag rules and the DPDP/TRAI
   position?
6. **Company entity.** Needed for the Swiggy Builders Club, DLT/WhatsApp Business verification and the
   Apple developer account.

---

## 10. What exists now

- **`src/carecircle/`** is one Python package with a CLI (`carecircle …`). It contains:
  - the content transformer and checker;
  - the renderer (cards, explainer MP4, .ics);
  - the check-in call simulator;
  - the cost report and the mock screen;
  - a provider layer: Azure works today, and the Meta path is wired but its tool calling is untested.
- **`web/chat/`** is the chat playground front end (`carecircle chat`). It is Azure-only for now, because the
  Meta keys are commented out in `.env`.
- **[../ARCHITECTURE.md](../ARCHITECTURE.md)** covers the code layout and engineering rules.
- **[FINDINGS.md](FINDINGS.md)** has all test results.
- **Outputs** go to `output/` (run `carecircle all`). See `output/mock/screens.png` for the caregiver view next to
  the "what Mummy sees" mirror.
