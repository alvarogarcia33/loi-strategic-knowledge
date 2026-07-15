param(
    [string]$TaskName = "LOI_AI Full Daily Sync",
    [string]$DailyAt = "09:00"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "run_full_daily_sync.ps1"

if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "No se encontro el ejecutor diario: $scriptPath"
}

try {
    $triggerTime = [datetime]::ParseExact(
        $DailyAt,
        "HH:mm",
        [Globalization.CultureInfo]::InvariantCulture
    )
}
catch {
    throw "La hora debe usar formato HH:mm, por ejemplo 09:00."
}

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$powerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$scriptPath`""

$action = New-ScheduledTaskAction `
    -Execute $powerShellExe `
    -Argument $arguments `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Actualiza Olympia y GIG-OS, regenera dossiers estrategicos y sincroniza el repositorio privado de GitHub."

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null

$registered = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host "Tarea registrada correctamente"
Write-Host "Nombre: $TaskName"
Write-Host "Usuario: $currentUser"
Write-Host "Estado: $($registered.State)"
Write-Host "Proxima ejecucion: $($info.NextRunTime)"
Write-Host "Ejecutor: $scriptPath"
