#!/usr/bin/env python3
"""
00_Program/verify_environment.py
================================
Run this on the DELIVERY MACHINE the morning of the session, and again on each
learner machine before Lab 1.

    python 00_Program/verify_environment.py

Exit codes:  0 = ready   1 = blocking failure   2 = ready with warnings

It checks four things in order of how badly each one ruins a day:
    1. Python version and required imports          (blocking)
    2. Seed data present and internally consistent  (blocking)
    3. Path A / Path B / offline connectivity       (warning - offline still works)
    4. Version-sensitive surfaces                   (warning - see the register)
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = "  OK  ", " WARN ", " FAIL "
blocking: list[str] = []
warnings: list[str] = []


def line(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label:<44} {detail}")


def section(name: str) -> None:
    print(f"\n{name}\n{'-' * 78}")


# ---------------------------------------------------------------------------
section("1. INTERPRETER AND PACKAGES")
# ---------------------------------------------------------------------------
major, minor = sys.version_info[:2]
if (major, minor) >= (3, 11):
    line(OK, "Python version", f"{major}.{minor}")
else:
    line(FAIL, "Python version", f"{major}.{minor} - need 3.11 or newer")
    blocking.append("Python < 3.11")

REQUIRED = ["langgraph", "openai", "pydantic", "chromadb", "pandas", "streamlit"]
OPTIONAL = {
    "azure.ai.projects": "Path B only - labs fall back to Path A",
    "azure.identity": "Path B only",
    "langgraph.checkpoint.sqlite": "REQUIRED BY THE CAPSTONE (human-in-the-loop)",
    "pypdf": "Day 2 stretch goal - PDF remittance parsing",
    "dotenv": "convenience only - config.py has a fallback parser",
}

for name in REQUIRED:
    try:
        mod = importlib.import_module(name)
        line(OK, name, getattr(mod, "__version__", ""))
    except Exception as exc:  # noqa: BLE001
        line(FAIL, name, f"{type(exc).__name__}: {exc}")
        blocking.append(f"missing package: {name}")

for name, why in OPTIONAL.items():
    try:
        importlib.import_module(name)
        line(OK, name, why)
    except Exception:  # noqa: BLE001
        line(WARN, name, f"absent - {why}")
        warnings.append(f"optional package absent: {name}")

# ---------------------------------------------------------------------------
section("2. SEED DATA")
# ---------------------------------------------------------------------------
SEED = ROOT / "shared" / "seed_data"
expected_files = {
    "bank_statement.csv": 10,
    "erp_ar_open.csv": 9,
    "deduction_codes.csv": 5,
}
for filename, expected_rows in expected_files.items():
    path = SEED / filename
    if not path.exists():
        line(FAIL, filename, "missing")
        blocking.append(f"missing seed file: {filename}")
        continue
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) == expected_rows:
        line(OK, filename, f"{len(rows)} rows")
    else:
        line(WARN, filename, f"{len(rows)} rows, expected {expected_rows}")
        warnings.append(f"{filename} row count changed")

remit = SEED / "remittance"
advices = sorted(remit.glob("*.txt")) if remit.is_dir() else []
line(OK if len(advices) == 5 else WARN, "remittance/*.txt",
     f"{len(advices)} documents")

# --- referential integrity: every remittance must name a real transaction ---
if (SEED / "bank_statement.csv").exists():
    with open(SEED / "bank_statement.csv", newline="", encoding="utf-8") as fh:
        txn_ids = {r["txn_id"] for r in csv.DictReader(fh)}
    orphans = [p.name for p in advices if p.name.split("_")[0] not in txn_ids]
    if orphans:
        line(FAIL, "remittance -> bank_statement links", f"orphans: {orphans}")
        blocking.append("remittance documents reference unknown transactions")
    else:
        line(OK, "remittance -> bank_statement links", "all resolve")

# --- the known-answer check: the Day 1 baseline must reproduce exactly -------
try:
    sys.path.insert(0, str(ROOT / "Day1_Foundations" / "solutions"))
    import lab05_compile_langgraph as engine  # noqa: E402

    with open(SEED / "bank_statement.csv", newline="", encoding="utf-8") as fh:
        bank_rows = list(csv.DictReader(fh))
    outcomes = {}
    for row in bank_rows:
        result = engine.graph.invoke(engine.initial_state(row))
        outcomes[result["txn_id"]] = result["end_state"]

    EXPECTED = {
        "BNK-1001": "CLOSED", "BNK-1002": "PARTIAL_MATCH", "BNK-1003": "CLOSED",
        "BNK-1004": "UAC", "BNK-1005": "UIC", "BNK-1006": "CLOSED",
        "BNK-1007": "CLOSED", "BNK-1008": "UAC", "BNK-1009": "PARTIAL_MATCH",
        "BNK-1010": "QUERY",
    }
    drift = {k: (v, outcomes.get(k)) for k, v in EXPECTED.items() if outcomes.get(k) != v}
    if drift:
        line(FAIL, "Day 1 known-answer baseline", f"drift: {drift}")
        blocking.append("Day 1 graph no longer reproduces the documented baseline")
    else:
        closed = sum(1 for v in outcomes.values() if v == "CLOSED")
        line(OK, "Day 1 known-answer baseline",
             f"10/10 states match; straight-through {closed}/10 = {closed * 10}%")
except Exception as exc:  # noqa: BLE001
    line(WARN, "Day 1 known-answer baseline", f"could not run: {type(exc).__name__}: {exc}")
    warnings.append("could not execute the Day 1 baseline check")

# ---------------------------------------------------------------------------
section("3. MODEL CONNECTIVITY")
# ---------------------------------------------------------------------------
try:
    from shared.config import settings
    from shared.foundry_client import get_chat_client

    line(OK, "config loaded", f"offline_mode={settings.offline_mode}")
    line(OK if settings.path_a_ready else WARN, "Path A (Azure OpenAI)",
         "endpoint + key present" if settings.path_a_ready else "not configured")
    line(OK if settings.path_b_ready else WARN, "Path B (Foundry project SDK)",
         "enabled" if settings.path_b_ready else "disabled (this is the safe default)")

    client = get_chat_client()
    line(OK, "chat client resolved", client.backend_name)

    if client.backend_name == "offline-stub":
        line(WARN, "live model call", "skipped - running on the offline stub")
        warnings.append("no live model: labs run, but Day 2 retrieval quality "
                        "claims CANNOT be demonstrated")
    else:
        reply = client.complete("Reply with exactly: ACK", "ping", max_tokens=5)
        if "ACK" in reply.upper():
            line(OK, "live model call", f"round-trip succeeded ({client.backend_name})")
        else:
            line(WARN, "live model call", f"unexpected reply: {reply[:60]!r}")
            warnings.append("model replied unexpectedly - check the deployment name")

    from shared.foundry_client import get_embedder

    emb = get_embedder()
    vec = emb(["damaged goods withheld"])[0]
    backend = getattr(emb, "backend_name", "?")
    line(OK, "embedder resolved", f"{backend}, dim={len(vec)}")
    if backend.startswith("offline"):
        warnings.append("offline embedder in use - LEXICAL not semantic similarity; "
                        "do not present Day 2 retrieval quality from this backend")
except Exception as exc:  # noqa: BLE001
    line(FAIL, "model layer", f"{type(exc).__name__}: {exc}")
    blocking.append("shared.foundry_client failed to initialise")

# ---------------------------------------------------------------------------
section("4. VERSION-SENSITIVE SURFACES")
# ---------------------------------------------------------------------------
print("These are not failures. They are things to RE-VERIFY before delivery.")
print("Full detail: 00_Program/VERSION_RISK_REGISTER.md\n")

try:
    from importlib.metadata import version

    for pkg, note in [
        ("azure-ai-projects", "client accessor shape has changed across releases"),
        ("langgraph", "interrupt / Command API is post-0.2; check before the Capstone"),
        ("chromadb", "client construction and embedding-function API changed at 0.5/1.0"),
        ("openai", "AzureOpenAI is stable; api_version string still pins behaviour"),
    ]:
        try:
            line(WARN, f"{pkg} {version(pkg)}", note)
        except Exception:  # noqa: BLE001
            line(WARN, f"{pkg} (not installed)", note)
except Exception:  # noqa: BLE001
    pass

# --- does LangGraph expose the interrupt API the Capstone needs? -------------
try:
    from langgraph.types import interrupt  # noqa: F401

    line(OK, "langgraph.types.interrupt", "available - Capstone HITL is viable")
except Exception:  # noqa: BLE001
    line(WARN, "langgraph.types.interrupt", "NOT available on this version - "
                                            "Capstone human-in-the-loop needs a rework")
    warnings.append("langgraph interrupt API unavailable")

# ---------------------------------------------------------------------------
section("VERDICT")
# ---------------------------------------------------------------------------
if blocking:
    print("NOT READY. Blocking issues:")
    for item in blocking:
        print(f"  - {item}")
    print("\nFix these before the session. Start with: "
          "pip install -r 00_Program/requirements.txt")
    sys.exit(1)

if warnings:
    print("READY, with warnings you should know about before you walk in:")
    for item in warnings:
        print(f"  - {item}")
    print("\nEvery lab will run. Read each warning and decide whether it changes "
          "what you claim in the room.")
    sys.exit(2)

print("READY. All checks passed.")
sys.exit(0)
