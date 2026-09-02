# Equivalencias estables del ecosistema

- Fecha de registro: 2026-09-02
- Estado: valores estables confirmados para calculos internos del ecosistema
- Vigencia: hasta que una comunicacion posterior indique un cambio

## Valores canonicos

| Moneda | Valor estable | Uso en esta base |
|---|---:|---|
| HMAP Coin | 50 EUR | Convertir comisiones, activaciones y costos expresados en HMAP |
| REEX Coin | 25 EUR | Convertir precios recomendados expresados en REEX |

## Regla de uso

Estos valores se consideran equivalencias fijas del ecosistema y no cotizaciones variables de mercado. Toda conversion de productos y activos debe utilizar:

```text
1 HMAP = 50 EUR
1 REEX = 25 EUR
```

No se deben presentar como supuestos, estimaciones ni precios temporales mientras esta ficha permanezca vigente.

## Jerarquia para determinar precios

1. Si Olympia publica un precio de venta recomendado en REEX, ese es el precio unitario principal de la lista.
2. El importe en REEX se convierte a EUR con la equivalencia estable de 25 EUR por REEX.
3. Si no existe precio recomendado, se calcula un precio base unitario dividiendo el costo de activacion entre el limite de farming.
4. Un precio calculado por costo no es una cotizacion de mercado ni garantiza margen o venta.

## Fuente y alcance

- HMAP: valor estable confirmado por el responsable de esta base.
- REEX: valor estable confirmado por el responsable de esta base.
- Las condiciones de productos se verifican por separado en Olympia-Lab.

## Historial

- 2026-09-02: se registran como canonicos 50 EUR por HMAP y 25 EUR por REEX.
