"""The record of every change the lab made: the weakness (with its evidence), the cause, what changed, and the round
that measures it. The report renders this table; the measured effect is read from the rounds themselves."""

from __future__ import annotations

CHANGES: list[dict[str, str]] = [
    # ---------------------------------------------------------------- round 2: from the round 1 diagnosis
    {"id": "C1", "round": "2", "cause": "prompt", "where": "studio/agents.py PLANNER",
     "weakness": "The planner recommended a spoken note for 40 of 41 reels, and a picture or video for lists. The "
                 "judge's best format was a card for 11 reels, a video for 9 and steps for 7.",
     "change": "Moments are chosen by the content's shape: a list is a card or steps, a method or exercise is steps or "
               "a video, a topic with parts is a map, one idea or the family's news is a note. A picture never goes alone."},
    {"id": "C2", "round": "2", "cause": "prompt", "where": "studio/agents.py maker rules",
     "weakness": "Makers dropped the reel's substance for reassurance: \"we can skip the computer part\", a 15-term "
                 "list cut to one example, 5 steps merged into one page (24 major \"prompt\" findings).",
     "change": "Keep the substance, simplify only the words: name every item of a list (up to 7), keep steps in order "
               "and each claim with its step, never tell her to skip a part; unconfirmed claims are the speaker's."},
    {"id": "C3", "round": "2", "cause": "prompt", "where": "studio/agents.py FACT_CHECK",
     "weakness": "9 of 41 reels were called likely scams, including an airport seat tip, a free university course "
                 "and student discounts, so their moments became warnings with no content.",
     "change": "A tip, opinion, recommendation, tutorial, exaggerated marketing or \"comment to get the link\" is "
               "unverified, not a scam, unless a main claim is false or it asks for money, details or a risky download."},
    {"id": "C4", "round": "2", "cause": "prompt", "where": "studio/agents.py card maker",
     "weakness": "Fridge cards left \"remember\" empty for lists (4 cards), the one line meant to be kept.",
     "change": "remember holds the date, time, name or thing to keep; for a list, its name (\"4 calming films\")."},
    {"id": "C5", "round": "2", "cause": "tool", "where": "models/studio.py, studio/agents.py, studio-view.js, studio_routes.py",
     "weakness": "Videos for exercises and demonstrations showed generic icons instead of the movement (17 major "
                 "\"tool\" findings: \"cannot show the mouth shape\", \"no visual model of the exercises\").",
     "change": "The reader describes every frame (pictures_en); a video scene can set frame to show the reel's own "
               "still behind its words; the viewer shows it. One movement per scene with its cue and a safety line."},
    {"id": "C6", "round": "2", "cause": "prompt", "where": "studio/agents.py READER",
     "weakness": "The reader summarised lists and steps loosely, so later agents had no item names to keep.",
     "change": "Facts keep each named item, each step in order and which claim goes with which step; a pasted caption "
               "is the creator's own words."},
    {"id": "C7", "round": "2", "cause": "workflow", "where": "lab/rounds.py source, composer.js hint",
     "weakness": "Film-clip reels carry their content in the caption (the film's title); a saved video loses it, so "
                 "moments could not name the film (5 major findings on 2 reels).",
     "change": "The share box asks for the caption when a video is attached; the lab passes the caption from round 2."},
    {"id": "C8", "round": "2", "cause": "workflow", "where": "lab/rounds.py choose()",
     "weakness": "The lab capped moments at three with the planner's picks first, so the profiler's content-based "
                 "choice was cut (a mind map was made once in 41 reels).",
     "change": "The planner's first two, then the profiler's first choice, then the rest, at most three."},
    # ---------------------------------------------------------------- round 3: from the round 2 diagnosis
    {"id": "C9", "round": "3", "cause": "workflow", "where": "models/studio.py content_shape, studio/swarm.py own_moments",
     "weakness": "Told in words to choose by shape (C1), the planner still recommended a note (and often a picture) "
                 "first: a resource list got note + picture, a vocabulary list note + picture.",
     "change": "The plan names the content's shape (list, steps, movement, topic, one idea, family news, warning); for a "
               "parent, code makes the shape's moment first (card, steps, video, map) and recommends at most two."},
    {"id": "C10", "round": "3", "cause": "prompt", "where": "studio/agents.py PLANNER and maker rules",
     "weakness": "For misleading or unverified reels the moments were warnings with no content (\"we cannot check if "
                 "they are true\"): the planner was told the plan \"must not spread its claims\".",
     "change": "Only a scam (asks for money, codes, details, secrecy) becomes a warning without its asks. Misleading or "
               "unverified: explain what it shows and says as the speaker's claims, and name the untrue ones."},
    {"id": "C11", "round": "3", "cause": "workflow", "where": "studio/swarm.py make",
     "weakness": "A video made with a note repeated the note scene by scene (\"heavy machinery for a nothing-to-do "
                 "message\").",
     "change": "Each maker is told which moments are made with it and to do its own format's job."},
    {"id": "C12", "round": "3", "cause": "prompt", "where": "studio/agents.py picture maker",
     "weakness": "Pictures drew a generic older woman listening at home instead of the reel's subject (\"invents a "
                 "scene that is not in the reel\").",
     "change": "Draw what the item is about (its place, the movement, the thing), not the parent or someone watching."},
    # ---------------------------------------------------------------- round 4: the full set, as on the home page
    {"id": "C18", "round": "4", "cause": "workflow", "where": "studio/swarm.py own_moments (PACKS)",
     "weakness": "One share made one to three moments, while the product promises (home page, \"Share a reel. Get a "
                 "conversation.\") a mind map, slides, a quiz, an animated video and a picture from one reel.",
     "change": "Every share makes the full set: the shape's moment leads (card, steps, video or map; else the planner's "
               "first), then map, slides, quiz, video and picture; a child's set is story, quiz game, video, map, picture."},
    {"id": "C13", "round": "4", "cause": "prompt", "where": "studio/agents.py maker rules",
     "weakness": "Keeping the substance (C2) cost clarity: clear fell from 4.41 to 3.97 (six film titles in one sentence); "
                 "\"he says\" for speakers of unknown gender; pages that only say Maya loves her.",
     "change": "One fact per sentence, at most 12 words, list items on their own lines; \"the reel says\" unless the "
               "speaker is known; every line carries content."},
    {"id": "C14", "round": "4", "cause": "prompt", "where": "studio/agents.py slides (steps) maker",
     "weakness": "Slides for a list or a topic read as fake steps (\"these are not steps Linda can follow\"), and the "
                 "last page was filler (\"Ask Maya For Help\").",
     "change": "Slides: one idea per page in order; a method's step, a list's item or a topic's part, named; the last "
               "page is the one thing to remember or do."},
    {"id": "C15", "round": "4", "cause": "prompt", "where": "studio/agents.py quiz (askme) maker",
     "weakness": "Quizzes asked trivial or sharing questions with absurd wrong answers (\"a kids cartoon show\").",
     "change": "Ask about the content's own facts; wrong choices sound possible; the explanation adds one fact."},
    {"id": "C16", "round": "4", "cause": "prompt", "where": "studio/agents.py mind map maker",
     "weakness": "Maps organised the conversation, not the content (branches \"Hello from Maya\", \"Fun Reel Question\"), "
                 "with telegraphic leaves (map mean 2.8).",
     "change": "Branches are the content's own parts (items, steps, groups, claims, by name); a leaf is a 4-10 word "
               "phrase that tells one fact."},
    {"id": "C17", "round": "4", "cause": "prompt", "where": "studio/agents.py video maker",
     "weakness": "The last scene was \"Maya can help\" filler.",
     "change": "The last scene is the one thing to remember or do."},
    {"id": "C19", "round": "4", "cause": "tool", "where": "lab/rounds.py draw",
     "weakness": "In the lab a picture was only its description, while the Studio draws it.",
     "change": "The lab draws every picture with Muse Image ($0.01), as the Studio does; /lab shows them."},
    # ---------------------------------------------------------------- round 5: from round 4's first results
    {"id": "C20", "round": "5", "cause": "workflow", "where": "studio/swarm.py unusable, answer_explained",
     "weakness": "A quiz marked the reel's false claim (\"a free iPhone and Android app\") as the right answer while its "
                 "own explanation said it was source code you build with a paid key.",
     "change": "Code checks that each question's explanation matches its marked choice better than any other; if not, "
               "the maker gets one more try, told what was wrong (the same check catches an empty moment)."},
    {"id": "C21", "round": "5", "cause": "prompt", "where": "studio/agents.py picture maker",
     "weakness": "Pictures still drew generic cosy rooms and parks (picture mean 3.2, the lowest): the ban on screens "
                 "and text left nothing of a film or app reel to draw.",
     "change": "Show the subject concretely: the movement from the side, the named things (a phone recording, a cinema "
               "seat facing a glowing blank screen, a shop shelf), or the place; no readable text, no real faces."},
    {"id": "C22", "round": "5", "cause": "model", "where": "studio/agents.py WATCHER, studio/swarm.py watch, content/ingest.py video_part",
     "weakness": "The reader saw 8 evenly spread frames, so it merged movements and lost their order (\"links one move "
                 "to two benefits\"; \"cannot show the timing or mouth shape\").",
     "change": "Muse Spark watches the whole video with its sound (input_video; tested: it gave each of the 5 voice "
               "exercises with its time and purpose) and returns a timeline the reader uses."},
    {"id": "C23", "round": "5", "cause": "tool", "where": "content/ingest.py frames_at, studio/swarm.py watch",
     "weakness": "Stills were spread evenly, so a video scene often showed the wrong moment for its words.",
     "change": "The stills are taken in the middle of each step the watcher found (up to 8), so scene N shows step N."},
    {"id": "C24", "round": "5", "cause": "tool", "where": "studio/agents.py ITEM_RESEARCHER, studio/swarm.py look_up",
     "weakness": "Film and website lists gave bare names (\"titles with no hint of what each film is like\").",
     "change": "A new agent looks up each named film, show, book, site, app, product, place or course on the web (genre, "
               "year, rating; free or paid) and the makers say what each one is."},
    {"id": "C25", "round": "5", "cause": "tool", "where": "studio/swarm.py find_focus (SAM 3.1), studio-view.js ringOn",
     "weakness": "In a movement still, an older reader may not see which part moves.",
     "change": "SAM 3.1 finds the body part the watcher names in each still; the video centres on it and rings it."},
    {"id": "C26", "round": "-", "cause": "workflow", "where": "content/social.py, app/studio_routes.py read_source",
     "weakness": "A reel shared as a link could not be opened, so the caregiver had to save and attach the video.",
     "change": "Reel and video links (Instagram, TikTok, YouTube, Facebook) are downloaded with their caption, through "
               "those sites' extractors only; photo posts and login-only reels get a plain message. Tested on 11 links."},
    {"id": "C27", "round": "Leo 3", "cause": "prompt", "where": "studio/agents.py CHILD_RULE",
     "weakness": "With films now looked up (C24), the safety review held 8 of Leo's 41 sets (3 before): sets offered "
                 "PG-13 and R films, kept handstand steps, or told him to \"follow for part two\".",
     "change": "A child's moments leave out anything rated for teens or adults, never give the steps of a stunt, and "
               "never ask him to follow or subscribe. Re-run on the 8 held reels."},
    {"id": "C28", "round": "-", "cause": "workflow", "where": "app/guards.py, costs.py spend (meta_app_usd)",
     "weakness": "The lab's calls, copied into the app's usage ledger for the credit meter, pushed it past the demo's $25 "
                 "spend guard, so the Studio refused new shares.",
     "change": "Lab rows are marked \"source\": \"lab\"; the credit meter counts them, the demo's guard doesn't (and "
               "reads the app's own ledger, so tests no longer depend on the real one)."},
    # ---------------------------------------------------------------- round 6: the family's own review of the moments
    {"id": "C29", "round": "6", "cause": "prompt", "where": "studio/agents.py maker rules",
     "weakness": "The family read the moments and found them robotic: \"Mom, I am Maya, and I saved this for you. The reel "
                 "says...\", the speaker's coat and the black-and-white picture, \"you do not need to follow or comment\". "
                 "Earlier rules caused part of it (C13 told makers to write \"the reel says\").",
     "change": "The family's own voice: pick up the chat, never introduce yourself, tell the content itself as news or a tip, "
               "name a person only when it matters, no disclaimers she doesn't need, a scam as kind news, products with what "
               "they're good for and an offer to get one."},
    {"id": "C30", "round": "6", "cause": "workflow", "where": "studio/verify.py robotic, studio/swarm.py _make_one",
     "weakness": "A rule in a prompt is followed most of the time, not always.",
     "change": "Code finds the robotic habits in what she will see (English and Japanese) and gives the maker one rewrite, "
               "told exactly which words to change; the version with fewer habits is kept."},
    {"id": "C31", "round": "6", "cause": "prompt", "where": "studio/agents.py PLANNER",
     "weakness": "Every kind of reel got the same treatment: ten films listed, a song quote with no hook, tech jargon, "
                 "stunts explained as a lecture.",
     "change": "A playbook by kind: films that suit her with an offer to watch together; products; recipes; tips as steps; a "
               "quote or song with the hook she knows (\"Remember Rafi's song?\"); tech told lightly; stunts to watch; scams "
               "as news; the question always about her own life. Safety notes only for a real risk."},
    {"id": "C32", "round": "6", "cause": "prompt", "where": "studio/agents.py FACT_SEARCH, FACT_CHECK; studio/swarm.py useful_links",
     "weakness": "Clickbait (\"comment RSA for the link\", \"$850,000 course\") was listed as a scam sign, so a real free "
                 "Stanford class got a scam warning and no link.",
     "change": "Only asks for money, codes, details, secrecy, impersonation or a risky download are scam signs; the real "
               "thing is judged, not the hook. Checked official links are added by code for anything without scam signs."},
    {"id": "C33", "round": "6", "cause": "tool", "where": "studio/inputs.py page_image, studio/swarm.py product_pictures and product_crops",
     "weakness": "A product reel said \"only her opinion, you do not need to buy anything\" and never named what each product "
                 "is for; a background song was looked up as a product.",
     "change": "Products named with what they're good for, a picture from the shop's own page (og:image, fetched with the "
               "same guards as links) or cut out of the reel's still by SAM 3.1, and \"I'd like one\" on her phone; the item "
               "researcher corrects an item's kind (a song is a song)."},
    {"id": "C34", "round": "7", "cause": "prompt", "where": "studio/agents.py maker rules, mind map maker",
     "weakness": "After round 6 the voice was warm but some moments still read like lists: \"Not for us\" after each of five "
                 "films, mind map leaves as labels (natural 3 of 5 on maps). The user: \"close to natural, how we explain "
                 "something to others\".",
     "change": "Explain it like over tea: why she'd care (\"you know how ...\" from her life), the gist, one or two details "
               "with a comparison she knows; contractions, a little reaction of your own; say once that something isn't for "
               "her; mind map leaves are short spoken sentences."},
    {"id": "C35", "round": "after 7", "cause": "workflow", "where": "studio/verify.py robotic",
     "weakness": "Round 7 still had \"not for us\" after each of five films on one card, and a video line about the "
                 "speaker's blue shirt: habits the first check didn't know.",
     "change": "The check also catches a refusal repeated after each item and describing the person in the reel (clothes, "
               "\"he makes funny faces\"); 5% of round 6-7 moments would now get the rewrite. Not yet measured in a round."},
    {"id": "J4", "round": "5 rescored", "cause": "evaluation", "where": "lab/agents.py JUDGE_V4",
     "weakness": "No score measured what the family complained about.",
     "change": "Judge v4 adds natural (1-5: the family talking vs a report) and counts each robotic habit as a problem; "
               "round 5 was scored again with it."},
    {"id": "J3", "round": "3 rescored", "cause": "evaluation", "where": "lab/agents.py JUDGE_V3",
     "weakness": "With a full set, \"format fit\" as \"is this the best format\" marks every map, quiz and picture down "
                 "by design.",
     "change": "Judge v3: format fit asks whether the moment uses its own format well; slides are one idea per slide. "
               "Round 3 was scored again with it, so round 4 compares like for like."},
    {"id": "K1", "round": "Leo 1", "cause": "workflow", "where": "lab/rounds.py kids, lab/agents.py JUDGE_CHILD",
     "weakness": "Untested: the same reels as a child's set (story, quiz game, video, map, picture) for Leo, 9.",
     "change": "A children's round with the child-safety review on every pack and a children's judge (safety first)."},
    {"id": "J2", "round": "1 rescored", "cause": "evaluation", "where": "lab/agents.py JUDGE_V2",
     "weakness": "The judge marked right things as faults: a note in Maya's voice as an invented speaker, a picture "
                 "judged on its caption alone, a watch-only framing of a risky exercise as missing content.",
     "change": "Judge v2 is told how moments work; round 1 was scored again with it, so every round compares like for like."},
    {"id": "T1", "round": "-", "cause": "evaluation", "where": "lab/rounds.py agreement()",
     "weakness": "Transcript agreement was near 0 for Hindi and Urdu reels because the reference was in another "
                 "script (Urdu script, or an English translation) while ours was in Devanagari.",
     "change": "Agreement is measured only when both transcripts use the same writing system; otherwise not comparable."},
    # ---------------------------------------------------------------- Notion
    {"id": "N1", "round": "Notion 2", "cause": "tool", "where": "connectors/__init__.py Notion.recent",
     "weakness": "Only the 25 most recently edited pages were listed, so the agent could not find older reel pages "
                 "(2 of 10 scenarios failed).",
     "change": "Follow Notion's result pages up to the limit asked for (at most 200)."},
    {"id": "N2", "round": "Notion 2", "cause": "tool", "where": "connectors/__init__.py Notion.read",
     "weakness": "Text inside toggles was never read, and a database row's properties were ignored (1 scenario failed).",
     "change": "Read nested blocks two levels down, follow block pagination, and put a row's properties first."},
    {"id": "N3", "round": "Notion 2", "cause": "prompt", "where": "lab/agents.py NOTION_ANSWER",
     "weakness": "Asked about one reel, the answerer used two other film pages that looked related.",
     "change": "Answer about the thing asked, not a near match; otherwise it isn't found."},
]
