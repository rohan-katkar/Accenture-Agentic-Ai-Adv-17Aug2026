#!/usr/bin/env python3
"""
Capstone/src/cli.py
===================
Command-line entrypoint for the reconciliation system.

    python3 -m Capstone.src.cli run                      # process the batch
    python3 -m Capstone.src.cli run --no-hitl            # terminate QUERY instead of suspending
    python3 -m Capstone.src.cli run --resume-from BNK-1004
    python3 -m Capstone.src.cli pending                  # list suspended threads
    python3 -m Capstone.src.cli resume <thread_id> --action assign_code \
        --reason-code D01 --by "J. Okonkwo" --rationale "confirmed by phone"
    python3 -m Capstone.src.cli accept                   # run the acceptance suite
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _p in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.telemetry import configure  # noqa: E402

DEFAULT_DB = "capstone_state.sqlite"
STATE_FILE = Path("capstone_last_run.json")


def cmd_run(args: argparse.Namespace) -> int:
    from Capstone.src.batch import export_outcomes, run_batch

    result = run_batch(db_path=args.db, hitl=not args.no_hitl,
                       resume_from=args.resume_from)

    print(f"\n{'TXN':<12}{'END STATE':<24}{'CODE':<9}{'OWNER':<26}THREAD")
    print("-" * 110)
    for o in result.outcomes:
        print(f"{o['txn_id']:<12}{o['end_state']:<24}"
              f"{str(o.get('reason_code') or '-'):<9}{str(o.get('owner') or '-'):<26}"
              f"{o.get('thread_id', '-')}")

    print(f"\n{result.summary()}")

    if result.suspended:
        print(f"\n{result.suspended} transaction(s) awaiting a human decision. "
              f"List them with:  python3 -m Capstone.src.cli pending")

    STATE_FILE.write_text(json.dumps(
        {"run_id": result.run_id,
         "threads": [o["thread_id"] for o in result.outcomes if "thread_id" in o],
         "suspended": [o["thread_id"] for o in result.outcomes
                       if o["end_state"] == "AWAITING_HUMAN"]},
        indent=2), encoding="utf-8")

    if args.export:
        path = export_outcomes(result, args.export)
        print(f"\nOutcomes exported to {path}")
    return 1 if result.failed else 0


def cmd_pending(args: argparse.Namespace) -> int:
    from Capstone.src.batch import pending

    if not STATE_FILE.exists():
        print("No previous run recorded. Run the batch first.")
        return 1
    threads = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("suspended", [])
    if not threads:
        print("No suspended transactions.")
        return 0

    for item in pending(args.db, threads):
        state = item["state"]
        print(f"\nthread   : {item['thread_id']}")
        print(f"waiting  : {', '.join(item['waiting_on'])}")
        print(f"txn      : {state.get('txn_id')}  variance {state.get('variance_usd')}")
        print(f"invoice  : {state.get('matched_invoice')}")
        print(f"evidence : {(state.get('reason_evidence') or '(none on file)')[:70]}")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    from Capstone.src.batch import resume_transaction

    if args.action == "assign_code" and not args.reason_code:
        print("--reason-code is required when --action assign_code")
        return 1

    decision = {"action": args.action, "decided_by": args.by,
                "rationale": args.rationale}
    if args.reason_code:
        decision["reason_code"] = args.reason_code

    final = resume_transaction(args.thread_id, decision, db_path=args.db)
    print(f"{final.get('txn_id')} → {final.get('end_state')}")
    print(f"  decided_by : {final.get('decided_by')}")
    print(f"  rationale  : {final.get('decision_rationale')}")
    for i, line in enumerate(final.get("trace", []), 1):
        print(f"  {i}. {line}")
    return 0


def cmd_accept(args: argparse.Namespace) -> int:  # noqa: ARG001
    import subprocess

    root = next(p for p in Path(__file__).resolve().parents if (p / "00_Program").is_dir())
    return subprocess.call([sys.executable, str(root / "Capstone" / "tests" / "test_acceptance.py")])


def main() -> int:
    ap = argparse.ArgumentParser(prog="capstone",
                                 description="Automated Payment & Reconciliation System")
    ap.add_argument("--db", default=DEFAULT_DB, help="checkpoint database path")
    ap.add_argument("--log-level", default="WARNING")
    sub = ap.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="process the payment batch")
    p_run.add_argument("--no-hitl", action="store_true",
                       help="terminate QUERY instead of suspending for a human")
    p_run.add_argument("--resume-from", help="skip up to and including this txn_id")
    p_run.add_argument("--export", help="write outcomes as JSON Lines to this path")
    p_run.set_defaults(func=cmd_run)

    p_pending = sub.add_parser("pending", help="list suspended transactions")
    p_pending.set_defaults(func=cmd_pending)

    p_resume = sub.add_parser("resume", help="resume one suspended transaction")
    p_resume.add_argument("thread_id")
    p_resume.add_argument("--action", required=True,
                          choices=["assign_code", "reject_deduction", "escalate"])
    p_resume.add_argument("--reason-code", choices=["D01", "D02", "D03", "D04", "D05"])
    p_resume.add_argument("--by", required=True, help="analyst name - attribution is not optional")
    p_resume.add_argument("--rationale", default="", help="why this decision was made")
    p_resume.set_defaults(func=cmd_resume)

    p_accept = sub.add_parser("accept", help="run the seven acceptance criteria")
    p_accept.set_defaults(func=cmd_accept)

    args = ap.parse_args()
    configure(level=args.log_level)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
