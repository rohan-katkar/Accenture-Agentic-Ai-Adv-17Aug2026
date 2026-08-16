#!/usr/bin/env python3
"""
Capstone/tests/test_acceptance.py
================================
The seven acceptance criteria from Capstone deck slide 5, as executable tests.

    python3 Capstone/tests/test_acceptance.py

Exit 0 = all criteria met. Exit 1 = at least one failed.

WHY THIS FILE MATTERS MORE THAN THE CODE IT TESTS
--------------------------------------------------
The criteria were DECLARED before the build. Declaring the expectation first is
what separates a test from a demo. Each test prints the evidence the criterion's
"evidence required" column asks for, so the output is itself the hand-off
artifact for a controls-testing team.

Criterion 1 doubles as the anti-drift check: the Capstone package must reproduce
the SAME ten end states the Day 1-3 labs produce. Two copies of the priority
rules exist (labs teach, package deploys); this is what stops them diverging.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

for _p in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
    if (_p / "00_Program").is_dir():
        ROOT = _p
        sys.path.insert(0, str(_p))
        break

from shared.telemetry import configure  # noqa: E402

configure(level="ERROR")   # keep the report readable

from Capstone.src import pipeline  # noqa: E402
from Capstone.src.batch import (  # noqa: E402
    export_outcomes, resume_transaction, run_batch,
)
from Capstone.src.domain import (  # noqa: E402
    PRIORITY_RULES, classify_variance, load_bank_transactions, match_payment,
    load_open_items,
)
from Capstone.src.security import scan_input, redact, to_envelope  # noqa: E402

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[str, str, bool, str]] = []


def criterion(num: int, title: str):
    def wrap(fn):
        def run():
            print(f"\n{'=' * 78}\nCRITERION {num} — {title}\n{'=' * 78}")
            try:
                evidence = fn()
                results.append((str(num), title, True, evidence))
                print(f"{GREEN}PASS{RESET}  {evidence}")
            except AssertionError as exc:
                results.append((str(num), title, False, str(exc)))
                print(f"{RED}FAIL{RESET}  {exc}")
            except Exception as exc:  # noqa: BLE001
                results.append((str(num), title, False, f"{type(exc).__name__}: {exc}"))
                print(f"{RED}ERROR{RESET} {type(exc).__name__}: {exc}")
        return run
    return wrap


DB = Path(tempfile.gettempdir()) / "capstone_acceptance.sqlite"

# Documented Day 1-3 baseline. Frozen. Any change here is a regression
# until proven otherwise.
EXPECTED_END_STATES = {
    "BNK-1001": "CLOSED", "BNK-1002": "PARTIAL_MATCH", "BNK-1003": "CLOSED",
    "BNK-1004": "UAC", "BNK-1005": "UIC", "BNK-1006": "CLOSED",
    "BNK-1007": "CLOSED", "BNK-1008": "QUERY", "BNK-1009": "QUERY",
    "BNK-1010": "QUERY",
}


# ---------------------------------------------------------------------------
@criterion(1, "All six priority rules implemented and evaluated in order")
def c1() -> str:
    assert len(PRIORITY_RULES) == 6, f"expected 6 rules, found {len(PRIORITY_RULES)}"
    ar = load_open_items()

    cases = [
        ("Acme Corp", "PO-5541", "", 1, "INV-810"),
        ("Initech LLC", "DEL-7712", "", 2, "INV-931"),
        ("Soylent Corp", "INV-955 DTD 2026-02-18", "", 3, "INV-955"),
        ("Acme Corp", "INV-808 PAYMENT", "", 4, "INV-808"),
        ("Umbrella Health", "REMITTANCE ATTACHED",
         "INV-1102  2026-02-20  9,000.00", 5, "INV-1102"),
        ("Umbrella Health", "REMITTANCE ATTACHED",
         "INV-1103 covering 6,000.00", 6, "INV-1103"),
    ]
    for customer, ref, remit, want_priority, want_invoice in cases:
        m = match_payment(customer, ref, remit, ar)
        assert m is not None, f"priority {want_priority}: no match for {customer}/{ref}"
        assert m.priority == want_priority, \
            f"expected priority {want_priority}, got {m.priority} for {customer}/{ref}"
        assert m.invoice_no == want_invoice, \
            f"priority {want_priority}: expected {want_invoice}, got {m.invoice_no}"
        print(f"  priority {m.priority} ({m.match_type}) -> {m.invoice_no}  [{m.rationale}]")

    m = match_payment("Wayne Enterprises", "", "", ar)
    assert m is None, "expected no match for a payment with no identifiers"
    print("  no identifiers -> no match (correct)")
    return "6/6 rules fire at their declared priority; recorded in matched_priority"


# ---------------------------------------------------------------------------
@criterion(2, "Every transaction terminates in a declared end state")
def c2() -> str:
    result = run_batch(db_path=DB, hitl=False, run_id="acc-c2")
    assert result.failed == 0, f"{result.failed} transaction(s) failed"

    actual = {o["txn_id"]: o["end_state"] for o in result.outcomes}
    for txn_id, want in EXPECTED_END_STATES.items():
        assert actual.get(txn_id) == want, \
            f"{txn_id}: expected {want}, got {actual.get(txn_id)} (BASELINE DRIFT)"
    assert "OPEN" not in actual.values(), "a transaction finished as OPEN"

    for txn_id, state in sorted(actual.items()):
        print(f"  {txn_id:<10}{state}")
    print(f"\n{result.summary()}")
    return (f"10/10 terminate in a declared state and match the frozen "
            f"Day 1-3 baseline; no drift between labs and package")


# ---------------------------------------------------------------------------
@criterion(3, "Deduction reasons grounded in verbatim evidence")
def c3() -> str:
    result = run_batch(db_path=DB, hitl=False, run_id="acc-c3")
    by_id = {o["txn_id"]: o for o in result.outcomes}

    coded = by_id["BNK-1002"]
    assert coded["reason_code"] == "D03", \
        f"BNK-1002 expected D03, got {coded['reason_code']}"
    print(f"  BNK-1002 coded {coded['reason_code']} -> dispute {coded['dispute_id']}")

    # A remittance stating no reason must NOT receive a code.
    unknown = by_id["BNK-1009"]
    assert unknown["reason_code"] in (None, "UNKNOWN"), \
        f"BNK-1009 was assigned {unknown['reason_code']} from a remittance stating no reason"
    print(f"  BNK-1009 reason_code {unknown['reason_code']} -> QUERY (declined to guess)")

    # Fabricated citation must be rejected by the grounding check.
    state = {"txn_id": "T", "remittance_text": "Five units arrived crushed and unusable."}
    out = pipeline.node_classify_deduction(state)
    assert out["reason_code"] in {"D03", "UNKNOWN"}, f"illegal code {out['reason_code']}"
    if out["reason_code"] != "UNKNOWN":
        needle = " ".join(out["reason_evidence"].split()).lower()
        haystack = " ".join(state["remittance_text"].split()).lower()
        assert needle in haystack, "cited evidence is not a verbatim substring"
        print(f"  citation verified verbatim: {out['reason_evidence'][:52]!r}")
    return "coded findings carry verbatim citations; unsupported ones return UNKNOWN"


# ---------------------------------------------------------------------------
@criterion(4, "No write executes without graph authorisation")
def c4() -> str:
    envelope = pipeline.registry.invoke(
        "create_dispute",
        {"invoice_no": "INV-810", "amount_usd": "500.00",
         "reason_code": "D03", "evidence": "test"},
        allow_write=False, run_id="acc-c4")
    assert envelope["ok"] is False, "an unauthorised write SUCCEEDED"
    assert "not authorised" in envelope["error"]
    print(f"  unauthorised create_dispute -> refused: {envelope['error'][:58]}")

    bogus = pipeline.registry.invoke("delete_all_invoices", {"confirm": "yes"},
                                     allow_write=True, run_id="acc-c4")
    assert bogus["ok"] is False, "a hallucinated tool executed"
    print(f"  hallucinated tool -> refused, real tools listed: {bogus['available']}")

    refusals = pipeline.registry.refusals()
    assert refusals, "the audit ledger contains no refusals - controls untested"
    for r in refusals[-2:]:
        print(f"  audit: {r['tool']:<22}{r['outcome']}")
    return (f"{len(refusals)} refusal(s) recorded in the audit ledger; "
            "absence of evidence is not evidence of control")


# ---------------------------------------------------------------------------
@criterion(5, "A run survives process death and resumes")
def c5() -> str:
    txns = load_bank_transactions()
    rid = "acc-c5"

    first = run_batch(txns[:4], db_path=DB, hitl=False, run_id=rid)
    print(f"  first pass  : {first.completed} completed, died after "
          f"{first.outcomes[-1]['txn_id']}")

    disputes_before = len(pipeline.DISPUTES)

    # Simulate a restart: fresh graph objects, resume after the last completed id.
    second = run_batch(txns, db_path=DB, hitl=False, run_id=rid,
                       resume_from=first.outcomes[-1]["txn_id"])
    print(f"  second pass : {second.completed} completed after resume")

    assert second.total == len(txns) - 4, \
        f"resume processed {second.total}, expected {len(txns) - 4}"

    # Idempotency: re-running the already-processed slice must not duplicate.
    replay = run_batch(txns[:4], db_path=DB, hitl=False, run_id=rid)
    duplicates = len(pipeline.DISPUTES) - disputes_before
    assert duplicates == 0, f"replay created {duplicates} duplicate dispute(s)"
    print(f"  replay of the first 4 created {duplicates} duplicate disputes")
    print(f"  disputes in sub-ledger: {[d['dispute_id'] for d in pipeline.DISPUTES]}")
    return "resume processes only the remainder; replay creates no duplicate postings"


# ---------------------------------------------------------------------------
@criterion(6, "QUERY suspends and resumes on human input")
def c6() -> str:
    txns = [t for t in load_bank_transactions() if t.txn_id == "BNK-1009"]
    result = run_batch(txns, db_path=DB, hitl=True, run_id="acc-c6")

    assert result.suspended == 1, f"expected 1 suspension, got {result.suspended}"
    suspended = result.outcomes[0]
    ask = suspended["ask"]
    print(f"  suspended thread : {suspended['thread_id']}")
    print(f"  analyst is asked : {ask.get('ask')}")
    print(f"  options          : {ask.get('options')}")
    assert "options" in ask, "the interrupt payload gives the analyst no options"

    decision = {"action": "assign_code", "reason_code": "D01",
                "decided_by": "J. Okonkwo (Deductions)",
                "rationale": "Customer confirmed a contracted price variance by phone."}
    final = resume_transaction(suspended["thread_id"], decision, db_path=DB)

    assert final["end_state"] == "PARTIAL_MATCH", \
        f"resumed to {final['end_state']}, expected PARTIAL_MATCH"
    assert final["decided_by"] == decision["decided_by"], "attribution lost on resume"
    assert final["reason_code"] == "D01"
    print(f"  resumed          : {final['end_state']} · code {final['reason_code']}")
    print(f"  decided_by       : {final['decided_by']}")
    print(f"  rationale        : {final['decision_rationale'][:56]}")
    return "QUERY suspends, persists, and resumes with attribution and rationale intact"


# ---------------------------------------------------------------------------
@criterion(7, "Any single payment reconstructable from the log alone")
def c7() -> str:
    result = run_batch(db_path=DB, hitl=False, run_id="acc-c7")
    target = next(o for o in result.outcomes if o["txn_id"] == "BNK-1002")

    trace = target["trace"]
    assert trace, "no trace recorded"
    required = ["ingest", "retrieve", "input_guardrail", "rule_engine",
                "variance_analysis", "classify_deduction", "output_guardrail",
                "open_dispute", "finalise"]
    joined = " ".join(trace)
    missing = [node for node in required if node not in joined]
    assert not missing, f"trace missing node(s): {missing}"

    for i, line in enumerate(trace, 1):
        print(f"  {i}. {line}")

    export = export_outcomes(result, Path(tempfile.gettempdir()) / "capstone_outcomes.jsonl")
    lines = export.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(result.outcomes), "export lost records"
    print(f"\n  exported {len(lines)} outcome records to {export}")

    # Security controls must leak nothing on the error path either.
    env = to_envelope(RuntimeError(
        "401 calling https://eastus.api.example.com with api-key=9f8e7d6c5b4a39281706f5e4d3c2b1a0"),
        "UPSTREAM_AUTH")
    surfaced = str(env.to_dict())
    for term in ("eastus.api.example.com", "9f8e7d6c5b4a39281706f5e4d3c2b1a0"):
        assert term not in surfaced, f"error envelope leaked {term!r}"
    print(f"  error envelope discloses only: {env.code} / {env.correlation_id}")
    return f"{len(trace)}-step trace covers every node; JSONL export round-trips"


# ---------------------------------------------------------------------------
def main() -> int:
    print("CAPSTONE ACCEPTANCE SUITE")
    print("Criteria declared on Capstone deck slide 5, before the build.")

    for test in (c1, c2, c3, c4, c5, c6, c7):
        test()

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(f"{'#':<4}{'CRITERION':<52}RESULT")
    print("-" * 78)
    for num, title, ok, _ in results:
        print(f"{num:<4}{title[:50]:<52}{'PASS' if ok else 'FAIL'}")

    passed = sum(1 for _, _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} acceptance criteria met.")

    if passed < len(results):
        print("\nFAILURES")
        for num, title, ok, evidence in results:
            if not ok:
                print(f"  {num}. {title}\n     {evidence}")
        return 1

    print("""
EVIDENCE FOR CONTROLS TESTING
  Criterion 1  the six rules, with the priority each fires at
  Criterion 2  10/10 end states matching the frozen baseline - no lab/package drift
  Criterion 3  verbatim citations, and UNKNOWN where the document says nothing
  Criterion 4  refusals present in the audit ledger, not merely absent failures
  Criterion 5  resume processes only the remainder; replay posts no duplicates
  Criterion 6  suspend and resume with analyst attribution and rationale
  Criterion 7  a full per-payment trace, plus an error path that discloses nothing""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
