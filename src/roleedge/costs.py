"""Turn measured token usage into dollars per content item and per check-in call.

Prices are list prices in USD per 1M tokens (input, cached input, output), checked 2026-10-28;
sources are in docs/FINDINGS.md. Usage was measured on Azure gpt-5-mini, so the Meta columns
are projections (other models tokenize differently).
"""

from __future__ import annotations

import json
from pathlib import Path

from .checkin import CHECKIN_DIR, CallRecord
from .config import LEDGER_FILE, OUTPUT_DIR
from .content import CONTENT_DIR, load
from .llm import Usage

PRICES_PER_1M = {
    "azure gpt-5-mini (measured)": (0.25, 0.025, 2.00),
    "meta muse-spark-1.3 (projection)": (1.25, 0.15, 4.25),
    "meta muse-spark-1.3-contributor (projection; Meta trains on data)": (0.10, 0.002, 0.20),
}
MEASURED = "azure gpt-5-mini (measured)"


def dollars(usage: Usage, price: tuple[float, float, float]) -> float:
    per_input, per_cached, per_output = price
    fresh_input = usage.input - usage.cached
    return (fresh_input * per_input + usage.cached * per_cached + usage.output * per_output) / 1e6


def priced(usage: Usage) -> dict[str, float]:
    return {name: round(dollars(usage, price), 5) for name, price in PRICES_PER_1M.items()}


def content_costs(content_dir: Path = CONTENT_DIR) -> dict[str, dict]:
    out = {}
    for case_dir in sorted(d for d in content_dir.iterdir() if (d / "digest.json").exists()):
        record = load(case_dir.name, content_dir)
        usage = Usage.from_dict(record.usage) + Usage.from_dict(record.verify_usage)
        out[record.case] = {"usage": usage.to_dict(), "latency_s": round(record.latency_s + record.verify_latency_s, 1),
                            **priced(usage)}
    return out


def call_costs(checkin_dir: Path = CHECKIN_DIR) -> dict[str, dict]:
    """Agent turns + report only; the simulated parent is test scaffolding, not a product cost."""
    out = {}
    for path in sorted(checkin_dir.glob("*.json")):
        record = CallRecord.model_validate_json(path.read_text(encoding="utf-8"))
        turns = record.metrics["agent_turns"] + [record.metrics["report"]]
        usage = sum((Usage.from_dict(t) for t in turns), Usage())
        out[record.scenario] = {"usage": usage.to_dict(), "agent_llm_calls": len(record.metrics["agent_turns"]),
                                "lines": len(record.transcript), **priced(usage)}
    return out


def build_report(output_file: Path = OUTPUT_DIR / "costs.json") -> dict:
    items, calls = content_costs(), call_costs()
    report = {
        "content_items": items,
        "checkin_calls_text_logic": calls,
        "avg_llm_cost_per_content_item_usd": round(sum(v[MEASURED] for v in items.values()) / max(1, len(items)), 5),
        "avg_llm_cost_per_checkin_logic_usd": round(sum(v[MEASURED] for v in calls.values()) / max(1, len(calls)), 5),
    }
    output_file.write_text(json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------- spend meter (what the ledger says we used)
META_BUDGET_USD = 100.0  # hackathon credits; they expire, so the meter shows what is left
PRICE_BY_MODEL: dict[str, tuple[float, float, float]] = {  # USD per 1M tokens: input, cached input, output
    "gpt5mini": (0.25, 0.025, 2.00),
    "muse-spark-1.3": (1.25, 0.15, 4.25),
    "muse-wonder-1.0": (4.0, 0.20, 20.0),  # preview pricing (FINDINGS.md section 6)
    "muse-spark-1.3-contributor": (0.10, 0.002, 0.20),
    "muse-spark-1.2": (1.25, 0.15, 4.25),
    "muse-spark-1.2-contributor": (0.10, 0.002, 0.20),
}
UNKNOWN_PRICE = (1.25, 0.15, 4.25)  # price an unknown model like full Spark, so the meter never under-counts


def spend(ledger_file: Path = LEDGER_FILE) -> dict:
    """Estimated spend from the usage ledger (calls replayed from the cache cost nothing). Meta has no balance API,
    so this is an estimate from token counts; the Meta dashboard has the real figure."""
    totals: dict[str, float] = {"meta": 0.0, "azure": 0.0}
    calls = {"meta": 0, "azure": 0}
    by_task: dict[str, float] = {}
    app_meta = 0.0  # without the evaluation lab's calls (rows marked "source": "lab"): what the demo's own guard counts
    if ledger_file.exists():
        for line in ledger_file.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("replayed_from_cache"):
                continue
            usage = Usage.from_dict(row)
            usd = dollars(usage, PRICE_BY_MODEL.get(row.get("model", ""), UNKNOWN_PRICE))
            provider = row.get("provider", "")
            totals[provider] = totals.get(provider, 0.0) + usd
            calls[provider] = calls.get(provider, 0) + 1
            if provider == "meta":
                task = row.get("task", "").split("/")[0]
                by_task[task] = by_task.get(task, 0.0) + usd
                if row.get("source") != "lab":
                    app_meta += usd
    return {"meta_usd": round(totals["meta"], 4), "meta_app_usd": round(app_meta, 4), "meta_calls": calls["meta"],
            "meta_left_usd": round(META_BUDGET_USD - totals["meta"], 2), "meta_budget_usd": META_BUDGET_USD,
            "azure_usd": round(totals["azure"], 4), "meta_by_task": {k: round(v, 4) for k, v in sorted(by_task.items())},
            "note": "Estimate from token counts. Web search and media calls may cost extra; check the Meta dashboard."}
