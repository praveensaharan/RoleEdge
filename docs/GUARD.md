# The tuned child guard: runbook

A LoRA fine-tune of Meta's **Llama Guard 3 1B** on roleEdge's own child policy (English and Japanese). It checks
every line of a pack made for a child before the parent approves it. While it isn't deployed, the Studio uses the
Muse Spark prompt guardian as today. **Nothing here runs by itself:** you start each step, and only the steps marked
*paid* cost money. Watch the Modal dashboard (Usage) while the Modal steps run.

All commands run from the repository root (`/home/azureuser/muse`). `python -m roleedge.guard_cli modal ...` is the
normal Modal CLI, signed in with the `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` already in `.env` (the Modal CLI doesn't
read `.env` by itself).

Code: [policy.py](../src/roleedge/guard/policy.py) (categories, prompt, answer format),
[data.py](../src/roleedge/guard/data.py) (training data), [guard_cli.py](../src/roleedge/guard_cli.py) (these
commands), [guard_lora.py](../modal_apps/guard_lora.py) (training, evaluation, endpoint on Modal),
[client.py](../src/roleedge/guard/client.py) and `Swarm.guard` (the Studio calling it).

Times and costs below are rough estimates, not measurements. Modal's L4 list price was about $0.80 per GPU-hour
when this was written; check Modal's pricing page.

## 0. One-time setup (free)

1. **Hugging Face:** sign in, open `meta-llama/Llama-Guard-3-1B`, accept Meta's licence (approval can take a
   while), and create a *read* token.
2. **Modal secret with that token:** in the Modal dashboard, Secrets, create a secret named `huggingface` from the
   Hugging Face template (key `HF_TOKEN`). The dashboard keeps the token out of your shell history.
3. **The guard's key** (so nobody else can wake its GPU): make one key and use it in two places.

   ```bash
   .venv/bin/python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Create a Modal secret named `roleedge-guard` with `GUARD_KEY=<that key>`, and add
   `ROLEEDGE_GUARD_KEY=<that key>` to `.env`.
4. **Check the Modal sign-in** (lists apps; free):

   ```bash
   .venv/bin/python -m roleedge.guard_cli modal app list
   ```

## 1. See what the data step will cost (free, calls nothing)

```bash
.venv/bin/python -m roleedge.guard_cli estimate
```

Today's defaults: 80 Muse Spark calls to write about 1,920 lines, about 64 calls to check them, about $0.05 at the
contributor model's prices. `--rounds` and `--per` change the size.

## 2. Write the training data (*paid: Meta, about $0.05*)

```bash
.venv/bin/python -m roleedge.guard_cli data
```

- **What it does:** Muse Spark writes English lines (for a 9-year-old) and Japanese lines (for an 8-year-old) in the
  Studio's styles, for every category, for plain safe lines and for safe lines close to the line. A second, blind
  Spark pass labels them; only agreed lines are kept. Then it splits them 80/10/10.
- **Asks first:** it prints the estimate and waits for `y`.
- **Time:** a few minutes.
- **Results:** `output/guard/data/train.jsonl`, `val.jsonl`, `test.jsonl` and `stats.json` (how many lines were
  written, kept and dropped).
- **Stop:** Ctrl+C. Every finished call is cached, so running it again continues for free from where it stopped.

## 3. Add the real child-pack lines to the test set (free, local)

```bash
.venv/bin/python -m roleedge.guard_cli real
```

Lines from Hana's and Leo's packs that passed review are added to `output/guard/data/real.jsonl`, as safe test
lines. They are never used for training.

## 4. Train the LoRA (*paid: Modal, L4*)

```bash
.venv/bin/python -m roleedge.guard_cli modal run modal_apps/guard_lora.py::train --run v1
```

- **What it does:** LoRA (r=16, 3 epochs, learning rate 2e-4; the loss is only on the answer) on Llama Guard 3 1B in
  bf16.
- **Time:** the first run also builds the image (a few minutes of CPU) and downloads the model (about 3 GB, into the
  shared `roleedge-hf-cache` volume, so later runs skip it). Training itself should take minutes.
- **Cost:** roughly $0.10 to $0.50 of GPU time.
- **Limits:** the job stops itself after 2 hours at most.
- **Results:** `output/guard/runs/v1/train.json` (loss curve, eval loss). The adapter goes to the Modal volume
  `roleedge-guard-runs` at `/v1/adapter`. `/serving.txt` is set to `v1`, so the endpoint serves the latest trained
  run.
- **Stop:** Ctrl+C in the terminal ends the run and its GPU. If you are unsure, check the dashboard (Apps) and stop
  it there.
- **Options:** `--epochs 2`, `--lr 1e-4`, `--rank 8`. Use another `--run` name to keep both runs.

## 5. Evaluate: base vs LoRA (*paid: Modal, L4*)

```bash
.venv/bin/python -m roleedge.guard_cli modal run modal_apps/guard_lora.py::evaluate --run base
```

```bash
.venv/bin/python -m roleedge.guard_cli modal run modal_apps/guard_lora.py::evaluate --run v1
```

- **What it does:** each command classifies every held-out test line (plus the real lines). `base` is Llama Guard 3
  1B with our categories in its prompt and no training; `v1` adds the LoRA.
- **Time:** minutes each, mostly GPU start and model load.
- **Cost:** a few cents each.
- **Limits:** stops itself after 1 hour at most.
- **Results:** `output/guard/eval/base.json` and `v1.json`: scores per language, plus every prediction so you can
  read the mistakes.
- **Stop:** Ctrl+C.

## 6. Evaluate today's Muse Spark guardian (*paid: Meta, a few cents*)

```bash
.venv/bin/python -m roleedge.guard_cli spark-eval
```

- **What it does:** runs the Studio's current `CHILD_GUARD` prompt, one line at a time, on the same test lines.
- **Asks first:** it shows the estimated cost and waits for `y`.
- **Results:** `output/guard/eval/spark.json`.
- **Stop:** Ctrl+C. Finished calls are cached.

## 7. The comparison table (free)

```bash
.venv/bin/python -m roleedge.guard_cli report --write
```

- **Output:** prints a table of accuracy, unsafe recall, unsafe precision, F1 and category match, per guard and
  language.
- **`--write`:** puts the table into [FINDINGS.md §17](FINDINGS.md#17-tuned-child-guard-roleedge).
- **Reading it:** for a child, recall on unsafe lines matters most (a missed unsafe line reaches the child). A false
  alarm only costs the parent one read. Deploy the LoRA only if it beats the base model and holds up in Japanese.

## 8. Deploy the endpoint (*paid only while it is awake: Modal, L4*)

```bash
.venv/bin/python -m roleedge.guard_cli modal deploy modal_apps/guard_lora.py
```

- **What it does:** deploys `Guard.classify`, which takes a pack's lines and returns safe, or unsafe with
  categories, for each line. The URL is printed, for example
  `https://<workspace>--roleedge-child-guard-guard-classify.modal.run`.
- **Cost:** nothing while idle. It scales to zero; at most one container, which shuts down 2 minutes after the last
  request. Each wake-up is a GPU start (about 30–60 s) plus up to 2 minutes awake, roughly 3–4 cents on an L4.
- **Turn it on in the app:** add `ROLEEDGE_GUARD_URL=<the URL>` to `.env` (next to `ROLEEDGE_GUARD_KEY`), then
  restart the app. A child's pack is then checked line by line by the tuned guard. Its agent row and trace say
  `modal/llama-guard-3-1b+lora`. If the endpoint doesn't answer within 60 seconds (for example a cold start), the
  Muse Spark guardian checks instead. Either way, anything flagged is held for the parent.

## 9. Check the live endpoint (*paid: one wake-up, about 3–4 cents*)

```bash
.venv/bin/python -m roleedge.guard_cli check
```

Sends two lines, one safe and one that asks for a school name, and prints the verdicts.

## 10. Stop everything

```bash
.venv/bin/python -m roleedge.guard_cli modal app stop roleedge-child-guard
```

This takes the endpoint down completely. Remove `ROLEEDGE_GUARD_URL` from `.env` and restart the app to go back to
the Muse Spark guardian. The adapters stay in the `roleedge-guard-runs` volume, which costs nothing to keep at this
size. Delete them from the dashboard (Storage) if you want.

## Safety limits built in

- **Endpoint key:** requests need `Authorization: Bearer <GUARD_KEY>`; anything else gets 401.
- **Request size:** at most 64 lines per request, each cut to 1,000 characters.
- **One GPU at a time:** at most one container (`max_containers=1`), awake for 2 minutes after the last request.
- **Job time limits:** training stops itself after 2 hours, evaluation after 1 hour.
- **Tests never wake the GPU:** the app only uses the endpoint next to the real Meta provider, so test and offline
  runs never call it, whatever `.env` says.
- **Unclear answers are held:** an answer the guard writes outside the format counts as "not safe", so the parent
  reads that line.
