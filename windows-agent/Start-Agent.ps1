$ErrorActionPreference = 'Stop'
$agentRoot = $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $agentRoot 'STOP')) { Remove-Item -LiteralPath (Join-Path $agentRoot 'STOP') }
$agentPython = Join-Path $agentRoot '.venv\Scripts\pythonw.exe'
$agentSupervisor = Join-Path $agentRoot 'supervisor.py'
if ((Test-Path -LiteralPath (Join-Path $agentRoot 'startup_chain.py')) -and ((Get-Content -LiteralPath (Join-Path $agentRoot 'config.json') -Raw | ConvertFrom-Json).startup_chain.enabled)) {
    $agentSupervisor = Join-Path $agentRoot 'startup_chain.py'
}
try {
    $agentTask = Get-ScheduledTask -TaskName 'PersonalWindowsAgent' -ErrorAction Stop
    if ($agentTask.Actions.Execute -eq $agentPython -and $agentTask.Actions.Arguments -eq ('"' + $agentSupervisor + '"')) {
        Start-ScheduledTask -TaskName 'PersonalWindowsAgent' -ErrorAction Stop
        Write-Output 'Agent started through Task Scheduler. Check manage.py status.'
        return
    }
} catch { }
Start-Process -FilePath $agentPython -ArgumentList @(('"' + $agentSupervisor + '"')) -WorkingDirectory $agentRoot -WindowStyle Hidden
Write-Output 'Agent supervisor launched. Check .venv\Scripts\python.exe manage.py status'
