@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PORT=8888"

cd /d "%ROOT%"

echo Starting ppdstr site server on port %PORT%...
echo Local URL: http://127.0.0.1:%PORT%/
echo Network URL: http://YOUR_PC_IP:%PORT%/
echo.
echo Keep this window open while the site should stay online.
echo Press Ctrl+C to stop the server.
echo.

start "" "http://127.0.0.1:%PORT%/"
python site\scripts\serve_public_site.py --host 0.0.0.0 --port %PORT%
