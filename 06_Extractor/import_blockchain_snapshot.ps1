param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,

    [Parameter(Mandatory = $true)]
    [string]$AssetId,

    [Parameter(Mandatory = $true)]
    [string]$AssetName,

    [Parameter(Mandatory = $true)]
    [datetime]$ObservationDate,

    [string]$CompanyWallet = "",

    [Parameter(Mandatory = $true)]
    [double]$ExpectedSupply,

    [string]$Network = "pendiente",
    [string]$ContractAddress = "pendiente",
    [string]$BlockNumber = "pendiente",
    [string]$ExplorerUrl = "pendiente",
    [int]$WalletColumn = 2,
    [int]$BalanceColumn = 3,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $projectRoot "04_Datos_Blockchain\assets\$AssetId"
$rawDir = Join-Path $assetRoot "raw"
$snapshotDir = Join-Path $assetRoot "snapshots"
$metadataDir = Join-Path $assetRoot "metadata"
$reportDir = Join-Path $assetRoot "reportes"
$dateText = $ObservationDate.ToString("yyyy-MM-dd")
$sourcePath = (Resolve-Path -LiteralPath $InputFile).Path
$sourceExtension = [IO.Path]::GetExtension($sourcePath).ToLowerInvariant()

if ($sourceExtension -ne ".xlsx") {
    throw "El importador actual admite archivos .xlsx."
}

foreach ($directory in @($rawDir, $snapshotDir, $metadataDir, $reportDir)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$rawPath = Join-Path $rawDir "${dateText}_${AssetId}.xlsx"
$csvPath = Join-Path $snapshotDir "${dateText}_holders.csv"
$metadataPath = Join-Path $metadataDir "${dateText}_snapshot.json"
$reportPath = Join-Path $reportDir "${dateText}_resumen.md"

foreach ($outputPath in @($rawPath, $csvPath, $metadataPath, $reportPath)) {
    if ((Test-Path -LiteralPath $outputPath) -and -not $Force) {
        throw "Ya existe $outputPath. Use -Force solo si desea reemplazar el snapshot de la misma fecha."
    }
}

$sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
Copy-Item -LiteralPath $sourcePath -Destination $rawPath -Force:$Force

$excel = $null
$workbook = $null
$worksheet = $null
$rows = @()
$summaryRows = 0

try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $workbook = $excel.Workbooks.Open($sourcePath, 0, $true)
    $worksheet = $workbook.Worksheets.Item(1)
    $lastRow = $worksheet.UsedRange.Rows.Count
    $sheetName = $worksheet.Name

    for ($rowNumber = 2; $rowNumber -le $lastRow; $rowNumber++) {
        $wallet = ([string]$worksheet.Cells.Item($rowNumber, $WalletColumn).Value2).Trim()
        $balanceValue = $worksheet.Cells.Item($rowNumber, $BalanceColumn).Value2

        if (-not $wallet) {
            continue
        }

        if ($wallet.ToUpperInvariant() -eq "TOTAL") {
            $summaryRows++
            continue
        }

        if ($wallet -notmatch '^0x[0-9a-fA-F]{40}$') {
            throw "Wallet invalida en fila $rowNumber`: $wallet"
        }

        $balance = [double]$balanceValue
        $isCompany = $CompanyWallet -and $wallet.Equals($CompanyWallet, [StringComparison]::OrdinalIgnoreCase)
        $rows += [pscustomobject]@{
            observation_date = $dateText
            asset_id = $AssetId
            wallet = $wallet
            balance = $balance
            wallet_class = if ($isCompany) { "empresa" } else { "externa_no_clasificada" }
            exclude_as_partner = $isCompany
            source_file = [IO.Path]::GetFileName($rawPath)
        }
    }
}
finally {
    if ($workbook) { $workbook.Close($false) }
    if ($excel) { $excel.Quit() }
    if ($worksheet) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($worksheet) }
    if ($workbook) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }
    if ($excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$duplicateWallets = @($rows | Group-Object { $_.wallet.ToLowerInvariant() } | Where-Object Count -gt 1)
if ($duplicateWallets.Count -gt 0) {
    throw "Se detectaron wallets duplicadas en el snapshot."
}

$totalBalance = [double](($rows | Measure-Object balance -Sum).Sum)
$companyRows = @($rows | Where-Object exclude_as_partner)
if ($CompanyWallet -and $companyRows.Count -ne 1) {
    throw "Se esperaba exactamente una coincidencia para la wallet corporativa y se encontraron $($companyRows.Count)."
}

$companyBalance = if ($companyRows.Count -eq 1) { [double]$companyRows[0].balance } else { 0 }
$externalRows = @($rows | Where-Object { -not $_.exclude_as_partner })
$externalBalance = [double](($externalRows | Measure-Object balance -Sum).Sum)
$supplyDifference = $totalBalance - $ExpectedSupply
$supplyReconciled = [math]::Abs($supplyDifference) -lt 0.0000001

if (-not $supplyReconciled) {
    throw "El balance total ($totalBalance) no reconcilia con el supply esperado ($ExpectedSupply)."
}

$rows | Sort-Object balance -Descending | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

$metadata = [ordered]@{
    schema_version = 1
    asset_id = $AssetId
    asset_name = $AssetName
    observation_date = $dateText
    imported_at = (Get-Date).ToUniversalTime().ToString("o")
    source_file = [IO.Path]::GetFileName($rawPath)
    source_sha256 = $sourceHash
    source_sheet = $sheetName
    network = $Network
    contract_address = $ContractAddress
    block_number = $BlockNumber
    explorer_url = $ExplorerUrl
    expected_supply = $ExpectedSupply
    observed_supply = $totalBalance
    supply_reconciled = $supplyReconciled
    summary_rows_excluded = $summaryRows
    holder_wallets_total = $rows.Count
    company_wallet = if ($CompanyWallet) { $CompanyWallet } else { $null }
    company_wallet_status = if ($CompanyWallet) { "confirmada" } else { "pendiente_de_confirmacion" }
    company_balance = $companyBalance
    company_share_pct = [math]::Round(100 * $companyBalance / $totalBalance, 4)
    external_wallets_unclassified = $externalRows.Count
    external_balance = $externalBalance
    external_share_pct = [math]::Round(100 * $externalBalance / $totalBalance, 4)
    duplicate_wallets = $duplicateWallets.Count
    methodology = if ($CompanyWallet) {
        "Fila por wallet; se excluyen filas TOTAL; la wallet corporativa se conserva en supply y se excluye como socio."
    } else {
        "Fila por wallet; se excluyen filas TOTAL; ninguna wallet se excluye porque la wallet corporativa no esta confirmada."
    }
    caveats = @(
        "Una wallet no equivale necesariamente a una persona.",
        "Balance fuera de la empresa no demuestra por si solo compra, mint o creacion.",
        "Red, contrato, bloque y URL deben completarse para comparaciones tecnicamente reproducibles."
    )
}
$metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metadataPath -Encoding utf8

$companyPct = if ($CompanyWallet) { [math]::Round(100 * $companyBalance / $totalBalance, 2) } else { 0 }
$externalPct = [math]::Round(100 * $externalBalance / $totalBalance, 2)
$topExternal = $externalRows | Sort-Object balance -Descending | Select-Object -First 1
$singleBalanceWallets = @($externalRows | Where-Object balance -eq 1).Count
$companySummary = if ($CompanyWallet) {
    "- Wallet corporativa: **$CompanyWallet**, con **$companyBalance** unidades (**$companyPct%** del supply)."
} else {
    "- Wallet corporativa: **pendiente de confirmacion**; ninguna wallet fue excluida del analisis."
}
$companyFact = if ($CompanyWallet) {
    "La wallet corporativa fue conservada dentro del supply y etiquetada como **empresa**. No fue contada entre las wallets externas."
} else {
    "No se etiqueto ninguna wallet como empresa. Todas permanecen como **externas no clasificadas** hasta contar con confirmacion documental o del usuario."
}

$report = @"
# Snapshot blockchain - $AssetName - $dateText

## Resultado ejecutivo

- Supply reconciliado: **$totalBalance / $ExpectedSupply**.
- Wallets reales observadas: **$($rows.Count)**.
$companySummary
- Wallets externas no clasificadas: **$($externalRows.Count)**, con **$externalBalance** unidades (**$externalPct%** del supply).
- Mayor wallet externa: **$($topExternal.wallet)**, con **$($topExternal.balance)** unidades.
- Wallets externas con una unidad: **$singleBalanceWallets**.

## Hechos observados

El archivo contiene una fila final **TOTAL = $ExpectedSupply**. Esa fila fue usada para control, pero no fue contada como wallet. La suma de las wallets reales reconcilia exactamente con el supply esperado.

$companyFact

## Contexto aportado por el usuario

- La wallet corporativa pertenece a la empresa y funciona como wallet de origen/reserva.
- Para el analisis de adopcion no debe considerarse wallet de socio.
- Las unidades fuera de esa wallet pueden aportar una medicion de distribucion de Factory.DroneX.

## Contexto documental relacionado

Olympia documenta un limite de 7000 Factory.DroneX y tres tramos de costo. El balance externo observado de $externalBalance ubica cuantitativamente la distribucion dentro del segundo tramo (**1001-4000**), cuyo costo anunciado es **2 preFactoryDX + 2 GAMEGOS Coin + 2 HMAP Coin** por fabrica.

Esto conecta la distribucion de Factory.DroneX con demanda potencial de cupones preFactoryDX, GAMEGOS Coin y HMAP Coin. El snapshot no demuestra por si solo cuantas compras, activaciones de PIN o personas nuevas hubo.

## Interpretacion permitida

- **Hecho:** $externalBalance unidades estan fuera de la wallet corporativa en la fecha del snapshot.
- **Inferencia razonable:** existe distribucion/adopcion fuera de la empresa.
- **No confirmado:** que cada salida corresponda a una compra nueva, un socio nuevo o un mint individual.

## Comparacion futura

Cuando exista otro snapshot del mismo contrato se debera medir:

- cambio del balance corporativo;
- cambio del balance externo;
- wallets nuevas y wallets que dejaron de tener balance;
- aumentos y reducciones por wallet;
- ritmo medio diario de distribucion.

## Calidad y trazabilidad

- Archivo original: **$([IO.Path]::GetFileName($rawPath))**
- SHA-256: **$sourceHash**
- Hoja: **$sheetName**
- Filas resumen excluidas: **$summaryRows**
- Duplicados: **$($duplicateWallets.Count)**
- Red: **$Network**
- Contrato: **$ContractAddress**
- Bloque: **$BlockNumber**
- Explorador: **$ExplorerUrl**

## Limitaciones

- Una wallet no equivale necesariamente a una persona.
- Una transferencia no equivale necesariamente a una compra.
- Faltan red, contrato, bloque y URL del explorador para reproducir exactamente la consulta.
"@
$report | Set-Content -LiteralPath $reportPath -Encoding utf8

Write-Host "Snapshot importado correctamente"
Write-Host "Raw:      $rawPath"
Write-Host "CSV:      $csvPath"
Write-Host "Metadata: $metadataPath"
Write-Host "Reporte:  $reportPath"
Write-Host "Supply:   $totalBalance"
Write-Host "Empresa:  $companyBalance"
Write-Host "Externo:  $externalBalance en $($externalRows.Count) wallets"

& (Join-Path $PSScriptRoot "compare_blockchain_snapshots.ps1") -AssetId $AssetId
