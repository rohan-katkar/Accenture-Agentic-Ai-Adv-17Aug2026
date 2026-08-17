# %% [markdown]
# # Lab 3.2 — Governance, Responsible AI & PII Masking
# Three governance controls, all enforced in code and verified by assertions:
#   1. **PII redaction** — buyer emails/phones/addresses masked BEFORE any text
#      reaches a model (chat-middleware layer, so it is impossible to bypass by
#      writing a different prompt).
#   2. **RBAC** — agent identities carry roles; only `erp.poster` may call
#      `post_ledger_entry`. Azure mode maps these to Entra ID app roles
#      (setup steps in the lab guide).
#   3. **Immutable audit log** — hash-chained JSONL: each record embeds the
#      SHA-256 of the previous record, so any tamper breaks the chain.

# %%
import asyncio, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import Agent, make_chat_client, MODE
from common.d365_store import D365Store
print(f"Mode: {MODE}")
OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)

# %% [markdown]
# ## Step 1 — PII redaction as chat middleware
# agent-framework middleware runs inside the client pipeline: every outbound
# message is rewritten before the model sees it.

# %%
from agent_framework import agent_middleware, AgentContext

# ------------------------------------------------------------------
# TODO — implement Step 1: PII redaction as chat middleware
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: PII redaction as chat middleware")

# %% [markdown]
# ## Step 2 — RBAC on ERP posting

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: RBAC on ERP posting
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: RBAC on ERP posting")

# %% [markdown]
# ## Step 3 — Hash-chained (tamper-evident) audit log
# "Signed" here = integrity-sealed via a SHA-256 hash chain. For cryptographic
# non-repudiation in production, countersign each hash with Azure Key Vault
# (`CryptographyClient.sign`) — call included in the lab guide.

# %%
# ------------------------------------------------------------------
# TODO — implement Step 3: Hash-chained (tamper-evident) audit log
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 3: Hash-chained (tamper-evident) audit log")

# %%
async def main():
    # --- PII middleware in the model path -------------------------------
    agent = Agent(client=make_chat_client(), name="masked_agent",
                  middleware=pii_redaction_middleware,
                  instructions="Summarize the buyer report.")
    dirty = ("Buyer Jane Roe (jane.roe@example.com, +1 415 555 0142, "
             "17 Elm Street) disputes FBA fee on NW-1017. Please redact and summarize.")
    resp = await agent.run(dirty)
    model_input = " ".join(MODEL_SAW)
    print("Model saw:", model_input[:120])
    # Assert on the CAPTURED model input, not the reply text — mode-independent.
    assert "jane.roe@example.com" not in model_input and "415 555" not in model_input
    assert "[EMAIL]" in model_input and "[PHONE]" in model_input and "[ADDRESS]" in model_input

    # --- RBAC ------------------------------------------------------------
    audit = AuditLog(OUT / "audit_chain.jsonl")
    erp = GovernedERP(D365Store(), audit)
    inv = erp.call("agent:smart_match", {"reconciliation.reader"},
                   "search_invoice", order_id="NW-1017")
    assert inv["amount"] == 1141.95
    try:
        erp.call("agent:smart_match", {"reconciliation.reader"},
                 "post_ledger_entry", order_id="NW-1017", amount=1141.95)
        raise AssertionError("reader must NOT post")
    except RBACError as e:
        print("RBAC denied as designed:", e)
    posted = erp.call("agent:erp_poster", {"erp.poster"},
                      "post_ledger_entry", order_id="NW-1017", amount=1141.95,
                      memo="human-approved variance")
    assert posted["status"] == "posted"

    # --- audit chain integrity + tamper detection ------------------------
    assert AuditLog.verify(OUT / "audit_chain.jsonl"), "chain must verify clean"
    lines = (OUT / "audit_chain.jsonl").read_text().splitlines()
    tampered = json.loads(lines[1]); tampered["outcome"] = "ALLOWED"
    (OUT / "audit_tampered.jsonl").write_text(
        "\n".join([lines[0], json.dumps(tampered)] + lines[2:]) + "\n")
    assert not AuditLog.verify(OUT / "audit_tampered.jsonl"), "tamper must break chain"
    print(f"Audit chain verified ({len(lines)} records); tampering detected correctly")
    print("LAB 3.2 PASS")

if __name__ == "__main__":
    asyncio.run(main())
