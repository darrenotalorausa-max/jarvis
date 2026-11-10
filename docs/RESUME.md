# Punto de reanudación

Última sesión: 2026-11-10. Rama: `claude/trusting-edison-s2ex3g`.

## Estado
Código subido a GitHub en la rama `claude/trusting-edison-s2ex3g`.

Interfaz rediseñada (ver `docs/DESIGN.md`). Producto unificado funcionando en Linux: backend, worker, interfaz, lanzadores, pruebas y documentación.
Detalle exacto en `docs/IMPLEMENTATION_STATUS.md`. Nada quedó a medias en el código.

## Para retomar (en orden de valor)

0. **Importar `DOOMSDAY.html`** cuando el usuario lo aporte: extractor con AST → manifiesto JSON → registros `mission` (campo `source_ref`) → `docs/source-audit.md` y `docs/source-coverage.md` con prueba de cobertura. El modelo de datos y la pantalla ya existen (`records.KINDS["mission"]`, `business.py`, `views/CommandCenter.tsx`); marca `doomsday_manifest` en ajustes al importar.

1. **Validar en Windows** (no se ha ejecutado nunca): `START_JARVIS.cmd` con Python/Node/FFmpeg presentes y ausentes;
   comprobar que `keyring` usa el Administrador de credenciales (Diagnóstico → «Credenciales»). Archivos: `START_JARVIS.cmd`,
   `SETUP_JARVIS.cmd`, `backend/requirements.lock` (marcadores de plataforma añadidos a mano), `backend/jarvis/launch.py`.
2. **Validar proveedores con claves reales**, uno por uno, desde Conexiones. Si un formato difiere, el arreglo está acotado a
   `backend/jarvis/providers/{llm,search,voice}.py`; dudas concretas listadas al final de `docs/PROVIDER_MATRIX.md`.
3. **Evaluar prompts con un modelo real** (calidad de expedientes, propuestas, lotes): `backend/jarvis/handlers/*.py`,
   subir `prompt_version` al cambiarlos para no reutilizar caché.
4. **Voz con micrófono real** en Chrome/Edge: `frontend/src/views/Command.tsx`.
5. **Sección Shopify en un tema real**: `backend/jarvis/templates/jarvis-landing.liquid`, `handlers/shopify.py`.

## Mejoras candidatas (no empezadas)
- Aprobar entregables desde Telegram; plantillas de WhatsApp; conectores de la lista E de `IMPLEMENTATION_STATUS.md`, empezando por Google Drive y Shopify.
- IA sobre datos personales solo con modelo local: preguntas a las notas, tutor a partir de PDF.
- Subida a tema borrador por la API de Shopify (con aprobación de envío externo).
- Reserva de presupuesto por trabajo completo en vez de por llamada.
- Historial de cambios de registros.
- Importar proyectos del CRM/panel existentes si su código llega a este repositorio.

## Comprobación rápida tras cualquier cambio
```bash
cd backend && ../.venv/bin/python -m pytest tests -q
cd ../frontend && npm run build
# instancia limpia + recorrido en navegador:
JARVIS_HOME=/tmp/jarvis-prueba JARVIS_SECRETS_BACKEND=file JARVIS_SECRETS_FILE=/tmp/jarvis-prueba/s.json JARVIS_NO_BROWSER=1 ../.venv/bin/python -m jarvis.launch &
node e2e/smoke.cjs
```
