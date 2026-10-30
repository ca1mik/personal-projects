$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$agentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
New-Item -ItemType Directory -Force -Path data,backups | Out-Null
icacls '.\data' /inheritance:r /grant:r "*${agentSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
icacls '.\backups' /inheritance:r /grant:r "*${agentSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
Write-Output 'Installed. Configure secrets locally using .venv\Scripts\python.exe manage.py secret telegram'
