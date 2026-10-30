@echo off
cd /d "%~dp0"
python repeater_gui.py
if errorlevel 1 pause
