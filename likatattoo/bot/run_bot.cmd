@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=.venv\Scripts\python.exe"
set "CREATED_VENV=0"

if not exist "%PYTHON_EXE%" (
  echo [setup] Virtual environment not found. Creating...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto :error
  set "CREATED_VENV=1"
)

if not exist "%PYTHON_EXE%" (
  echo [error] Could not create .venv\Scripts\python.exe
  goto :error
)

if "%CREATED_VENV%"=="1" (
  echo [setup] Installing dependencies...
  "%PYTHON_EXE%" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

echo [run] Starting Telegram bot...
"%PYTHON_EXE%" main.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [error] Bot stopped with exit code %EXIT_CODE%.
  pause
)

exit /b %EXIT_CODE%

:error
echo.
echo [error] Failed to start the bot.
pause
exit /b 1
