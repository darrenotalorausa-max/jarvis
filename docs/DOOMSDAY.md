# Vision: Jarvis + Doomsday

Vision es la fusión de Jarvis y Doomsday en una sola aplicación: un proceso, un puerto (8765), una base de datos y una interfaz. Jarvis conversa y coordina (voz, chat, Telegram,
horarios) y conserva sus estudios; Doomsday aporta los 100 módulos del «Laboratorio Estratégico». No hay nada que arrancar aparte.

## Arrancar
```bash
./scripts/start.sh [--app]              # o scripts/start_vision.sh · Windows: START_VISION.cmd o START_JARVIS.cmd
cd backend && ../.venv/bin/python -m pytest tests -q
cd frontend && npm run build
node frontend/e2e/smoke.cjs             # recorrido de Jarvis (instancia LIMPIA en marcha)
node frontend/e2e/doomsday.cjs          # recorrido de los módulos (otra instancia LIMPIA)
```

## Cómo se unieron
- **Datos**: una sola base. Las cuatro capas de Doomsday reutilizan los espacios que Jarvis ya tenga (tu «Personal» es la capa personal; tu negocio, la capa interna) y solo se crean las que falten.
  Si existía `doomsday_home/` de cuando corría aparte, el primer arranque importa sus registros, entregables, conexiones, archivos y skills sin pisar nada; la carpeta queda intacta.
- **Jarvis maneja Doomsday** (`bridge.py`): «G02 calcula» ejecuta la herramienta de un módulo, «G04: …» le da una orden, «brief» resume lo que exige decisión, «módulos de pauta» busca. Con IA conectada, en lenguaje libre.
  Vale por texto, por voz, por Telegram y en los agentes con horario. Son acciones internas: nada externo sale por el asistente.
- **Interfaz**: tablero de Vision, «Hablar con Jarvis» (el núcleo con voz), capas, las diez categorías y los doce estudios de Jarvis en el mismo menú. El buscador (Ctrl K) encuentra módulos, estudios y guías de la biblioteca.
  El rol «equipo» conserva la vista de trabajo de Jarvis; el rol «cliente» ve solo la revisión de su espacio.

## Mapa
- `backend/doomsday/catalog.py` los 100 módulos (declarativo): datos, herramientas, acciones, capa, autonomía.
- `kinds.py` tipos de registro `dd_*` · `tools.py` 32 herramientas deterministas (sin IA) · `skills/*.md` 100 skills integradas · `skills.py` versiones, importación y prompt.
- `engine.py` trabajo `dd_run`: skill + registros + evidencia calculada + fuentes → entregable `dd` revisable (+ registros).
- `tools2.py` segunda tanda de herramientas sin IA (búsqueda, plantillas de documentos, listas de pasos, bandeja por reglas, análisis de llamadas y de código, paquetes) · `content.py` plantillas de pasos, frases y 6 secciones Liquid.
- `plans.py` planes de acciones externas con una sola aprobación (publicar en redes, lanzar anuncios en pausa, compras entregadas a Meta, Discord, tema), lecturas de Gmail y Oura, aceptación electrónica del cliente.
- `integrations.py` Meta/TikTok Ads, WhatsApp, operador logístico, borrador de Shopify, medios de creativos, recorte de clips y espacios por cliente.
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

## Planes de acciones externas
`plans.create_plan` encola un trabajo `dd_plan` con pasos encadenados contra una app conectada. El panel del módulo muestra cada paso (método, URL y cuerpo) y el dueño lo aprueba
una vez: la aprobación va ligada al hash de los pasos, es de un solo uso y puede fijar una hora («programar»). Si un paso falla, el plan se detiene y dice qué se ejecutó ya; no se reintenta solo.

## Diseño
Lenguaje visual del manual `DOOMSDAY.html` del usuario: neutros de sistema (suelo `#f5f5f7`, paneles blancos), oscuro automático en negro puro, botones píldora, azul de sistema para
«lo siguiente» y las acciones, y un color por capa. La firma es el dial del tablero: cien segmentos, uno por módulo, en cuatro anillos. La hoja de decisiones está en la cabecera de
`frontend/src/doomsday/doomsday.css`, que solo redefine tokens de `styles.css` y ajusta componentes; sin sombras y sin animar propiedades de layout.
Comprobación: `node "<skill>/scripts/check.mjs" frontend/src/doomsday` (0 errores, 0 avisos).
