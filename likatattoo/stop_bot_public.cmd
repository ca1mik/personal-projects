@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*localtunnel*--port 8080*') -or ($_.CommandLine -like '*cloudflared*8080*') -or ($_.CommandLine -like '*localhost.run*127.0.0.1:8080*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Robokassa public tunnel stopped.
