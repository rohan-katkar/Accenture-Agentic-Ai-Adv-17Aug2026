# Environment Setup — VS Code + Azure

## 1. FASTEST PATH — GitHub Codespaces (zero local install)

Open the repo on GitHub > Code > Codespaces > 'Create codespace on main'. The .devcontainer builds Python 3.12 + Azure CLI + Node automatically, then runs setup: venv, dependencies, seed data, and the full 17-test acceptance suite. When the terminal prints 'Environment ready', you are validated — try `./.venv/bin/python capstone/engine.py demo`. Azure mode works from Codespaces too: `az login --use-device-code`, then fill .env.

## 2. LOCAL PATH — one-command setup

Windows PowerShell: `./setup.ps1` · Linux/macOS/WSL2: `./setup.sh`. Both create .venv, install pinned dependencies, generate seed data, and run the acceptance suite. A green 17/17 is your definition of 'environment ready'.

## 3. Install prerequisites (manual path)

Install VS Code with the Python and Jupyter extensions, Python 3.10–3.12 (labs are validated on 3.12; the SDK declares support through 3.14 but this package was not executed on 3.14), Git, and Azure CLI (az). Windows users: labs run identically in native Windows or WSL2.

## 4. Clone and create the virtual environment (manual path)

Open the repo folder in VS Code. Terminal: `python -m venv .venv` then activate (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere) and `pip install -r requirements.txt`. Select the .venv interpreter via the VS Code command palette: 'Python: Select Interpreter'.

## 5. Generate seed data

Run `python common/data_gen.py`. This writes the settlement CSV (26 rows including planted defects), 24 D365 invoices, and the policy corpus. Deterministic: same seed, same data, every machine.

## 6. Validate OFFLINE mode

Run `python -m pytest tests/ -q`. All 17 acceptance tests must pass with NO Azure credentials — this proves your local environment before any cloud dependency enters the picture.

## 7. Provision Azure (once per cohort)

In the Azure portal create an Azure AI Foundry resource + project. In the Foundry portal, deploy a chat model (e.g. a gpt-4o-mini class deployment) and note the DEPLOYMENT name. Copy the Project endpoint from the project Overview page (shape: https://<resource>.services.ai.azure.com/api/projects/<project>). [VERIFY: portal navigation labels change frequently — confirm against current docs at learn.microsoft.com before delivery.]

## 8. Authenticate

Run `az login` (device code on locked-down machines: `az login --use-device-code`). The labs use DefaultAzureCredential, so no keys are ever stored in code. Your identity needs the 'Azure AI User' role (or equivalent data-plane role) on the Foundry project. [VERIFY role name against current RBAC docs.]

## 9. Switch to AZURE mode

Copy .env.template to .env and fill FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT. Every lab prints its mode on startup; re-run any lab and it will now execute against live Foundry models. No lab code changes — the switch lives entirely in common/model.py.

## 10. Repository layout for learners

Work in labs/dayN/starters/ (loud NotImplementedError placeholders per step) or labs/dayN/notebooks/. Reference implementations live separately in solutions/dayN/ — same structure, cell for cell, so diffing your starter against its solution is always possible. Starters and notebooks are GENERATED from solutions (builders/gen_starters_notebooks.py); never edit them by hand.

## 11. Run labs in VS Code

Each lab exists twice, in lockstep: solutions/dayN/labN_M.py (and labs/dayN/starters/) use `# %%` cell markers — VS Code renders 'Run Cell' links directly in the editor. The same content is in labs/dayN/notebooks/*.ipynb for the Jupyter UI. Both are generated from the same source; use whichever you prefer.

