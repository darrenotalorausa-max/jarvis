# Punto de reanudación

Última sesión: 2026-11-10. Rama: `claude/trusting-edison-s2ex3g`.

## Estado
Código subido a GitHub en la rama `claude/trusting-edison-s2ex3g`.

Interfaz rediseñada (ver `docs/DESIGN.md`). Producto unificado funcionando en Linux: backend, worker, interfaz, lanzadores, pruebas y documentación.
Detalle exacto en `docs/IMPLEMENTATION_STATUS.md`. Nada quedó a medias en el código.

Último bloque: Claude y ChatGPT por API, conector universal (`connectors.py`, `views/Apps.tsx`), monitores (`monitors.py`), usuarios con rol (`access.py`), importadores (`imports.py`), tutor y notas (`handlers/study.py`), texto bíblico (`scripture.py`), MCP (`mcp_server.py`), modo aplicación (`launch.py --app`, `scripts/windows/`) y Docker. 100 pruebas y recorrido en navegador en verde. Añadido después: medios por API (`providers/media.py`), memoria (`memory.py`), horarios (`schedules.py`), aprobaciones por Telegram (`notify.py`) y manos libres (`views/Command.tsx`, `voice.ts`). HUD de Comando rediseñado sin tarjetas (`docs/DESIGN.md`).

## Doomsday (sesión 2026-11-11, rama `claude/cool-gates-knm1i3`)
Construido y probado en Linux; ver `docs/DOOMSDAY.md` y la sección Doomsday de `IMPLEMENTATION_STATUS.md`. Para retomar, en orden de valor:
1. Conectar una IA real en Doomsday (Conexiones) y evaluar las skills del top 5 (G04, M06, G02, M01, V02) con casos reales; ajustar `backend/doomsday/skills/*.md`.
2. Importar las skills propias del usuario (Dawn, tema, guiones) desde Skills → «Importar mis skills».
3. Integraciones reales por orden: sincronización de gasto de Meta por campaña (`app.py`, junto a `sync_shopify`), Dropi (API o importador de su exportación), pausa de anuncios como `connector_action`, Higgsfield para M06, WhatsApp para V05.
4. G04: subir secciones del tema e imágenes al borrador de Shopify.
5. Validar `START_DOOMSDAY.cmd` en Windows.

## Para retomar (en orden de valor)

0. **Importar `DOOMSDAY.html`** cuando el usuario lo aporte: extractor con AST → manifiesto JSON → registros `mission` (campo `source_ref`) → `docs/source-audit.md` y `docs/source-coverage.md` con prueba de cobertura. El modelo de datos y la pantalla ya existen (`records.KINDS["mission"]`, `business.py`, `views/CommandCenter.tsx`); marca `doomsday_manifest` en ajustes al importar.

1. **Validar en Windows** (no se ha ejecutado nunca): `SETUP_JARVIS.cmd` crea el acceso directo «Jarvis OS» y la ventana de aplicación abre (pywebview + WebView2); micrófono y sonido dentro de esa ventana; `START_JARVIS.cmd` con Python/Node/FFmpeg presentes y ausentes;
   comprobar que `keyring` usa el Administrador de credenciales (Diagnóstico → «Credenciales»). Archivos: `START_JARVIS.cmd`,
   `SETUP_JARVIS.cmd`, `backend/requirements.lock` (marcadores de plataforma añadidos a mano), `backend/jarvis/launch.py`.
2. **Validar proveedores con claves reales**, uno por uno, desde Conexiones. Si un formato difiere, el arreglo está acotado a
   `backend/jarvis/providers/{llm,search,voice}.py`; dudas concretas listadas al final de `docs/PROVIDER_MATRIX.md`.
2b. **Validar cada plantilla de Apps conectadas con una cuenta real** (`backend/jarvis/connectors.py`, `PRESETS`): rutas, versión de API y permisos; OAuth con Google. Instalar FFmpeg en la imagen de Docker en un servidor real y arrancar con `docker compose up` (la imagen ya se construyó y arrancó sin ese paso). Probar el servidor MCP con Claude Desktop.
2c. **Probar con cuentas reales lo último añadido:** una imagen y un video (ajustar `media_params` por modelo), botones de Telegram, y manos libres con micrófono (sobre todo el modo de transcripción por servidor: umbral de volumen en `startHands`).
3. **Evaluar prompts con un modelo real** (calidad de expedientes, propuestas, lotes): `backend/jarvis/handlers/*.py`,
   subir `prompt_version` al cambiarlos para no reutilizar caché.
4. **Voz con micrófono real** en Chrome/Edge: `frontend/src/views/Command.tsx`.
5. **Sección Shopify en un tema real**: `backend/jarvis/templates/jarvis-landing.liquid`, `handlers/shopify.py`.

## Mejoras candidatas (no empezadas)
- Aprobar entregables y acciones de apps desde Telegram; plantillas de WhatsApp.
- Importación programada desde apps conectadas hacia registros (hoy las acciones son a petición); usar acciones de lectura como herramientas de los trabajos.
- Empaquetado como ejecutable único (PyInstaller) con instalador; HTTPS propio para el modo servidor.
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
