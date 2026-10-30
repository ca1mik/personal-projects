$ErrorActionPreference = 'Stop'
$agentRoot = $PSScriptRoot
$agentPython = Join-Path $agentRoot '.venv\Scripts\pythonw.exe'
$agentSupervisor = Join-Path $agentRoot 'supervisor.py'
if ((Test-Path -LiteralPath (Join-Path $agentRoot 'startup_chain.py')) -and ((Get-Content -LiteralPath (Join-Path $agentRoot 'config.json') -Raw | ConvertFrom-Json).startup_chain.enabled)) {
    $agentSupervisor = Join-Path $agentRoot 'startup_chain.py'
}
$agentAction = New-ScheduledTaskAction -Execute $agentPython -Argument ('"' + $agentSupervisor + '"') -WorkingDirectory $agentRoot
$agentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$agentPrincipal = New-ScheduledTaskPrincipal -UserId $agentUser -LogonType Interactive -RunLevel Limited
$agentTrigger = New-ScheduledTaskTrigger -AtLogOn -User $agentUser
$agentSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
try {
    Register-ScheduledTask -TaskName 'PersonalWindowsAgent' -Action $agentAction -Trigger $agentTrigger -Principal $agentPrincipal -Settings $agentSettings -Description 'Personal Telegram Windows agent; current user, interactive desktop, no elevation' -Force | Out-Null
    Write-Output 'Autostart: Task Scheduler PersonalWindowsAgent (interactive logon, limited user)'
} catch {
    $agentStartup = [Environment]::GetFolderPath('Startup')
    $agentShortcut = Join-Path $agentStartup 'PersonalWindowsAgent.lnk'
    $agentShell = New-Object -ComObject WScript.Shell
    $agentLink = $agentShell.CreateShortcut($agentShortcut)
    $agentLink.TargetPath = $agentPython
    $agentLink.Arguments = '"' + $agentSupervisor + '"'
    $agentLink.WorkingDirectory = $agentRoot
    $agentLink.WindowStyle = 7
    $agentLink.Save()
    Write-Output ('Task Scheduler unavailable; per-user Startup shortcut created: ' + $agentShortcut)
}
