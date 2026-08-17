# %% [markdown]
# # Lab 2.4 — Observability, OpenTelemetry & CI/CD Pipelines
# Instrument the settlement pipeline with **OpenTelemetry spans**, compute the
# **dollar cost per settlement file** from token usage, and generate a working
# **GitHub Actions** workflow.
#
# [VERIFY note] agent-framework 1.14.0's `agent_framework.observability` module
# exposes ObservabilitySettings/telemetry layers but no `setup_observability()`
# helper; this lab therefore uses the stable public opentelemetry-sdk API,
# which works identically in offline and Azure modes (swap the exporter for
# azure-monitor-opentelemetry to land traces in Application Insights).

# %%
import asyncio, csv, json, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from common.model import Agent, make_chat_client, MODE
from common.d365_store import D365Store

OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)
print(f"Mode: {MODE}")

# %% [markdown]
# ## Step 1 — Tracer with an in-memory exporter (assertable in tests)
# Production swap: `AzureMonitorTraceExporter` -> Application Insights.

# %%
# ------------------------------------------------------------------
# TODO — implement Step 1: Tracer with an in-memory exporter (assertable in tests)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Tracer with an in-memory exporter (assertable in tests)")

# %% [markdown]
# ## Step 2 — Token cost model
# Prices are ILLUSTRATIVE constants for the cost-math exercise — real Azure
# OpenAI pricing varies by deployment/region; verify on the Azure pricing page
# before quoting numbers to a client.

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: Token cost model
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: Token cost model")

# %% [markdown]
# ## Step 3 — Traced pipeline over one settlement file

# %%
# ------------------------------------------------------------------
# TODO — implement Step 3: Traced pipeline over one settlement file
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 3: Traced pipeline over one settlement file")

# %% [markdown]
# ## Step 4 — GitHub Actions workflow (packaging + tests)

# %%
# ------------------------------------------------------------------
# TODO — implement Step 4: GitHub Actions workflow (packaging + tests)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 4: GitHub Actions workflow (packaging + tests)")

# %%
async def main():
    totals = await process_file("settlement_2026_08_batch1.csv")
    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    file_span = next(s for s in spans if s.name == "settlement.file")
    llm_spans = [s for s in spans if s.name == "llm.classify"]

    dur_ms = (file_span.end_time - file_span.start_time) / 1e6
    step_ms = [(s.end_time - s.start_time) / 1e6 for s in llm_spans]
    print(f"Spans captured: {len(spans)} ({sorted(names)})")
    print(f"File span: {dur_ms:.1f} ms total; per-step max {max(step_ms):.1f} ms")
    print(f"Tokens: in={totals['input_tokens']} out={totals['output_tokens']} "
          f"-> cost ${totals['cost_usd']:.6f} per file "
          f"(${totals['cost_usd']/totals['records']:.6f}/record, illustrative prices)")

    # C7: agent-framework auto-emits its own spans ("invoke_agent <name>") on
    # the global tracer provider — built-in instrumentation, free of charge.
    assert {"settlement.file", "settlement.record", "llm.classify"} <= names
    assert any(n.startswith("invoke_agent") for n in names), "framework spans expected"
    assert len(llm_spans) == 10 and all(m < 1000 for m in step_ms), "sub-second steps"
    assert totals["cost_usd"] > 0
    import yaml  # validate workflow parses
    parsed = yaml.safe_load(WORKFLOW)
    assert "test" in parsed["jobs"] and "package" in parsed["jobs"]
    print(f"Workflow written: {wf_dir/'deploy.yml'} (YAML valid)")
    print("LAB 2.4 PASS")

if __name__ == "__main__":
    asyncio.run(main())
