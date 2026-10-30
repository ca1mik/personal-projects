@echo off
cd /d "%~dp0"
"%~dp0python\python.exe" "%~dp0launch.py" --stop
"%~dp0python\python.exe" "%~dp0launch.py" --stop --demo
