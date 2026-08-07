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
- `03_Reuniones_Presidencia`
  Evidencia privada: reuniones, conferencias, pre-releases y comunicaciones presidenciales.
- `03_Reuniones_Presidencia/reuniones_privadas`
  Minutas o resumenes de reuniones privadas.
- `03_Reuniones_Presidencia/conferencias_presidencia`
  Conferencias, traducciones, pre-releases y comunicaciones presidenciales.
- `04_Datos_Blockchain`
  Datos cuantitativos de blockchain: snapshots por activo, holders, supply, metadata y reportes.
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

Si no se revisaron esas areas, la respuesta debe aclarar que la busqueda fue parcial.

