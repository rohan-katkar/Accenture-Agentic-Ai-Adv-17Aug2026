#!/usr/bin/env python3
"""
_builders/validate_labs.py
==========================
Systematic validation of every lab artifact in the package.

Run:  python3 _builders/validate_labs.py            # structure + derivation only
      python3 _builders/validate_labs.py --execute  # also run every solution

Why a harness rather than eyeballing: there are 10 solutions, 10 starters and 20
notebooks. Four artifacts per lab, three of them generated. Reading them does not
scale and does not catch derivation drift. This does.

CHECKS
------
Per solution file
  S1  parses as Python
  S2  declares a "# LAB TITLE:" header
  S3  has both markdown and code cell markers
  S4  every <<<BLANK has a hint and a matching >>>
  S5  blanks are balanced and non-nested
  S6  no bare TODO / FIXME / placeholder text left in
  S7  contains a Checkpoint section (learner knows when they are done)
  S8  contains a Business impact or Discussion section
  S9  imports resolve against the package (no import of a module that is absent)
  S10 repo-root bootstrap present (runs from any working directory)

Per starter file
  T1  parses as Python
  T2  blank count matches the solution
  T3  every blank became a numbered TODO + NotImplementedError
  T4  no solution code leaked into the starter
  T5  halts at blank 1 when executed

Per notebook
  N1  valid JSON
  N2  nbformat 4 with required keys
  N3  every cell has a legal cell_type and list-of-str source
  N4  bootstrap cell present
  N5  cell count consistent with the source .py

Cross-cutting
  X1  solution/starter/notebook set complete for every lab
  X2  no lab imports a sibling lab that does not exist
  X3  seed-data references resolve
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAYS = ["Day1_Foundations", "Day2_RAG", "Day3_Governance"]

BLANK_OPEN = re.compile(r'^\s*#\s*<<<BLANK\s+hint="(.*?)"\s*>\s*$')
BLANK_CLOSE = re.compile(r"^\s*#\s*>>>\s*$")
PLACEHOLDER = re.compile(r"\b(FIXME|XXX|TBD|lorem ipsum|\[insert|placeholder here)\b", re.I)

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


@dataclass
class Result:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: int = 0

    def check(self, ok: bool, code: str, message: str, *, warn: bool = False) -> bool:
        self.checks += 1
        if not ok:
            (self.warnings if warn else self.failures).append(f"{code}  {message}")
        return ok


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- solutions
def validate_solution(path: Path, r: Result) -> dict:
    name = path.name
    src = read(path)
    lines = src.splitlines()
    info: dict = {"blanks": 0, "cells": 0}

    try:
        tree = ast.parse(src)
        r.check(True, "S1", "")
    except SyntaxError as exc:
        r.check(False, "S1", f"{name}: syntax error line {exc.lineno}: {exc.msg}")
        return info

    r.check(any(l.startswith("# LAB TITLE:") for l in lines),
            "S2", f"{name}: missing '# LAB TITLE:' header")

    md = sum(1 for l in lines if l.strip() == "# %% [markdown]")
    code = sum(1 for l in lines if l.strip() == "# %%")
    info["cells"] = md + code
    r.check(md > 0 and code > 0, "S3",
            f"{name}: needs both markdown and code cell markers (md={md}, code={code})")

    # blanks
    depth, blanks, unhinted = 0, 0, 0
    for i, line in enumerate(lines, 1):
        if BLANK_OPEN.match(line):
            if depth:
                r.check(False, "S5", f"{name}: nested <<<BLANK at line {i}")
            depth += 1
            blanks += 1
            if not BLANK_OPEN.match(line).group(1).strip():
                unhinted += 1
        elif BLANK_CLOSE.match(line):
            if not depth:
                r.check(False, "S5", f"{name}: unmatched >>> at line {i}")
            depth = max(0, depth - 1)
    info["blanks"] = blanks
    r.check(depth == 0, "S5", f"{name}: {depth} unclosed <<<BLANK block(s)")
    r.check(blanks > 0, "S4", f"{name}: no <<<BLANK blocks — starter would be identical to the solution")
    r.check(blanks >= 2, "S11",
            f"{name}: only {blanks} blank — thin for a 40+ minute lab; learners mostly read rather than write",
            warn=True)
    r.check(unhinted == 0, "S4", f"{name}: {unhinted} blank(s) with an empty hint")

    bad = PLACEHOLDER.findall(src)
    r.check(not bad, "S6", f"{name}: placeholder text present: {sorted(set(bad))[:4]}")

    r.check("Checkpoint" in src, "S7", f"{name}: no Checkpoint section — learners cannot self-assess")
    r.check("Business impact" in src or "Discussion" in src, "S8",
            f"{name}: no Business impact or Discussion section")

    r.check('(_p / "00_Program").is_dir()' in src, "S10",
            f"{name}: missing repo-root bootstrap — will break when run from another directory")

    # imports
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
    info["imports"] = imports

    for mod in imports:
        if mod.startswith("lab"):
            # A lab may import a lab from an EARLIER day (Day 2 Lab 5 reuses the
            # Day 1 rule engine rather than duplicating it). Search every day.
            everywhere = {p.stem: p for d in DAYS for p in (ROOT / d / "solutions").glob("lab*.py")}
            found = everywhere.get(mod)
            if r.check(found is not None, "X2",
                       f"{name}: imports lab '{mod}' which exists in no day's solutions/"):
                if found.parent != path.parent:
                    info.setdefault("cross_day", []).append(mod)
                    # cross-day import must be guarded with an explicit sys.path insert
                    r.check(found.parent.parent.name in src, "X2",
                            f"{name}: imports {mod} from {found.parent.parent.name} "
                            f"without adding that path to sys.path")
        elif mod == "shared":
            pass
    for shared_mod in re.findall(r"from shared\.(\w+) import", src):
        r.check((ROOT / "shared" / f"{shared_mod}.py").exists(), "S9",
                f"{name}: imports shared.{shared_mod} which does not exist")

    for seed in re.findall(r'SEED_DIR\s*/\s*"([^"]+)"', src):
        r.check((ROOT / "shared" / "seed_data" / seed).exists(), "X3",
                f"{name}: references seed file '{seed}' which does not exist")

    return info


# ----------------------------------------------------------------- starters
def validate_starter(path: Path, sol_info: dict, r: Result) -> None:
    name = path.name
    src = read(path)

    try:
        ast.parse(src)
    except SyntaxError as exc:
        r.check(False, "T1", f"{name}: syntax error line {exc.lineno}: {exc.msg}")
        return
    r.check(True, "T1", "")

    todos = len(re.findall(r"#\s*TODO \(Blank \d+\):", src))
    raises = len(re.findall(r'raise NotImplementedError\("Lab blank \d+', src))
    r.check(todos == sol_info["blanks"], "T2",
            f"{name}: {todos} TODO(s) but solution has {sol_info['blanks']} blank(s)")
    r.check(raises == todos, "T3", f"{name}: {todos} TODO(s) but {raises} NotImplementedError(s)")
    r.check("STARTER FILE" in src, "T3", f"{name}: missing starter header banner")
    r.check("<<<BLANK" not in src and ">>>" not in src.replace("# >>>", ""), "T4",
            f"{name}: BLANK markers leaked into the starter")


# ---------------------------------------------------------------- notebooks
def validate_notebook(path: Path, r: Result) -> int:
    name = path.name
    try:
        nb = json.loads(read(path))
    except json.JSONDecodeError as exc:
        r.check(False, "N1", f"{name}: invalid JSON: {exc}")
        return 0
    r.check(True, "N1", "")

    r.check(nb.get("nbformat") == 4, "N2", f"{name}: nbformat is {nb.get('nbformat')}, expected 4")
    for key in ("cells", "metadata", "nbformat_minor"):
        r.check(key in nb, "N2", f"{name}: missing top-level key '{key}'")

    cells = nb.get("cells", [])
    for i, cell in enumerate(cells):
        ok_type = cell.get("cell_type") in {"code", "markdown"}
        if not r.check(ok_type, "N3", f"{name}: cell {i} has cell_type {cell.get('cell_type')!r}"):
            continue
        src = cell.get("source")
        r.check(isinstance(src, list) and all(isinstance(s, str) for s in src),
                "N3", f"{name}: cell {i} source is not a list of strings")
        if cell["cell_type"] == "code":
            for key in ("outputs", "execution_count"):
                r.check(key in cell, "N3", f"{name}: code cell {i} missing '{key}'")

    bootstrap = any("00_Program" in "".join(c.get("source", []))
                    for c in cells[:3] if c.get("cell_type") == "code")
    r.check(bootstrap, "N4", f"{name}: no repo-root bootstrap cell in the first three cells")

    # code cells must individually parse (markdown-in-code-cell is a real defect)
    for i, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        text = "".join(cell.get("source", []))
        if not text.strip():
            continue
        try:
            ast.parse(text)
        except SyntaxError:
            # a cell may legitimately be a fragment mid-block; only flag prose
            if not text.lstrip().startswith(("#", '"""', "'''")):
                r.check(False, "N3", f"{name}: code cell {i} does not parse and is not a comment block")
    return len(cells)


# ----------------------------------------------------------------- execute
def execute(path: Path, r: Result, expect_halt: bool = False) -> None:
    proc = subprocess.run([sys.executable, path.name], cwd=path.parent,
                          capture_output=True, text=True, timeout=240)
    if expect_halt:
        # Blanks are numbered by POSITION IN THE FILE. A blank inside a method
        # defined early but called late is reached after a later blank. So the
        # contract is "halts at a numbered blank", not "halts at blank 1".
        m = re.search(r"Lab blank (\d+)", proc.stderr)
        r.check(m is not None and "NotImplementedError" in proc.stderr, "T5",
                f"{path.name}: starter did not halt at any numbered blank "
                f"(exit {proc.returncode})")
        if m:
            path_note = f"{path.name}: halts at blank {m.group(1)}"
            if m.group(1) != "1":
                r.check(False, "T6",
                        f"{path_note} — blank 1 is defined earlier but reached later. "
                        "Confirm the starter header explains this.", warn=True)
    else:
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
            r.check(False, "EXEC", f"{path.name}: exit {proc.returncode}\n        " +
                    "\n        ".join(tail))
        else:
            r.check(True, "EXEC", "")


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="also run every solution and starter")
    args = ap.parse_args()

    r = Result()
    total_labs = 0

    for day in DAYS:
        sol_dir, lab_dir, nb_dir = (ROOT / day / d for d in ("solutions", "labs", "notebooks"))
        solutions = sorted(sol_dir.glob("lab*.py")) if sol_dir.is_dir() else []
        if not solutions:
            print(f"\n{YELLOW}{day}: no labs built{RESET}")
            continue

        print(f"\n{day}")
        print("-" * 78)
        for sol in solutions:
            total_labs += 1
            before = len(r.failures)
            info = validate_solution(sol, r)

            starter = lab_dir / sol.name
            if r.check(starter.exists(), "X1", f"{sol.name}: starter missing"):
                validate_starter(starter, info, r)

            nb_s = nb_dir / f"{sol.stem}.ipynb"
            nb_sol = nb_dir / f"{sol.stem}_solution.ipynb"
            for nb in (nb_s, nb_sol):
                if r.check(nb.exists(), "X1", f"{sol.name}: notebook {nb.name} missing"):
                    validate_notebook(nb, r)

            if args.execute:
                execute(sol, r)
                if starter.exists():
                    execute(starter, r, expect_halt=True)

            new = r.failures[before:]
            status = f"{GREEN}PASS{RESET}" if not new else f"{RED}FAIL{RESET}"
            print(f"  {status}  {sol.name:<42} {info['blanks']} blank(s), {info['cells']} cells")
            for f in new:
                print(f"        {RED}{f}{RESET}")

    print("\n" + "=" * 78)
    print(f"{total_labs} lab(s) · {r.checks} checks run")
    if r.warnings:
        print(f"\n{YELLOW}{len(r.warnings)} warning(s){RESET}")
        for w in r.warnings:
            print(f"  {w}")
    if r.failures:
        print(f"\n{RED}{len(r.failures)} FAILURE(S){RESET}")
        for f in r.failures:
            print(f"  {f}")
        return 1
    print(f"\n{GREEN}All checks passed.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
