# One-command setup: Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe common\data_gen.py
& .\.venv\Scripts\python.exe -m pytest tests\ -q
Write-Host "Setup complete - 17/17 acceptance tests must show above."
Write-Host "VS Code: Ctrl+Shift+P -> 'Python: Select Interpreter' -> .venv"
