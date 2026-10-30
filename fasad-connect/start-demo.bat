@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0python\python.exe" "%~dp0launch.py" --demo
if errorlevel 1 pause
