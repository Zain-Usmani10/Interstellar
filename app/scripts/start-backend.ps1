# Start the Interstellar backend (PowerShell). Usage: app\scripts\start-backend.ps1 [simulator|fpga]
# Creates .venv from requirements-core.txt on first run. Settings come from .env (see .env.example).
param([ValidateSet("simulator", "fpga")][string]$Mode)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv ..."
    py -3.10 -m venv .venv
    & .venv\Scripts\python.exe -m pip install -q -r requirements-core.txt
}
if ($Mode) { $env:TRANSPORT_MODE = $Mode }
& .venv\Scripts\python.exe -m app.backend.api
