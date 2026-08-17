# %% [markdown]
# # Lab 2.2 — Multimodal Exception Handling & Logic Apps Integration
# Three exception-handling channels for a damaged Amazon PDF credit memo:
#   1. **Multimodal extraction** — a scanned/damaged memo is parsed into
#      structured line items. OFFLINE: a deterministic OCR-noise parser proves
#      the repair pipeline; AZURE: the same image bytes go to a Foundry vision
#      deployment (code path included, gated on credentials).
#   2. **Logic Apps notification** — the escalation payload is POSTed to a
#      Logic Apps HTTP-trigger URL. OFFLINE: payload is written to an outbox
#      file with the exact JSON the connector would receive.
#   3. **Speech summary** — an SSML exception summary is generated; AZURE mode
#      synthesizes it with azure-cognitiveservices-speech (code path included).

# %%
import asyncio, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))
from common.model import MODE, foundry_configured

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
print(f"Mode: {MODE}")

# %% [markdown]
# ## Step 1 — The damaged credit memo
# A realistic OCR dump: smudged glyphs (O->0, l->1), a torn amount, and one
# clean line. The extractor must repair what it can and *flag* what it cannot.

# %%
# ------------------------------------------------------------------
# TODO — implement Step 1: The damaged credit memo
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: The damaged credit memo")

# %% [markdown]
# ## Step 2 — Azure vision path (runs only with credentials)
# With a live Foundry multimodal deployment the raw memo image is sent as an
# image content part; the model returns the same structured schema.

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: Azure vision path (runs only with credentials)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: Azure vision path (runs only with credentials)")

# %% [markdown]
# ## Step 3 — Logic Apps escalation payload (HTTP trigger contract)

# %%
# ------------------------------------------------------------------
# TODO — implement Step 3: Logic Apps escalation payload (HTTP trigger contract)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 3: Logic Apps escalation payload (HTTP trigger contract)")

# %% [markdown]
# ## Step 4 — Voice exception summary (SSML)

# %%
# ------------------------------------------------------------------
# TODO — implement Step 4: Voice exception summary (SSML)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 4: Voice exception summary (SSML)")

# %%
async def main():
    extraction = (await extract_with_foundry_vision(b"")) if foundry_configured() \
        else extract_line_items(DAMAGED_MEMO)
    print("Extraction:", json.dumps(extraction, indent=2))
    assert len(extraction["items"]) == 2, "two readable lines must extract"
    assert extraction["items"][1]["credit_usd"] == 1205.00, "glyph repair: 1,2O5.00 -> 1205.00"
    assert extraction["exceptions"] == [{"order_id": "NW-1015", "issue": "amount_unreadable"}]

    payload = build_logicapp_payload(extraction)
    print("Logic App:", send_to_logic_app(payload))
    assert payload["severity"] == "high"

    ssml = build_ssml(extraction)
    print("Speech:", synthesize(ssml))
    assert "1 exception" in ssml
    print("LAB 2.2 PASS")

if __name__ == "__main__":
    asyncio.run(main())
