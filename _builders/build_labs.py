#!/usr/bin/env python3
"""
_builders/build_labs.py
=======================
Single source of truth for every lab artifact.

You author ONE file per lab: the complete, runnable solution in
<Day>/solutions/labXX_*.py. This builder derives everything else:

    solutions/labXX.py   --(strip blanks)-->  labs/labXX.py        (starter)
    solutions/labXX.py   --(cellify)------->  notebooks/labXX_solution.ipynb
    labs/labXX.py        --(cellify)------->  notebooks/labXX.ipynb (starter)

Why derive rather than hand-maintain four files: content drift. A fix applied to
the solution but not the notebook is the single most common defect in shipped
lab packages. Here it is structurally impossible.

MARKUP CONTRACT
---------------
Cell boundaries:
    # %% [markdown]     -> everything until the next marker becomes a markdown
                           cell (leading "# " stripped from each line)
    # %%                -> code cell

Removable blanks (become TODOs in the starter):
    # <<<BLANK hint="Define the four required state fields">
    ...solution code...
    # >>>

Run:  python _builders/build_labs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAYS = ["Day1_Foundations", "Day2_RAG", "Day3_Governance"]

BLANK_OPEN = re.compile(r'^(\s*)#\s*<<<BLANK\s+hint="(.*?)"\s*>\s*$')
BLANK_CLOSE = re.compile(r"^\s*#\s*>>>\s*$")


# ---------------------------------------------------------------------------
# 1. Solution -> starter
# ---------------------------------------------------------------------------
def strip_blanks(source: str) -> tuple[str, int]:
    out: list[str] = []
    lines = source.splitlines()
    i, blank_no = 0, 0
    while i < len(lines):
        m = BLANK_OPEN.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue

        indent, hint = m.group(1), m.group(2)
        blank_no += 1
        i += 1
        while i < len(lines) and not BLANK_CLOSE.match(lines[i]):
            i += 1
        i += 1  # skip the closing marker

        rule = indent + "# " + "-" * 66
        out.extend([
            rule,
            f"{indent}# TODO (Blank {blank_no}): {hint}",
            rule,
            f'{indent}raise NotImplementedError("Lab blank {blank_no} - see the TODO above")',
        ])
    return "\n".join(out) + "\n", blank_no


def starter_header(title: str, blanks: int) -> str:
    return (
        "# " + "=" * 74 + "\n"
        f"# STARTER FILE - {title}\n"
        "# " + "=" * 74 + "\n"
        f"# There are {blanks} blank(s) to complete, each marked with a TODO.\n"
        "# Work top to bottom. Run the file after each blank - it fails loudly at the\n"
        "# next unfinished blank it REACHES, which tells you where you are.\n"
        "#\n"
        "# Blanks are numbered by position in the file, not by execution order. A blank\n"
        "# inside a function defined early but called late is reached after a later one,\n"
        "# so the file may halt at blank 2 before blank 1. That is expected.\n"
        "#\n"
        "# Stuck? The completed file is in ../solutions/ - but try for ten minutes\n"
        "# first. The debugging is the lesson.\n"
        "# " + "=" * 74 + "\n\n"
    )


# ---------------------------------------------------------------------------
# 2. .py (cell-marked) -> .ipynb  (nbformat v4 schema, written directly)
# ---------------------------------------------------------------------------
def cellify(source: str) -> list[dict]:
    cells: list[dict] = []
    kind = "code"
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        text = "\n".join(buf).strip("\n")
        if not text.strip():
            buf.clear()
            return
        if kind == "markdown":
            stripped = [re.sub(r"^#\s?", "", ln) for ln in text.splitlines()]
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": _as_source("\n".join(stripped)),
            })
        else:
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": _as_source(text),
            })
        buf.clear()

    for line in source.splitlines():
        if line.strip() == "# %% [markdown]":
            flush()
            kind = "markdown"
            continue
        if line.strip() == "# %%":
            flush()
            kind = "code"
            continue
        buf.append(line)
    flush()
    return cells


def _as_source(text: str) -> list[str]:
    """nbformat stores source as a list of lines, each keeping its newline
    except the last."""
    lines = text.split("\n")
    return [ln + "\n" for ln in lines[:-1]] + [lines[-1]]


def notebook(cells: list[dict], title: str) -> dict:
    return {
        "cells": [{
            "cell_type": "markdown",
            "metadata": {},
            "source": _as_source(
                f"# {title}\n\n"
                "**Accenture Batch 1 - Agentic AI Foundation**\n\n"
                "> Run the setup cell first. It puts the repository root on `sys.path` so "
                "that `from shared...` imports resolve no matter where Jupyter was launched."
            ),
        }, {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": _as_source(
                "# --- notebook bootstrap (repository root on sys.path) ---\n"
                "import sys, pathlib\n"
                "p = pathlib.Path.cwd()\n"
                "while p != p.parent and not (p / '00_Program').is_dir():\n"
                "    p = p.parent\n"
                "sys.path.insert(0, str(p))\n"
                "print('repo root ->', p)"
            ),
        }] + cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ---------------------------------------------------------------------------
# 3. Orchestration
# ---------------------------------------------------------------------------
def main() -> int:
    built = 0
    for day in DAYS:
        sol_dir = ROOT / day / "solutions"
        lab_dir = ROOT / day / "labs"
        nb_dir = ROOT / day / "notebooks"
        if not sol_dir.is_dir():
            continue
        lab_dir.mkdir(exist_ok=True)
        nb_dir.mkdir(exist_ok=True)

        for sol in sorted(sol_dir.glob("lab*.py")):
            src = sol.read_text(encoding="utf-8")
            first = next((l for l in src.splitlines() if l.startswith("# LAB TITLE:")), "")
            title = first.replace("# LAB TITLE:", "").strip() or sol.stem

            starter_body, blanks = strip_blanks(src)
            starter = starter_header(title, blanks) + starter_body
            (lab_dir / sol.name).write_text(starter, encoding="utf-8")

            (nb_dir / f"{sol.stem}.ipynb").write_text(
                json.dumps(notebook(cellify(starter), f"{title} - Starter"), indent=1),
                encoding="utf-8")
            (nb_dir / f"{sol.stem}_solution.ipynb").write_text(
                json.dumps(notebook(cellify(src), f"{title} - Solution"), indent=1),
                encoding="utf-8")

            print(f"  {day}/{sol.name}: {blanks} blank(s) -> starter + 2 notebooks")
            built += 1

    print(f"\nBuilt artifacts for {built} lab(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
