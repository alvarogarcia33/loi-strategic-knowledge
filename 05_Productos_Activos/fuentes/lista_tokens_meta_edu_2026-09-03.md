# Fuente: Lista de Tokens - Meta EDU

- Fecha del archivo recibido: 2026-09-03
- Tipo: planilla de referencias aportada por el responsable de la base
- Archivo de origen: `Lista de Tokens - Meta EDU.xlsx`
- Hojas de origen: `Hoja 1` y `MOG`
- Filas de datos preservadas: 106
- Destino consolidado: `../02_Planilla_Maestra_Productos_Activos.xlsx`

## Tratamiento aplicado

La planilla aportada se integro con el catalogo de H-MAP Industries y con las equivalencias ya confirmadas en LOI_AI. Se normalizaron nombres equivalentes, se conservaron todas las filas originales y se creo una fila maestra por activo.

El resultado contiene:

- 89 activos unicos;
- 78 activos con valor EUR disponible;
- 31 productos oficiales de H-MAP Industries con formulas auditables;
- 2 equivalencias canonicas: HMAP y REEX;
- 10 conflictos o validaciones abiertas.

## Regla de interpretacion

- `Equivalencia canonica`: valor estable confirmado para calculos internos.
- `Precio recomendado`: precio publicado por Olympia y convertido desde REEX.
- `Calculado por costo`: costo de activacion dividido entre el limite de farming.
- `Referencia aportada`: dato util para analisis, pero no confirmado como precio oficial o estable.
- `Sin referencia`, `Revisar` o `No usar sin validar`: no debe convertirse en precio definitivo.

## Principales conflictos detectados

- DOMINION figura a 60 EUR en `Hoja 1` y a 50 EUR en `MOG`; ademas, InteraSwap documenta un valor dinamico.
- Shard Setter 90D figura a 210 EUR y tambien a 3 DOMINION; las cifras no concilian con ninguna de las dos referencias de DOMINION.
- Antallagi figura a 1 EUR, mientras una observacion indica un promedio de 0,80 EUR.
- Hexatile no tiene valor en la hoja principal y figura a 2,75 HEXA en `MOG`.
- INT figura a 85,50 EUR, pero la documentacion de InteraSwap no establece una equivalencia fija.
- PreFactory mezcla una referencia de 150 EUR con una posible comision de transferencia del mismo importe.
- 1 GM y REEX Miner no cuentan con precios confirmados.
- GAME GOS y GOS figuran a 50 EUR y 60 EUR respectivamente; se debe confirmar si son activos distintos.

## Criterio futuro

Toda nueva planilla de precios debe incorporarse al mismo libro maestro, manteniendo fecha, fuente, unidad original, metodo y estado de validacion. El archivo aportado no se considera por si solo una fuente oficial de mercado.
