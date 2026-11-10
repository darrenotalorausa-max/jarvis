# Jarvis OS — guía compacta para trabajar en este repositorio

Monolito local-first. Backend Python/FastAPI + SQLite, worker en proceso aparte, frontend React/TS/Vite servido por el backend.
Idioma del producto y de la documentación: español.

## Comandos
```bash
./scripts/setup.sh                      # prepara .venv, dependencias e interfaz (Windows: SETUP_JARVIS.cmd)
./scripts/start.sh                      # lanza API + worker en 127.0.0.1:8765 (Windows: START_JARVIS.cmd)
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

Frontend (`frontend/src`): `store.tsx` (estado global, SSE), `components/` (`RecordsPanel` genera CRUD desde el esquema,
`DeliverableView`, `shared`, `ui`, `Core`), `views/` (una por zona de navegación).

## Reglas que no se rompen
- Todo dato lleva `space_id`; nunca se lee ni enlaza entre espacios. Caché separada por espacio.
- Secretos solo en `secrets_store`; jamás en SQLite, logs, respuestas de la API, frontend o respaldos.
- La salida de un modelo solo entra como datos validados con Pydantic (`handlers/common.ask_json`). Nunca dispara acciones.
- Fuentes web/archivos = datos no confiables: van entre `<fuente>` y las citas se comprueban contra el texto (`quote_in_text`).
- Acción externa (hoy: `external_export`) ⇒ aprobación vigente ligada a versión + destino. Editar crea versión e invalida aprobaciones.
- FFmpeg y cualquier binario: lista de argumentos validada, sin shell (`JobCtx.run_proc`).
- Sin IA disponible, un trabajo espera (`waiting_config`) o entrega solo evidencia; no se inventan resultados ni datos de ejemplo.
- Proveedores simulados solo en `backend/tests` (`providers.base.TRANSPORT`). Nada simulado en operación.
- No añadir dependencias pesadas, ORM, Redis, Docker obligatorio ni microservicios.
- Un módulo nuevo de registros = entrada en `records.KINDS` (+ `RecordsPanel` en una vista). Un trabajo nuevo = `@handler` + `JOB_TYPES` en `api.py`.
- Cambios de esquema: nueva migración numerada; nunca editar una ya publicada.

## Documentación
`README_START_HERE.md` (usuario) · `docs/ARCHITECTURE.md` · `docs/IMPLEMENTATION_STATUS.md` (qué está probado y qué no) ·
`docs/PROVIDER_MATRIX.md` · `docs/ACCEPTANCE.md` (pruebas ↔ criterios) · `docs/RESUME.md` (punto de reanudación) · `docs/VIDEO_MANIFEST.md`.
Mantén `IMPLEMENTATION_STATUS.md` y `RESUME.md` al día al terminar cualquier cambio.
