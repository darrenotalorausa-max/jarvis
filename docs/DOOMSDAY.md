# Doomsday

Aplicación aparte dentro de este repositorio: los 100 módulos del «Laboratorio Estratégico: 100 oportunidades de software», cada uno con panel propio.
Proceso, puerto (8766) y base de datos (`doomsday_home/`) propios. Reutiliza el motor de Jarvis; Jarvis no la contiene.

## Arrancar
```bash
./scripts/start_doomsday.sh [--app]     # Windows: START_DOOMSDAY.cmd
cd backend && ../.venv/bin/python -m pytest tests/test_doomsday.py -q
cd frontend && npm run build            # compila Jarvis (dist) y Doomsday (dist-doomsday)
node frontend/e2e/doomsday.cjs          # recorrido en navegador contra una instancia LIMPIA en marcha
```
Instancia limpia: `DOOMSDAY_HOME=<carpeta vacía> JARVIS_SECRETS_BACKEND=file JARVIS_SECRETS_FILE=<ruta> JARVIS_NO_BROWSER=1 python -m doomsday.launch`.
Variables: `DOOMSDAY_HOME`, `DOOMSDAY_PORT`.

## Mapa
- `backend/doomsday/catalog.py` los 100 módulos (declarativo): datos, herramientas, acciones, capa, autonomía.
- `kinds.py` tipos de registro `dd_*` · `tools.py` 32 herramientas deterministas (sin IA) · `skills/*.md` 100 skills integradas · `skills.py` versiones, importación y prompt.
- `engine.py` trabajo `dd_run`: skill + registros + evidencia calculada + fuentes → entregable `dd` revisable (+ registros).
- `app.py` rutas `/api/dd/*` sobre la API del motor · `launch.py`, `worker.py`, `env.py`.
- `frontend/src/doomsday/` interfaz (`App.tsx` tablero, categorías, skills; `Module.tsx` panel de módulo y widgets; `doomsday.css` solo redefine tokens).

## Cómo funciona un módulo
1. **Datos**: registros tipados (CRUD e importación CSV generados desde el esquema).
2. **Herramientas**: cálculo determinista con esos registros. Sin datos lo dice; no hay cifras de ejemplo.
3. **Órdenes**: una «orden libre» y acciones con formulario. La skill del módulo y el estándar profesional gobiernan el prompt; el resultado se valida con Pydantic y llega a Revisión como borrador con versiones y aprobación.
4. **Skill**: editable por módulo; la tuya sustituye a la integrada y la anterior queda en `doomsday_home/skills/_historial/`.

Las cuatro capas (personal, interna, clientes, comercial) son espacios distintos: no comparten datos ni caché. La capa personal solo usa una conexión de nube marcada para datos personales.
Sin IA un trabajo espera configuración o entrega solo la evidencia calculada. Escribir en un sistema externo pasa siempre por `connector_action` con aprobación.

## Añadir o cambiar
Módulo: `M(...)` en `catalog.py` + sección `## ID · Nombre` en `skills/`. Tipo de dato: `K(...)` en `kinds.py`. Herramienta: `@tool` en `tools.py`.
Las rutas `/api/dd/*` no están en la lista blanca de `access.allowed`: solo el propietario.
