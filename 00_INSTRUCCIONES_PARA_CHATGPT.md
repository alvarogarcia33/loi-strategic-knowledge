# Instrucciones para usar esta base con ChatGPT

Este repositorio es una base documental estrategica privada. No debe consultarse como si fuera una sola carpeta ni una sola fuente.

## Carpetas principales

- `01_Olympia/markdown`
  Noticias y documentos extraidos de Olympia-lab.
- `01_Olympia/metadata`
  Metadata de las fuentes de Olympia: URL original, fechas, categoria y datos tecnicos.
- `02_GIG_OS/markdown`
  Noticias y documentos extraidos de GIG-OS.
- `02_GIG_OS/metadata`
  Metadata de las fuentes de GIG-OS.
- `02_GIG_OS/Asamblea_Accionistas`
  Expedientes de votaciones y materiales corporativos de RSL, con capturas fechadas, condiciones y enlaces a los comunicados de GIG. Consultar esta carpeta para preguntas sobre las propuestas, calendario y consecuencias de la votación de septiembre-octubre de 2026. Distinguir textos originales de notas de lectura y comprobar si el estado capturado sigue vigente.
- `03_Reuniones_Presidencia`
  Evidencia privada: reuniones, conferencias, pre-releases y comunicaciones presidenciales.
- `03_Reuniones_Presidencia/reuniones_privadas`
  Minutas o resumenes de reuniones privadas.
- `03_Reuniones_Presidencia/conferencias_presidencia`
  Conferencias, traducciones, pre-releases y comunicaciones presidenciales.
- `04_Datos_Blockchain`
  Datos cuantitativos de blockchain: snapshots por activo, holders, supply, metadata y reportes.
- `05_Productos_Activos`
  Inventario de productos, objetos, monedas, tokens, NFT y cupones. Incluye descripcion, utilidad, condiciones operativas, relaciones economicas, fecha de consulta y URL fuente.
- `05_Productos_Activos/00_Inventario_Maestro.md`
  Indice general de los elementos documentados y ruta hacia su ficha vigente.
- `05_Productos_Activos/01_Lista_de_Precios.md`
  Lista canonica de precios unitarios, costos, conversiones y metodo de valoracion de los 31 articulos de H-MAP Industries.
- `05_Productos_Activos/productos`
  Catalogos y fichas de objetos productivos o utilizables dentro del ecosistema.
- `05_Productos_Activos/monedas_tokens`
  Fichas de monedas y tokens, incluidos valores y mecanismos cuando existan fuentes suficientes.
- `05_Productos_Activos/nft_cupones`
  Fichas de NFT, cupones, derechos de uso y activos equivalentes.
- `09_Analisis_GPT`
  Dossiers curados por tema. Sirven como primera capa de lectura estrategica, pero no reemplazan a las fuentes primarias.

## Regla principal de consulta

Para responder preguntas estrategicas, ChatGPT debe cruzar informacion entre carpetas. No debe responder usando solo una fuente si existen otras carpetas relevantes.

Orden recomendado:

1. Revisar `09_Analisis_GPT` para obtener una vista estrategica inicial.
2. Revisar `01_Olympia/markdown` y `01_Olympia/metadata` para confirmar fuentes publicas de Olympia.
3. Revisar `02_GIG_OS/markdown` y `02_GIG_OS/metadata` para contexto historico y fuentes publicas de GIG-OS.
4. Revisar `03_Reuniones_Presidencia` para evidencia privada, comunicaciones del presidente y notas no publicas.
5. Revisar `04_Datos_Blockchain` cuando la pregunta involucre tokens, NFT, cupones, supply, holders, distribucion o actividad observable.
6. Revisar `05_Productos_Activos` cuando la pregunta involucre definiciones, utilidad, farming, costos, limites, precios recomendados o relaciones entre productos y monedas.

## Regla para productos y activos

Para responder sobre un producto, moneda, token, NFT o cupon:

1. Localizar primero el elemento en `05_Productos_Activos/00_Inventario_Maestro.md`.
2. Leer su catalogo o ficha detallada dentro de `05_Productos_Activos`.
3. Para precios, consultar `05_Productos_Activos/01_Lista_de_Precios.md` y `05_Productos_Activos/monedas_tokens/Equivalencias_Estables.md`.
4. Contrastar la definicion con `01_Olympia` y `02_GIG_OS`.
5. Contrastar cantidades, supply, holders o actividad con `04_Datos_Blockchain` si existen snapshots.
6. Revisar `03_Reuniones_Presidencia` si la pregunta requiere intencion, estrategia o informacion previa al lanzamiento.
7. Indicar siempre la fecha de vigencia o consulta de precios, limites, farming y condiciones.

No asumir que un precio recomendado equivale a precio de mercado. No asumir que velocidad de farming, comision, limite, fecha de retiro o disponibilidad permanecen sin cambios.

## Regla de precios y monedas estables

- `1 HMAP = 50 EUR`.
- `1 REEX = 25 EUR`.
- Estas equivalencias son valores estables canonicos del ecosistema, no supuestos ni cotizaciones variables.
- Si Olympia publica precio recomendado en REEX, usarlo como precio unitario principal y convertirlo a EUR.
- Si no existe precio recomendado, usar el precio base calculado documentado en `05_Productos_Activos/01_Lista_de_Precios.md`.
- No llamar "valor neto" al costo unitario ni a la diferencia bruta.
- No estimar valores de GICO u otras monedas mientras no exista una equivalencia canonica registrada.

## Regla para InteraSwap e intercambios

Para preguntas sobre InteraSwap, INT Coin, DOMINION Coin o conversiones monetarias, consultar `05_Productos_Activos/monedas_tokens/InteraSwap_INT_DOMINION.md` y contrastar sus fuentes en Olympia y GIG-OS.

- No afirmar que INT o DOMINION tienen un precio fijo en EUR.
- El par INT/DOMINION utiliza un tipo de cambio dinamico que cambia con las transacciones.
- Las comisiones publicadas el 16.04.2026 son condiciones historicas de lanzamiento; la propia fuente anuncio un aumento dos meses despues.
- El rango implicito de 3,20 a 3,26 REEX por INT es una inferencia matematica historica, no una cotizacion oficial ni vigente.
- Los premios en cantidades iguales de REEX, INT y DOMINION no demuestran igualdad de valor entre esas monedas.
- Si se solicita una tasa actual, indicar que hace falta una captura fechada de la interfaz del pool.

## Regla para noticias recientes

Si el usuario dice que algo es reciente, nuevo, de hoy, ultimo o recien publicado:

1. Buscar primero en fuentes con fechas recientes.
2. Revisar `01_Olympia/markdown` por fecha.
3. Revisar `03_Reuniones_Presidencia/conferencias_presidencia` y `03_Reuniones_Presidencia/reuniones_privadas` por fecha.
4. Luego cruzar con `09_Analisis_GPT` y `02_GIG_OS` si hace falta contexto historico.

No conviene empezar por documentos antiguos si la pregunta se refiere a una novedad reciente.

## Regla para Gold Traditions Coin / GTC

Para preguntas sobre Gold Traditions Coin o GTC, revisar como minimo:

- `01_Olympia/markdown/06-08-2026_gold-traditions-coin-ya-está-a-la-venta_dfce208fe588.md`
- `01_Olympia/markdown/07-08-2026_gold-traditions-coin-qué-cosa-es-para-qué-por-qué_f1bbbd0602d3.md`
- `03_Reuniones_Presidencia/conferencias_presidencia/2026-08-07_gold_traditions_coin_pre_release.md`
- `09_Analisis_GPT/03_Legends_of_Interactions.md`
- `09_Analisis_GPT/04_HMAP.md`
- `09_Analisis_GPT/05_Maestros_del_Juego.md`

La carpeta correcta es `03_Reuniones_Presidencia`, no `3_Reuniones_Presidencia`.

## Regla de evidencia

Separar siempre:

- Hechos documentados.
- Inferencias.
- Hipotesis.
- Informacion faltante.

Si una afirmacion aparece solo en Olympia, decir que es fuente Olympia.
Si aparece tambien en reuniones o comunicaciones presidenciales, decirlo por separado.
Si una afirmacion surge de blockchain, marcarla como dato observado, no como intencion o promesa.

## Regla anti-respuesta incompleta

Antes de responder "no encontre informacion", verificar al menos:

- `09_Analisis_GPT`
- `01_Olympia/markdown`
- `02_GIG_OS/markdown`
- `03_Reuniones_Presidencia`
- `04_Datos_Blockchain`, si aplica
- `05_Productos_Activos`, si aplica

Si no se revisaron esas areas, la respuesta debe aclarar que la busqueda fue parcial.
