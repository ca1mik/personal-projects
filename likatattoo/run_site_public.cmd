@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PORT=8812"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -and (($_.CommandLine -like '*serve_public_site.py*') -or ($_.CommandLine -like '*http.server 8812*'))) -or ($_.CommandLine -like '*cloudflared*8812*') -or ($_.CommandLine -like '*localtunnel*--port 8812*') -or ($_.CommandLine -like '*localhost.run*127.0.0.1:8812*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

if exist "%ROOT%site-server.out.log" del /f /q "%ROOT%site-server.out.log"
if exist "%ROOT%site-server.err.log" del /f /q "%ROOT%site-server.err.log"
if exist "%ROOT%site-tunnel.out.log" del /f /q "%ROOT%site-tunnel.out.log"
if exist "%ROOT%site-tunnel.err.log" del /f /q "%ROOT%site-tunnel.err.log"

echo Starting local site server on port %PORT%...
start "ppdstr Site Server" /min cmd /c "cd /d "%ROOT%" && python site\scripts\serve_public_site.py --host 0.0.0.0 --port %PORT% 1>site-server.out.log 2>site-server.err.log"

timeout /t 2 /nobreak >nul

echo Starting public tunnel...
start "ppdstr Site Tunnel" /min cmd /c "cd /d "%ROOT%" && ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -T -R 80:127.0.0.1:%PORT% nokey@localhost.run 1>site-tunnel.out.log 2>site-tunnel.err.log"

start "" "http://127.0.0.1:%PORT%/"

echo.
echo Local URL:
echo   http://127.0.0.1:%PORT%/
echo.
echo Public URL will appear in:
echo   %ROOT%site-tunnel.out.log
echo.
echo Keep the started windows running while the site should stay online.
