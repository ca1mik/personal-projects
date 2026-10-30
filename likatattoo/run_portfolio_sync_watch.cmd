@echo off
setlocal
cd /d "%~dp0"
python site\scripts\watch_portfolio_sync.py --source "F:\Yandex.Disk\ppdstr" --build-bundle
endlocal
