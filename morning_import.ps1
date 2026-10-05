# Morning import (Windows Task Scheduler "GameDesign Morning Import", daily 06:45; runs at next
# start-up if the PC was off). Runs import_data.py on the CSVs the Apps Script exported at 06:00,
# appends the output to %LOCALAPPDATA%\game-design\import.log, and posts to Slack if it failed
# (user environment variable SLACK_WEBHOOK_URL, the same webhook the Apps Script uses).
# Results land in design/data and the game repos uncommitted, for review.
# Install / remove: tools/install_morning_import.ps1 [-Remove]

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $env:LOCALAPPDATA 'game-design'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'import.log'

$started = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$output = & python (Join-Path $repo 'tools\import_data.py') 2>&1 | Out-String
$code = $LASTEXITCODE
Add-Content -Path $log -Encoding utf8 -Value "===== $started exit $code`n$output"

$webhook = [Environment]::GetEnvironmentVariable('SLACK_WEBHOOK_URL', 'User')
if ($code -ne 0 -and $webhook) {
    $tail = ($output -split "`n" | Select-Object -Last 25) -join "`n"
    $body = @{ text = "*Morning import FAILED on $env:COMPUTERNAME* (exit $code)`n``````$tail``````" } | ConvertTo-Json
    Invoke-RestMethod -Uri $webhook -Method Post -ContentType 'application/json; charset=utf-8' `
        -Body ([Text.Encoding]::UTF8.GetBytes($body)) | Out-Null
}
exit $code
