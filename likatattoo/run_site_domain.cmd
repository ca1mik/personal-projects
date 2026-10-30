@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PORT=8812"
set "PUBLIC_IP=89.124.111.103"
set "CADDY_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Packages\CaddyServer.Caddy_Microsoft.Winget.Source_8wekyb3d8bbwe\caddy.exe"

if not exist "%CADDY_EXE%" (
  echo Caddy executable was not found at:
  echo   %CADDY_EXE%
  echo Install Caddy first or update this script.
  exit /b 1
)

cd /d "%ROOT%"

if not exist "%ROOT%deploy\caddy" mkdir "%ROOT%deploy\caddy"
if not exist "%ROOT%deploy\caddy\storage" mkdir "%ROOT%deploy\caddy\storage"
if not exist "%ROOT%deploy\caddy\config" mkdir "%ROOT%deploy\caddy\config"

netsh advfirewall firewall add rule name="ppdstr domain http 80" dir=in action=allow protocol=TCP localport=80 >nul 2>nul
netsh advfirewall firewall add rule name="ppdstr domain https 443" dir=in action=allow protocol=TCP localport=443 >nul 2>nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$site = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*serve_public_site.py*' }; if (-not $site) { Start-Process -WindowStyle Minimized -FilePath 'cmd.exe' -ArgumentList '/c', 'cd /d ""%ROOT%"" && python site\scripts\serve_public_site.py --host 127.0.0.1 --port %PORT% 1>site-server.out.log 2>site-server.err.log' | Out-Null }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*caddy.exe*deploy\caddy\Caddyfile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

if exist "%ROOT%deploy\caddy\caddy.out.log" del /f /q "%ROOT%deploy\caddy\caddy.out.log"
if exist "%ROOT%deploy\caddy\caddy.err.log" del /f /q "%ROOT%deploy\caddy\caddy.err.log"

echo Starting local domain proxy on ports 80 and 443...
start "ppdstr Domain Proxy" /min cmd /c "cd /d "%ROOT%" && ""%CADDY_EXE%"" run --config deploy\caddy\Caddyfile 1>deploy\caddy\caddy.out.log 2>deploy\caddy\caddy.err.log"

echo.
echo Local site upstream:
echo   http://127.0.0.1:%PORT%/
echo.
echo Local domain test:
echo   curl.exe -H "Host: ppdstr.online" http://127.0.0.1/
echo.
echo Domain target that must be set at the registrar:
echo   A @   -> %PUBLIC_IP%
echo   A www -> %PUBLIC_IP%
echo.
echo Once DNS points here, Caddy will serve the site on:
echo   http://ppdstr.online/
echo   https://ppdstr.online/
echo.
echo Logs:
echo   %ROOT%deploy\caddy\caddy.out.log
echo   %ROOT%deploy\caddy\caddy.err.log
