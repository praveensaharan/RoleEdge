# roleEdge Studio: explain anything to family, the way they'll engage with it

Date: 2026-11-02 · Status: building (the user chose to skip questions and go straight to a plan) · Deadline: Nov 4, 9 PM EST

## Why

The main idea: **connect with family in a better way, and keep them engaged even when you have little time.** You
share something (a message, a photo, a video, a link, a voice note). A team of agents researches it first, works
out what you're trying to say, and proposes the best way to explain it to Mom (or a child): a short video, an
audio overview, slides, flashcards or a mind map. *(Superseded the same day: these were NotebookLM's own formats; see
"moments, not documents" below.)* You approve, it's sent, and
you watch on a live mirror what Mom sees and does with it. Her engagement comes back to you.

## The flow

1. **Share** anything into a chat (WhatsApp Web-style screen for you).
2. **Research swarm** (in parallel, shown live as an agent activity panel):
   - *Reader*: what this is; facts, numbers, dates, claims (Muse Spark, with images).
   - *Fact checker*: checks claims (Spark built-in web search if the key allows it, otherwise "unverified");
     scam signs; sources cited.
   - *Audience*: who it's for (Mom 81, reads slowly, Japanese; or a 9-year-old) and what she engaged with before.
   - *Context*: why it matters to her now (care plan, upcoming events, recent conversation).
3. **Planner** proposes an *explanation plan*: the one thing to remember, a 3–5 point outline, recommended
   formats ranked with reasons, tone and language, what to leave out, and a question that starts a conversation.
   Shown as a plan card with format toggles (Video, Audio, Slides, Flashcards, Mind map).
4. **Maker swarm**, one agent per chosen format, in parallel:
   - *Slides*: 4–6 big-type slides with line icons.
   - *Flashcards*: 4–6 cards, front and back, with "I knew it / show me again".
   - *Mind map*: root, up to 5 branches, up to 3 leaves each (drawn by code as SVG).
   - *Audio overview*: a 60–90 s script, one or two voices (your voice + the assistant), played by the device voice.
   - *Video*: a narrated slide video (scenes + narration), played in the browser, no rendering wait.
5. **Verifier (code)**: dates and times must appear in the source (the existing S2 checks); the final send gate
   (T5) runs on every text; anything doubtful is held for you.
6. **Send** → Mom's phone gets a push banner, opens the app, and plays the pack.
7. **Engagement back**: opened, watched %, flashcard answers, replies → shown to you ("watched twice, 3/4 cards,
   asked a question") and stored as signals for the trend engine.

## Screens

- **You (WhatsApp Web-style):** chat list on the left (Mom, child, family), the conversation in the middle with an
  attach menu (photo, video, document, link, voice), and a right panel that switches between **Studio**
  (sources, research with citations, plan, format toggles, outputs, live agent activity) and **Mom's phone** (live
  mirror). Layout like WhatsApp Web, but roleEdge's own tokens (RoleSpace ink, sparing blue), not WhatsApp's
  green, logo or trade dress. *(Call made by me.)*
- **Mom (iPhone-style):** a realistic iPhone frame (Dynamic Island, status bar, home indicator), a home screen
  with the roleEdge app, a push banner when something arrives, and an iOS-style app: chat with Kenji, then
  full-screen viewers for the video, audio (two speakers), slides (swipe), flashcards (tap to flip) and mind map.
  Large type; Japanese for the Japan circle.

## Models, "tuned per task", and money

- **Runtime is Meta only** (Stage 1 and the organiser rulings): Muse Spark 1.3 for every agent, Muse Image for an
  optional cover picture, Muse Voice Transcribe for voice notes. Voices are the device voice (allowed). Modal is
  not needed for this feature.
- **"A tuned model for each task", honestly:** fine-tuning a separate model per task isn't possible in 2.5 days on
  this budget, and Meta's hosted Spark can't be fine-tuned through the API we have. Each agent is instead a
  **specialist**: its own instructions, output schema, examples, model and effort setting, and a small test set.
  A real fine-tune of an open Meta model stays a stretch goal. *(Call made by me.)*
- **Spend:** every Meta call (text and media) is logged in the ledger with a price, and the workspace shows a
  running total. Meta has no balance API we can call, so the meter is an estimate from token counts; check the
  Meta dashboard for the real figure. One pack costs well under a cent with the contributor model.

## Build order

1. Studio backend: agent profiles, research swarm, planner, makers, verifier, API, live events, spend meter.
2. The WhatsApp Web-style workspace with the Studio panel and agent activity.
3. The iPhone-style app for Mom with the five viewers and engagement events; the live mirror.
4. Polish, Japanese circle, a judge-friendly replay path, README.

## Trade-off against HACKATHON.md *(call made by me; the user can override)*

This becomes the main new story. The trend engine (the USP) stays. The shopper and the Gmail/Notion/Slack
sources move to "if time allows".

## Revision (same day): a premium, RoleSpace-style presentation

The user found the WhatsApp Web + iPhone look not premium enough, pointed to RoleSpace as the standard, and freed
the presentation ("we are not building the mobile app; just show it will work like this"). What changed:

- **Your side is a Studio, not a chat clone.** A top bar (circle switcher with coloured dots, live Meta spend
  meter), a share box (attach photo/video, link, voice note; "Research first" or "Quick message"), and a stream of
  share cards, newest first. Each card shows the pipeline the way RoleSpace shows a policy decision: agent checks
  that tick off (spinner, then mint tick), the plan with verified-source chips, the formats as bordered selectable
  rows (2px ink when chosen), outputs as cards with a coloured top edge, the code checks, Approve and send, and
  "What she did" with progress meters. Mono labels and a mono footer line (model, agent runs, model time).
- **Her side is one calm app in a minimal device frame,** live on the right: no fake home screen or app icons.
  Something new slides in as a banner; a pack opens full screen, one format at a time.
- **Design values come from RoleSpace** (re-created, not copied): ink #111, 8px-radius buttons at 40px, pill-shaped
  segmented controls and badges, Inter 600 with negative tracking, JetBrains Mono labels, 1px #e5e7eb hairlines,
  12px cards, pastel badge pairs, one easing curve, no hover lifts, no emoji, line icons only.

## Revision (same day): children, apps and reels

The user asked for an English demo next to Japan, children as a second audience, room for Gmail, Slack and Notion,
and reels that work well for parents and children. What changed:

- **English demo:** the "Maya and Mom" circle (Los Angeles, Mom 79) runs the same Studio end to end.
- **Children** *(overrides PIVOT.md "coming soon" for the Studio; the user asked for it):* each circle has a child
  (Hana 8 in Tokyo, Leo 9 in LA). The share box has "Explain it to"; the agents write for that reader (hiragana-first
  Japanese for Hana, simple English for Leo, a "kind teacher" rule: nothing frightening, no money, dating, sign-ups,
  secrets or meeting anyone). A **child guardian** agent reads every line of a child's pack; anything it flags is a
  soft hold the parent reads before sending. Children can't message back yet: everything goes through the parent.
  Their screen is `/phone/<circle>?member=<id>`; the parent's phone never shows a child's pack.
- **Apps** (`roleedge.connectors`): Notion is real when `NOTION_TOKEN` is in `.env` (pages shared with an internal
  integration); Gmail and Slack are declared slots, shown as "coming next". The share box's "Apps" panel lists them,
  and a slow black-and-white strip shows the apps after them, using their own marks (Simple Icons, CC0 path data
  only; the marks are their owners' trademarks and only name the apps).
- **Reels:** a shared video becomes 8 frames spread over the whole reel (on-screen text readable) plus a transcript
  of its speech; uploads up to 50 MB. Instagram, TikTok and Facebook links can't be opened without a login, so the
  share box asks for the saved video instead. **No model training on Modal is needed** for this: Muse Spark reads
  the frames, Muse Voice Transcribe hears the speech, and each agent is a specialist prompt with its own schema.
  Tested on four real reels (a manipulation-awareness reel for Mom, a cockpit-tour reel for Leo that the fact
  checker called misleading, a Perfect Days reel for Okaasan, a konbini kanji reel for Hana): about a cent each.

## Errands: she asks, the assistant finds out or orders (same day)

The user asked for "Mom asks how long Uber Eats takes, or when Amazon delivers; the first time it asks me to read
Gmail, then I can always allow it, so she is answered even when I'm not near my phone", and for Rakuten price
checks and orders.

- **Her words are routed** (errand router, Muse Spark) at the same time as the reply reader: delivery, price,
  order, or none. An errand replaces the generic "message received".
- **Ask once, then always allow:** reading mail or spending money asks the caregiver the first time (Always allow /
  Allow once / Not now); she hears "I'll check with Kenji". Once allowed, she is answered at once. Permissions live
  on the circle (`permissions`) and can be stopped from the Activity tab.
- **Delivery answers** come only from mail that passes the sender check (T8); a fake courier notice is blocked
  before any model reads it. The reader must quote the arrival time from the mail and say only what it says; code
  checks every time and date against those mails (S2) and the send gate (T5) runs on the answer.
- **Prices and orders are written by code** from the catalog (2,380円, never a model's number). Orders stay within
  the circle's spending limit; above it the caregiver is asked every time, and "always" never stretches the limit.
- **Labelled stand-ins:** the mailbox is a demo mailbox (synthetic Uber Eats, Instacart, Amazon, Yamato mails and one
  fake courier mail, timed around "now") until Gmail sign-in is connected; the shop is a simulated Rakuten Ichiba /
  Amazon catalog with a simulated checkout until a store API is connected.

## Revision (same day): moments, not documents, and the family relay

The first version's five formats (video, audio overview with two voices, slides, flashcards, mind map) were
NotebookLM's own Studio list, in the same tile grid, so the product read as a copy. NotebookLM makes study
material for the person who uploaded it. roleEdge makes something for another person to do with their family, so
the formats were replaced by **moments**, chosen for who receives them. Each one ends with something that comes
back to the caregiver.

| For the parent | What it is | What comes back |
|---|---|---|
| **In your words** (note) | 3–6 sentences in the caregiver's own words, read aloud, ending with a question | how far she listened |
| **Show me how** (steps) | one step per screen, at her own pace, "read it to me" on each | how far she got |
| **Fridge card** (card) | one page to keep: 3–5 lines, the one date or thing to remember, who to ask; the caregiver can print it | that she read it |
| **Ask me** (askme) | two gentle questions; a different answer just shows the right one, warmly | what she got first time, and **what to talk about** |

| For a child | What it is | What comes back |
|---|---|---|
| **Picture story** (story) | 3–6 pages read aloud | how far they got |
| **Quiz game** (quiz) | 3–4 questions, stars, one more try instead of a wrong-answer buzzer | stars, and what to talk about |
| **Explore map** (map) | tap each part open | how much they opened |
| **Ask Grandma** (relay) | 2–3 questions to ask their grandparent about the topic (her own life and memories); tapping one sends it | the questions asked |

- Code keeps the plan to the recipient's own four moments (`formats_for`), whatever the planner returns, and drops
  any quiz question whose answer index isn't among its choices before anyone sees it.
- The phone labels are the person's own words: "ケンジからのお話", "ひとつずつ", "とっておくメモ", "おさらい"
  for Okaasan; "えほん", "クイズ", "たんけんマップ", "おばあちゃんにきいてみよう" for Hana.
- NotebookLM's other formats were considered and left out: Reports and Data tables are for researchers, not for
  an 81-year-old or an 8-year-old. Quiz and Infographic survive in a different form, as Ask me / Quiz game and the
  Fridge card.
- Packs made with the old formats show a note ("share it again for the new moments") and aren't shown on the
  phones.

### The family relay (grandchild and grandparent)

The caregiver sits between two generations. The relay lets the grandchild and the grandparent talk through the
app, with the caregiver watching over:

1. Hana asks Grandma something: she taps a question in an *Ask Grandma* moment, or types or holds the
   microphone on her own phone (the talk bar on a child's screen always goes to her grandparent).
2. The question arrives on Okaasan's phone as a big card ("はなちゃんから"), with Hana's own voice when she spoke.
   She taps **Answer Hana** and holds the microphone (or types). The talk bar shows who she is answering, and goes
   back to the caregiver afterwards.
3. Hana gets Grandma's answer retold simply, Grandma's own voice, a picture of what she described (Muse Image,
   about $0.01, drawn only when the checks passed), and one question to ask next, which she can tap to keep going.

Every relay is on the caregiver's stream, with an English gloss. **Code checks what reaches each person:** the
final send gate and the date rule run on everything, and what reaches a child also passes the child-safety review
(the tuned guard when it is deployed, otherwise Muse Spark). Anything held waits for the caregiver ("send anyway"
works only for soft holds, never for a link or a request for money). A relay only runs between the parent and a
child; the caregiver has their own channel. If the relay writer can't run, the words are passed on as they were
said, and anything for a child is held until the caregiver reads it. Relays are sent without waiting for approval
when the checks pass: both people are inside the closed circle (T1), and a conversation between a grandmother and
a grandchild shouldn't wait for a parent's tap. *(My call; easy to switch to "approve every relay to a child".)*

Live run (2026-11-02, real Meta calls): Hana tapped "おばあちゃんが ちいさいころ、おかいものは どんな おみせだったの？",
it reached Okaasan in 7 s; her typed answer about the dagashi shop reached Hana in 32 s (retold, child guard,
picture), with the next question "どんな あじの あめだったの？". The English demo (Leo and Grandma, hopscotch) worked
the same way. Meta spend for both reels, eight moments and three relays was about $0.013, plus $0.02 for two pictures.

## Revision (2026-11-03): apps panel and the home page

- **Apps panel:** the "Coming next" strip of app marks is gone. The panel lists six apps as tiles: Notion (real when
  `NOTION_TOKEN` is set), and Gmail, Slack, Spotify, Google Photos and LINE as "Not connected" slots.
- **Home page:** `/` is now a public home page (`web/app/home.html`, `css/home.css`, `js/home.js`). The Studio moved to
  `/studio`, and `/?circle=<id>` redirects there. The page labels every feature "Live", "Simulated" or "Coming next".
  It compares roleEdge with categories of products (no company names) and cites a source for every number. Its
  roadmap section shows unbuilt ideas, so keep that section out of the hackathon video.
