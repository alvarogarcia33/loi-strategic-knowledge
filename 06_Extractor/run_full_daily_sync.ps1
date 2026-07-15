$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\alvar\Documents\LOI_AI\06_Extractor"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SystemPython = "C:\Python314\python.exe"
$PythonExe = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { $SystemPython }
$LogPath = Join-Path $ProjectRoot "logs\full_daily_sync_scheduler.log"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
$OutputEncoding = New-Object Text.UTF8Encoding $false

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python no encontrado. Rutas revisadas: $VenvPython y $SystemPython"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

if ((Test-Path -LiteralPath $LogPath) -and (Get-Item -LiteralPath $LogPath).Length -gt 5MB) {
    $archivePath = Join-Path (Split-Path -Parent $LogPath) "full_daily_sync_scheduler.previous.log"
    Move-Item -LiteralPath $LogPath -Destination $archivePath -Force
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting full daily sync" | Out-File -LiteralPath $LogPath -Append -Encoding utf8

Push-Location $ProjectRoot
try {
    & $PythonExe "sync_github.py" 2>&1 | Out-File -LiteralPath $LogPath -Append -Encoding utf8
    $exitCode = $LASTEXITCODE
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] Finished full daily sync with exit code $exitCode" | Out-File -LiteralPath $LogPath -Append -Encoding utf8
    exit $exitCode
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] Full daily sync failed: $($_.Exception.Message)" | Out-File -LiteralPath $LogPath -Append -Encoding utf8
    exit 1
}
finally {
    Pop-Location
}
