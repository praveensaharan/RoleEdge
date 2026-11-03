# Product demo web app: implementation plan (plan 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `/demo`, an animated, editable web app that plays the saved outputs of both families (India, Japan)
as five flows across a caregiver phone, a Saathi lane with the grandma-and-grandchild mascot, and a parent phone.

**Architecture:** Static files in `web/demo/`, served by the existing FastAPI app (`GET /demo`, static mount
`/demo-static`). The page fetches `/api/demo/story` (plan 1) once. `flows.js` turns a family's data into plain
step lists; `player.js` runs steps in order; `stage.js` draws each step on the phones; `mascot.js` draws the
mascot and switches its state. No build step, no framework, no model calls.

**Tech stack:** HTML, CSS (custom properties, keyframes), ES modules, Web Animations API; FastAPI; Playwright
(already used by `render/`) for screenshots.

**Spec:** `docs/superpowers/specs/2026-10-28-product-demo-design.md` (Part 2).

## Global constraints

- Design system: `docs/design.md` (red `#e60000`, ink `#25282b`, Inter, 800-weight uppercase hero, 60px pills,
  6px cards). Token values identical to `web/chat/css/tokens.css`.
- Model text is always escaped before display (rule S9): build DOM with `textContent`, never `innerHTML` with
  story data.
- Held dates (rule S2) never appear as reminders: they show a lock and "waiting for your OK".
- Every animation has a reduced-motion path (`prefers-reduced-motion: reduce`): show the end state with a fade.
- Each file has one job and stays under about 200 lines. All UI words live in `copy.js`.
- Not a git repo: each task ends with `pytest -q`, `ruff check src tests` and a screenshot check.

## Contracts (shared by all tasks)

**Story** (from `/api/demo/story`): `{ families: [{ id, label, caregiver: {name, relation}, parent: {call_name,
full_name, language}, recipients: [...], items: [{ case, input, recipient, scam, digest, held_actions,
held_fields, voice_note, media: {card?, video?, calendar?} }], calls: [{ scenario, status, transcript: [[who,
line]], events: [{turn, tool, args}], report }], missing: [...] }] }`.

**Step** (built by `flows.js`): `{ do: string, at: "caregiver" | "lane" | "parent", caption: string,
mascot?: "idle" | "thinking" | "happy" | "worried" | "calling", hold?: ms, ...payload }`.
`do` is one of: `bubble`, `fly`, `build-card`, `approve`, `land-card`, `voice`, `shield`, `safety-card`,
`held-note`, `lift-date`, `calendar-chip`, `reminder`, `lock`, `ring`, `line`, `tool-chip`, `status`, `alert`,
`tap`, `mirror`.

**Flow**: `{ id, label, icon, steps(family) -> Step[] | null }` (null hides the chip when data is missing).

**Player**: `createPlayer({ stage, onStep }) -> { load(steps), play(), pause(), replay(), isPlaying() }`.
`onStep(index, step)` updates dots and caption.

**Stage**: `createStage(root) -> { reset(family), run(step) -> Promise<void> }`; each `do` is one function in
a `RENDER` table, so adding a step type is one new entry.

**Mascot**: `mountMascot(el, { scale }) -> { set(state) }`; `PALETTE` and grids exported for editing.

## Files

| File | Job |
|---|---|
| `src/carecircle/config.py` | `DEMO_WEB_DIR = REPO_ROOT / "web" / "demo"` |
| `src/carecircle/chat/app.py` | `GET /demo`, mount `/demo-static` |
| `tests/test_story.py` | route test for `/demo` and a static file |
| `web/demo/index.html` | skeleton: hero, family switch, chips, stage (3 columns), controls |
| `web/demo/css/tokens.css` | design tokens (copied values) |
| `web/demo/css/layout.css` | hero band, chips, stage grid, controls, responsive stack |
| `web/demo/css/phone.css` | phone frame, chat bubbles, cards, chips, status light, call screen |
| `web/demo/css/motion.css` | every keyframe + reduced-motion overrides |
| `web/demo/js/copy.js` | all UI words (English) + per-language bits (Hindi, Japanese, English) |
| `web/demo/js/story.js` | fetch story, cache it, `familyById` |
| `web/demo/js/flows.js` | the five flows as step lists (editing guide at top) |
| `web/demo/js/player.js` | runs steps; play, pause, replay |
| `web/demo/js/stage.js` | DOM for each step type on the phones and lane |
| `web/demo/js/mascot.js` | pixel grids, palette, states |
| `web/demo/js/dom.js` | tiny helpers: `el(tag, cls, text)`, `wait(ms)`, `animate()` with reduced-motion |
| `web/demo/js/main.js` | wires family switch, chips, controls |
| `README.md` | how to open the demo and the editing guide |

---

### Task 1: Routes and page skeleton

- [ ] Write the failing test in `tests/test_story.py`:

```python
def test_demo_page_and_assets_are_served(tmp_path):
    content_dir, checkin_dir = save_fixture(tmp_path)
    client = TestClient(create_app({"azure": FakeProvider()}, content_dir=content_dir, checkin_dir=checkin_dir))
    page = client.get("/demo")
    assert page.status_code == 200 and 'id="stage"' in page.text
    assert client.get("/demo-static/js/main.js").status_code == 200
```

- [ ] Run it: FAIL (404). Add `DEMO_WEB_DIR` to `config.py`; in `create_app` add

```python
    @app.get("/demo")
    def demo_page() -> FileResponse:
        return FileResponse(DEMO_WEB_DIR / "index.html")

    app.mount("/demo-static", StaticFiles(directory=DEMO_WEB_DIR, check_dir=False), name="demo-static")
```

- [ ] Create `index.html`, the four CSS files, `copy.js`, `story.js`, `dom.js`, `main.js` (family switch and
  chips rendered from the story; stage columns empty). Run the test: PASS.
- [ ] Screenshot `/demo` at 1440×900 and 390×844 (Playwright script in the scratchpad); check the hero, switch,
  chips and three columns (stacked on mobile).

### Task 2: Mascot

- [ ] `mascot.js`: grandma and grandchild grids and heart (as approved), one `PALETTE`, states `idle` (bob +
  blink), `thinking` (three sparkles orbit), `happy` (heart burst), `worried` (shake + sweat drop), `calling`
  (phone pixel beside grandma). `motion.css` holds the keyframes.
- [ ] Mount it in the hero (large) and the lane (small). Screenshot each state via `?mascot=<state>`.

### Task 3: Player, flows and stage: content flows

- [ ] `player.js`, `stage.js`, `flows.js` with **Share and simplify**, **Scam held back**, **Deadline to
  reminder**, driven by real items: first non-scam item with a card for share; first `scam: true` item for
  scam; first item with a dated calendar action for deadline (held actions show `lock`).
- [ ] Screenshot the end of each flow for both families (`?family=japan&flow=scam&end=1` jumps to the end).

### Task 4: Call and mirror flows

- [ ] **Saathi calls**: ring, transcript lines (first 8, typewriter), a `tool-chip` per event (severity
  colour for `flag_concern`), `status` from `call.status` (code-computed), `alert` on the caregiver phone with
  the report headline; Japan shows the `social_contact` line. Picks the most serious call (red > amber > green).
- [ ] **See what they see**: parent taps the card, plays the voice note; the caregiver phone shows a mirrored,
  smaller view with an "eye" badge replaying the taps.
- [ ] Screenshot end states for both families.

### Task 5: Check everything and document editing

- [ ] Run every flow for both families in Playwright; assert no console errors; capture end-state screenshots
  into the scratchpad and show them to the user.
- [ ] README: "Product demo" section with `carecircle chat` → `http://127.0.0.1:8000/demo` and the editing guide.
- [ ] `pytest -q` and `ruff check src tests` pass.
