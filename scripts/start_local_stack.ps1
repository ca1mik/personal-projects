$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

if (-not (Test-Path "apps\web\.env.local")) {
  Copy-Item "apps\web\.env.local.example" "apps\web\.env.local"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  throw "Python virtual environment not found at .venv. Create it first with python -m venv .venv"
}

Write-Host "Running runtime doctor..."
& ".\.venv\Scripts\python.exe" "scripts\runtime_doctor.py"

Write-Host ""
$queueMode = "redis"
$queueModeLine = Get-Content ".env" | Where-Object { $_ -match '^QUEUE_MODE=' } | Select-Object -First 1
if ($queueModeLine) {
  $queueMode = ($queueModeLine -split '=', 2)[1].Trim().ToLowerInvariant()
}

Write-Host ""
if ($queueMode -eq "redis") {
  Write-Host "Starting Redis with Docker Compose..."
  docker compose up redis -d
}
else {
  Write-Host "QUEUE_MODE=inline, skipping Redis and worker startup."
}

Write-Host ""
Write-Host "Starting API, worker, and web in new windows..."
Start-Process powershell -WorkingDirectory $root -ArgumentList @("-NoExit", "-Command", ".\.venv\Scripts\python.exe scripts\dev_api.py")
if ($queueMode -eq "redis") {
  Start-Process powershell -WorkingDirectory $root -ArgumentList @("-NoExit", "-Command", ".\.venv\Scripts\python.exe scripts\run_worker.py")
}
Start-Process powershell -WorkingDirectory $root -ArgumentList @("-NoExit", "-Command", "corepack pnpm --dir apps/web dev")

Write-Host ""
Write-Host "Local stack launch requested."
Write-Host "Web:  http://localhost:3000"
Write-Host "API:  http://localhost:8000"
Write-Host "Docs: http://localhost:8000/docs"
