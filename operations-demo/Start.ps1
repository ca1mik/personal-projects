$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$demoPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3 is required.' }
    & $demoPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $demoPython -c 'import fastapi, uvicorn, openpyxl' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $demoPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
Write-Output 'Open http://127.0.0.1:8769  |  Ctrl+C to stop'
& $demoPython -m uvicorn app:app --host 127.0.0.1 --port 8769
