@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PORT=8080"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*localtunnel*--port 8080*') -or ($_.CommandLine -like '*cloudflared*8080*') -or ($_.CommandLine -like '*localhost.run*127.0.0.1:8080*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

if exist "%ROOT%bot-tunnel.out.log" del /f /q "%ROOT%bot-tunnel.out.log"
if exist "%ROOT%bot-tunnel.err.log" del /f /q "%ROOT%bot-tunnel.err.log"

echo Starting public tunnel for the Robokassa callback server on port %PORT%...
start "ppdstr Bot Tunnel" /min cmd /c "cd /d "%ROOT%" && ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -T -R 80:127.0.0.1:%PORT% nokey@localhost.run 1>bot-tunnel.out.log 2>bot-tunnel.err.log"

echo.
echo Local callback health URL:
echo   http://127.0.0.1:%PORT%/robokassa/health
echo.
echo Public URL will appear in:
echo   %ROOT%bot-tunnel.out.log
echo.
echo Then set the public host in bot/.env and in the Robokassa cabinet:
echo   ROBOKASSA_RESULT_URL=https://PUBLIC-HOST/robokassa/result
echo   ROBOKASSA_SUCCESS_URL=https://PUBLIC-HOST/robokassa/success
echo   ROBOKASSA_FAIL_URL=https://PUBLIC-HOST/robokassa/fail
echo.
echo If the health endpoint does not open locally, start the bot first via run_tattoo_bot.cmd.
echo Keep the started tunnel window running while Robokassa callbacks should stay online.
