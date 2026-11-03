# CareCircle product demo: design

Date: 2026-10-28 · Status: approved in chat, awaiting spec review

## Goal

A local web app that shows what CareCircle does, as animated flows played from **real saved outputs**, for two
families: the existing Indian family and a new Japanese one. For Japan the focus is older people living alone
who feel lonely. The code must be easy to edit: words, flows, colours and the mascot each live in one small file.

## Decisions already made

- **Kind of app:** an interactive demo (caregiver phone → Saathi → parent phone), not a landing page or a live
  prototype. It never calls a model; it plays what the pipeline saved in `output/`.
- **Mascot:** "Both together": a pixel-art grandmother (grey bun, round glasses, red shawl) and grandchild (red
  t-shirt) with a beating heart between them. New art, not the playground's cat. Nothing country-specific in it.
- **Japan:** added to the real pipeline and run through the real models (a few cents), not hand-written screens.
- **Tech:** plain HTML, CSS and ES modules served by the existing FastAPI app, no build step. Rejected: React +
  Vite + Framer Motion (adds a Node toolchain, harder to edit), one static HTML export (data baked in).

## Part 1: Japan and loneliness in the pipeline

### 1.1 Japanese family (demo data, `demo.py`, synthetic only, rule S7)

- **Parent:** Yoshiko Sato, called "Okaasan", 81, Japanese (kanji and kana), lives alone in Sendai, timezone
  Asia/Tokyo. **Caregiver:** her son Kenji, at work in Tokyo. Emergency number **119**. Daily call 10:00 am.
- **Content cases** (text only, so no new sample media):
  - `line_scam`: a forwarded LINE message from someone posing as a grandson who lost his phone and urgently needs
    money sent from an ATM (the "ore ore" / furikome scam).
  - `city_notice`: a Sendai city notice: free health check-up for over-75s, book by a stated date.
- **Check-in scenario** `lonely_day`: she has spoken to no one for three days, skipped lunch, took her medicine,
  no medical red flags.
- `demo.py` groups everything per family (`FAMILIES`: id, label, care plan, recipient keys, content case ids,
  call scenario names) so the CLI, costs and the story builder loop over families instead of one hard-coded plan.

### 1.2 Make the content pipeline and renderer locale-aware

Each item below is currently India-only:

| Where | Today | Change |
|---|---|---|
| `models/people.py` `Recipient` | no timezone | add `timezone` (IANA name) |
| `content/prompts.py` digest prompt | "today is {today} (Asia/Kolkata)" | use the recipient's timezone. The Indian prompt text stays byte-identical, so its cache still replays |
| `render/calendar.py` | `TIMEZONE = Asia/Kolkata` | use the recipient's timezone |
| `render/i18n.py` | Hindi and English labels and date phrases | add Japanese ("11月30日まで", trust labels, "Kenjiから · Saathiがやさしく説明") |
| `render/theme.py` fonts | Inter + Noto Sans Devanagari | add Noto Sans JP |
| `content/verify.py` `date_mentions` (rule S2) | no Japanese dates | recognise `11月12日`, `12日`, `10時30分`, `午前/午後`, weekdays `月曜日`…, `今日/明日/昨日/明後日`, full-width digits (NFKD) |

The S2 change matters for safety: without it a Japanese wording fix that moves a date would be applied.

### 1.3 Loneliness in the check-in call

A product change to `checkin/prompts.py` (clinician review still required, rule S5):

- New call-flow step: ask whether they have talked with anyone or gone out recently. If they sound lonely, chat
  warmly for a moment about something they enjoy and offer to set up a call with the caregiver.
- New safety-rule line: feeling lonely, or not having spoken with anyone for days, is a `flag_concern` with
  severity `"watch"`. Escalation code is unchanged: watch already means amber (rule S3).
- `CallReport` gains `social_contact: str` (who they talked to recently, any loneliness signs).

### 1.4 Paid runs

`carecircle content line_scam city_notice`, `carecircle render`, and `carecircle checkin` for all three scenarios
(the two Indian calls re-run because their prompts changed). Expected cost: a few cents (see `output/costs.json`).
Indian content is not re-run: its prompts are unchanged.

### 1.5 Story bundle for the web app

`src/carecircle/story.py` (layer 3) reads saved outputs and returns one JSON document:

```text
{ "families": [ {
    "id": "india" | "japan", "label", "caregiver": {name, relation}, "parent": {call_name, full_name, language},
    "items": [ { "case", "kind", "input", "recipient", "digest", "held_fields": [...], "scam": bool,
                 "media": {"card", "video", "voice_note", "calendar"} } ],
    "calls": [ { "scenario", "status", "transcript": [[who, line]], "events": [...], "report": {...} } ] } ] }
```

Missing outputs are skipped with a note in the bundle (`"missing": [...]`), never an error, so the page works
after a partial run. The chat server (`chat/app.py`) adds `GET /demo` (the page), `GET /api/demo/story`, and a
read-only static mount of `output/content` at `/media/content`.

## Part 2: The web app (`web/demo/`)

### 2.1 Layout

- **Hero** (ink band): the mascot duo, an 800-weight uppercase headline, a one-line promise, and the family switch
  (India · Japan, a pill toggle).
- **Flow chips** under the hero: one per flow.
- **Stage:** caregiver phone (left) → Saathi lane with the mascot narrating (middle) → parent phone (right). On
  narrow screens the phones stack and the lane becomes a strip between them.
- **Controls:** play / pause / replay, step dots, and a "what's happening" caption per step.

### 2.2 Flows (each built from real data)

| Flow | Steps |
|---|---|
| Share and simplify | item bubble appears on caregiver phone → flies into the lane, mascot "thinking" → card panels build one by one → Approve pill pressed → card slides onto parent phone → voice-note waveform plays, mascot "happy" |
| Scam held back | forwarded message heads to the lane → red shield stops it, mascot "worried" → safety card goes to the parent instead → caregiver sees "held back" |
| Deadline to reminder | a date lifts out of the text → drops into a calendar chip → reminder rings on the parent phone. Held dates (S2) show a "waiting for your OK" lock instead |
| Saathi calls | parent phone rings → transcript lines type in → tool chips pop (record_checkin, flag_concern) → status light morphs to the computed colour → alert slides onto the caregiver phone. Japan: the loneliness moment and `social_contact` line |
| See what they see | parent taps the card and plays the voice note → a mirrored "eye" view replays the taps on the caregiver phone |

### 2.3 Mascot (`js/mascot.js`)

Character grids plus one palette object (skin, hair, shawl, shirt are named colours). States: `idle` (bob and
blink), `thinking` (sparkles), `happy` (heart burst), `worried` (small shake), `calling` (phone). Rendered as crisp
SVG, like the playground's sprites.

### 2.4 Files (each with one job, under about 200 lines)

| File | Job |
|---|---|
| `web/demo/index.html` | page skeleton only |
| `css/tokens.css` | the shared design tokens (same values as `web/chat/css/tokens.css`) |
| `css/layout.css`, `css/phone.css`, `css/motion.css` | page layout, phone frames, every keyframe |
| `js/copy.js` | every English UI string, plus per-family UI words |
| `js/story.js` | fetch `/api/demo/story`, pick a family |
| `js/flows.js` | each flow as a plain list of steps, e.g. `{ at: "parent", show: "card" }` |
| `js/player.js` | runs steps with timing; play, pause, replay, step dots |
| `js/stage.js` | draws bubbles, cards, chips and status lights on the phones |
| `js/mascot.js` | sprite grids, palette, states |
| `js/main.js` | wires it together |

Editing guide (top of `flows.js` and in the README): change words in `copy.js`, reorder or add steps in
`flows.js`, change colours in `tokens.css`, change the mascot in `mascot.js`.

### 2.5 Motion

CSS keyframes for loops (bob, blink, ring, pulse, waveform, typewriter caret) and the Web Animations API for
moves between phones. `prefers-reduced-motion` shows each step's end state with a short fade instead.

## Testing

- **Python (pytest):** Japanese care plan and recipient validate; Japanese date mentions (held when a fix moves
  `11月12日`, applied when only wording changes); calendar uses the recipient's timezone; Japanese i18n phrases;
  the check-in prompt contains the loneliness step; `story.build` on a fixture output folder (including a
  missing case); `/api/demo/story` and `/demo` via the FastAPI test client. Layer test stays green.
- **Visual:** a Playwright screenshot at the end of every flow, for both families, shared with the user.
- **Real runs:** the Japanese digests, card, calendar and call are checked by reading the saved outputs.

## Out of scope

Real phones, real voice, sending anything, log-in, other languages beyond Hindi, English and Japanese, and
re-running the Indian content cases.

## Revision (2026-10-28): professional redesign

After the first build the user asked for an enterprise look, not a cartoonish one. What changed:

- **No emoji anywhere.** One line-icon set (`src/carecircle/render/icons.py`) is used by the cards, the explainer
  video and, via `/api/demo/icons`, the web app. The digest's `emoji` fields became `icon`, chosen by the model
  from a fixed list (`models.IconName`); stray emoji in model text are stripped when rendering.
- **No mascot.** The pixel-art grandmother and grandchild were replaced by a CareCircle mark (two linked circles).
- **Palette "refined red":** ink #2B2A33, brand red #B4232C used sparingly, warm neutrals (#F7F6F4), and separate
  status colours (green #1E7B4B, amber #9A5B00, alert red #B42318) so red only ever means urgent.
- **Web app:** top nav, sentence-case hero with measured costs and a "today at a glance" card from real outputs,
  Saathi's lane became a workflow panel (steps, progress, result, activity log in plain words), and a "safety by
  design" section. Motion is limited to entering, travelling, filling and confirming.
- The mock screen (`output/mock/screens.png`) follows the same rules.
