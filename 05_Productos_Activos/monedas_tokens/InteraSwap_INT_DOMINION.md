# InteraSwap: INT Coin, DOMINION Coin y mecanismos de intercambio

- Fecha de consolidacion: 2026-09-03
- Fuentes revisadas: Olympia, GIG-OS y dossiers estrategicos locales
- Mecanismo principal: pool DEX bidireccional `INT Coin <-> DOMINION Coin`
- Estado de precio: dinamico; no existe una equivalencia fija vigente en la base

## Conclusion ejecutiva

InteraSwap no fija un precio estable para INT Coin ni para DOMINION Coin. El pool establece un tipo de cambio dinamico entre ambas monedas y cada transaccion modifica las condiciones futuras. La base permite documentar el mecanismo, las comisiones historicas, el cashback y otras rutas de obtencion de INT, pero no permite declarar un precio actual en EUR para INT o DOMINION.

## Estado de valor por moneda

| Moneda o activo | Valor fijo documentado | Mecanismo de valor o intercambio | Estado |
|---|---:|---|---|
| INT Coin | No | Intercambio bidireccional con DOMINION en InteraSwap; creacion mediante GOS#; farming o conversiones historicas | Variable |
| DOMINION Coin | No | Intercambio bidireccional con INT en InteraSwap; farming finalizado el 15.07.2026 | Variable y condicionado por el pool |
| M*E Coin | No | Conversion a INT al tipo vigente; primera operacion sin comision, siguientes con 10 % en INT | Tasa dinamica no registrada |
| GICO Coin | No | Staking historico para producir INT y participacion en otros programas | Sin equivalencia EUR canonica |
| GOS Coin | No | Comision historica para farming de INT | Sin equivalencia EUR canonica |
| GOS# | No | Saldo especifico utilizable para crear INT Coin | Ratio de creacion no documentado |
| inBTC, inETH y ESCUDO | No en esta ficha | Intercambio bidireccional por REEX mediante MetaFi | Tipo confirmado al ejecutar |

## Funcionamiento documentado de InteraSwap

- Lanzamiento anunciado el 16.04.2026 como herramienta DeFi y pool DEX.
- Par inicial y documentado: `INT Coin / DOMINION Coin`.
- Opera en ambos sentidos: INT por DOMINION y DOMINION por INT.
- Cada transaccion influye en el tipo de cambio futuro.
- Un volumen alto en una direccion puede volver mas favorable la direccion inversa.
- El tamano del pool aumenta con la actividad de usuarios.
- La interfaz incluye graficos para monitorear el tipo de cambio en tiempo real.
- La base no contiene capturas numericas del tipo de cambio vigente ni del tamano del pool.

## Comisiones anunciadas al lanzamiento

La fuente del 16.04.2026 indico que estas comisiones aumentarian dos meses despues. Por eso deben tratarse como **condiciones historicas de lanzamiento**, no como tarifas vigentes en septiembre de 2026.

| Volumen intercambiado | Comision anunciada por INT | Equivalente EUR por INT | Porcentaje aproximado al lanzamiento |
|---:|---:|---:|---:|
| 1.000 INT o mas | 0,05 REEX | 1,25 EUR | 1,55 % |
| Entre 500 y 1.000 INT | 0,06 REEX | 1,50 EUR | 1,85 % |
| Entre 100 y 500 INT | 0,07 REEX | 1,75 EUR | 2,15 % |
| Entre 25 y 100 INT | 0,08 REEX | 2,00 EUR | 2,50 % |
| Entre 1 y 25 INT | 0,10 REEX | 2,50 EUR | 3,10 % |

Conversion utilizada: `1 REEX = 25 EUR`.

La redaccion original superpone los extremos de algunos intervalos. Para una operacion situada exactamente en un limite debe consultarse la interfaz y no inferirse el tramo.

## Referencia matematica historica

Al dividir la comision por el porcentaje aproximado informado, se obtiene un importe unitario implicito al lanzamiento de aproximadamente `3,20 a 3,26 REEX por INT`, equivalente a `80,00 a 81,40 EUR por INT`.

```text
Importe implicito = comision REEX por INT / porcentaje de comision
```

Esta cifra es una **inferencia matematica historica**, no una cotizacion oficial de INT, no establece el ratio INT/DOMINION y no debe usarse como precio actual.

## CashBack

- 10 o mas transacciones en una direccion: recuperacion del 10 % de las comisiones.
- 50 o mas transacciones en una direccion: recuperacion del 20 % de las comisiones.
- El conteo y el cashback se calculan por separado para `INT -> DOMINION` y `DOMINION -> INT`.
- El cashback se paga en HMAP Coin.
- Las comisiones se contabilizan desde la primera transaccion y el usuario puede reclamar el cashback al cumplir la condicion.

### Costo economico historico despues de cashback

| Comision bruta | EUR bruto | EUR tras cashback 10 % | EUR tras cashback 20 % |
|---:|---:|---:|---:|
| 0,05 REEX | 1,25 | 1,13 | 1,00 |
| 0,06 REEX | 1,50 | 1,35 | 1,20 |
| 0,07 REEX | 1,75 | 1,58 | 1,40 |
| 0,08 REEX | 2,00 | 1,80 | 1,60 |
| 0,10 REEX | 2,50 | 2,25 | 2,00 |

El cashback se recibe en HMAP y no reduce directamente la comision pagada en REEX. La tabla expresa equivalencia economica usando `1 HMAP = 50 EUR` y `1 REEX = 25 EUR`.

## Campana inicial de premios

Durante las primeras cuatro semanas se premio cada miercoles al usuario con mayor volumen de INT intercambiado durante los siete dias anteriores:

- devolucion del 50 % de comisiones en HMAP;
- una cantidad de INT igual al numero de REEX gastados en comisiones;
- una cantidad de DOMINION igual al numero de REEX gastados en comisiones.

Ejemplo documentado: 100 REEX pagados en comisiones generaban un premio de 25 HMAP, 100 INT y 100 DOMINION. Esta campana concluyo en mayo de 2026 y no es una condicion vigente.

El ejemplo valida la conversion entre HMAP y REEX para la devolucion del 50 %, pero no demuestra que 1 INT o 1 DOMINION tengan el mismo valor que 1 REEX. Las cantidades adicionales eran premios.

## Otros mecanismos documentados para obtener o convertir INT

### H-MAP System

- H-MAP.9: las combinaciones otorgaban la misma cantidad de INT que anteriormente se acreditaba en DOMINION; la fuente no incluye el ratio numerico.
- H-MAP.7PRO: `50 FARMING POINTS = 1 INT Coin`.
- El 20.08.2026 se amplio la posibilidad de recibir INT por combinaciones hasta el 05.11.2026.

### Farming historico de INT en NETSBO

Condiciones anunciadas el 10.06.2025:

```text
10 GICO Coin o 15 M*E Coin = 1 paquete
1 paquete = 1 INT Coin en 30 dias
Comision = 1 GOS Coin
```

Estas condiciones tenian plazos especificos y deben conservarse como antecedente historico, no como mecanismo vigente sin una nueva verificacion.

### Conversion M*E Coin por INT Coin

- Conversion al tipo de cambio vigente.
- Primera operacion sin comision.
- Operaciones posteriores: comision del 10 % del monto de la transaccion, pagada en INT.
- El articulo no registra el tipo numerico M*E/INT.

### Creacion mediante GOS#

La cuenta GOS# recibe premios por combinaciones de System Transformator y ese saldo puede utilizarse para crear INT Coin. La base no contiene el ratio GOS#/INT.

### MetaFi para obtener REEX

- Activos de entrada documentados: inBTC, inETH o ESCUDO.
- Intercambio bidireccional con REEX mediante IA Wallet y el modulo MetaFi.
- La pantalla inicial muestra una tasa aproximada; la tasa actualizada aparece antes de confirmar y es la aplicada a la operacion.

## Relacion economica y operativa

- INT es la unidad funcional de Interatum: pago, staking, reputacion, premios y gobernanza.
- DOMINION fue presentado como moneda transaccional de la oficina interna de los Maestros del Juego.
- El farming de DOMINION finalizo el 15.07.2026, aumentando la relevancia del intercambio secundario mediante InteraSwap.
- Desde el 29.07.2026 a las 17:00 CET, las operaciones de InteraSwap se contabilizan en Market Level Up.
- InteraSwap conecta economicamente Interatum con Legends of Interactions y TerritoryX, pero el par del pool documentado sigue siendo INT/DOMINION.

## Datos faltantes para una valoracion vigente

- Tipo de cambio actual `INT/DOMINION` y `DOMINION/INT`.
- Liquidez y reservas actuales del pool.
- Volumen por periodo y slippage real.
- Comisiones vigentes despues del aumento anunciado para junio de 2026.
- Valor EUR canonico de INT y DOMINION, si la empresa decide fijarlo.
- Ratio de creacion GOS#/INT.
- Tipo numerico de conversion M*E/INT.

Para obtener precios actuales sera necesario crear snapshots periodicos de la interfaz de InteraSwap. Las noticias historicas no sustituyen esos datos.

## Fuentes primarias

- [GIG-OS, 16.04.2026: pool INT Coin / DOMINION Coin](https://gig-os.com/es/gold-news/read/intera-swap-pool-de-intercambio-de-int-coin-y-dominion-coin-0185)
- [GIG-OS, 14.05.2026: cierre de premios y continuidad del cashback](https://gig-os.com/es/gold-news/read/intera-swap-concluimos-la-serie-de-premios-0192)
- [GIG-OS, 26.06.2026: graficos de tipo de cambio en tiempo real](https://gig-os.com/es/gold-news/read/siempre-un-paso-adelante-configure-el-equilibrio-perfecto-de-sus-activos)
- [Olympia, 15.07.2026: fin del farming de DOMINION y obtencion de INT](https://olympia-lab.com/es/news/post/la-fase-de-farming-de-dominion-coin-ha-finalizado-nuevas-oportunidades)
- [GIG-OS, 17.07.2026: uso de InteraSwap tras el fin del farming](https://gig-os.com/es/gold-news/read/intera-swap-es-el-momento-de-tomar-decisiones-rapidas)
- [Olympia, 05.08.2026: InteraSwap en Market Level Up](https://olympia-lab.com/es/news/post/factorydronex-e-intera-swap-ahora-influyen-en-su-carrera)
- [GIG-OS, 10.08.2026: funciones y obtencion de INT Coin](https://gig-os.com/es/gold-news/read/int-coin-el-motor-de-su-exito-en-interatum)
- [Olympia, 20.08.2026: extension de combinaciones para INT](https://olympia-lab.com/es/news/post/reciba-int-coin-en-h-map-system-hasta-el-5-de-noviembre)
- [GIG-OS, 10.06.2025: farming inicial de INT](https://gig-os.com/es/gold-news/read/comienza-el-farming-de-int-coin-1095)
- [GIG-OS, 10.11.2025: reglas de conversion M*E/INT](https://gig-os.com/es/gold-news/read/preparense-para-el-intercambio-de-me-coin-por-int-coin-1167)
- [GIG-OS, 08.10.2024: intercambio de activos envueltos por REEX](https://gig-os.com/es/gold-news/read/como-obtener-reex-coin-996)

## Historial

- 2026-09-03: consolidacion inicial desde Olympia y GIG-OS.
