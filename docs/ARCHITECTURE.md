# Arquitectura

## Decisiones

| Decisión | Motivo |
|---|---|
| Monolito modular: FastAPI + SQLite + React/Vite | Un solo producto instalable; sin servicios externos para lo básico |
| SQLite directo con migraciones SQL numeradas (sin ORM) | Menos dependencias; `PRAGMA WAL` permite API y worker concurrentes |
| Worker en proceso separado, cola en SQLite | Los trabajos sobreviven a reinicios; la API nunca ejecuta trabajo largo |
| Adaptadores HTTP con `httpx` en vez de SDK por proveedor | Seis proveedores con ~300 líneas, errores traducidos a un solo vocabulario de estados |
| Registros tipados por esquema (`records.KINDS`) | ~25 tipos CRUD (tareas, leads, campañas, movimientos…) con validación y formularios generados |
| Entregable = lista de secciones tipadas | Un solo visor/editor/revisor para expedientes, propuestas, lotes, paquetes y videos |
| Frontend sin router ni librería de estado | Rutas por `#hash`, un contexto y `fetch`; 2 dependencias de ejecución (react, react-dom) |
| SSE para progreso | Una conexión; el servidor lee la tabla de eventos. No hay sondeo ni llamadas a modelos abiertas |

## Procesos

```
START_JARVIS.cmd ─► python -m jarvis.launch ─┬─► uvicorn jarvis.api:app  (127.0.0.1:8765, sirve frontend/dist y /api)
                                             └─► python -m jarvis.worker (subproceso; lee la cola de SQLite)
```
El lanzador migra la base, vigila el worker y, al recibir Ctrl+C, detiene ambos. El worker arranca recuperando lo que
quedó «ejecutando».

## Datos (`data/jarvis.db`)

`spaces` (frontera de separación: personal/negocio/marca/cliente, con política de IA) · `records` (registros tipados) ·
`files` (+ contenido en `data/files/<espacio>/`) · `connections` (sin secretos) · `jobs` + `job_events` ·
`sources` (evidencia con URL, fechas, estado y texto) · `deliverables` + `deliverable_versions` + `comments` + `approvals` ·
`cache` · `usage` · `messages` (conversación con Jarvis) · `audit` · `settings`.

## Cola de trabajos

Estados: `pending` → `running` → `completed | failed | cancelled`, con esperas `waiting_config`, `waiting_quota`
(se reanuda sola en `resume_at`) y `waiting_approval`.

- **Idempotencia:** índice único parcial sobre `idempotency_key` para trabajos activos; repetir una petición devuelve el mismo trabajo.
- **Latido:** cada 5 s; un trabajo `running` sin latido en 45 s vuelve a la cola (o falla si agotó `max_attempts`).
- **Cancelación cooperativa:** el latido lee `cancel_requested`; los manejadores lo comprueban en cada etapa y `run_proc` termina el subproceso.
- **Reintentos:** solo errores inesperados o marcados como recuperables, con espera creciente y tope. Errores de datos no se reintentan.
- **Concurrencia:** N trabajos (2 por defecto), uno solo de video a la vez, y un semáforo por conexión según su `concurrency`.
- **Límites por trabajo:** llamadas, tokens, costo estimado y duración (`limits`), aplicados en `router.Ctx` y `JobCtx`.

## Router de IA (`router.py`)

1. Filtra conexiones por capacidad y estado (no configurada, sin permiso, cuota agotada, condiciones sin aceptar…).
2. Aplica la política del espacio (`sin_ia`, `solo_local`, `nube_permitida`) y la de datos personales de la conexión.
3. Excluye las de pago salvo que el gasto esté activado y quede presupuesto mensual; excluye las que superan su límite configurado.
4. Ordena: local → nube sin costo declarado → pago.
5. Caché por `(espacio, categoría, proveedor, modelo, versión de prompt, contenido)` con TTL; sin TTL no hay caché.
6. Reserva el costo estimado, llama (hasta 2 reintentos con espera solo ante timeout/red), concilia con los tokens reportados.
7. Si no queda ninguna: `needs_config` o `quota` con los motivos de cada conexión. Nunca cambia a pago ni a otro endpoint por su cuenta.

## Seguridad

- Escucha en loopback; middleware que valida `Host` y `Origin` (DNS rebinding y peticiones de otras webs). Sin autenticación: es de un solo usuario local.
- Secretos: `keyring` del sistema; alternativa en archivo del perfil de usuario (se avisa en la interfaz). La API solo devuelve una máscara.
- Importador web: solo http(s), resolución DNS a IP públicas, cada redirección revalidada, comprobación de la IP del par tras conectar,
  `robots.txt`, respeto de 401/403/429, 1,5 MB máximo. Las conexiones configuradas por el usuario sí pueden ser locales (Ollama).
- Archivos: lista de extensiones, nombre saneado, ruta generada por ID, tamaño máximo, descargas como adjunto (HTML generado se sirve con CSP `sandbox`).
- Modelos: salida validada por esquema; las fuentes no pueden cerrar su delimitador; citas verificadas; el asistente solo ejecuta herramientas
  del registro con argumentos validados y ninguna herramienta actúa fuera del equipo.
- Respaldo: sin secretos; restauración con validación de rutas y huellas, confirmación explícita y copia previa automática.

Limitación conocida del importador: entre la validación DNS y la conexión existe una ventana teórica de re-resolución; se mitiga
comprobando la IP real del par y descartando la respuesta, pero la petición GET ya se habría enviado.

## Interfaz

Dos modos sobre los mismos datos: **COMMAND** (núcleo de estado, conversación, voz, pendientes y actividad) y **WORKSPACE**
(módulos con tablas, formularios, editor y revisión). El núcleo deriva su estado de hechos: micrófono abierto, voz en curso,
petición o trabajos en ejecución, error de la última orden, decisiones por aprobar. Animaciones CSS, detenidas con la pestaña
oculta y desactivadas con `prefers-reduced-motion`.
