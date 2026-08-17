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
PII_RULES = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\+?\d[\d\s().-]{8,}\d"), "[PHONE]"),
    (re.compile(r"\b\d{1,5}\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd)\b", re.I), "[ADDRESS]"),
]

def redact(text: str) -> tuple[str, int]:
    hits = 0
    for rx, token in PII_RULES:
        text, n = rx.subn(token, text)
        hits += n
    return text, hits


from agent_framework import agent_middleware, AgentContext

# C8 (runtime finding): with a custom BaseChatClient, @chat_middleware attached
# to Agent(middleware=...) is NOT invoked — use @agent_middleware, and the
# `next` continuation takes NO arguments (`await next()`, not `next(ctx)`).
MODEL_SAW: list[str] = []   # capture buffer: exactly what reached the model path

@agent_middleware
async def pii_redaction_middleware(ctx: AgentContext, next):
    """Mask PII in every outbound message before model invocation."""
    total = 0
    for msg in ctx.messages:
        for content in getattr(msg, "contents", []):
            if hasattr(content, "text") and content.text:
                content.text, n = redact(content.text)
                total += n
        MODEL_SAW.append(msg.text or "")
    if total:
        print(f"  [middleware] redacted {total} PII token(s) pre-model")
    await next()

# %% [markdown]
# ## Step 2 — RBAC on ERP posting

# %%
ROLE_GRANTS = {  # Azure mode: Entra ID app roles on the agent's managed identity
    "reconciliation.reader": {"search_invoice"},
    "erp.poster": {"search_invoice", "post_ledger_entry"},
}

class RBACError(PermissionError):
    pass

class GovernedERP:
    def __init__(self, store: D365Store, audit):
        self.store, self.audit = store, audit

    def call(self, principal: str, roles: set[str], op: str, **kw):
        allowed = set().union(*(ROLE_GRANTS.get(r, set()) for r in roles))
        if op not in allowed:
            self.audit.log(principal=principal, op=op, outcome="DENIED", detail=kw)
            raise RBACError(f"{principal} lacks permission for {op}")
        result = getattr(self.store, op if op != "search_invoice" else "find_invoice")(**kw)
        self.audit.log(principal=principal, op=op, outcome="ALLOWED", detail=kw)
        return result

# %% [markdown]
# ## Step 3 — Hash-chained (tamper-evident) audit log
# "Signed" here = integrity-sealed via a SHA-256 hash chain. For cryptographic
# non-repudiation in production, countersign each hash with Azure Key Vault
# (`CryptographyClient.sign`) — call included in the lab guide.

# %%
class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.write_text("")          # fresh chain per run
        self._prev = "GENESIS"

    def log(self, **fields):
        record = {"ts": datetime.now(timezone.utc).isoformat(),
                  "prev_hash": self._prev, **fields}
        payload = json.dumps(record, sort_keys=True)
        record["hash"] = hashlib.sha256(payload.encode()).hexdigest()
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        self._prev = record["hash"]

    @staticmethod
    def verify(path: Path) -> bool:
        prev = "GENESIS"
        for line in path.read_text().splitlines():
            rec = json.loads(line)
            h = rec.pop("hash")
            if rec["prev_hash"] != prev:
                return False
            if hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest() != h:
                return False
            prev = h
        return True

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
