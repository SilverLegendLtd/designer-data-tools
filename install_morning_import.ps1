# Registers (or with -Remove, deletes) the daily Windows task that runs morning_import.ps1 at 06:45
# local time. StartWhenAvailable: if the PC is off at 06:45 the import runs soon after the next start.
param([switch]$Remove)

$name = 'GameDesign Morning Import'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    return
}
$script = Join-Path $PSScriptRoot 'morning_import.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$trigger = New-ScheduledTaskTrigger -Daily -At '06:45'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Runs game-design tools/import_data.py after the 06:00 Sheets export (Apps Script).' -Force |
    Select-Object TaskName, State
