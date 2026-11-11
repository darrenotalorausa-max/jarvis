# Vision (Jarvis + Doomsday) — guía compacta para trabajar en este repositorio

Monolito local-first. Backend Python/FastAPI + SQLite, worker en proceso aparte, frontend React/TS/Vite servido por el backend.
Idioma del producto y de la documentación: español.

## Comandos
```bash
./scripts/setup.sh                      # prepara .venv, dependencias e interfaz (Windows: SETUP_JARVIS.cmd)
./scripts/start.sh [--app]              # lanza API + worker en 127.0.0.1:8765; --app = ventana propia (Windows: START_JARVIS.cmd, siempre --app)
cd backend && ../.venv/bin/python -m pip install -r requirements-dev.txt
cd backend && ../.venv/bin/python -m pytest tests -q          # ~25 s, usa FFmpeg real
cd frontend && npm run build            # tsc --noEmit + vite build → frontend/dist
node frontend/e2e/smoke.cjs             # recorrido en navegador contra una instancia LIMPIA en marcha (Playwright + FFmpeg)
```
Para una instancia limpia de pruebas: `JARVIS_HOME=<carpeta vacía> JARVIS_SECRETS_BACKEND=file JARVIS_SECRETS_FILE=<ruta> JARVIS_NO_BROWSER=1 python -m jarvis.launch`.

## Mapa (backend/jarvis)
- `config.py` rutas/env · `db.py` SQLite + `migrations/NNN_*.sql` · `util.py`
- `security.py` SSRF, rutas, redacción · `secrets_store.py` keyring o archivo fuera de `data/`
- `providers/` adaptadores HTTP (`llm`, `search`, `voice`, `base` = errores→estados) · `connections.py` catálogo, CRUD, prueba
- `router.py` selección por capacidad, política local/gratis primero, caché, cuotas, presupuesto, uso
- `jobs.py` cola persistente · `worker.py` ejecución, latido, cancelación, recuperación · `handlers/` un archivo por módulo
- `records.py` registros tipados por esquema (`KINDS`) + CSV · `review.py` entregables, versiones, comprobaciones, aprobaciones, exportación
- `webfetch.py` importador web seguro · `economy.py` · `backup.py` · `assistant.py` herramientas de Jarvis · `api.py` · `launch.py`
- `connectors.py` conector universal (plantillas, OAuth, acciones) · `monitors.py` · `imports.py` (Apple Health, OFX) · `scripture.py` · `mcp_server.py` · `handlers/{apps,study}.py`
- `providers/media.py` + `handlers/media.py` imágenes y video por API · `memory.py` memoria a largo plazo · `schedules.py` agentes con horario
- `notify.py` avisos al celular, órdenes y aprobaciones por Telegram (`providers/notify.py`) · `access.py` acceso en red con código, usuarios y roles · `business.py` Centro de negocios · `life.py` indicadores personales y repaso espaciado · `library.py` biblioteca (`content/`)

Frontend (`frontend/src`): `store.tsx` (estado global, SSE), `components/` (`RecordsPanel` genera CRUD desde el esquema,
`DeliverableView`, `shared`, `ui`, `Core`), `views/` (una por zona de navegación).

## Vision = Jarvis + Doomsday (una sola aplicación)
El producto se llama **Vision**: un proceso, una base de datos y una interfaz. `backend/jarvis/` es el motor y los estudios de Jarvis; `backend/doomsday/` aporta los 100 módulos
(`catalog.py`, `skills/*.md`, `tools.py`, `tools2.py`, `plans.py`, `integrations.py`) y se registra con `doomsday.load()` (lo llaman el worker y la API). `doomsday/bridge.py` da a Jarvis
las herramientas para manejar los módulos; `doomsday/seed.py` asigna las cuatro capas reutilizando los espacios que ya existan; `doomsday/fusion.py` importa una vez los datos de la
antigua carpeta `doomsday_home/`. La interfaz única está en `frontend/src/doomsday/` (`App.tsx` es el armazón; las vistas de Jarvis siguen en `views/`). Guía: `docs/DOOMSDAY.md`.
Pruebas de navegador (cada una contra una instancia LIMPIA): `node frontend/e2e/smoke.cjs` (Jarvis) y `node frontend/e2e/doomsday.cjs` (módulos).

## Reglas que no se rompen
- Todo dato lleva `space_id`; nunca se lee ni enlaza entre espacios. Caché separada por espacio.
- Secretos solo en `secrets_store`; jamás en SQLite, logs, respuestas de la API, frontend o respaldos.
- La salida de un modelo solo entra como datos validados con Pydantic (`handlers/common.ask_json`). Nunca dispara acciones.
- Fuentes web/archivos = datos no confiables: van entre `<fuente>` y las citas se comprueban contra el texto (`quote_in_text`).
- Acción externa ⇒ aprobación vigente y específica: `external_export` ligada a versión + destino (editar crea versión e invalida aprobaciones); `connector_action` ligada al hash exacto de la petición, de un solo uso. Leer de una app conectada no requiere aprobación; todo lo que no sea GET, sí.
- Rutas nuevas de la API: decide en `access.allowed` qué rol las alcanza; por defecto solo el propietario.
- Única excepción: avisos al propio dueño (`notify.py`), bajo la política que él configura en cada canal. Solo título, estado y motivo; nunca contenido de entregables ni datos de espacios personales. Si el dueño activa «aprobar desde este chat» (desactivado por defecto), ese Telegram recibe además el resumen del entregable o la petición exacta de la acción; la decisión solo vale desde el chat autorizado, una vez, y ligada a versión o hash.
- La memoria (`memory.py`) es por espacio y entra en los prompts entre `<memoria>` como datos, no como instrucciones. Los agentes con horario solo ejecutan órdenes del asistente (herramientas internas) y respetan la pausa global.
- Generar imágenes o video gasta saldo del usuario: solo a petición suya o de un horario que él creó, por el router (presupuesto y política del espacio). Las descargas de resultados pasan por `check_public_url`.
- Una misión solo pasa a `completada_verificada` con criterio de cierre y evidencia (`records._check_rules`). Nunca se inventan tareas del manual DOOMSDAY.
- `content/` es conocimiento del usuario y guías: las guías no afirman precios ni cuotas en cifras.
- FFmpeg y cualquier binario: lista de argumentos validada, sin shell (`JobCtx.run_proc`).
- Sin IA disponible, un trabajo espera (`waiting_config`) o entrega solo evidencia; no se inventan resultados ni datos de ejemplo.
- Proveedores simulados solo en `backend/tests` (`providers.base.TRANSPORT`). Nada simulado en operación.
- No añadir dependencias pesadas, ORM, Redis, Docker obligatorio ni microservicios.
- Un módulo nuevo de registros = entrada en `records.KINDS` (+ `RecordsPanel` en una vista). Un trabajo nuevo = `@handler` + `JOB_TYPES` en `api.py`.
- Cambios de esquema: nueva migración numerada; nunca editar una ya publicada.
- Interfaz: colores, radios, espacios y tiempos solo mediante los tokens de `styles.css`; sin sombras, sin `transition: all`, sin animar propiedades de layout. El núcleo es el único elemento con luz y animación continua (`docs/DESIGN.md`).

## Documentación
`README_START_HERE.md` (usuario) · `docs/ARCHITECTURE.md` · `docs/IMPLEMENTATION_STATUS.md` (qué está probado y qué no) ·
`docs/PROVIDER_MATRIX.md` · `docs/ACCEPTANCE.md` (pruebas ↔ criterios) · `docs/RESUME.md` (punto de reanudación) · `docs/VIDEO_MANIFEST.md` · `docs/DESIGN.md` (hoja de decisiones visuales).
Mantén `IMPLEMENTATION_STATUS.md` y `RESUME.md` al día al terminar cualquier cambio.
