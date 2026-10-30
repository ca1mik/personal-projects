# PowerShell script to record a demo video of the bot flow
# File: f:/test/scripts/record_demo.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 1. Start Docker Compose services
Write-Host "Starting Docker Compose services..."
docker compose up -d

# 2. Wait for the app health endpoint
$port = $env:APP_PORT
if (-not $port) { $port = "8000" }
$healthUrl = "http://localhost:${port}/health"
Write-Host "Waiting for health endpoint $healthUrl..."
while ($true) {
  try {
    $resp = curl -s $healthUrl
    if ($resp -match '"status"\s*:\s*"ok"') { break }
  } catch {}
  Start-Sleep -Seconds 2
}
Write-Host "App is ready."

# 3. Send a mock /start command via Telegram API if token is set
if ($env:TELEGRAM_BOT_TOKEN) {
  Write-Host "Sending /start to Telegram bot..."
  $payload = @{ chat_id = 123456; text = "/start" } | ConvertTo-Json -Compress
  Invoke-RestMethod -Uri "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/sendMessage" -Method Post -Body $payload -ContentType "application/json"
  Start-Sleep -Seconds 5
} else {
  Write-Host "No Telegram token – skipping Telegram call (mock mode)."
}

# 4. Record a 30‑second screen video using ffmpeg (gdigrab)
$artifactDir = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent)) "artifacts"
if (-not (Test-Path $artifactDir)) { New-Item -ItemType Directory -Path $artifactDir | Out-Null }
$outFile = Join-Path $artifactDir "demo_mock.mp4"
Write-Host "Recording demo (30s) to $outFile..."
ffmpeg -y -f gdigrab -framerate 25 -i desktop -t 30 -c:v libx264 -preset veryfast -crf 23 "$outFile"

# 5. Shut down Docker Compose services
Write-Host "Stopping Docker Compose services..."
docker compose down

Write-Host "Demo video saved at $outFile"
