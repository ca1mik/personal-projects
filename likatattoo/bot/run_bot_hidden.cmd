@echo off
setlocal
cd /d "%~dp0"
if not exist "data" mkdir "data"
".venv\Scripts\python.exe" main.py 1>>"data\bot.out.log" 2>>"data\bot.err.log"
