# CareCircle: architecture and engineering rules

This document explains how the code is organised and the rules every change must follow.
If you change a rule, change this file in the same commit.

- Product plan: [docs/PLAN.md](docs/PLAN.md)
- Feasibility results: [docs/FINDINGS.md](docs/FINDINGS.md)
- Visual design system: [docs/design.md](docs/design.md)

---

## 1. Languages and stack

| Part | Language / tool | Why |
|---|---|---|
| AI pipelines, agents, API | **Python 3.11+**, FastAPI, pydantic, httpx | Python is the strongest ecosystem for model SDKs, LiveKit Agents (voice calls), ffmpeg and Playwright tooling. pydantic gives typed data and the JSON schemas the models must fill. |
| Rendering (cards, explainer video, mocks) | Jinja2 HTML templates → headless Chromium (Playwright) → ffmpeg | HTML/CSS gives correct Indic text, emoji and brand styling. Templates keep the HTML out of Python. |
| Chat playground (web) | Plain **HTML + CSS + ES modules**, no build step | Small and readable, and runs anywhere. There is no framework to learn and no toolchain to break. |
| Product web app (later) | **TypeScript** (e.g. Next.js) | Typed UI code at product scale. The API types are generated from the FastAPI OpenAPI schema, not written by hand. |
| iOS app (later) | **Swift / SwiftUI**, or React Native if code is shared with Android | It needs CallKit, PushKit and a Share Extension. The choice is open (PLAN §9). |
| Quality | pytest, ruff | Fast tests that need no network, and one lint and format standard. |

## 2. Repository layout

```
ARCHITECTURE.md        you are here
README.md              setup and commands
pyproject.toml         package, dependencies, tool settings
.env.example           every environment variable (copy to .env; never commit .env)
docs/                  PLAN.md, FINDINGS.md, design.md
data/samples/          synthetic inputs only (fictional reel, bill, notice)
src/carecircle/
  config.py            settings and paths - the ONLY reader of environment variables
  models/              domain data (pydantic): Digest, Recipient, CarePlan, CallReport ...
  llm/                 model access
    base.py              Provider interface
    azure.py, meta.py    the two providers (wire formats live only here)
    http.py              the only HTTP calls to model APIs (timeouts, retries)
    schema.py            pydantic model -> strict JSON Schema / tool definition
    client.py            LLM = provider + disk cache + usage ledger
    providers.py         registry, configured providers, contributor-model guard
  content/             shared item -> digest -> checker (+ prompts.py)
  checkin/             daily check-in call: agent loop, tools, escalation rule, report (+ prompts.py)
  render/              card, explainer video, calendar (.ics), theme, i18n, templates/
  chat/                chat playground API (FastAPI)
  demo.py              synthetic people, care plan, call scenarios, content cases
  samples.py           generates the synthetic media in data/samples
  costs.py             measured usage -> dollars
  mock.py              caregiver + "what Mummy sees" mock screen
  cli.py               `carecircle <command>` entry point
web/chat/              chat playground front end
  index.html
  css/                 tokens.css (design tokens) + one file per area, imported by app.css
  js/                  main.js wires modules; one feature per module (see §8)
tests/                 unit tests, no network
output/   (generated)  pipeline results - never edit by hand, never commit
.cache/   (generated)  model-call cache - delete to force fresh calls
```

## 3. Layers and import direction

Imports only point **down** this stack. A module never imports from its own layer or a higher one, except
inside its own package. **`tests/test_layers.py` enforces this**, so a violation fails the tests.

```
 4  cli.py · chat/                                entry points (the only places that print or start servers)
          │
 3  demo.py · samples.py · costs.py · mock.py     fixtures and reports built from pipeline outputs
          │
 2  content/ · checkin/ · render/                 features (they never import each other)
          │
 1  llm/                                          model access (render/ may NOT use it: rule A3)
          │
 0  config.py · models/                           foundation: settings, and data with no I/O
```

- `models/` imports nothing from the package except other models.
- `llm/` imports only `config` and itself. Feature code reaches a model only through `LLM` (pipelines) or a
  `Provider` (the chat playground).
- `render/` turns `models` into files. It must not call a model.
- `demo.py` is the only place with demo data. Feature modules take people, plans and items as arguments.

## 4. How the main flows work

**Content transformer** (`carecircle content`, then `carecircle render`):
1. `demo.CONTENT_CASES` builds a `ContentItem`: text plus images. Videos become sampled frames (`content/ingest.py`).
2. `content.transform` makes one strict-JSON call that fills a `Digest`.
   - English parts are for the sender.
   - The recipient's parts are in their language.
3. `content/verify.py` runs a second call that checks the recipient's text against the source.
   - `apply_fixes` applies wording fixes.
   - Date issues are held for review (rule S2).
4. A `DigestRecord` is saved to `output/content/<case>/digest.json`.
5. `render.render_record` writes:
   - `card.png`, `explainer.mp4` and `event.ics` (calendar, without held dates);
   - `article.md` and `voice_note.txt`.

**Daily check-in call** (`carecircle checkin`):
1. `checkin.run_call` runs the agent loop. Saathi gets the care plan in its prompt and four tools (`checkin/tools.py`).
   Saathi asks about medicines, meals, pain and whether they have talked with anyone; loneliness is a "watch"
   concern, so the call turns amber.
2. A `SimulatedParent` (a second model) plays a hidden scenario. In the product, this is a real voice call.
3. Every tool call is recorded as an event.
4. After the call, the model writes a report. `escalation_status(events)` then **overrides its status**
   (rule S3).

**Chat playground** (`carecircle chat`):
1. The browser keeps the history and POSTs it to `/api/chat` each turn.
2. `ChatRequest.to_messages` converts it to canonical messages, and `Provider.chat` answers.
3. The response carries normalised usage (`input / cached / output / reasoning`), which the UI shows per message
   and in total.

## 5. Architecture rules

| # | Rule |
|---|---|
| **A1** | **One way to call a model.** Use `LLM` (cache and ledger) in pipelines, and a `Provider` only in the chat playground. HTTP calls to model APIs exist only in `llm/http.py`. |
| **A2** | **Messages are provider-neutral.** Everything inside the codebase uses the Chat Completions message shape. A provider converts to its own wire format at the edge (for example `MetaProvider.to_responses_input`). |
| **A3** | **The model writes content; code decides structure.** Layout, calendar dates, escalation colour, order state and anything else that must not be wrong is computed in code. The model fills text. |
| **A4** | **pydantic models are the contract.** Model output schemas and tool arguments come from `strict_schema(Model)` and `tool_spec(...)`. Never hand-write JSON Schema. Keep field order stable: it is the order the model fills. |
| **A5** | **Configuration lives in `config.py` only.** Secrets live only in `.env`. Every variable is listed in `.env.example`. |
| **A6** | **Prompts live in each feature's `prompts.py`** as named constants with `{placeholders}`. Editing a prompt changes the cache key, so re-run the pipeline and review the outputs before merging. |
| **A7** | **HTML comes from Jinja templates** (`render/templates/`, autoescaped), never from string-building in Python. Brand colours and fonts live in `render/theme.py` and `web/chat/css/tokens.css`; both follow `docs/design.md`. |
| **A8** | **Generated files** (`output/`, `.cache/`) are never edited by hand and never committed. `carecircle all` rebuilds them. |
| **A9** | **Runs are reproducible.** Demo runs use a fixed `TODAY`, and model calls replay from the cache. If a change should not affect prompts, `carecircle all` must print `replay=True` for every case. |
| **A10** | **New providers implement `llm.base.Provider`** and register in `llm/providers.py`. Nothing else in the codebase may name a specific vendor. |

## 6. Safety and product rules

These come from the feasibility findings. Where the code enforces a rule, a test guards it.

| # | Rule | Enforced in |
|---|---|---|
| **S1** | **No training-contributor models for real data.** Meta `*-contributor` models train on content. Pipelines refuse them unless `ALLOW_CONTRIBUTOR_MODELS=1` (synthetic tests only). | `llm/providers.py: pipeline_provider` · `tests/test_llm.py` |
| **S2** | **The checker never changes dates or times.** Questioned dates are held for the sender, including a wording fix that would change a date or time written in the text (article, narration, voice note), and, checked in code, any action date or time the shared text never mentions (photos whose text has no dates are left to the checker, which sees the image). Unreadable dates are held too. Held dates do not appear in the calendar or on the card. | `content/verify.py: apply_fixes, date_mentions, unsupported_dates` · `render/calendar.py` · `render/card.py` · `tests/test_verify_policy.py`, `tests/test_render.py` |
| **S3** | **The call status colour is computed by code from tool events, not by the model's summary.** red = an urgent concern; amber = a watch item or a missed medicine. Tool arguments are checked (case is ignored; invalid calls are sent back to the agent), and a value that cannot be read never lowers the status: an unreadable severity counts as urgent, an unreadable medicine status as missed. | `checkin/escalation.py` · `checkin/tools.py: read_arguments` · `tests/test_escalation.py` |
| **S4** | **Tools tell the agent the truth about state.** A food order is "pending approval", never "placed". Money and orders always need the caregiver's approval. | `checkin/tools.py` |
| **S5** | **Saathi always says it is an AI helper, never impersonates the caregiver, and never uses a cloned voice.** A clinician must review the call prompts and the red-flag list before real use. No diagnosis, no dose advice. | `checkin/prompts.py` (review required) |
| **S6** | **Approve-before-send is the default** for anything Saathi sends to a parent or child, until the measured error rates justify auto-send. | product, still to build |
| **S7** | **Only synthetic data in the repository**: no real names, phone numbers, health data or photos. | review |
| **S8** | **Kids:** no ads or analytics SDKs, and verifiable parental consent (DPDP Act). | product, still to build |
| **S9** | **Model text is always escaped before display**: Jinja autoescape in templates, and `escapeHtml` in the web UI. | `render/theme.py` · `web/chat/js/format.js` · `tests/test_render.py` |

## 7. Python conventions

- Start every module with `from __future__ import annotations` and a docstring that says **what the module does and
  why it exists**.
- Put type hints on every public function. Use pydantic models for data that crosses a boundary (model output,
  files, API) and frozen dataclasses for internal values.
- **Naming:** functions are verbs (`transform`, `build_calendar`), data types are nouns (`Digest`, `CallRecord`) and
  constants are `UPPER_CASE`. No abbreviations beyond common ones (`id`, `url`, `llm`).
- **Comments** explain *why* (a decision, a bug that was hit, a rule number), not *what* the next line does.
- **Errors:** raise `ConfigError` (setup problems) or `ProviderError` (API problems). Never use a bare `except:`.
  Library code doesn't print; `cli.py` does.
- **Files:** use `pathlib` and write `encoding="utf-8"` explicitly. Use `json.dumps(..., ensure_ascii=False)` so Indic
  text stays readable.
- Keep functions small and single-purpose. If you need a section comment inside a function, extract a function
  instead.
- **Formatting and lint:** `ruff check src tests` must pass. Lines are at most 120 characters, except prompts and
  templates.

## 8. Front-end conventions (web/chat)

- **ES modules, one feature per file.** `main.js` only wires them together.

| Module | Owns |
|---|---|
| `state.js` | all mutable state, plus saved preferences (localStorage) |
| `dom.js` | element lookups |
| `api.js` | every `fetch` to the server |
| `model-picker.js` | model dropdown and effort chips |
| `chat.js` | sending a turn, rollback on error, new chat |
| `messages.js` | rendering messages and usage chips |
| `usage-panel.js` | sidebar totals and cache meter |
| `attachments.js` | images |
| `voice.js` | dictation and read-aloud |
| `markdown.js`, `format.js`, `toast.js`, `sprites.js` | helpers |

- Other modules never touch `localStorage` or `fetch` directly.
- Escape model and user text before using `innerHTML` (`escapeHtml`, `renderMarkdown`).
- **CSS:** design tokens live in `tokens.css`, with one file per screen area. New colours or sizes become tokens
  first. Keep the single red accent (`docs/design.md`).
- Document a function's inputs and outputs with JSDoc where they are not obvious.

## 9. Testing

- `python -m pytest`: unit tests in `tests/`. They need **no network and no `.env`** (they use `FakeProvider`
  from `tests/conftest.py`).
- **Must be tested:**
  - every safety rule enforced in code (S1, S2, S3, S9);
  - schema generation;
  - provider wire-format conversion;
  - API validation and error mapping;
  - calendar output.
- **Behaviour regressions:** run `carecircle all`. Unchanged prompts replay from the cache (`replay=True`), so any
  diff in `output/` comes from code. Changed prompts make new calls; review the diffs in `digest.json` and the
  rendered cards before merging.
- **The front end** is checked by driving it in headless Chromium (send a message with an image, switch models,
  start a new chat) with no console errors.

## 10. Recipes

**Add a provider:**
1. Subclass `Provider` in `llm/<name>.py` and implement `default_model`, `list_models`, `chat`,
   `complete_json` and `call_tools`.
2. Add a config dataclass and environment variables in `config.py` and `.env.example`.
3. Register it in `PROVIDER_CLASSES` and `configured_providers`.
4. Add a wire-format test like `test_meta_converts_chat_messages_to_responses_input`.

**Add a field the model must produce:**
1. Add it to the pydantic model in `models/` at the right position.
2. Mention it in the feature's `prompts.py`.
3. Use it in code.
4. Re-run and review the outputs.

**Add a content case (demo):**
1. Put a synthetic input in `data/samples/`.
2. Add a `ContentCase` to `demo.CONTENT_CASES`.
3. Run `carecircle content <id>` and then `carecircle render <id>`.

**Add a check-in tool:**
1. Define its arguments as a model in `models/checkin.py`.
2. Add `tool_spec(...)` to `checkin/tools.py` and a truthful simulated result.
3. Describe when to use it in `checkin/prompts.py`.
4. If it affects the status colour, update `escalation.py` and its tests.

**Run the pipelines on Meta:** set `META_API_KEY`, a **non-contributor** `META_MODEL` and
`CARECIRCLE_PROVIDER=meta`. `call_tools` raises until Meta tool calling has been verified, so check-in calls
stay on Azure until then.

## 11. Where this is heading

This repository is the feasibility stage. When the product is built (docs/PLAN.md §4), these packages split
along the same seams:

| Today | Becomes |
|---|---|
| `llm/` | a shared library used by every service (same interface, more providers, e.g. TTS/STT) |
| `content/` + `render/` | a **worker service** fed by a job queue; outputs go to object storage |
| `checkin/` | a **LiveKit voice agent** (same prompts, tools and escalation rule; real-time speech in place of text turns) |
| `chat/` | the start of the **product API** (FastAPI), with auth, family circles and messages in Postgres |
| `web/chat/` | replaced by the TypeScript web app; the design tokens carry over |
| `demo.py` | test fixtures only |

## 12. Definition of done for any change

- [ ] Imports respect §3, and the change follows the A and S rules (or this file is updated to say why not).
- [ ] `python -m pytest` and `ruff check src tests` pass.
- [ ] `carecircle all` runs. Cache replays are unchanged unless the change touched prompts on purpose, and if it did, the outputs were reviewed.
- [ ] New settings are in `.env.example`, and user-visible behaviour is in the README or docs.
- [ ] No secrets or real personal data were added.
