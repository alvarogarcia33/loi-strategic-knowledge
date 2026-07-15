param(
    [Parameter(Mandatory = $true)]
    [string]$AssetId
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $projectRoot "04_Datos_Blockchain\assets\$AssetId"
$snapshotDir = Join-Path $assetRoot "snapshots"
$reportDir = Join-Path $assetRoot "reportes"

$snapshotFiles = @(
    Get-ChildItem -LiteralPath $snapshotDir -File -Filter "*_holders.csv" |
        Sort-Object Name
)

if ($snapshotFiles.Count -lt 2) {
    Write-Host "Se necesitan al menos dos snapshots para comparar $AssetId."
    exit 0
}

$previousFile = $snapshotFiles[-2]
$currentFile = $snapshotFiles[-1]
$previousDate = $previousFile.BaseName.Substring(0, 10)
$currentDate = $currentFile.BaseName.Substring(0, 10)
$previousRows = @(Import-Csv -LiteralPath $previousFile.FullName)
$currentRows = @(Import-Csv -LiteralPath $currentFile.FullName)

function Convert-Balance([object]$value) {
    return [double]::Parse(
        [string]$value,
        [Globalization.NumberStyles]::Float,
        [Globalization.CultureInfo]::InvariantCulture
    )
}

function New-WalletMap([object[]]$rows) {
    $map = @{}
    foreach ($row in $rows) {
        $map[$row.wallet.ToLowerInvariant()] = $row
    }
    return $map
}

function Get-Metrics([object[]]$rows) {
    $companyRows = @($rows | Where-Object wallet_class -eq "empresa")
    $externalRows = @($rows | Where-Object wallet_class -ne "empresa")
    $companyBalance = ($companyRows | ForEach-Object { Convert-Balance $_.balance } | Measure-Object -Sum).Sum
    $externalBalance = ($externalRows | ForEach-Object { Convert-Balance $_.balance } | Measure-Object -Sum).Sum
    return [pscustomobject]@{
        company_wallets = $companyRows.Count
        company_balance = [double]$companyBalance
        external_wallets = $externalRows.Count
        external_balance = [double]$externalBalance
        total_supply = [double]($companyBalance + $externalBalance)
    }
}

$previousMap = New-WalletMap $previousRows
$currentMap = New-WalletMap $currentRows
$previousMetrics = Get-Metrics $previousRows
$currentMetrics = Get-Metrics $currentRows
$allWallets = @($previousMap.Keys + $currentMap.Keys | Sort-Object -Unique)
$changes = @()

foreach ($walletKey in $allWallets) {
    $previousRow = $previousMap[$walletKey]
    $currentRow = $currentMap[$walletKey]
    $previousBalance = if ($previousRow) { Convert-Balance $previousRow.balance } else { 0.0 }
    $currentBalance = if ($currentRow) { Convert-Balance $currentRow.balance } else { 0.0 }
    $walletClass = if ($currentRow) { $currentRow.wallet_class } else { $previousRow.wallet_class }
    $changes += [pscustomobject]@{
        wallet = if ($currentRow) { $currentRow.wallet } else { $previousRow.wallet }
        wallet_class = $walletClass
        previous_balance = $previousBalance
        current_balance = $currentBalance
        delta = $currentBalance - $previousBalance
        status = if (-not $previousRow) {
            "nueva"
        } elseif (-not $currentRow) {
            "sin_balance_actual"
        } elseif ($currentBalance -gt $previousBalance) {
            "aumento"
        } elseif ($currentBalance -lt $previousBalance) {
            "reduccion"
        } else {
            "sin_cambio"
        }
    }
}

$externalChanges = @($changes | Where-Object wallet_class -ne "empresa")
$newWallets = @($externalChanges | Where-Object status -eq "nueva")
$exitedWallets = @($externalChanges | Where-Object status -eq "sin_balance_actual")
$increasedWallets = @($externalChanges | Where-Object status -eq "aumento")
$decreasedWallets = @($externalChanges | Where-Object status -eq "reduccion")
$externalDelta = $currentMetrics.external_balance - $previousMetrics.external_balance
$companyDelta = $currentMetrics.company_balance - $previousMetrics.company_balance
$days = ([datetime]$currentDate - [datetime]$previousDate).Days
$dailyRate = if ($days -gt 0) { [math]::Round($externalDelta / $days, 4) } else { 0 }

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$changeCsvPath = Join-Path $reportDir "${previousDate}_vs_${currentDate}_wallet_changes.csv"
$reportPath = Join-Path $reportDir "${previousDate}_vs_${currentDate}_comparacion.md"
$changes | Sort-Object { [math]::Abs($_.delta) } -Descending |
    Export-Csv -LiteralPath $changeCsvPath -NoTypeInformation -Encoding utf8

$report = @"
# Comparacion blockchain - $AssetId - $previousDate a $currentDate

## Resultado ejecutivo

- Dias entre snapshots: **$days**.
- Balance externo anterior: **$($previousMetrics.external_balance)**.
- Balance externo actual: **$($currentMetrics.external_balance)**.
- Variacion externa neta: **$externalDelta**.
- Variacion media diaria: **$dailyRate unidades/dia**.
- Wallets externas anteriores: **$($previousMetrics.external_wallets)**.
- Wallets externas actuales: **$($currentMetrics.external_wallets)**.
- Wallets nuevas observadas: **$($newWallets.Count)**.
- Wallets sin balance actual: **$($exitedWallets.Count)**.
- Wallets con aumento: **$($increasedWallets.Count)**.
- Wallets con reduccion: **$($decreasedWallets.Count)**.

## Reconciliacion

- Supply anterior: **$($previousMetrics.total_supply)**.
- Supply actual: **$($currentMetrics.total_supply)**.
- Cambio del balance corporativo: **$companyDelta**.
- Cambio del balance externo: **$externalDelta**.

Si el supply permanece constante, una reduccion corporativa equivalente al aumento externo es consistente con distribucion desde la empresa. Para llamarla compra, creacion o activacion se requiere revisar transacciones y reglas del contrato.

## Lectura analitica permitida

- Los cambios de balance son hechos observados entre snapshots.
- Las wallets nuevas muestran nuevas direcciones con balance, no necesariamente personas nuevas.
- La variacion externa mide distribucion neta, no volumen bruto de transferencias.
- Una wallet puede transferir activos a otra sin que exista una compra nueva.

## Archivos comparados

- Anterior: **$($previousFile.Name)**
- Actual: **$($currentFile.Name)**
- Detalle por wallet: **$([IO.Path]::GetFileName($changeCsvPath))**
"@
$report | Set-Content -LiteralPath $reportPath -Encoding utf8

Write-Host "Comparacion generada"
Write-Host "Reporte: $reportPath"
Write-Host "Cambios: $changeCsvPath"
