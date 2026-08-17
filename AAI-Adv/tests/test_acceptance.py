"""Acceptance tests — the package is complete only when ALL of these pass.

Run: python -m pytest tests/ -q        (offline mode, no Azure needed)

Each lab solution is executed as a subprocess: build-and-run, not review.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

LABS = [
    "solutions/day1/lab1_1.py",
    "solutions/day1/lab1_2.py",
    "solutions/day1/lab1_3.py",
    "solutions/day1/lab1_4.py",
    "solutions/day2/lab2_1.py",
    "solutions/day2/lab2_2.py",
    "solutions/day2/lab2_3.py",
    "solutions/day2/lab2_4.py",
    "solutions/day3/lab3_1.py",
    "solutions/day3/lab3_2.py",
    "solutions/day3/lab3_3.py",
    "solutions/day3/lab3_4.py",
]


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    # C12: Windows consoles default child stdout to cp1252; any non-ASCII
    # print then crashes the lab. Force UTF-8 for all lab subprocesses.
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([PY, str(ROOT / script), *args], capture_output=True,
                          text=True, cwd=ROOT, timeout=180, env=env)


def test_at00_seed_data_regenerates():
    r = run("common/data_gen.py")
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert info["rows_written"] == 26 and info["invoices_written"] == 24


def _lab_test(script):
    def _t():
        r = run(script)
        assert r.returncode == 0, f"{script} failed:\n{r.stderr[-2000:]}"
        assert "PASS" in r.stdout, f"{script} did not print PASS"
    return _t


for i, lab in enumerate(LABS, 1):
    globals()[f"test_at{i:02d}_{Path(lab).stem}"] = _lab_test(lab)


def test_at13_capstone_demo_end_to_end():
    r = run("capstone/engine.py", "demo")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "'NW-1017', 'NW-1023'" in r.stdout or '"NW-1017"' in r.stdout
    assert "human_approved" in r.stdout and "human_rejected" in r.stdout
    assert "Ledger entries: 23" in r.stdout


def test_at14_starters_raise_not_silent():
    """Every generated starter must raise NotImplementedError, never `...`."""
    starters = list(ROOT.glob("labs/day*/starters/lab*.py"))
    assert len(starters) == 12, f"expected 12 starters, found {len(starters)}"
    for s in starters:
        text = s.read_text()
        assert "NotImplementedError" in text, f"{s.name} lacks loud placeholders"


def test_at15_notebooks_exist_and_parse():
    import nbformat
    nbs = list(ROOT.glob("labs/day*/notebooks/*.ipynb")) + \
          list(ROOT.glob("capstone/*.ipynb"))
    assert len(nbs) == 13, f"expected 13 notebooks, found {len(nbs)}"
    for nb in nbs:
        parsed = nbformat.read(str(nb), as_version=4)
        assert len(parsed.cells) >= 3


def test_at16_bicep_and_workflow_artifacts():
    assert (ROOT / "infra" / "main.bicep").exists()
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())
    assert {"test", "package"} <= set(wf["jobs"])
