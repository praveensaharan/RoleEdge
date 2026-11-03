# Reel Lab: evaluate, improve and prove the agents, reel by reel

*Started 2026-11-03. Owner: the RoleEdge agent team. This file is the working plan and the running log; the generated
report with every table lives in [reel-lab/REPORT.md](reel-lab/REPORT.md) (re-created by `python -m roleedge.lab report`).*

## Why

A real reel is the hardest thing a caregiver shares: bad audio, fast cuts, on-screen text, music, another language.
If the agents turn real reels into moments that are accurate, clear and worth a parent's or a child's time, they can
handle anything. Each reel is one test case. We do not accept a first result: we score it, find the weakness, fix the
cause (prompt, model, tool, workflow or data), run it again and keep the record.

## Ground rules

- Work reel by reel; never skip a file without recording why.
- The source folder `/home/azureuser/insta-analyze` is **read only**. Everything we make goes to `output/reel-lab/`
  (git-ignored: it holds derived media) and the reports to `docs/reel-lab/`.
- No key, token or private integration data is ever written to a report, a log line or the repository.
- An integration is "working" only after a test against it passed, and the report says which test.
- Every prompt or workflow change names the weakness it fixes and is checked by a re-run.
- Spending is logged per call (the usage ledger) and summed per reel and per round.

## Phases and status

| # | Phase | Status |
|---|---|---|
| 1 | Inventory: every reel, its files and metadata; reels without a video recorded with the reason | done: 44 reels, 41 usable, 3 image posts skipped |
| 2 | Technical check per reel: audio (present, loudness, silence share, speech) and video (resolution, blur, freezes, brightness) | done (ffmpeg, bands per reel in REELS.md) |
| 3 | Understanding per reel: transcript (Muse Voice Transcribe), visual reading (Muse Spark on frames), content type, best formats | done |
| 4 | Round 1, baseline: the Studio swarm as it is today makes the chosen moments for every usable reel; scored | done |
| 5 | Diagnosis: weaknesses grouped by cause (prompt, model, tool, workflow, data) | done, after every round |
| 6 | Round 2+: targeted fixes, re-run, compare, until the quality bar is met or the limit is the data | done: rounds 2-5, and a children's set for Leo |
| 7 | Notion: inspect the integration and its permissions, create test pages, run five retrieval scenarios | done: 7/10 → 10/10; test pages moved to the trash |
| 8 | Mock Gmail, Slack, Zoom and Google Calendar you can add to; agents pick the new items up; real-integration plan | done: 5/5 end to end; INTEGRATIONS.md |
| 9 | Report: inventory, quality, content, agent choices, before/after, prompt changes, Notion, calendar, costs | done: reel-lab/REPORT.md, REELS.md, OUTPUTS.md, and the `/lab` page |

## How a reel is scored (measurable, not "looks good")

**Technical (code, from ffmpeg):** resolution, frame rate, audio present, integrated loudness (LUFS), share of
silence, share of blurry frames, frozen-video share, scene cuts per 10 s. Each gets a pass / weak / fail band.

**Understanding (code + model):**
- *transcript agreement*: similarity between our transcript and an independent one (the earlier Gemini analysis in
  the source folder), 0..1;
- *reading coverage*: share of the reel's key points (independent analysis) that our reader also found, judged
  point by point;
- *usable*: enough speech or on-screen text to explain anything at all.

**Moments (code + judge):** for every moment made:
- *valid*: the schema and the code checks pass (counts in range, quiz answers valid, no date that isn't in the
  source, the final send gate);
- *judge score* (Muse Wonder, a rubric with five 1-5 criteria): **faithful** to the source, **clear** for the reader,
  **engaging**, **useful** (something to do or remember), **format fit** (this format suits this content);
- *coverage*: share of the reel's key points the moment carries;
- *verifier*: the Studio's own verifier verdict (approved, notes, fixes).

**The bar:** every usable reel gets at least one moment with judge score >= 4.2 of 5 and no "fix" issue; the
average across reels rises from round to round; no unsafe output (exercise, health or money advice) ever passes.

## Which output for which reel

| Content | First choice | Also |
|---|---|---|
| Educational, conceptual, information-dense | Mind map | Slides, quiz |
| A topic that tells a story or has steps | Slides (one idea per slide, icons and a picture) | Mind map |
| Exercise, movement, practical how-to | Animated video (one movement per scene, cues, safety line) | Slides |
| An interesting or complex idea | In your words + picture + quiz | Mind map |
| A website, app or online tool | Walkthrough slides (what it is, how to use it, limits) | Fridge card |
| Movie or entertainment list | Fridge card (the list) + a question to talk about | Picture |
| Too little content, unsafe or not suitable | Nothing made; the reason recorded | |

## Notion test plan (phase 7)

Scenarios, each with an expected answer written before the run:
1. retrieve one specific fact from one page;
2. summarise a page;
3. answer a question from a page;
4. combine facts from two pages;
5. ask for something the pages don't contain: the agent must say it isn't there, not invent it.

## Calendar and mock apps plan (phase 8)

- Demo Gmail, Slack, Zoom and Google Calendar that you can **add items to** from the Studio, stored per circle.
- Agents pick them up: shares from the apps panel, delivery answers from mail, and schedule answers ("When are you
  visiting?") from the calendar and meetings, by the disclosure rules (travel and family events: share; work:
  "busy until 4" only).
- A readiness report for real Google Calendar, Gmail, Slack and Zoom sign-in: scopes, consent screens, token storage,
  and the tests to run once credentials are provided. No real calendar is touched until then.

## Decisions taken without asking (overnight run)

The user asked for the whole task to be finished overnight without questions; where a choice was open, this is the
default taken and why.

- **Spending limit:** $50 for the whole lab, new calls stop at $45 (`lab/budget.py`); raised by the user to $55
  for rounds 6-7 and Leo's round 4. Counted as the Meta spend in
  `output/usage.jsonl` (every lab ledger is appended to it once, so nothing is counted twice) plus Muse Voice
  Transcribe at $0.18 an audio hour. The usage ledger also holds the app's own calls from before the lab, so the
  figure errs high.
- **Reader for the tests:** Linda (79, English, the "chen" circle). The user works in English; one parent keeps rounds
  comparable. Japanese stays a demo locale.
- **Judge:** Muse Wonder (`lab/judge`, then `lab/judge_v2`), the strongest Meta model, separate from the agents under
  test (Muse Spark). After round 1 the judge itself was found to mark right things as faults (see J2 in the report);
  round 1 was scored again with judge v2 so every round compares like for like.
- **Key points** for coverage come from the earlier, independent analysis in the source folder, not from our own
  reader, so the agents are not graded against themselves.
- **Notion test pages** went into the reels database (the integration has no plain page to create them under), titled
  "[RoleEdge test]", synthetic data only; they are moved to the Notion trash at the end (restorable for 30 days). The
  one page of another database the integration can see was never read.
- **Calendar:** no real calendar was touched; the Google client id in the source folder belongs to another project
  and was not used. The demo apps can be added to instead, and the real-connection plan is in
  [reel-lab/INTEGRATIONS.md](reel-lab/INTEGRATIONS.md).
- **The full set (the user's request on 2026-11-03):** every reel now becomes what the home page's "Share a reel. Get
  a conversation." shows: a mind map, slides, a quiz, an animated video and a picture, led by the moment the content's
  shape calls for (a card for a list, a note for one idea); a child gets a picture story, a quiz game, an animated
  video, a mind map and a picture. This is the Studio's default now, not only the lab's.
- **Children:** Leo (9) in the same circle; his own judge puts safety first, and every pack also goes through the
  child-safety review (Muse Spark; the tuned guard on Modal was not woken).
- **Nothing is committed**; all work is left in the working tree for review.

## Log

*Newest first. Each entry: what changed, why (the weakness), and the measured effect.*

- 2026-11-03: **Leo's round 4, the children's set in the family's voice** (C27, C29-C34, the children's judge v2 with
  natural). Code, same check on both: moments with a robotic habit 84% (round 2) → **3%**. The safety review held 8 sets
  in round 2 and **none** now: the makers leave adult things out and keep a child's version (a dating reel became "being
  friendly is like riding a bike", insults became "we don't copy mean words"). On the new judge: best moment per reel
  4.45, 31 of 41 at the bar, every moment 4.03, natural 4.0 (round 2 on the old judge: 4.25, 29, 3.72). Spend for the
  whole lab: $54.14 of the $55 the user set.
- 2026-11-03: **Round 7, explain it like a person** (C34; the user: "close to natural, how we explain something to
  others"): start with why she'd care ("You know how ..."), the gist, a comparison she knows, contractions, say once
  that something isn't for her, mind map leaves as spoken sentences. Against round 6 (judge v4): natural 3.62 → 3.82,
  engaging 3.69 → 3.88, maps 3.45 → 3.60, slides 3.88 → 3.99, best moment per reel 4.27 → 4.31, reels at the bar
  23 → 25, major findings 121 → 91; usefulness flat (3.10 → 3.05). Two habits still slipped through (a refusal after
  each item, describing the speaker's shirt); the code check now catches them (C35). 66 approved moments exported for
  fine-tuning.
- 2026-11-03: **Round 6, the family's voice** (C29-C33, judge v4; the user read the moments and found them robotic:
  "Mom, I am Maya, and I saved this for you. The reel says..."). Measured two ways. Code: moments with a robotic habit
  85% (round 5) → **0%** (6% under the stricter check added after round 7, C35). Judge v4 (round 5 scored again with it): natural 2.07 → **3.62**, best moment per reel
  3.61 → 4.27, reels at the bar 4 → 23, every moment 3.08 → 3.77, major findings 233 → 121. Part of the old voice was
  our own doing: C13 had told the makers to write "the reel says". The approved moments are exported as fine-tuning
  pairs (`python -m roleedge.lab dataset`, 35 so far). The budget was raised by the user to $55.
- 2026-11-03: **Leo's round 3** on the 8 reels the safety review held (C27): 5 now pass; 3 are still held for Maya
  (dating advice, stock trading, a quant-finance course), whose subjects are for adults: holding them is the
  intended outcome. The demo's spend guard no longer counts the lab's calls (C28).
- 2026-11-03: **Leo's round 2** (the watcher, stills, lookups and SAM for children): mean best 4.15 → 4.25, reels at
  the bar 21 → 29, every moment 3.59 → 3.72, major findings 121 → 100; the safety review held 8 (3 before), because
  the film lookups now show ratings the makers hadn't yet been told to respect.
- 2026-11-03: **Reel and post links** (C26): a reel shared as a link is downloaded with its caption and watched like an
  attached video; photo posts and login-only reels get a plain message. 11/11 source links as expected; tested end
  to end in the Studio with a reel link (download, watcher, SAM, lookups, plan, full set).
- 2026-11-03: **Round 5** (C20-C25: the whole video watched by Muse Spark, stills at each step, SAM 3.1 marking what
  to watch, an item researcher for films and sites, the quiz answer check, concrete pictures). Against round 4 on
  judge v3: pictures 3.31 → 3.49, slides 3.57 → 3.61, video 3.88 → 3.92, cards 3.51 → 3.65, the weakest moment per
  reel 2.91 → 3.08; maps 3.54 → 3.43 and notes 4.0 → 3.86 slipped; every moment 3.61 → 3.63 (flat), reels at the
  bar 26 → 21. The gain is where the reel shows something (the voice exercises: video 3.8 → 4.8, map 4.8); reels that
  are only music or an opinion have little more to give.
- 2026-11-03: **Leo's round 1** (K1): the children's set (story, quiz game, video, map, picture) on all 41 reels:
  mean best 4.15, every moment 3.59; the safety review held 3 packs for Maya (keeping a goal secret, stock trading
  losses, dating).
- 2026-11-03: **Round 4, the full set** (C13-C19, judge v3; the user asked for the home page's full set on every
  reel): 239 moments; mean best 4.02 → 4.17, reels at the bar 16 → 26 (round 3 rescored with judge v3); clear
  4.12 → 4.28; maps 3.4 → 3.54, slides 3.4 → 3.57, pictures 3.02 → 3.31 (now drawn).
- 2026-11-03: **Round 3** (C9-C12): major findings 83 → 58 (judge v2); unsafe advice that passed the gate: round 1
  two, round 2 none, round 3 one (none in rounds 4-5); mean best flat (3.94 → 3.97): fewer faults, but still only one
  to three moments per reel.
- 2026-11-03: **Round 3 fixes** (from the round 2 diagnosis, C9-C12 in the report): the planner still recommended a
  note for nearly every reel even when told to choose by shape, so the plan now names the content's shape and code
  makes the shape's moment first for a parent; misleading reels got content-free warnings because the planner was
  told "must not spread its claims", now the content stays as the speaker's claims and the untrue ones are named;
  makers know what else is made with them (videos repeated the note); pictures drew a generic person at home, now
  they draw what the reel is about.
- 2026-11-03: **Round 2** with C1-C8 (format by shape, keep the substance, calmer fact check, card "remember", the
  reel's own stills in a video, the caption). Mixed: fewer major findings per reel, but the mean best score did not
  rise (see the report): the planner did not follow the shape rule, and the makers wrote warnings in place of content.
- 2026-11-03: **Demo apps you can add to** (phase 8): Gmail, Slack, Zoom and a new Google Calendar demo, an Add form
  in the Studio's Apps panel, and a new schedule errand ("when are you visiting?") that sees work only as "busy".
  End to end on Meta: 5 of 5 questions answered as expected, the work event's title never reached the model.
- 2026-11-03: **Notion** (phase 7): integration inspected (counts only), 3 test pages created, 10 scenarios. Baseline
  7/10 (search lists only 25 pages; toggles and properties unread; one near-match answer); after N1-N3: 10/10, every
  quote found word for word in its page.
- 2026-11-03: **Round 1** baseline on all 41 usable reels, $2.84. Judge v1 mean best 3.64 (3 reels at the bar),
  rescored with judge v2: 3.99 (17 at the bar). Diagnosis in the report.
- 2026-11-03: inventory and technical probe: 44 reels, 41 with video, 3 image posts recorded as skipped. Audio is
  loudness-normalised on every reel (about -14 LUFS), so the audio bands pass everywhere; the differences are in
  speech (3 reels have no words at all) and in the picture (1 frozen, 3 dark, 3 blurry).
- 2026-11-03: plan written; lab tooling started (`src/roleedge/lab/`).

## Finished (2026-11-03, updated after rounds 6-7 and Leo's round 4)

**Done**
- Phases 1-9: 44 reels inventoried (41 usable, 3 photo posts skipped with the reason), measured, transcribed, watched
  whole, and run through the Studio's own agents in 7 rounds for Linda (79) and 4 for Leo (9); every moment scored by
  a Muse Wonder judge; every weakness traced to its cause and recorded (the change log in REPORT.md, C1-C35, J2-J4).
- The family's own review (round 6 on): the moments now sound like the family talking. Robotic habits in moments
  85% → 5% for Linda and 84% → 3% for Leo (code); natural 2.07 → 3.82 for Linda (judge v4); Linda's best moment per reel
  3.61 → 4.31 and 4 → 25 reels at the bar on the same judge; Leo 31 of 41 at the bar with nothing held by the safety
  review.
- The product changed with it: the full set of moments from one share; the voice rules and a code check that rewrites
  a robotic moment once; a playbook by kind of reel; a video watcher (Muse Spark reads the whole video), stills at each
  step, SAM 3.1 marking what to watch and cutting products out of the reel; an item researcher; checked links for
  genuine things; product pictures with "I'd like one"; reel links downloaded with their caption; the demo apps you can
  add to; your own Gmail, Calendar or Notion, or the demo ones; a more natural device voice.
- Reports: [reel-lab/REPORT.md](reel-lab/REPORT.md), [REELS.md](reel-lab/REELS.md), [OUTPUTS.md](reel-lab/OUTPUTS.md),
  [INTEGRATIONS.md](reel-lab/INTEGRATIONS.md), and the `/lab` page (linked from the home page). 66 approved moments are
  exported as fine-tuning pairs (117: Linda's and Leo's; `output/reel-lab/style-dataset.jsonl`, `python -m roleedge.lab dataset`).
- Spend: $54.14 of the $55 limit the user set (the lab's ledgers, Muse Voice Transcribe and Muse Image). Nothing
  committed.

**Not done, or not reached**
- Usefulness stays the lowest score (about 3.1 for Linda): many reels are music, opinion or entertainment with little
  to teach; the remaining gap is mostly the reels themselves.
- The stricter robotic check added after round 7 (C35) is in the product but hasn't been measured in a round yet.
- No real Google Calendar or Gmail sign-in until a Google OAuth client is added to .env; Notion's real connection is
  tested end to end.
- Photo posts by link: yt-dlp can't fetch them and the lab doesn't imitate a browser; the caregiver attaches them.
- Japanese: the rounds ran in English for Linda and Leo; the Japanese circle uses the same agents but wasn't scored.
- No model has been fine-tuned yet: the dataset is ready for a LoRA on an open Llama model (as the child guard was).
