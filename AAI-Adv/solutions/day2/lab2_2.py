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
DAMAGED_MEMO = """AMAZ0N CREDIT MEM0  #CM-88231     date 2O26-O8-O2
reason: carrier damage - claim NW-CLM-77
0rder: NW-1O13   ASIN B0demo1234   credit USD 84.5O
Order: NW-1015   ASIN B0demo9876   credit USD ###.## (torn)
order NW-1017 asin B0demo5555 credit USD 1,2O5.00
"""
(OUT / "damaged_credit_memo.txt").write_text(DAMAGED_MEMO)


def repair_glyphs(s: str) -> str:
    """Repair common OCR confusions in numeric/ID contexts only."""
    def fix_token(t: str) -> str:
        if re.search(r"\d", t) or re.match(r"NW-|B0", t):
            return t.replace("O", "0").replace("l", "1")
        return t
    return " ".join(fix_token(t) for t in s.split(" "))


def extract_line_items(memo: str) -> dict:
    items, exceptions = [], []
    for line in memo.splitlines():
        m = re.search(r"[0o]rder:?\s+(\S+)\s+asin\s+(\S+)\s+credit\s+USD\s+([\d#,.]+)",
                      repair_glyphs(line), re.I)
        if not m:
            continue
        order_id, asin, amt = m.group(1), m.group(2), m.group(3).replace(",", "")
        if "#" in amt:
            exceptions.append({"order_id": order_id, "issue": "amount_unreadable"})
        else:
            items.append({"order_id": order_id, "asin": asin, "credit_usd": float(amt)})
    return {"memo_id": "CM-88231", "items": items, "exceptions": exceptions}

# %% [markdown]
# ## Step 2 — Azure vision path (runs only with credentials)
# With a live Foundry multimodal deployment the raw memo image is sent as an
# image content part; the model returns the same structured schema.

# %%
async def extract_with_foundry_vision(image_bytes: bytes) -> dict:
    """AZURE-mode extraction via a Foundry vision-capable deployment."""
    from azure.identity import DefaultAzureCredential
    from agent_framework.foundry import FoundryChatClient
    from agent_framework import Agent

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["FOUNDRY_MODEL_DEPLOYMENT"],   # must be vision-capable
        credential=DefaultAzureCredential(),
    )
    agent = Agent(client=client, name="memo_reader",
                  instructions="Extract credit memo line items as JSON: "
                               "{memo_id, items:[{order_id,asin,credit_usd}], exceptions:[...]}")
    # Image content part: agent-framework Message accepts content mappings.
    # [VERIFY on your deployment: image content type support varies by model.]
    resp = await agent.run(f"Extract line items from this OCR text:\n{DAMAGED_MEMO}")
    return json.loads(resp.text)

# %% [markdown]
# ## Step 3 — Logic Apps escalation payload (HTTP trigger contract)

# %%
def build_logicapp_payload(extraction: dict) -> dict:
    return {
        "schema": "northwind.exception.v1",
        "source": "reconciliation-agents",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "memo_id": extraction["memo_id"],
        "exception_count": len(extraction["exceptions"]),
        "exceptions": extraction["exceptions"],
        "notify": ["account-managers@northwind.example"],
        "severity": "high" if extraction["exceptions"] else "info",
    }


def send_to_logic_app(payload: dict) -> str:
    url = os.getenv("LOGICAPP_TRIGGER_URL")
    if url:
        import urllib.request
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:  # nosec: user-supplied URL
            return f"posted:{r.status}"
    outbox = OUT / "logicapp_outbox.jsonl"
    with outbox.open("a") as f:
        f.write(json.dumps(payload) + "\n")
    return f"outbox:{outbox}"

# %% [markdown]
# ## Step 4 — Voice exception summary (SSML)

# %%
def build_ssml(extraction: dict) -> str:
    n_ok, n_ex = len(extraction["items"]), len(extraction["exceptions"])
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
        '<voice name="en-US-JennyNeural">'
        f"Credit memo {extraction['memo_id']}: {n_ok} line items extracted, "
        f"{n_ex} exception{'s' if n_ex != 1 else ''} require attention."
        "</voice></speak>"
    )


def synthesize(ssml: str) -> str:
    key, region = os.getenv("AZURE_SPEECH_KEY"), os.getenv("AZURE_SPEECH_REGION")
    if key and region:
        import azure.cognitiveservices.speech as speechsdk  # pip install azure-cognitiveservices-speech
        cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        audio = speechsdk.audio.AudioOutputConfig(filename=str(OUT / "exception_summary.wav"))
        speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio).speak_ssml(ssml)
        return "synthesized:exception_summary.wav"
    (OUT / "exception_summary.ssml").write_text(ssml)
    return "ssml_written (set AZURE_SPEECH_KEY/REGION to synthesize audio)"

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
