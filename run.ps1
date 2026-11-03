# Start RoleEdge on http://localhost:8100 (another port: $env:PORT=8200; .\run.ps1).
# Run it with: powershell -ExecutionPolicy Bypass -File run.ps1
# The first run makes a Python environment in .venv and installs the app (a few minutes).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Port = if ($env:PORT) { $env:PORT } else { "8100" }
$env:PYTHONUTF8 = "1"  # files are UTF-8 (the Japanese family's text), as on macOS and Linux

function Test-Python([string[]]$Command) {
  if (-not (Get-Command $Command[0] -ErrorAction SilentlyContinue)) { return $false }
  $rest = @($Command | Select-Object -Skip 1)
  try { & $Command[0] @rest -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null } catch { return $false }
  return $LASTEXITCODE -eq 0
}

$Py = $null
foreach ($candidate in @(@("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"), @("python"), @("python3"))) {
  if (Test-Python $candidate) { $Py = $candidate; break }
}
if (-not $Py) {
  Write-Host "RoleEdge needs Python 3.11 or newer: winget install Python.Python.3.12 (then open a new PowerShell window)"
  exit 1
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "Note: ffmpeg isn't installed, so videos, reel links and voice recordings won't work (winget install Gyan.FFmpeg)."
  Write-Host "      Typed messages and web pages still do."
}

if (-not (Test-Path ".venv\Scripts\roleedge.exe")) {
  Write-Host "First run: installing RoleEdge into .venv ..."
  $rest = @($Py | Select-Object -Skip 1)
  & $Py[0] @rest -m venv .venv
  if ($LASTEXITCODE -ne 0) { Write-Host "Could not make a Python environment (see above)."; exit 1 }
  & .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
  & .venv\Scripts\python.exe -m pip install --quiet -e .
  if ($LASTEXITCODE -ne 0) { Write-Host "Installing failed (see above)."; exit 1 }
}

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
if (-not (Select-String -Path ".env" -Pattern '^META_API_KEY="?[^"\s]+' -Quiet)) {
  Write-Host "Add your Meta Model API key to the .env file in this folder (META_API_KEY=`"...`"), then run this again."
  exit 1
}
Write-Host "Checking the Meta key ..."
& .venv\Scripts\roleedge.exe check
if ($LASTEXITCODE -ne 0) { Write-Host "The Meta key didn't work (see above)."; exit 1 }

Write-Host ""
Write-Host "RoleEdge is starting. Open http://localhost:$Port"
Write-Host "  caregiver: http://localhost:$Port/studio      Linda's phone: http://localhost:$Port/phone/chen"
Write-Host "  Japanese family's phone: http://localhost:$Port/phone/sato      tuning lab: http://localhost:$Port/lab"
Write-Host "Stop it with Ctrl+C."
& .venv\Scripts\roleedge.exe serve --port $Port
