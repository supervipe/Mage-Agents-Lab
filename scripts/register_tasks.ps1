$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create the .venv and install dependencies first.' }

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
$worker = New-ScheduledTaskAction -Execute $python -Argument '-m app.worker' -WorkingDirectory $projectRoot
$web = New-ScheduledTaskAction -Execute $python -Argument '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $projectRoot

Register-ScheduledTask -TaskName 'MageAgentsLabWorker' -Action $worker -Trigger $trigger -Settings $settings -Description 'Checks Gmail and news for Mage Agents Lab' -Force | Out-Null
Register-ScheduledTask -TaskName 'MageAgentsLabDashboard' -Action $web -Trigger $trigger -Settings $settings -Description 'Local Mage Agents Lab dashboard' -Force | Out-Null
Write-Host 'Tasks registered. Sign out and back in, or start them in Task Scheduler.'
