# LOI_AI

Base documental privada y sincronizable para análisis estratégico en ChatGPT.

Antes de consultar la base desde un Proyecto de ChatGPT, leer:

- `00_INSTRUCCIONES_PARA_CHATGPT.md`

Ese archivo define el protocolo de busqueda cruzada entre Olympia, GIG-OS, reuniones privadas, datos blockchain y dossiers estrategicos.

## Qué contiene

- `01_Olympia`
  Contenido documental extraído de Olympia en Markdown y metadata local.
- `02_GIG_OS`
  Contenido documental extraído de GIG-OS en Markdown y metadata local.
- [02_GIG_OS/Asamblea_Accionistas](02_GIG_OS/Asamblea_Accionistas/README.md)
  Expedientes fechados de asambleas y votaciones. Incluye las cuatro vistas de la votación RSL anunciada tras la conferencia del 25/09/2026, sus condiciones y fuentes originales.
- `03_Reuniones_Presidencia`
  Notas estratégicas manuales de reuniones, en formato Markdown.
- `04_Datos_Blockchain`
  Snapshots fechados de tokens, NFT y cupones, con datos originales, CSV normalizado, metadata y reportes comparativos.
- `05_Productos_Activos`
  Inventario normalizado de productos, objetos, monedas, tokens, NFT y cupones, con descripcion, utilidad, relaciones, condiciones y fuente fechada.
- `09_Analisis_GPT`
  Dossiers estratégicos curados para subir directamente a un Proyecto de ChatGPT Plus.

## Qué representa este repositorio

Este repositorio GitHub representa solo la **capa estratégica documental** que queremos usar con ChatGPT:

- fuentes primarias de Olympia
- fuentes primarias de GIG-OS
- reuniones privadas resumidas
- evidencia cuantitativa observable en blockchain
- fichas de productos y activos con condiciones operativas vigentes
- dossiers estratégicos curados

La infraestructura técnica local queda fuera del repo para evitar ruido.

## Qué no contiene

Este repositorio no debería incluir:

- credenciales
- sesiones autenticadas
- cookies
- `.env`
- estado del navegador
- bases SQLite sensibles
- embeddings o infraestructura IA local
- la carpeta `06_Extractor`
- la carpeta `08_Reportes`
- la carpeta `07_IA`
- reportes internos de IA como `05_Reportes_IA`
- imágenes pesadas no necesarias para el análisis conversacional
- logs grandes

## Cómo se actualiza

El flujo esperado es:

1. Actualizar Olympia con el extractor local.
2. Actualizar GIG-OS con el extractor local.
3. Importar nuevos snapshots blockchain cuando existan.
4. Incorporar o actualizar fichas de productos y activos cuando exista una fuente nueva.
5. Regenerar `09_Analisis_GPT`, incorporando las reuniones privadas relacionadas con cada tema.
6. Revisar el plan de archivos a subir de la capa estratégica.
7. Hacer commit y push al repositorio GitHub.

Script principal:

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python sync_github.py --plan-only
```

Cuando el plan sea correcto:

```powershell
python sync_github.py
```

La actualización automática local se ejecuta mediante la tarea programada de Windows `LOI_AI Full Daily Sync`, todos los días a las 09:00. Si el equipo estaba apagado, Windows la inicia al volver a estar disponible con la sesión del usuario abierta. El resultado queda registrado localmente en `06_Extractor/logs/full_daily_sync_scheduler.log`.

## Cómo usarlo con ChatGPT

La forma recomendada es subir a un Proyecto de ChatGPT:

- `01_Olympia\markdown`
- `02_GIG_OS\markdown`
- `01_Olympia\metadata`
- `02_GIG_OS\metadata`
- `03_Reuniones_Presidencia`
- `04_Datos_Blockchain`
- `05_Productos_Activos`
- `09_Analisis_GPT`

Uso sugerido:

- `09_Analisis_GPT` como capa estratégica resumida.
- `01_Olympia` y `02_GIG_OS` como evidencia documental cruda.
- `03_Reuniones_Presidencia` como capa privada de contexto y confirmación.
- `04_Datos_Blockchain` como evidencia cuantitativa observada y comparable en el tiempo.
- `05_Productos_Activos` como catalogo de definiciones, usos, costos, limites, rendimientos anunciados y relaciones economicas.

## Criterio documental

- Olympia y GIG-OS se conservan como fuentes primarias.
- `09_Analisis_GPT` funciona como capa curada de síntesis estratégica.
- Cada dossier de `09_Analisis_GPT` incorpora automáticamente fuentes nuevas de Olympia y GIG-OS todavía no absorbidas por su análisis curado.
- Las reuniones no reemplazan la fuente documental; la complementan.
- Los datos blockchain deben distinguir observacion, clasificacion e inferencia.
- Las fichas de productos deben conservar fecha y URL de consulta; sus precios, limites y condiciones no deben tratarse como permanentes.
- `LOI_AI` local es la base maestra.
- GitHub es el espejo estratégico para ChatGPT.
