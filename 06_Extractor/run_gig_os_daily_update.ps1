$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\alvar\Documents\LOI_AI\06_Extractor"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogPath = Join-Path $ProjectRoot "logs\gig_os_daily_update_scheduler.log"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python virtualenv not found at $PythonExe"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting GIG-OS daily update" | Out-File -LiteralPath $LogPath -Append -Encoding utf8

Push-Location $ProjectRoot
try {
    & $PythonExe "main.py" --platform gig_os --daily-update --debug 2>&1 | Out-File -LiteralPath $LogPath -Append -Encoding utf8
    $exitCode = $LASTEXITCODE
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] Finished GIG-OS daily update with exit code $exitCode" | Out-File -LiteralPath $LogPath -Append -Encoding utf8
    exit $exitCode
}
finally {
    Pop-Location
}
