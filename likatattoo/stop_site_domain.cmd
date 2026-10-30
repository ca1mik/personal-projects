@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*caddy.exe*deploy\caddy\Caddyfile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Domain proxy stopped. Public site server was left running.
