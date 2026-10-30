@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,openpyxl" 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto error
)
echo Open http://127.0.0.1:8769 in your browser. Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8769
pause
exit /b
:error
echo Install Python 3.12 or newer and check Internet access for first setup.
pause
