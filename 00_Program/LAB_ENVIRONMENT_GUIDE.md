# How to Run the Labs — Environment Guide

**Accenture Batch 1 · Agentic AI Foundation**

Four supported ways to run this package. Pick one, follow it to the end, and stop
when `verify_environment.py` returns 0 or 2.

> **You do not need Azure credentials to do the labs.** Set `LAB_OFFLINE_MODE=true`
> and every lab runs end to end against a deterministic stub. Read
> [§7 Offline mode](#7-offline-mode-and-what-it-does-not-prove) before quoting any
> number produced that way — the limits are real and specific.

---

## 1. Which option should you pick?

| | **A · Local VS Code** | **B · Local Jupyter** | **C · GitHub Codespaces** | **D · Azure ML compute** |
|---|---|---|---|---|
| Setup time | 10–15 min | 10 min | **~3 min** | 20–30 min |
| Needs local install | yes | yes | **no** | no |
| Survives a locked corporate laptop | often not | often not | **yes** | yes |
| Debugger, breakpoints | **best** | limited | good | good |
| Streamlit web apps | **easy** | awkward | easy (port forwarding) | needs care — see §5.6 |
| Azure private endpoints reachable | only via VPN | only via VPN | no | **yes, natively** |
| Managed identity (no keys) | no | no | no | **yes** |
| Cost | free | free | free tier, then billed | **billed per hour — stop it** |
| Persists between days | yes | yes | yes (60-day idle default) | yes |

**Recommendations**

- **Most learners → A (Local VS Code).** Best debugging, and the debugger matters
  in Day 1 Lab 4 where a wrong customer-normalisation returns an empty match and
  *no error at all*.
- **Locked-down laptop, or you want everyone identical in 3 minutes → C.**
- **Your Azure OpenAI resource is behind a private endpoint, or your security team
  forbids API keys → D.** It is the only option that gives you managed identity.
- **B only if your organisation has standardised on Jupyter** and you would fight
  IT to install VS Code.

You can switch later. Nothing in the package is tied to an editor.

---

## 2. Prerequisites common to every option

| Item | Requirement |
|---|---|
| Python | 3.11 or 3.12 (the verifier refuses anything older) |
| Disk | ~1.5 GB for dependencies |
| Network | access to PyPI; Azure endpoints only if you are not using offline mode |
| Azure (optional) | an Azure OpenAI / Foundry chat deployment and an embedding deployment |

**The one fact that causes the most day-one support tickets:** the `model=`
parameter takes the **deployment name**, not the model family name. If your
deployment is called `gpt4o-prod`, you pass `gpt4o-prod` — not `gpt-4o`.

---

## 3. Option A — Local VS Code

### 3.1 Install

1. **Python 3.12** — [python.org/downloads](https://www.python.org/downloads/).
   On Windows, tick **"Add python.exe to PATH"** during install.
2. **VS Code** — [code.visualstudio.com](https://code.visualstudio.com/).
3. Open the package folder in VS Code. It will prompt you to install the
   recommended extensions from `.vscode/extensions.json` — accept.

### 3.2 Bootstrap

```bash
# macOS / Linux / WSL
bash setup.sh
```

```powershell
# Windows PowerShell
.\setup.ps1
# If script execution is blocked, run this once in the same window first:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

`setup.sh` / `setup.ps1` creates a virtual environment, installs the pinned
dependencies, creates `.env` from the template, builds the Day 2 vector corpus,
and runs the verifier.

### 3.3 Select the interpreter

`Ctrl+Shift+P` (`Cmd+Shift+P` on macOS) → **Python: Select Interpreter** → choose
`./.venv/bin/python` (`.\.venv\Scripts\python.exe` on Windows).

If you skip this, VS Code runs your system Python, none of the imports resolve,
and the error is confusing. It is the single most common Option A problem.

### 3.4 Configure

Edit `.env` at the repository root:

```ini
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_API_KEY=<paste-key>
AZURE_OPENAI_CHAT_DEPLOYMENT=<your-deployment-name>
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<your-embedding-deployment-name>
LAB_OFFLINE_MODE=false
```

No credentials? Leave the endpoint blank and set `LAB_OFFLINE_MODE=true`.

### 3.5 Verify and run

```bash
python 00_Program/verify_environment.py     # 0 = ready · 1 = blocked · 2 = warnings
python Day1_Foundations/labs/lab01_environment_and_telemetry.py
```

`.vscode/launch.json` ships five debug configurations (`F5`):

| Configuration | Use |
|---|---|
| **Run current lab file** | runs whichever lab you have open, from its own directory |
| **Verify environment** | the pre-flight check |
| **Capstone: run batch** | `python -m Capstone.src.cli run` |
| **Capstone: acceptance suite** | the seven criteria |
| **Streamlit: Day 1 console** | launches the web app under the debugger |

`justMyCode` is set to `false` on **Run current lab file** deliberately — you will
want to step into `shared/` and into LangGraph.

---

## 4. Option B — Local Jupyter

Every lab ships as a notebook as well as a script:

```
Day1_Foundations/notebooks/lab01_environment_and_telemetry.ipynb           starter
Day1_Foundations/notebooks/lab01_environment_and_telemetry_solution.ipynb  complete
```

### 4.1 Bootstrap

```bash
bash setup.sh            # or .\setup.ps1 on Windows
source .venv/bin/activate    # .\.venv\Scripts\Activate.ps1 on Windows

python -m ipykernel install --user \
    --name agentic-batch1 \
    --display-name "Python (Agentic Batch 1)"

jupyter lab
```

### 4.2 Select the kernel

In each notebook: **Kernel → Change Kernel → Python (Agentic Batch 1)**.

If you leave it on the default kernel you get `ModuleNotFoundError: langgraph`
even though the package is installed — it is installed in the venv, and the
default kernel is not.

### 4.3 The bootstrap cell

Every generated notebook opens with a cell that walks up the directory tree
looking for `00_Program/` and puts that directory on `sys.path`:

```python
import sys, pathlib
p = pathlib.Path.cwd()
while p != p.parent and not (p / '00_Program').is_dir():
    p = p.parent
sys.path.insert(0, str(p))
print('repo root ->', p)
```

**Run it first, every time.** It is why `from shared.telemetry import ...` resolves
regardless of where JupyterLab was launched.

### 4.4 Known limitations of Option B

- **Streamlit web apps do not run inside a notebook.** Open a terminal
  (JupyterLab → File → New → Terminal) and run
  `streamlit run Day1_Foundations/webapp/app_reconciliation_console.py`.
- **Debugging is weaker.** JupyterLab has a debugger, but Day 1 Lab 4 and the
  Capstone are noticeably easier to work through in VS Code.
- **Re-running cells out of order** causes confusing state in Day 2 Lab 5 and
  Day 3 Lab 4, which build a graph incrementally. **Kernel → Restart & Run All**
  is your friend.

---

## 5. Option C — GitHub Codespaces

The fastest path to twenty identical environments, and the answer when corporate
laptops will not permit a local Python install.

### 5.1 Launch

1. Push this package to a GitHub repository (or open the one your trainer provides).
2. **Code ▾ → Codespaces → Create codespace on main**.
3. Wait. `.devcontainer/devcontainer.json` builds a Python 3.12 container, and
   `post-create.sh` installs dependencies, creates `.env` with
   `LAB_OFFLINE_MODE=true`, builds the Day 2 corpus and runs the verifier.

Everything is preconfigured: the extensions, the interpreter, `PYTHONPATH`, and
port forwarding for Streamlit (8501) and JupyterLab (8888).

### 5.2 Add credentials

The container starts in offline mode because a Codespace has no Azure credentials
by default. To go live, either edit `.env`, or — better — use Codespaces secrets:

**Repository → Settings → Secrets and variables → Codespaces → New repository secret**

Create `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
`AZURE_OPENAI_CHAT_DEPLOYMENT` and `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`.
They arrive as environment variables, and `shared/config.py` reads the real
process environment **before** `.env`, so they win automatically. Then set
`LAB_OFFLINE_MODE=false` in `.env`.

> Secrets are the right mechanism for a shared teaching repository: nobody pastes
> a key into a file that could be committed.

### 5.3 Streamlit in a Codespace

```bash
streamlit run Day1_Foundations/webapp/app_reconciliation_console.py
```

VS Code detects port 8501 and offers to open it. If it does not, use the **Ports**
tab and click the globe icon on 8501.

### 5.4 Cost and lifecycle

Codespaces bills compute and storage beyond the free monthly allowance. **Stop
the codespace when you finish for the day** — it does not stop itself immediately.
Default idle timeout is 30 minutes and default retention is 30 days; both are
configurable per organisation, so check yours.

### 5.5 Same container, locally

If you have Docker Desktop and the **Dev Containers** extension, you can use the
identical container on your own machine: `Ctrl+Shift+P` → **Dev Containers:
Reopen in Container**. Same setup, no Codespaces billing.

---

## 6. Option D — Azure Machine Learning compute instance

Choose this when your Azure OpenAI resource sits behind a **private endpoint**, or
when your security team will not issue API keys and you need **managed identity**.

> **Version-sensitivity notice.** The Azure ML portal UI and the `az ml` CLI both
> change. The flow below is the stable shape; **verify the exact menu names and
> command syntax against current Microsoft Learn documentation before you deliver
> this to a class.** Do not present any specific `az ml` invocation as settled.

### 6.1 Create the compute instance

**Portal route (recommended for a classroom):**

1. Open **Azure ML Studio** → your workspace → **Compute** → **Compute instances**
   → **+ New**.
2. Name it (per-user names — compute instances are single-user by design).
3. **Virtual machine size:** a general-purpose 2–4 vCPU / 14 GB size such as
   `Standard_DS11_v2` is ample. These labs are **not** GPU workloads —
   embeddings and inference happen in the Azure OpenAI service, not on this VM.
   Provisioning a GPU size wastes money and provisioning quota.
4. **Schedule:** set an auto-shutdown schedule. Do this at creation time, not
   later.
5. Create, and wait for **Running**.

**CLI route** (`az ml compute create …`) exists in the Azure CLI ML extension v2.
It is convenient for provisioning a whole cohort, but **check the current
parameter names before relying on it** — this is exactly the surface the notice
above refers to.

### 6.2 Get the package onto it

Once the instance shows **Running**, open **Terminal** from the compute instance's
application list.

```bash
cd ~/cloudfiles/code/Users/$USER
git clone <your-repo-url> agentic-batch1
cd agentic-batch1
```

No git remote? Upload the zip through **Notebooks → Upload folder**, then
`unzip` in the terminal.

> `~/cloudfiles/code/Users/<you>` is backed by the workspace file share and
> **survives an instance restart**. Anything you write elsewhere on the VM does
> not. Clone there, not into `~`.

### 6.3 Environment and kernel

```bash
bash setup.sh --conda
conda activate agentic-batch1

python -m ipykernel install --user \
    --name agentic-batch1 \
    --display-name "Python (Agentic Batch 1)"
```

Refresh the browser tab, then pick **Python (Agentic Batch 1)** as the kernel in
any notebook.

`environment.yml` deliberately installs the lab packages via
`-r 00_Program/requirements.txt` rather than restating them. One pin list, one
place to change it.

### 6.4 Credentials — the reason to be here

This is the option where you can drop API keys entirely.

1. Enable a **managed identity** on the compute instance (system-assigned is
   fine).
2. Grant that identity the **Cognitive Services OpenAI User** role on your Azure
   OpenAI resource.
3. In `.env`, leave `AZURE_OPENAI_API_KEY` **empty** and set the endpoint and
   deployment names.

`shared/foundry_client.py` calls `build_credential()`, which falls back to
`DefaultAzureCredential` when no static token is supplied — and
`DefaultAzureCredential` picks up the compute instance's managed identity
automatically. No code changes.

This is also the moment to make the Day 1 Lab 2 point concrete: the
`StaticTokenCredential` you wrote is a *teaching and break-glass* construct.
Managed identity is what production looks like, and here it is, working, with the
same calling code.

### 6.5 Verify

```bash
python 00_Program/verify_environment.py
```

### 6.6 Streamlit on a compute instance — read this before you promise it

An Azure ML compute instance does **not** expose arbitrary ports publicly by
default. Three approaches, in the order I would try them:

1. **VS Code Remote (best).** Attach VS Code to the compute instance from Azure ML
   Studio, run Streamlit in the integrated terminal, and let VS Code forward the
   port to your laptop. Same experience as Option A.
2. **SSH tunnel.** If the instance was created with SSH access enabled:
   `ssh -L 8501:localhost:8501 azureuser@<instance> -p <port>`, then browse to
   `http://localhost:8501`.
3. **The compute instance app proxy.** Azure ML exposes some applications on a
   per-instance URL. **I am not going to give you that URL pattern from memory** —
   it has changed and it varies by region. If you want to use it, confirm the
   current form in Microsoft Learn first.

If none of these is available in your tenant, run the web apps locally
(Option A) and use the compute instance for the labs themselves. Nothing in the
Streamlit apps needs Azure — they read local files and the local vector store.

### 6.7 Cost — say this to the class out loud

**A compute instance bills for every hour it is running, whether or not anyone is
using it.** Stop it at the end of each day. Set an auto-shutdown schedule at
creation. A cohort of twenty instances left running over a weekend is a real and
entirely avoidable expense.

---

## 7. Offline mode, and what it does *not* prove

Set `LAB_OFFLINE_MODE=true` in `.env`. Every lab runs end to end with no network
calls. This is the right choice for dry runs, air-gapped rooms, and mornings when
a key has expired.

| Surface | Offline behaviour | What you may **not** claim from it |
|---|---|---|
| Chat model | deterministic keyword stub that quotes verbatim from its input | anything about model reasoning, generalisation or accuracy |
| Embeddings | hashed bag-of-words, 256-dim, L2-normalised | **semantic** retrieval quality — this is *lexical* matching |
| Vector store | real ChromaDB if installed, in-memory cosine fallback otherwise | performance or scaling characteristics |

The embedder limitation is concrete, not theoretical: *"short paid"* and
*"underpaid"* share no tokens and will **not** retrieve each other offline, though
a real embedding model places them close together.

Every lab prints its active backend at start-up. **If a number leaves the room on
a slide, the backend that produced it goes next to it.**

---

## 8. Verifying, whichever option you chose

```bash
python 00_Program/verify_environment.py
```

| Exit | Meaning |
|---|---|
| **0** | ready |
| **1** | blocked — fix before starting |
| **2** | ready, with warnings you should read |

It checks four things, in descending order of how badly each ruins a day:

1. **Interpreter and packages** — by *importing* them, not by reading `pip list`.
   A package can be installed and still fail to import.
2. **Seed data and known answers** — row counts, remittance-to-transaction links,
   and a known-answer test: all ten Day 1 end states must reproduce exactly.
3. **Backends** — which model path is live, and whether the embedder is semantic
   or lexical.
4. **Version-sensitive surfaces** — what to re-check today.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: shared` | wrong interpreter, or launched from a directory the bootstrap could not resolve | select the venv/conda interpreter; run from the repository root |
| `ModuleNotFoundError: langgraph` in a notebook | notebook is on the default kernel, not the lab kernel | Kernel → Change Kernel → **Python (Agentic Batch 1)** |
| `DeploymentNotFound` on the first model call | `model=` was given the model family name | pass the **deployment name** exactly as it appears in the Foundry portal |
| Day 2 Lab 3 exits: *collection is empty* | Day 2 Lab 1 was skipped — it builds the corpus | run `Day2_RAG/solutions/lab01_vector_ingestion.py` once |
| Capstone: BNK-1002 has no reason code | same cause — no corpus | as above |
| Retrieval returns odd neighbours | offline lexical embedder | expected; switch to Path A for any quality claim |
| Starter halts at blank 2 before blank 1 | blanks are numbered by file position, not execution order | expected; the starter header explains it |
| `pip install` fails behind a corporate proxy | PyPI blocked | set `HTTPS_PROXY`, or use Option C / D |
| Streamlit shows a blank page in Codespaces | port not forwarded | Ports tab → globe icon on 8501 |
| PowerShell refuses to run `setup.ps1` | execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |

**None of these is a code defect.** All are documented, and most are printed as
actionable error messages by the code itself.

---

## 10. Trainer checklist

Run this **the afternoon before Day 1**, not on the morning.

- [ ] Decide the option for this cohort and tell learners in advance.
- [ ] Run `verify_environment.py` on the delivery laptop. Green?
- [ ] Confirm `langgraph-checkpoint-sqlite` is installed — Day 3 Lab 6 and the
      Capstone need it for durable checkpoints.
- [ ] Confirm the chat **and** embedding deployment names are correct.
- [ ] Build the Day 2 corpus once so nobody hits an empty collection.
- [ ] For Option D: auto-shutdown schedules set on **every** instance.
- [ ] For Option C: Codespaces secrets configured, or offline mode accepted.
- [ ] Re-read `00_Program/VERSION_RISK_REGISTER.md` — particularly the
      `azure-ai-projects` entry (Path B) and the Azure ML surfaces in §6 above.
- [ ] Collect the names of anyone still red. Those are the people to arrive early
      for.

---

## 11. Reference — commands by task

```bash
# setup
bash setup.sh                    # macOS / Linux / WSL / Azure ML
.\setup.ps1                      # Windows
bash setup.sh --conda            # conda instead of venv

# verification
python 00_Program/verify_environment.py

# labs
python Day1_Foundations/labs/lab01_environment_and_telemetry.py        # starter
python Day1_Foundations/solutions/lab01_environment_and_telemetry.py   # complete
jupyter lab Day1_Foundations/notebooks/

# web apps
streamlit run Day1_Foundations/webapp/app_reconciliation_console.py
streamlit run Day2_RAG/webapp/app_remittance_explorer.py
streamlit run Capstone/webapp/app_analyst_console.py

# capstone
python -m Capstone.src.cli run
python -m Capstone.src.cli pending
python Capstone/tests/test_acceptance.py

# trainer: regenerate every derived artifact, then validate
bash _builders/build_all.sh
python _builders/validate_labs.py --execute
```
