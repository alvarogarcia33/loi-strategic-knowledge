# Factory.DroneX - medicion blockchain

## Definicion del activo

`Factory.DroneX` representa una fabrica digital de drones premium. La documentacion de Olympia establece un supply maximo de `7000` fabricas.

## Regla corporativa

La wallet `0xBE55e36198D44b20886610AcC3d6c49B06B00C7A` fue identificada por el usuario como wallet de la empresa.

- Su balance forma parte del supply total.
- No debe contarse como wallet de socio.
- La reduccion de su balance entre snapshots puede indicar distribucion hacia otras wallets, pero no debe llamarse compra o creacion sin revisar las transacciones.

## Regla economica documentada

Olympia describe tres tramos para crear Factory.DroneX:

- unidades `1-1000`: 1 preFactoryDX + 1 GAMEGOS Coin + 1 HMAP Coin;
- unidades `1001-4000`: 2 preFactoryDX + 2 GAMEGOS Coin + 2 HMAP Coin;
- unidades `4001-7000`: 3 preFactoryDX + 3 GAMEGOS Coin + 3 HMAP Coin.

Fuente documental: `01_Olympia/markdown/30-05-2026_factory-dronex-fabrica-de-los-drones-premium_d45d3386a323.md`.

Con `2061` unidades observadas fuera de la wallet corporativa el 2026-07-02, el activo se encuentra cuantitativamente dentro del segundo tramo, siempre que el balance fuera de la empresa represente efectivamente fabricas creadas/distribuidas segun el contrato.

## Relaciones analiticas

- `preFactoryDX`: el anuncio oficial relaciona su obtencion con activaciones de PIN en H-MAP.
- `GAMEGOS Coin`: forma parte del costo de creacion y proviene del farming de PIN segun el contexto documental.
- `HMAP Coin`: forma parte del costo de creacion.

Por lo tanto, el crecimiento de Factory.DroneX puede funcionar como indicador indirecto de demanda de esos tres insumos. No permite determinar por si solo cuantas activaciones, compras o personas nuevas existieron.

