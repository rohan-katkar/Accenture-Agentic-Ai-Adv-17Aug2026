# =====================================================================
# One-command bootstrap for Windows PowerShell.
#   .\setup.ps1
#   .\setup.ps1 -NoCorpus
# If script execution is blocked, run once:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# =====================================================================
param([switch]$NoCorpus)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== 1. Python environment ===" -ForegroundColor Cyan
$ver = (python -c "import sys;print('%d.%d'%sys.version_info[:2])")
if ($ver -notin @("3.11", "3.12")) {
    Write-Host "Python $ver found. This package needs 3.11 or 3.12." -ForegroundColor Red
    exit 1
}
Write-Host "Python $ver OK"

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip --quiet
python -m pip install -r 00_Program\requirements.txt
Write-Host "Activate later with:  .\.venv\Scripts\Activate.ps1"

Write-Host "`n=== 2. Configuration ===" -ForegroundColor Cyan
if (Test-Path ".env") {
    Write-Host ".env already exists - left untouched."
} else {
    Copy-Item 00_Program\.env.example .env
    Write-Host "Created .env from the template."
    Write-Host "Edit it to add AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY,"
    Write-Host "or set LAB_OFFLINE_MODE=true to run everything without Azure."
}

if (-not $NoCorpus) {
    Write-Host "`n=== 3. Day 2 remittance corpus ===" -ForegroundColor Cyan
    try {
        python Day2_RAG\solutions\lab01_vector_ingestion.py *> $null
        Write-Host "Vector collection built."
    } catch {
        Write-Host "Skipped - run Day2_RAG\solutions\lab01_vector_ingestion.py manually."
    }
}

Write-Host "`n=== 4. Verification ===" -ForegroundColor Cyan
python 00_Program\verify_environment.py

Write-Host "`nNext:  python Day1_Foundations\labs\lab01_environment_and_telemetry.py"
