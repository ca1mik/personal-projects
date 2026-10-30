$ErrorActionPreference = 'Stop'
$agentRoot = $PSScriptRoot
Set-Content -LiteralPath (Join-Path $agentRoot 'STOP') -Value 'Local emergency stop' -Encoding utf8
& (Join-Path $agentRoot '.venv\Scripts\python.exe') (Join-Path $agentRoot 'manage.py') stop
Write-Output 'Emergency stop requested; supervisor will exit. Start-Agent.ps1 starts it again; /resume clears task pause.'
