# Base de productos y activos

Esta carpeta consolida definiciones y condiciones de los elementos economicos y operativos del ecosistema LOI. Complementa las noticias de Olympia y GIG-OS, las comunicaciones presidenciales y los datos observados en blockchain.

## Estructura

- `00_Inventario_Maestro.md`: indice unico de elementos documentados.
- `01_Lista_de_Precios.md`: precios unitarios, conversiones, costos y metodo aplicado.
- `02_Planilla_Maestra_Productos_Activos.xlsx`: libro unico para consolidar valores, referencias, formulas, conflictos y fuentes.
- `productos/`: catalogos y fichas de objetos que se producen, utilizan o comercializan.
- `monedas_tokens/`: monedas, tokens, valoraciones, mecanismos y relaciones.
- `nft_cupones/`: NFT, cupones, derechos de uso y activos equivalentes.
- `fuentes/`: metadata de cada extraccion o documento de origen.
- `plantillas/`: formato obligatorio para nuevas fichas.

## Criterio documental

- Cada dato debe indicar fuente y fecha de consulta.
- Los textos descriptivos deben resumir la fuente sin convertir publicidad en hecho comprobado.
- Precio recomendado, costo, comision, farming, limite y disponibilidad son campos temporales.
- Las equivalencias canonicas vigentes son `1 HMAP = 50 EUR` y `1 REEX = 25 EUR`; se documentan en `monedas_tokens/Equivalencias_Estables.md`.
- Cuando exista precio recomendado de Olympia, este tiene prioridad. Si no existe, el precio base se calcula como costo de activacion dividido entre limite de farming.
- Una afirmacion comercial se registra como afirmacion de la fuente, no como rendimiento garantizado.
- Los datos de blockchain se enlazan con `../04_Datos_Blockchain`; no se duplican aqui.
- Las comunicaciones privadas se enlazan con `../03_Reuniones_Presidencia`; no sustituyen fuentes publicas.
- Cuando una condicion cambie, se actualiza la ficha vigente y se registra el cambio en su seccion de historial.
- Toda nueva planilla de precios o tokens debe integrarse en `02_Planilla_Maestra_Productos_Activos.xlsx`; no se deben crear libros maestros paralelos.

## Planilla maestra

La planilla maestra contiene seis hojas: `Resumen`, `Maestro_Valores`, `Catalogo_HMAP`, `Equivalencias`, `Conflictos` y `Fuente_Original`.

- `HMAP = 50 EUR` y `REEX = 25 EUR` son las unicas equivalencias canonicas vigentes.
- Los precios recomendados de Olympia se calculan desde REEX mediante formulas.
- Las referencias aportadas por terceros se conservan con fecha y estado, pero no se transforman automaticamente en valores canonicos.
- Los conflictos quedan abiertos hasta disponer de una fuente que los resuelva.
- `Fuente_Original` conserva todas las filas de cada Excel incorporado para permitir auditoria.

## Estado inicial

El primer catalogo corresponde a H-MAP Industries consultado el 2 de septiembre de 2026. Se verificaron las vistas 7PT, 9PT y 7PT PRO: las tres mostraban los mismos 31 elementos y las mismas condiciones.

## Incorporaciones futuras

Para agregar una moneda, token, NFT o producto nuevo:

1. Crear una ficha desde `plantillas/FICHA_PRODUCTO_ACTIVO.md`.
2. Guardarla en la subcarpeta que corresponda.
3. Agregarla a `00_Inventario_Maestro.md`.
4. Conservar URL, fecha y alcance de la fuente.
5. Relacionarla con snapshots blockchain si existen.
