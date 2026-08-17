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
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("northwind.reconciliation")

# %% [markdown]
# ## Step 2 — Token cost model
# Prices are ILLUSTRATIVE constants for the cost-math exercise — real Azure
# OpenAI pricing varies by deployment/region; verify on the Azure pricing page
# before quoting numbers to a client.

# %%
PRICE_PER_1K = {"input": 0.00015, "output": 0.0006}  # APPROXIMATE, illustrative

def usage_cost(input_tokens: int, output_tokens: int) -> float:
    return round(input_tokens / 1000 * PRICE_PER_1K["input"]
                 + output_tokens / 1000 * PRICE_PER_1K["output"], 6)

# %% [markdown]
# ## Step 3 — Traced pipeline over one settlement file

# %%
async def process_file(filename: str) -> dict:
    store = D365Store()
    agent = Agent(client=make_chat_client(), name="matcher",
                  instructions="Classify each record: reply JSON verdict for the variance.")
    totals = {"input_tokens": 0, "output_tokens": 0, "records": 0}

    with tracer.start_as_current_span("settlement.file", attributes={"file": filename}):
        rows = list(csv.DictReader((ROOT / "data" / "settlements" / filename).open()))
        for row in rows[:10]:
            with tracer.start_as_current_span("settlement.record",
                                              attributes={"order_id": row["order_id"]}) as span:
                inv = store.find_invoice(row["order_id"])
                variance = round((inv["amount"] if inv else 0) - float(row["net_amount"].strip("()")), 2)
                with tracer.start_as_current_span("llm.classify") as llm_span:
                    resp = await agent.run(f"variance={variance} for {row['order_id']}")
                    u = resp.usage_details or {}
                    itok = int(u.get("input_token_count", 0) or 0)
                    otok = int(u.get("output_token_count", 0) or 0)
                    llm_span.set_attribute("llm.input_tokens", itok)
                    llm_span.set_attribute("llm.output_tokens", otok)
                    llm_span.set_attribute("llm.cost_usd", usage_cost(itok, otok))
                totals["input_tokens"] += itok
                totals["output_tokens"] += otok
                totals["records"] += 1
                span.set_attribute("variance_usd", variance)

    totals["cost_usd"] = usage_cost(totals["input_tokens"], totals["output_tokens"])
    return totals

# %% [markdown]
# ## Step 4 — GitHub Actions workflow (packaging + tests)

# %%
WORKFLOW = """name: agents-ci
on:
  push: { branches: [main] }
  workflow_dispatch: {}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install dependencies
        run: |
          python -m pip install -r requirements.txt
      - name: Generate seed data
        run: python common/data_gen.py
      - name: Run acceptance tests (offline mode)
        run: python -m pytest tests/ -q

  package:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build agent container
        run: docker build -t northwind-agents:${{ github.sha }} .
      # Deployment to Azure Container Apps requires OIDC federation:
      # azure/login@v2 with AZURE_CLIENT_ID/TENANT_ID/SUBSCRIPTION_ID secrets.
"""
wf_dir = ROOT / ".github" / "workflows"
wf_dir.mkdir(parents=True, exist_ok=True)
(wf_dir / "deploy.yml").write_text(WORKFLOW)

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
