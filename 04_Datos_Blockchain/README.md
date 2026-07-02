# Datos blockchain

Esta carpeta conserva snapshots fechados de distribucion de tokens, NFT, cupones y otros activos del ecosistema. Su objetivo es contrastar anuncios de Olympia y GIG-OS con evidencia cuantitativa observable en blockchain.

## Estructura

Cada activo tiene su propia carpeta:

```text
assets/<activo>/
|- raw/         # Exportaciones originales sin modificar
|- snapshots/   # CSV normalizado, una fila por wallet
|- metadata/    # Procedencia, reglas, hash y controles de calidad
`- reportes/    # Resumen legible para ChatGPT
```

El nombre obligatorio de cada snapshot comienza con la fecha de observacion:

```text
YYYY-MM-DD_<activo>.xlsx
YYYY-MM-DD_holders.csv
YYYY-MM-DD_snapshot.json
YYYY-MM-DD_resumen.md
```

## Jerarquia de evidencia

- `raw`: evidencia original exportada del explorador.
- `snapshots`: representacion normalizada del archivo original.
- `metadata`: reglas de clasificacion, procedencia y controles de calidad.
- `reportes`: metricas derivadas e interpretacion cautelosa.

Los datos blockchain se consideran evidencia cuantitativa observada. No reemplazan los anuncios oficiales y tampoco convierten automaticamente una wallet en una persona.

## Reglas de medicion

1. Conservar siempre el archivo original y su hash SHA-256.
2. Registrar fecha, red, contrato y bloque cuando esten disponibles.
3. Excluir filas de totales del conjunto de wallets, pero reconciliarlas con el supply.
4. Conservar las wallets corporativas en el snapshot y etiquetarlas como `empresa`.
5. No contar una wallet corporativa como wallet de socio.
6. Llamar `wallet externa no clasificada` a toda wallet cuya titularidad no este confirmada.
7. No equiparar wallets con personas ni transferencias con compras sin evidencia adicional.
8. Comparar siempre snapshots del mismo contrato, red y criterio de clasificacion.

## Comparaciones temporales

Con dos o mas snapshots del mismo activo se podran calcular:

- variacion del balance corporativo;
- variacion del balance fuera de la empresa;
- wallets nuevas, desaparecidas o con cambio de balance;
- concentracion y dispersion de la tenencia;
- ritmo de distribucion entre fechas.

La interpretacion economica debe cruzarse con las reglas documentadas en `01_Olympia`, `02_GIG_OS` y las señales de `03_Reuniones_Presidencia`.

El importador local genera el snapshot y, cuando existen al menos dos fechas para el activo, compara automaticamente las dos mas recientes:

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
.\import_blockchain_snapshot.ps1 `
  -InputFile "C:\ruta\YYYY-MM-DD_activo.xlsx" `
  -AssetId "activo" `
  -AssetName "Nombre del activo" `
  -ObservationDate "YYYY-MM-DD" `
  -CompanyWallet "0x..." `
  -ExpectedSupply 7000
```

## Datos pendientes que mejoran la trazabilidad

- blockchain y chain ID;
- direccion del contrato;
- numero de bloque del snapshot;
- URL exacta del explorador;
- definicion tecnica de mint, burn y transferencias del activo.
