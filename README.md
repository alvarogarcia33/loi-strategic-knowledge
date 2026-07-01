# LOI_AI

Base documental privada y sincronizable para análisis estratégico en ChatGPT.

## Qué contiene

- `01_Olympia`
  Contenido documental extraído de Olympia en Markdown y metadata local.
- `02_GIG_OS`
  Contenido documental extraído de GIG-OS en Markdown y metadata local.
- `03_Reuniones_Presidencia`
  Notas estratégicas manuales de reuniones, en formato Markdown.
- `09_Analisis_GPT`
  Dossiers estratégicos curados para subir directamente a un Proyecto de ChatGPT Plus.
- `06_Extractor`
  Scripts locales para actualización, validación y sincronización GitHub.

## Qué no contiene

Este repositorio no debería incluir:

- credenciales
- sesiones autenticadas
- cookies
- `.env`
- estado del navegador
- bases SQLite sensibles
- embeddings o infraestructura IA local
- imágenes pesadas no necesarias para el análisis conversacional
- logs grandes

## Cómo se actualiza

El flujo esperado es:

1. Actualizar Olympia con el extractor local.
2. Actualizar GIG-OS con el extractor local.
3. Validar o refrescar `09_Analisis_GPT`.
4. Revisar el plan de archivos a subir.
5. Hacer commit y push al repositorio GitHub.

Script principal:

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python sync_github.py --plan-only
```

Cuando el plan sea correcto:

```powershell
python sync_github.py
```

## Cómo usarlo con ChatGPT

La forma recomendada es subir a un Proyecto de ChatGPT:

- `01_Olympia\markdown`
- `02_GIG_OS\markdown`
- `03_Reuniones_Presidencia`
- `09_Analisis_GPT`

Uso sugerido:

- `09_Analisis_GPT` como capa estratégica resumida.
- `01_Olympia` y `02_GIG_OS` como evidencia documental cruda.
- `03_Reuniones_Presidencia` como capa privada de contexto y confirmación.

## Criterio documental

- Olympia y GIG-OS se conservan como fuentes primarias.
- `09_Analisis_GPT` funciona como capa curada de síntesis estratégica.
- Las reuniones no reemplazan la fuente documental; la complementan.
