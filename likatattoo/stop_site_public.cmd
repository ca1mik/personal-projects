@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -and (($_.CommandLine -like '*serve_public_site.py*') -or ($_.CommandLine -like '*http.server 8812*'))) -or ($_.CommandLine -like '*localtunnel*--port 8812*') -or ($_.CommandLine -like '*cloudflared*8812*') -or ($_.CommandLine -like '*localhost.run*127.0.0.1:8812*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Site server and public tunnel stopped.
