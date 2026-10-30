$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' -X utf8 manage.py secret telegram
Write-Output 'Token updated. Use Stop-Agent.ps1, Start-Agent.ps1 and /resume to reload it.'
