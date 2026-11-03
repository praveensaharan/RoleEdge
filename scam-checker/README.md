# scam-checker: a Japanese scam checker fine-tuned from Meta's Muse Glimmer

A self-contained kit. Copy this folder anywhere, add your own cases, and train on Modal. It makes a LoRA adapter for
[Muse Glimmer 30B](https://huggingface.co/meta-models/Muse-Glimmer-30B). The adapter checks one message received in
Japan (SMS, LINE, WhatsApp, email, a phone call written out, a social-media DM) for scams, and you can publish it on
Hugging Face for others to use. It then gets scored against Muse Spark, GPT and Claude on real messages.

Nothing runs by itself: you start every step. Steps marked *paid* cost money; the costs below are estimates, not
measurements, unless stated.

---

## Contents

1. [What the model answers](#1-what-the-model-answers)
2. [Why this task](#2-why-this-task)
3. [Muse Glimmer: what we checked](#3-muse-glimmer-what-we-checked)
4. [The data](#4-the-data)
5. [Adding your own cases](#5-adding-your-own-cases)
6. [The real test set](#6-the-real-test-set)
7. [Runbook](#7-runbook)
8. [Costs and times](#8-costs-and-times)
9. [Risks and limits](#9-risks-and-limits)
10. [Folder layout](#10-folder-layout)
11. [Sources](#11-sources)

---

## 1. What the model answers

One JSON object per message:

```json
{"scam": true, "type": "refund", "red_flags": ["ATMで手続き", "本日中"], "advice": "電話を切って、家族に確認してください。"}
```

| Field | Meaning |
|---|---|
| `scam` | true or false |
| `type` | the scam type below, or `none` for a genuine message |
| `red_flags` | up to 4 phrases **copied exactly** from the message, so code can check them and an app can highlight them |
| `advice` | one calm sentence in plain Japanese for an older person; empty if genuine |

| Type | What it covers |
|---|---|
| `family_impersonation` | オレオレ詐欺: a son or grandson with a new number, an accident, trouble at work, someone coming to collect money |
| `fake_official` | Pretending to be police, prosecutors, a ministry, the city office or a bank's security team (偽警察) |
| `refund` | 還付金詐欺: a refund that can only be received at an ATM or by online banking now |
| `fake_bill` | 架空料金請求: unpaid fees, lawsuits, gift-card or convenience-store payment codes |
| `investment` | SNS型投資詐欺: a famous person or "teacher", a LINE or WhatsApp group, fees to withdraw profits |
| `romance` | SNS型ロマンス詐欺: someone met online who soon needs money |
| `phishing` | フィッシング: a fake courier, bank, card, shop, carrier, tax-office or ETC notice with a link |
| `job_task` | 副業・タスク詐欺 and 闇バイト: easy pay for likes or reviews, then a deposit; high-pay "jobs" that are crimes |
| `prize` | 当選詐欺: a win that needs a fee or card details |
| `other` | any other scam |

**Two prompts** ([policy.py](scamcheck/policy.py)):
- **Full prompt:** every scam type and the rules. Untrained models get this one: base Glimmer, Muse Spark, GPT and
  Claude.
- **Short prompt (124 characters):** the tuned Glimmer is trained and asked with this one. It has learned the types
  and rules. The full prompt is about 20 times longer and would be repeated in every training example, so the short
  one makes training several times cheaper.

If the answer isn't valid JSON in this format, it counts as a scam. A confused checker warns instead of letting a
message through.

## 2. Why this task

- **A real problem in Japan.** Scam losses have been near record highs in recent years, and older people are the
  main targets. Check the National Police Agency's (警察庁) latest figures before quoting a number. Scams arrive by
  SMS and LINE above all, and job and investment scams often come by WhatsApp from foreign numbers. Whoscall says
  about 30% of scam calls in Japan come from overseas.
- **The apps are crowded; open models are not.**
  - Apps: Whoscall (number database plus AI), Dawn's 特殊詐欺 AI 判定サービス (scam-judging service, launched
    September 2026, closed), AI scam protection in Android (October 2026), and NTT Security's ChatSpamDetector (email,
    by prompting a large model).
  - Hugging Face: English phishing models, Korean, Thai and Chinese smishing (scam text) models, and small general
    scam guards. **We found no Japanese one** (search on Nov 3, 2026).
  - Research: a 2026 paper on Japanese phishing emails uses LoRA but published no model.
- **Our position:** the first open (Apache 2.0) Japanese scam checker across SMS, LINE, WhatsApp, phone and email,
  with red flags and advice, and a public test set. That matters to banks, phone companies, messaging apps and care
  services that can't send customer messages to an overseas API.
- **The answer format is backed by research.** Small models trained only on scam/not-scam labels did poorly in one
  study; training on explanations worked better. Our red flags and advice play that role.
- **The honest claim to aim for:** "beats Haiku and gpt-5-mini on real Japanese messages by X%, close to Sonnet, at a
  fraction of the cost, and runs on your own servers." Don't claim it beats Sonnet at everything.

## 3. Muse Glimmer: what we checked

From the model card and config on Hugging Face (`meta-models/Muse-Glimmer-30B`, checked Nov 3, 2026):

| | |
|---|---|
| Licence | **Apache 2.0, not gated**: publishing a fine-tuned adapter is allowed (keep the licence and notice) |
| Size | **Dense, 29.8B parameters**: 52 layers, hidden size 6656, 2 KV heads; about 60 GB in bf16 |
| Input | **Text and images** (screenshots, documents); video only as separate frames |
| Audio | **Not supported.** Phone scams have to be transcribed first, which is what the "phone call written out" channel is for. |
| Languages | Trained on 100+ languages; the card doesn't say whether Japanese is in the "strongly supported" set |
| Origin | Distilled from Muse Spark |
| Software | Config saved with transformers 5.15.0.dev0; this kit uses transformers 5.22.1 (the latest release on Nov 3, 2026) |
| Chat format | `<|start|>role<|message|>…<|eot|>`, with a reasoning channel (`assistant to=self`) and an answer channel (`assistant to=user`); "Reasoning strength: low/medium/high/xhigh" in the system prompt |
| Smaller versions | 4-bit, GGUF and ExecuTorch builds exist (24–32 GB devices), useful for people running it locally |

**What this means for us:**
- **Images:** a later version could also read screenshots. Older people often forward a screenshot instead of the
  text. Code could draw our messages as phone screenshots to make that training data.
- **Distilled from Spark:** Spark also writes our training data, so untrained Glimmer may already be close to Spark.
  Expect the training to help most with false alarms, the answer format and the real test set.
- **Training format:** the tuned model is trained to answer straight away in the answer channel, with no reasoning.
  That's fast and cheap to run.

## 4. The data

| Set | Target size | Where it comes from | Used for |
|---|---|---|---|
| `train` / `val` | about 6,000–7,500 / 700 | Muse Spark writes, then code and a blind Spark pass check; plus your cases | training |
| `test` | about 700 | the same, held out | quick checks only |
| `real_test` | about 300 | real published messages, labelled by their source | **the headline scores** |

About 40–50% of the training rows should be scams. Every scam type gets a matching **genuine look-alike** target: a
real city refund notice, a real police warning, a real courier notice. Those teach the model not to cry wolf.

**How the synthetic messages are made** ([generate.py](scamcheck/generate.py)):
1. **21 batches per round:** 9 scam types, 9 genuine look-alikes and 3 everyday. Each batch is 20 messages. Rounds
   rotate the channels, who receives the message (a woman in her 70s living alone, a university student, and so on)
   and the situation (tax season, New Year, after a typhoon, and so on).
2. **Code checks:**
   - Red flags must really occur in the message (a scam needs at least one).
   - Messages with Chinese characters not used in Japanese (确, 卡) are dropped.
   - Messages must be 10–1,500 characters.
3. **A blind second Spark pass** labels every message without seeing the intended label. A message is kept only if
   both agree on scam or not, and on the type.
4. **A third of the senders are blanked**, because forwarded messages often come without one.

**What the first sample showed (Nov 3, 2026: 1,260 messages, about $0.07, about 10 minutes):**

| Problem | Why it matters | Fix (now in the prompt or code) | After the fix (pilot) |
|---|---|---|---|
| Links: 21% of scams had one vs 3% of genuine messages | The model would learn "has a link = scam" | About half of genuine company notices link to the company's real domain | 28% vs 21% |
| Every message was short and similar in length (longest 171 characters) | Real scam emails are much longer | About one in five is a full email | Longest 321; still only 4% are long |
| 6 messages contained Chinese characters (确定申告, 卡) | 5 of the 6 were genuine, which teaches the wrong thing | Code drops them | Tested |
| Repeated openings: 「お母さん、俺だよ」 ("Mom, it's me") 10 times | The model memorises templates | "Vary how messages open" | Fewer repeats |
| The blind check dropped only 18 of 1,260 (1.4%) | Spark finds its own messages easy; truly hard cases are rare | Not fixed by prompting: **your cases and the real test set are what make it honest** | — |

That sample is in [data/synthetic/spark_v0_sample.jsonl](data/synthetic/spark_v0_sample.jsonl): 1,236 rows after
dropping the 6 with Chinese characters, made with the **older** prompt. It's there so the notebook and a first
training run work straight away. Delete it once you've generated new data.

## 5. Adding your own cases

Put CSV (or JSONL) files in [data/cases/](data/cases/). Start from [my_cases.csv](data/cases/my_cases.csv) (headers
only), and see [_template.csv](data/cases/_template.csv) for three worked examples. Files starting with `_` are
skipped. Open them in Excel, Numbers or Google Sheets, and save as CSV UTF-8.

| Column | Required | What to write |
|---|---|---|
| `text` | yes | the message exactly as it arrived |
| `scam` | yes | `yes` or `no` (also accepted: true/false, 1/0, 詐欺/本物) |
| `type` | if a scam | one of the types in section 1; leave empty for a genuine message |
| `red_flags` | if a scam | phrases copied **exactly** from the text, separated by `\|`: `新しい番号\|今日中に50万必要` |
| `advice` | if a scam | one calm sentence in plain Japanese |
| `channel` | no | `sms`, `line`, `whatsapp`, `email`, `phone`, `sns_dm` |
| `sender` | no | as it showed: `+62 812…`, a LINE name, an email address |
| `split` | no | `test` keeps the row out of training (use it for your hardest cases); empty means training |
| `note` | no | for you; ignored |

**Most useful to add:**
- **Genuine messages that look scary:** real refund notices, bank fraud alerts, courier notices, city notices about
  scams. These cut false alarms, which matters most for keeping people's trust.
- **New scam patterns:** fake police video calls, AI voice-clone calls, investment groups, job "tasks".
- **Messages that are hard to call:** these are rare in the synthetic data.

`python -m scamcheck build` checks every row. A row with a problem (an unknown type, a red flag that isn't in the
text) is skipped and printed with its file and line number, so you can fix it.

## 6. The real test set

Put real messages in [data/real/real_messages.csv](data/real/real_messages.csv) (see
[_template.csv](data/real/_template.csv)). Same columns as cases, plus `source_url` (required) and `published`.

- **Scams:** examples published by the police (警察庁, prefectural police), the National Consumer Affairs Center
  (国民生活センター) and the anti-phishing council (フィッシング対策協議会).
- **Genuine:** real notices from cities, banks, couriers and phone companies.
- **The label comes from the source, not from a model**, so nobody has to judge Japanese by hand and the test isn't
  circular.
- `build` never puts these into training, and it removes any training row that matches one.
- Check each site's reuse terms. If they don't allow reuse, keep the file private and publish only the scores.

## 7. Runbook

All commands run from this folder.

### 0. One-time setup (free)

```bash
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements.txt
cp .env.example .env                                   # add META_API_KEY (only needed for `generate`)
modal setup                                            # signs this machine in to Modal (opens a browser)
```

On Hugging Face, create an access token: **read** is enough to train, **write** is needed to publish. In the Modal
dashboard, go to Secrets and create a secret named `huggingface` from the Hugging Face template (key `HF_TOKEN`).
Every Modal step needs this secret to exist.

### 1. Generate more synthetic messages (*paid: Meta, about $0.05 per round*)

```bash
python -m scamcheck estimate --rounds 20     # free: calls, messages, cost
python -m scamcheck generate --rounds 20     # asks first; writes data/synthetic/spark_rounds_000-019.jsonl
```

- **Each round:** 21 batches of 20 messages. 20 rounds is about 8,400 messages, about $0.90 and 1–2 hours.
- **Running it again** adds new rounds after the last one, instead of repeating old ones.
- **Stopping:** Ctrl+C. Finished calls are cached in `.cache/`, so a rerun continues for free.

### 2. Add your cases and real messages (free)

Edit `data/cases/my_cases.csv` and `data/real/real_messages.csv` (sections 5 and 6).

### 3. Build the final sets (free)

```bash
python -m scamcheck build
```

It merges everything into `data/final/` and prints any skipped rows and the counts. Run it again after every change.

### 4. Look at the data (free)

Open [notebooks/data.ipynb](notebooks/data.ipynb) and run all cells. It shows:
- counts per type, channel and split;
- the link and length shortcuts to watch for;
- the checks (red flags really in the message, no message in two splits);
- examples, and exactly what the model is trained on;
- after evaluation: scores, mistakes and the loss curve.

### 5. Modal: weights and smoke test (*paid: a few cents, then about $1*)

```bash
modal run modal_train.py::download     # CPU only: about 60 GB into the volume scamcheck-hf-cache (once)
modal run modal_train.py::smoke        # H100: load, check the format, answer 3 messages
```

The smoke test is the go/no-go check. It must print:
- `loaded in … s` and GPU memory of about 60 GB;
- the linear-layer names, with `LoRA would go on N layers` showing language-model layers (not vision ones);
- `training format matches the chat template: True`;
- three sensible JSON answers from untrained Glimmer.

If any of these fails, stop and fix it before training. Paste the output to whoever helps you.

### 6. Train (*paid: Modal H100*)

```bash
modal run modal_train.py::train --run try --max-rows 200 --epochs 1     # minutes: does the loss fall?
modal run modal_train.py::train --run v1                                # the real run
```

- **Settings:** LoRA rank 16 on the language model's attention and MLP layers; 2 epochs; learning rate 1e-4;
  batches of 4 × 4 accumulation steps; the loss is only on the answer.
- **Options:** `--epochs`, `--lr`, `--rank`, `--batch`, `--accum`, `--max-rows`.
- **Output:** the adapter goes to the Modal volume `scamcheck-runs` at `/<run>/adapter`, saved after each epoch. The
  loss curve goes to `results/train_<run>.json`.
- **Progress:** it prints the loss, the validation loss and the minutes left. The job stops itself after 6 hours.
  Ctrl+C stops it and its GPU; if unsure, check Apps in the Modal dashboard.

### 7. Evaluate (*paid: Modal H100*)

```bash
modal run modal_train.py::evaluate --run base     # untrained Glimmer, full prompt, answers straight away
modal run modal_train.py::evaluate --run v1       # the tuned one, short prompt
modal run modal_train.py::evaluate --run base --think --limit 200    # optional: the untrained model reasons first
python -m scamcheck report                        # the comparison table from results/
```

Scores and every prediction go to `results/glimmer_<run>.json`. Read the mistakes in the notebook.

| Score | Meaning |
|---|---|
| Catch rate | share of scams caught |
| False alarms | share of genuine messages flagged |
| Type match | caught scams given the right type |
| Flag match | caught scams where a predicted red flag overlaps a labelled one |
| Unparsed | answers not in the format |

**Ship v1 only if it beats base** on catch rate *and* false alarms on `real_test`.

**Still to build:** the same scoring for Muse Spark, GPT (gpt-5-mini on Azure) and Claude (Haiku and Sonnet). Each
gets `scamcheck.messages(row)` (the full prompt), and `scamcheck.metrics.save` writes the results file. Never use
Claude's or GPT's answers as training data; their terms don't allow it. Use them only for scoring.

### 8. Publish (*free*)

```bash
modal run modal_train.py::publish --run v1 --repo your-name/glimmer-scam-checker-ja            # private
modal run modal_train.py::publish --run v1 --repo your-name/glimmer-scam-checker-ja --public   # when ready
```

It uploads the adapter with a model card ([model_card.py](scamcheck/model_card.py)). The card covers what the model
does, how to use it, how it was trained, and the score table from `results/`. The repo is **private unless you pass
`--public`**: read the card before making it public.

### Tests (free)

```bash
python -m pytest tests -q
```

## 8. Costs and times

Modal's H100 was about $4 per GPU-hour when this was written; check Modal's pricing page. All rows are estimates,
except the Meta data row, which was measured on the sample.

| Step | Time | Cost |
|---|---|---|
| Synthetic data, 20 rounds | 1–2 h | about $0.90 (Meta) |
| `download` | 10–30 min, once | cents (CPU) |
| `smoke` | 10–15 min, mostly loading | about $1 |
| `train --max-rows 200 --epochs 1` | about 15 min | about $1 |
| `train` on about 7,000 rows, 2 epochs | roughly 1–2 h | roughly $5–8 |
| `evaluate` (about 1,000 messages, no reasoning) | 15–30 min | $1–2 |
| `evaluate --think` | several times longer | use `--limit` |

## 9. Risks and limits

- **Software support for Glimmer:** it's a new architecture. If transformers 5.22.1 or peft 0.21.2 can't load or
  train it, the smoke test shows that first. Then change the versions at the top of
  [modal_train.py](modal_train.py).
- **Japanese quality isn't confirmed** by Meta. The base evaluation will show it.
- **The synthetic data is easy and circular:** Spark writes it, Spark checks it, and Glimmer is distilled from
  Spark. Your hard cases and the real test set are what make the scores honest.
- **Shortcuts:** watch section 5 of the notebook. If only scams have links, foreign numbers or long texts, the model
  learns the shortcut instead of the scam.
- **Terms:**
  - Check that Meta's terms allow training on Muse Spark's outputs.
  - Check the reuse terms of every real-message source.
  - Never train on Claude's or GPT's outputs.
  - The contributor model (`*-contributor`) lets Meta train on what you send. Use it for synthetic data only, never
    for real people's messages.
- **It's a warning tool, not a guarantee.** It will miss some new scams and flag some genuine messages. In an app, a
  person decides.

## 10. Folder layout

```
scam-checker/
  README.md                 this file
  modal_train.py            download, smoke, train, evaluate, publish (Modal)
  requirements.txt          local packages (modal, pandas, matplotlib, ipykernel, pytest)
  .env.example              META_API_KEY for `generate`
  scamcheck/
    policy.py               scam types, prompts, answer format (also used by the roleEdge app; keep them identical)
    generate.py             synthetic messages from Muse Spark, checked twice
    meta_api.py             small Meta API client with a disk cache and spend log
    build.py                merge, check, deduplicate, split -> data/final
    metrics.py              catch rate, false alarms, type and flag match
    model_card.py           the Hugging Face model card
    cli.py                  python -m scamcheck estimate | generate | build | report
  data/
    synthetic/              Muse Spark messages (spark_v0_sample.jsonl to start)
    cases/                  your cases (my_cases.csv; _template.csv has examples)
    real/                   real published messages, test only (real_messages.csv)
    final/                  made by `build`; uploaded to Modal with each run
  notebooks/data.ipynb      look at the data, the scores and the mistakes
  results/                  scores and loss curves from Modal runs (made when you evaluate)
  tests/                    python -m pytest tests -q
```

The roleEdge app has its own copy of [policy.py](scamcheck/policy.py) at `src/roleedge/scam/policy.py`. A test there
checks the two files are identical while this folder is in the repository. If you change the prompt here, copy the
file back.

## 11. Sources

- [Muse Glimmer 30B on Hugging Face](https://huggingface.co/meta-models/Muse-Glimmer-30B) (model card, config,
  chat template)
- [tbreak: Muse Glimmer open weights](https://tbreak.com/meta-muse-glimmer-open-weights-30b/)
- [mer.vin: Muse Glimmer 30B](https://mer.vin/news/muse-glimmer-30b-is-metas-first-open-weight-model-since-llama-4/)
- [ドーン「特殊詐欺 AI 判定サービス」](https://www.zaikei.co.jp/article/20260930/871695.html)
- [Whoscall: 2026 AI scam trends](https://prtimes.jp/main/html/rd/p/000000057.000058563.html)
- [Android AI scam defences](https://www.prsol.cc/2026/10/17/android-gets-ai-defenses-against-messaging-scams-fake-calls/)
- [NTT Security: ChatSpamDetector](https://jp.security.ntt/insights_resources/tech_blog/cpd-phishing-email-detection-with-generative-ai/)
- [LaCATODA 2026: Japanese phishing emails and LoRA](https://ceur-ws.org/Vol-4178/paper4.pdf)
- [Improving phishing email detection of small LLMs](https://arxiv.org/html/2505.00034v2)
