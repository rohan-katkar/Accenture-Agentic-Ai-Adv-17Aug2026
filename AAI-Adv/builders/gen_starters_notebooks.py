"""Generate student starters + Jupyter notebooks FROM the solutions.

Starters are derived, never hand-authored (single source of truth): the body
of each `# %%` code cell that carries a `## Step N` heading in the preceding
markdown is replaced with a loud `raise NotImplementedError("STEP N: ...")`,
keeping imports, scaffolding, and the final assertion cell intact so students
get immediate red/green feedback.

Notebooks are converted from the `# %%` cell markers (VS Code runs those
natively too, so .py and .ipynb stay in lockstep).
"""
import re
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]


def split_cells(src: str) -> list[tuple[str, str]]:
    """[(kind, body)] where kind is 'markdown'|'code', from # %% markers."""
    cells, kind, buf = [], "code", []
    for line in src.splitlines():
        if line.startswith("# %%"):
            if buf:
                cells.append((kind, "\n".join(buf).strip("\n")))
            kind = "markdown" if "[markdown]" in line else "code"
            buf = []
        else:
            buf.append(line)
    if buf:
        cells.append((kind, "\n".join(buf).strip("\n")))
    return [(k, b) for k, b in cells if b.strip()]


def md_text(body: str) -> str:
    return "\n".join(re.sub(r"^#\s?", "", l) for l in body.splitlines())


def to_notebook(solution: Path, dest: Path) -> None:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3",
                                 "language": "python"}
    for kind, body in split_cells(solution.read_text()):
        if kind == "markdown":
            nb.cells.append(nbf.v4.new_markdown_cell(md_text(body)))
        else:
            # __main__ guard is meaningless in a notebook: run main() directly.
            body = body.replace('if __name__ == "__main__":\n    asyncio.run(main())',
                                "await main()")
            body = body.replace('if __name__ == "__main__":\n    main()',
                                "main()")
            nb.cells.append(nbf.v4.new_code_cell(body))
    dest.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, str(dest))


STEP_RE = re.compile(r"##\s*Step\s*(\d+)\s*[—-]\s*(.+)")

def to_starter(solution: Path, dest: Path) -> None:
    cells = split_cells(solution.read_text())
    out, last_step = [], None
    for i, (kind, body) in enumerate(cells):
        if kind == "markdown":
            m = STEP_RE.search(body)
            if m:
                last_step = (m.group(1), m.group(2).strip())
            out.append("# %% [markdown]\n" + body)
            continue
        is_final = i == len(cells) - 1 or "async def main" in body or \
                   'if __name__ == "__main__"' in body
        if last_step and not is_final:
            n, title = last_step
            first = body.splitlines()[0]
            keep_imports = "\n".join(l for l in body.splitlines()
                                     if l.startswith(("import ", "from ")))
            out.append(
                "# %%\n" + (keep_imports + "\n\n" if keep_imports else "") +
                "# ------------------------------------------------------------------\n"
                f"# TODO — implement Step {n}: {title}\n"
                "# The assertions in the final cell define 'done'. Named failure\n"
                "# modes and hints are in the lab guide for this step.\n"
                "# ------------------------------------------------------------------\n"
                f'raise NotImplementedError("STEP {n}: {title}")'
            )
            last_step = None
        else:
            out.append("# %%\n" + body)
    text = "\n\n".join(out) + "\n"
    # C11: starters live one level deeper than solutions, so fixed parents[N]
    # indexing breaks. Replace with an upward search for the repo marker.
    text = text.replace(
        "ROOT = Path(__file__).resolve().parents[2]",
        'ROOT = next(p for p in Path(__file__).resolve().parents\n'
        '            if (p / "common" / "model.py").exists())',
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)


def main():
    solutions = sorted(ROOT.glob("solutions/day*/lab*.py"))
    assert len(solutions) == 12, f"expected 12 solutions, found {len(solutions)}"
    for sol in solutions:
        day_dir = ROOT / "labs" / sol.parent.name     # starters/notebooks live under labs/
        stem = sol.stem
        to_starter(sol, day_dir / "starters" / f"{stem}.py")
        to_notebook(sol, day_dir / "notebooks" / f"{stem}.ipynb")
        print(f"  {sol.name} -> starter + notebook")
    cap = ROOT / "capstone" / "engine.py"
    to_notebook(cap, ROOT / "capstone" / "capstone.ipynb")
    print("  capstone -> notebook")
    print(f"Generated {len(solutions)} starters, {len(solutions)+1} notebooks")


if __name__ == "__main__":
    main()
