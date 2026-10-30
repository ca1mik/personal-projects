$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$guardianPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $guardianPython)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
    & $guardianPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
Write-Output 'Open http://127.0.0.1:8782 | Test data only | Ctrl+C to stop'
& $guardianPython -m uvicorn app:app --host 127.0.0.1 --port 8782
