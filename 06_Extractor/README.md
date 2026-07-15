# LOI AI - Extractor

Infraestructura base para el extractor documental privado de GIG-OS y Olympia.

La Fase 2.1 crea:

- Estructura de carpetas.
- Configuracion desde `.env`.
- Logging rotativo.
- Base SQLite local.
- Tablas de control documental.
- Modelos Pydantic base.
- Validacion de rutas al iniciar.

La Fase 2.2 agrega autenticacion real de Olympia con Playwright, navegador Chromium visible y persistencia de sesion.

Actualmente ya incluye:

- autenticacion real con Playwright,
- descubrimiento de URLs de noticias Olympia,
- extraccion limitada de articulos,
- guardado de Markdown,
- guardado de metadata JSON,
- descarga de imagenes,
- deduplicacion por URL y hashes en SQLite,
- corrida diaria de Olympia con reporte.

## Instalacion

Desde PowerShell:

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
python main.py
```

## Ejecucion

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python main.py
```

Al ejecutar, el sistema:

1. Carga variables desde `.env` si existe.
2. Valida rutas requeridas.
3. Configura logs en `logs\extractor.log`.
4. Crea o actualiza la base SQLite en `data\articles.sqlite`.
5. Registra las plataformas base `gig_os` y `olympia`.
6. Muestra un resumen de estado en consola.

## Configuracion Olympia

Crear o editar `.env` con estos valores:

```text
OLYMPIA_BASE_URL=https://...
OLYMPIA_LOGIN_URL=https://...
OLYMPIA_USERNAME=tu_usuario
OLYMPIA_PASSWORD=tu_password
HEADLESS=false
```

Si la deteccion automatica de campos no alcanza, definir selectores explicitos:

```text
OLYMPIA_USERNAME_SELECTOR=input[name="username"]
OLYMPIA_PASSWORD_SELECTOR=input[type="password"]
OLYMPIA_SUBMIT_SELECTOR=button[type="submit"]
OLYMPIA_LOGIN_SUCCESS_SELECTOR=.selector-que-solo-aparece-logueado
OLYMPIA_LOGOUT_SELECTOR=.selector-de-cerrar-sesion
```

## Prueba de login Olympia

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python main.py --platform olympia --login-test
```

La prueba:

1. Abre Chromium visible.
2. Reutiliza `data\browser_state\olympia_state.json` si la sesion sigue vigente.
3. Si no hay sesion valida, abre la URL de login.
4. Completa usuario y contrasena desde `.env`.
5. Guarda el estado autenticado.
6. Registra eventos en `logs\extractor.log`.
7. Guarda screenshots de error en `data\screenshots`.

## Descubrimiento de estructura Olympia

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python main.py --platform olympia --discover-structure --debug
```

Genera:

- `data\olympia_structure_report.json`
- `C:\Users\alvar\Documents\LOI_AI\08_Reportes\olympia_structure_report.md`
- screenshots en `data\screenshots\structure`

## Extraccion limitada de noticias Olympia

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python main.py --platform olympia --extract-news --limit 5 --debug
```

La extraccion usa la sesion autenticada guardada en `data\browser_state\olympia_state.json`,
descubre enlaces con patron `/es/news/post/`, guarda Markdown, metadata JSON e imagenes,
y registra cada articulo en SQLite evitando duplicados por URL y hashes.

## Actualizacion diaria de Olympia

Comando manual:

```powershell
cd C:\Users\alvar\Documents\LOI_AI\06_Extractor
python main.py --platform olympia --daily-update --debug
```

Este flujo:

1. reutiliza `data\browser_state\olympia_state.json`,
2. revisa las categorias de noticias ya detectadas,
3. filtra duplicados por URL antes de abrir articulos,
4. filtra duplicados por hash y URL al guardar,
5. guarda solo articulos nuevos en `01_Olympia`,
6. registra la corrida en SQLite (`runs` y `run_events`),
7. genera reporte JSON y Markdown en `C:\Users\alvar\Documents\LOI_AI\08_Reportes`.

Script para Task Scheduler:

```powershell
C:\Users\alvar\Documents\LOI_AI\06_Extractor\run_olympia_daily_update.ps1
```

El script usa la virtualenv local y escribe una traza adicional en:

```text
C:\Users\alvar\Documents\LOI_AI\06_Extractor\logs\olympia_daily_update_scheduler.log
```

## Estructura de salida

La base privada vive dentro de `C:\Users\alvar\Documents\LOI_AI`:

- `01_Olympia\markdown`
- `01_Olympia\metadata`
- `01_Olympia\images`
- `02_GIG_OS\markdown`
- `02_GIG_OS\metadata`
- `02_GIG_OS\images`
- `03_Reuniones`
- `04_Traducciones`
- `05_Resumenes`
- `07_Base_Vectorial`
- `08_Reportes`

## Base de datos

La base local contiene:

- `platforms`
- `articles`
- `article_images`
- `runs`
- `run_events`

Los indices y restricciones UNIQUE evitan duplicados por URL, hash de URL y hash de contenido.
