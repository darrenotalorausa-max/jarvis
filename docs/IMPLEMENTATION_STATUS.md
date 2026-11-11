# Estado de implementación

Fecha: 2026-11-10 · Versión 0.1.0. Este documento distingue lo comprobado de lo que solo está escrito.

**Cómo se comprobó:** 100 pruebas automáticas del backend (`pytest`, con FFmpeg real y proveedores simulados solo en las pruebas)
y un recorrido en navegador real (Chromium, `frontend/e2e/smoke.cjs`) sobre una instalación limpia en Linux.
**No se ha ejecutado nada en Windows ni contra proveedores o servicios reales** (no había credenciales ni acceso de red a ellos). Tampoco se pudo abrir la ventana de aplicación. Docker sí se construyó y arrancó, salvo el paso de FFmpeg (ver B).

## A. Implementado y probado

| Área | Qué está probado |
|---|---|
| Datos | Migraciones idempotentes, persistencia tras reinicio, validación de registros, aislamiento entre espacios |
| Cola y worker | Idempotencia, cancelación (pendiente y en ejecución), latido, recuperación tras caída, reintentos con tope, esperas por configuración/cuota/aprobación, worker como proceso separado, parada limpia |
| Router | Pago desactivado por defecto, presupuesto, orden local primero, caché por contenido/espacio/versión con TTL, políticas de espacio y de datos personales, cuota (429) sin bucles, reintentos limitados ante timeout, límites por trabajo |
| Conexiones | Estados comprensibles (credencial inválida, sin permiso, cuota agotada, no compatible, no configurada, condiciones sin aceptar), secretos fuera de la base y enmascarados, validación de URL |
| Seguridad | SSRF (privadas, loopback, metadatos, esquemas, redirecciones), `robots.txt` y bloqueos, traversal, tipos y tamaño de archivo, guardas de `Host`/`Origin`, redacción de secretos |
| Revisión | Versionado, comprobaciones automáticas, comentarios, aprobación ligada a versión/destino/caducidad, invalidación al editar, comparación de versiones, exportación MD/JSON/CSV/archivos |
| Envío externo | Webhook que no sale sin aprobación específica, vigente y de un solo uso |
| Mesa de oportunidades | Búsqueda → lectura → análisis → expediente con fuentes y fechas; cita no verificable ⇒ hipótesis; salida malformada rechazada; inyección en fuentes sin efecto; modo solo evidencia sin modelo; conversión a proyecto/brief/producto/servicio |
| Leads y propuestas | Búsqueda, exclusión de directorios, deduplicación por dominio, exclusiones, canal público, observación con cita verificada, propuesta sin precio inventado, exportación CSV |
| Fábrica de contenido | Lote desde brief con biblioteca solo de la marca, afirmaciones por verificar, recursos faltantes; sin modelo espera |
| Editor audiovisual | Lectura de medios, recorte, unión, 3 formatos, 3 encuadres, previsualización de encuadre, subtítulos SRT/VTT (importar, editar, exportar, incrustar), normalización, lotes, fallo aislado por clip, originales intactos, registro de comandos, manifiesto, sugerencias por silencios |
| Constructor Shopify | Datos faltantes, sección Liquid con schema válido, plantilla JSON coherente, ZIP, instrucciones, vista previa aislada, exclusión de beneficios sin respaldo, inspección de tema aportado (solo lectura) |
| Clipping | Cinco estados separados, estimado solo con vistas elegibles, alertas, preferencia de CPM, importación desde URL con cifras verificadas |
| Economía | Importación CSV con mapeo, duplicados y errores por fila; resumen por proyecto y moneda; contribución por hora |
| Personal y operaciones | Crear, editar, consultar, archivar y exportar en todos los tipos; hábitos de 7 días; temporizador de enfoque (interfaz, recorrido en navegador) |
| Jarvis (texto) | Comandos deterministas → herramientas; con modelo: solo herramientas del registro con argumentos validados; respuestas con ID y estado del trabajo |
| Visión | Descripción de imagen con conexión que declare visión; respeta la política del espacio |
| Respaldo | Ciclo crear → modificar → restaurar, sin secretos, copia previa automática, rechazo de respaldos alterados o con rutas inseguras |
| Interfaz | Primer inicio, las 13 pantallas, estados vacíos, CRUD, video de extremo a extremo, revisión, Shopify, error de conexión, trabajos, respaldo, foco por teclado, movimiento reducido, móvil sin desbordamiento, sin errores de consola ni respuestas 5xx |
| Diseño | Rediseño con la skill Anti-Slop: tokens, Inter + JetBrains Mono locales, elevación tonal, estados completos, núcleo con progreso real; verificador de la skill sin errores ni avisos (`docs/DESIGN.md`) |
| Centro de negocios | Misiones por negocio y sección con 12 estados; «completada verificada» exige criterio de cierre y evidencia; resumen que distingue «sin datos» de 0; decisiones; botón Ejecutar que lanza un trabajo real; pausa global de agentes |
| Avisos y celular | Telegram, WhatsApp Cloud API y ntfy: carga útil, validación, política por evento, exclusión de espacios personales, fallo de aviso que no rompe el trabajo; órdenes por Telegram solo del chat autorizado y sin repetición; acceso al panel en red con código, sesión y límite de intentos |
| Vida (Health, Mind, Faith, Wealth OS) | 20 tipos de registro con crear, editar, archivar y exportar; tablero con promedios de sueño y ánimo, patrimonio neto por moneda, presupuesto, alertas de suscripciones y vencimientos; repaso espaciado de tarjetas |
| Biblioteca y skills | 58 documentos (guías de conexión y de vida, tus 36 apuntes, modelos de negocio, atlas); búsqueda; carga de skills propias y su uso al generar contenido; bloqueo de rutas fuera de la biblioteca |
| Gemma en la API de Gemini | Reintento compatible cuando el modelo rechaza instrucción de sistema o modo JSON |
| Conector universal (Apps conectadas) | 14 plantillas + API personalizada; autenticación por token, cabecera, URL, Basic y OAuth 2.0 con renovación; lectura inmediata; escritura solo con aprobación de la petición exacta, de un solo uso y con caducidad; en navegador: crear app, leer, solicitar y rechazar. Todo contra servidores simulados o la propia API local |
| Claude y ChatGPT por API | Adaptadores con respuestas simuladas: Claude con el SDK oficial, OpenAI por HTTP; rechazo del modelo → error visible, sin cambio silencioso de modelo |
| Monitores proactivos | 9 reglas fijas sin IA, frecuencia, sin repetir hallazgos, tope diario de avisos, se detienen con la pausa global; en navegador: crear y ejecutar |
| Usuarios con rol | Propietario, equipo y cliente; contraseñas con PBKDF2; sesiones; lista de rutas permitidas por rol y por espacio; los espacios personales nunca se comparten; en navegador: crear usuario |
| Importadores | Apple Health (`export.zip`/`export.xml`: sueño, entrenamientos, pasos) y extractos OFX/QFX, ambos con vista previa y sin duplicar; OFX en navegador |
| Tutor y preguntas a las notas | Ruta de estudio desde archivo (módulos, autoevaluación, tarjetas) y respuesta citando notas, con modelo simulado; sin modelo permitido no se envía nada (en navegador) |
| Texto bíblico | Carga de una traducción aportada por el usuario (texto o JSON), pasaje por referencia y búsqueda; en navegador |
| MCP y API externa | Servidor MCP por stdio (initialize, tools/list, tools/call) y órdenes con token rotatorio, limitados a herramientas internas de un espacio de negocio |
| Servidor detrás de proxy | Con acceso en red, una petición reenviada por un proxy inverso o con `JARVIS_REQUIRE_LOGIN=1` (por defecto en Docker) exige sesión aunque llegue por loopback; antes entraba como propietario. Probado en pytest y en el contenedor |
| Generación de imágenes y video | Trabajo `media_generate`: OpenAI (imágenes y video con sondeo), Gemini (imágenes) y fal.ai (cola), con respuestas simuladas; guarda archivos y crea entregable; sin proveedor espera configuración; descargas solo por https a direcciones públicas; en navegador: formulario y espera sin proveedor |
| Memoria a largo plazo | «recuerda que…», «olvida…», «¿qué recuerdas?»; por espacio, sin duplicados; llega al prompt del asistente y, si se marca, al de los trabajos; nunca cruza espacios; en navegador |
| Agentes con horario | Diario, semanal o por intervalo; ejecutan una orden del asistente; una vez por periodo, tope diario, respetan la pausa; «Ejecutar ahora»; en navegador |
| Aprobar y rechazar desde Telegram | Botones y texto; solo el chat autorizado; un solo uso y caducidad; ligado a la versión del entregable o al hash de la petición; opción desactivada por defecto; con Telegram simulado |
| Voz manos libres | Palabra de activación «Jarvis» con el reconocimiento del navegador (probado con un reconocedor simulado: ignora lo que no empieza por «Jarvis», ejecuta la orden, modo «Jarvis» a solas) |
| Apagado desde el panel | `POST /api/shutdown` detiene API y worker cuando se inició con el lanzador |
| Instalación Unix | `scripts/setup.sh` + `scripts/start.sh` desde un clon limpio (ver ACCEPTANCE.md) |

## B. Implementado, sin comprobar con credenciales o entorno reales

| Elemento | Qué falta comprobar |
|---|---|
| `START_JARVIS.cmd` / `SETUP_JARVIS.cmd` | **Nunca se han ejecutado en Windows.** Escritos sin bloques con paréntesis y en ASCII para minimizar riesgos |
| Almacén de credenciales de Windows y macOS (`keyring`) | Solo se probó la alternativa en archivo (Linux sin almacén). `pywin32-ctypes` se añadió al lock a mano |
| Telegram, WhatsApp Cloud API, ntfy | Probados con respuestas simuladas; ningún mensaje real enviado. WhatsApp: no se comprobó la ventana de 24 h de Meta |
| Acceso desde el celular | Probado con cliente simulado de red; no con un teléfono real ni con el cortafuegos de Windows |
| Sonido de arranque y señales | Sintetizados con Web Audio; el navegador de pruebas no reproduce audio, no se han escuchado |
| Guías de la biblioteca | Redactadas con conocimiento general; los pasos de cada proveedor no se comprobaron con cuentas reales y no incluyen precios |
| Gemini, Groq, API compatible con OpenAI | Adaptadores probados con respuestas simuladas según su formato documentado; sin llamadas reales |
| Ollama | Probado contra un servidor local que imita su API por HTTP real; no contra Ollama ni un modelo real |
| Brave Search, Tavily | Formato verificado solo por resultados de búsqueda sobre su documentación (no se pudo abrir la documentación oficial desde el entorno de desarrollo). `count`/`freshness` de Brave y `time_range` de Tavily requieren confirmación |
| ElevenLabs (voz) | Petición según documentación (`/v1/text-to-speech/{voice_id}`, `/v2/voices`); sin llamada real |
| Transcripción (endpoint `/audio/transcriptions`, faster-whisper) | Sin llamada real ni modelo local descargado |
| Onda del núcleo con nivel real del micrófono | Implementada con Web Audio; sin probar con micrófono real |
| Voz en el navegador (pulsar para hablar, lectura de respuestas) | El navegador de pruebas no ofrece reconocimiento ni micrófono. Probado solo el respaldo a texto y que el micrófono no aparece abierto |
| Sección Shopify | Validada estructuralmente; **no instalada en una tienda ni en un tema real** |
| Todas las plantillas de Apps conectadas | Contrastadas el 2026-11-11 con la documentación oficial de versiones: Shopify pasa a `2026-10` y Meta a `v26.0` (la `v21.0` de anuncios había caducado); Notion `2022-06-28` sigue admitida. **Ninguna se ha probado con una cuenta real**: rutas, versiones de API y permisos pueden requerir ajuste |
| OAuth con Google u otro proveedor real | Probado solo con un servidor de autorización simulado |
| Generación real de imágenes y video | Formatos de petición según la documentación pública (OpenAI `/images/generations` y `/videos`, cola de fal.ai, `generateContent` de Gemini). **Ninguno probado con una cuenta real**; los parámetros por modelo pueden requerir «Parámetros extra» |
| Manos libres con micrófono real | No hay micrófono en el entorno. El modo con transcripción por servidor (detección de voz por volumen) **no se ha ejecutado**; solo compila |
| Botones de Telegram reales | Probado contra un Telegram simulado (`sendMessage` con `inline_keyboard`, `callback_query`, `answerCallbackQuery`) |
| Claude y OpenAI reales | Sin clave ni red hacia ellos durante el desarrollo |
| Ventana de aplicación (`--app`, pywebview) | Comprobado solo el respaldo: sin pywebview abre el navegador y el apagado funciona. **La ventana no se ha visto en ningún sistema.** El acceso directo de Windows (`scripts/windows/acceso_directo.ps1`) no se ha ejecutado |
| Docker (`Dockerfile`, `docker-compose.yml`) | Imagen construida y contenedor arrancado en pruebas: interfaz, inicio de sesión obligatorio, API, worker y persistencia tras reinicio. **Sin comprobar:** la instalación de FFmpeg (`apt-get`), bloqueada por la red del entorno, y `docker compose` como tal (se usó `docker build` + `docker run`) |
| Servidor MCP con un cliente real (Claude Desktop u otro) | Probado solo el protocolo con mensajes simulados |
| Apple Health con una exportación real | Probado con un XML de ejemplo con la estructura documentada |
| Calidad de los resultados con modelos reales | Los prompts no se han evaluado con ningún modelo real |

## C. Dependencia externa pendiente (la pones tú)

- **`DOOMSDAY.html`:** no se entregó. Sin él no existe extractor, manifiesto ni matriz de cobertura, y no hay ninguna tarea del manual cargada.

- Claves de API y aceptación de condiciones de cada proveedor; modelo elegido de tu lista.
- Ollama instalado con un modelo, si quieres IA local.
- FFmpeg para el editor; `faster-whisper` para transcripción local.
- URL de entrada (webhook) de tu CRM para el envío externo.
- Tu CRM, sistema de pagos y panel diario: **no están en este repositorio**, así que no hay integración directa. Se cubren con importación CSV, exportación CSV/JSON y el webhook.

## D. Limitaciones conocidas

- Sin autenticación: pensado para un usuario en loopback. No lo expongas a la red.
- La reserva de presupuesto es por llamada, no por trabajo completo; el tope por trabajo se aplica con `limits`.
- Los costos son estimaciones (uso reportado × precios que configuras). No se consulta la facturación del proveedor.
- La cuota «confirmada» solo se muestra si el proveedor la envía en cabeceras `x-ratelimit-*`.
- La investigación hace un número pequeño y configurable de consultas y lecturas; no cubre «todo internet». Páginas que
  requieren JavaScript, inicio de sesión o bloquean robots no se leen. PDF: solo texto extraíble (sin OCR).
- Las comprobaciones de enlaces son de formato; no se visita cada enlace.
- Las sugerencias de momentos sin transcripción se basan en pausas de audio, no en el contenido.
- Normalización de audio en una pasada; subtítulos incrustados con estilo fijo; el selector de variantes de Shopify no actualiza precio sin recargar.
- Los registros no guardan historial de cambios campo a campo (sí lo guardan los entregables y la auditoría de acciones sensibles).
- Clipping y experimentos se actualizan a mano o por CSV; no hay conectores de plataformas ni de analítica.
- Restaurar un respaldo no restaura credenciales ni la carpeta `exports/`.
- El modo de video (clipping, publicidad…) etiqueta el proyecto y orienta las sugerencias; no cambia la codificación.
- Interfaz solo en español.

## E. No implementado

- **Del superprompt DOOMSDAY:** importación del manual (falta el archivo), **sincronización entre una instalación local y otra en servidor** (son instalaciones separadas; se mueve con respaldo), conector de Google Ads (su API exige token de desarrollador), sincronización automática en segundo plano de los datos de las apps conectadas (las acciones se ejecutan a petición), modo claro y calendario. La memoria es la que el dueño dicta («recuerda que…»): Jarvis no aprende ni guarda nada por su cuenta. **Sistema de plugins:** no existe un cargador de código de terceros; la extensión se hace con datos, no con código: acciones declarativas del conector universal, skills en la biblioteca, MCP y la API de órdenes.
- **De los 20 módulos de vida:** sincronización en vivo con relojes o Health Connect (Apple Health se importa por archivo; el resto por CSV), pedidos a supermercados, escaneo de productos, alarmas, bloqueo de distracciones, tutor a partir de video, análisis del diario con IA, **texto bíblico y comentarios incluidos** (se carga la traducción que aporte el usuario; los comentarios van como notas), **conexión bancaria directa** (se importa el extracto OFX/QFX) y simulación de inversiones.

- Envío de mensajes, publicación en redes, activación de campañas o cambios de presupuesto (excluido a propósito en esta versión).
- Subida del paquete Shopify a un tema por API: solo exportación ZIP (la plantilla de Shopify en Apps conectadas lee datos y crea productos en borrador con aprobación). Tampoco un tema completo de tienda.
- Edición de imágenes o video existentes por IA, imagen a video y voces generadas dentro de los clips: solo texto a imagen y texto a video.
- Exportación nativa a Premiere, Resolve u otros editores.
- Agregación bancaria por API y conciliación contable.
- Escucha permanente fuera de la pantalla de Comando (manos libres se activa a mano y se detiene al salir) y clonación de voz.
- Aprobaciones por WhatsApp o ntfy (solo Telegram permite responder).
- Sincronización entre equipos y cifrado HTTPS propio (en red o servidor hay que ponerlo detrás de VPN o proxy).


## Doomsday (2026-11-11)
Aplicación aparte (`backend/doomsday`, `frontend/src/doomsday`, puerto 8766, datos en `doomsday_home/`). Detalle en `docs/DOOMSDAY.md`.

**Probado** (`tests/test_doomsday.py`, 15 pruebas; `frontend/e2e/doomsday.cjs`, 13 pasos en navegador):
- Catálogo de 100 módulos en 10 categorías y 4 capas aisladas; los 100 paneles abren.
- 100 skills integradas; edición, historial, restauración e importación (.md / .zip).
- Herramientas deterministas: utilidad COD, equilibrio, ofertas, escenarios, conciliación, guardián de pauta, cumplimiento, PII, embudo, churn, hábitos, suscripciones, UTM, salud de tienda (con bloqueo SSRF y ronda horaria).
- Órdenes `dd_run` con proveedor simulado: prompt con skill, fuentes entre `<fuente>`, entregable revisable, registros emitidos, revisión automática de cumplimiento, salida malformada rechazada, espera sin IA o entrega solo evidencia.
- Bóveda: el secreto no entra en SQLite ni en auditoría. Lectura de pedidos de Shopify sin duplicados.

**Integraciones (segunda tanda, `backend/doomsday/integrations.py`, `tests/test_doomsday_integrations.py`, 8 pruebas con transporte simulado; recorrido en navegador de 16 pasos):**
- Gasto de Meta Ads y TikTok Ads por anuncio y día → `dd_gasto_pauta` (alta o actualización, producto asignado si aparece en la campaña).
- Pausa y reanudación de campañas/anuncios (M01) y envío de WhatsApp (V05) como `connector_action`: nada sale sin aprobar la petición exacta.
- Exportación CSV del operador logístico (Dropi u otro): vista previa, estados, fletes, costos y liquidaciones; sin duplicados.
- G04: borrador completo en Shopify desde una ficha APROBADA (secciones como HTML, precio, imagen, título y descripción SEO).
- M06: video o imagen de un creativo aprobado por el router de medios del motor (OpenAI, Gemini, fal.ai).
- C04: recorte real con FFmpeg (probado con FFmpeg real, vertical 9:16). P04: grabación en el navegador → transcripción del motor.
- G07: en tiendas Shopify verifica producto disponible y carrito (solo lecturas).
- V06: un espacio por cliente; un módulo no se ejecuta fuera de su capa; clientes y equipo ven solo Revisión.

**Tercera tanda (`tools2.py`, `content.py`, `plans.py`, `tests/test_doomsday_tools2.py`, 10 pruebas; recorrido en navegador de 19 pasos):**
- Los 100 módulos tienen función propia sin IA (63 herramientas en total; una prueba lo exige y ejecuta cada herramienta en vacío).
- Búsqueda, perfil de voz medido, puntaje de hooks e ideas, radar de productos, vigía de competidores, ficha de una web, extracto de textos.
- Propuesta, contrato y reporte por plantilla desde planes y casos autorizados, guardables como entregable; cobros recurrentes; aceptación electrónica simple del cliente (rol «cliente», solo su espacio).
- Listas de pasos desde 7 plantillas, bandeja clasificada por reglas con el estado real del pedido, acuerdos de reuniones, análisis de llamadas, revisión de un diff.
- Tokens a CSS con contraste, paquetes de skills en .zip, 6 secciones Liquid (esquema JSON validado), plan de estudio, lectura, comidas, frases de venta en inglés.
- Planes con una sola aprobación y programables: publicar en Instagram, Facebook, LinkedIn y X; lanzar campaña, conjunto y anuncios de imagen en Meta (todo en pausa); compras entregadas a la API de conversiones con el teléfono solo en hash; estructura y bienvenida de Discord; subida de secciones a un tema.
- Lectura de Gmail y de Oura; sueño importado de Apple Health.
- Interfaz nueva con el lenguaje del manual DOOMSDAY del usuario, claro y oscuro, dial de 100 segmentos navegable con teclado.

**Vision: fusión de Jarvis y Doomsday (2026-11-11).** Una sola aplicación (`jarvis.launch` sirve la API unificada; el worker carga `doomsday.load()`). Probado: 136 pruebas de backend;
`smoke.cjs` completo (todo Jarvis: primer inicio, comando, estudios, apps, monitores, usuarios, memoria, manos libres, teclado, móvil) y `doomsday.cjs` (22 pasos) contra la aplicación unificada.
Jarvis ejecuta herramientas y órdenes de los módulos por comando directo; las capas reutilizan los espacios existentes; la carpeta `doomsday_home/` se importa una vez sin pisar nada.
No probado: la importación con una carpeta `doomsday_home/` real de un usuario (solo con una de prueba) y la vista del rol «equipo» en navegador.

**No probado con cuentas reales:** ninguna orden se ha ejecutado con un modelo real (calidad de las skills sin evaluar). Todas las plataformas (Shopify, Meta, TikTok, WhatsApp, Instagram, LinkedIn, X, Discord, Gmail, Oura) se probaron solo con transporte simulado y sus rutas se escribieron de memoria de la documentación pública: hay que validarlas una a una. Las secciones Liquid no se han instalado en ninguna tienda. Generación de video, micrófono, `START_DOOMSDAY.cmd` y la ventana `--app` sin ejecutar.

**No construido (y por qué):** publicar en TikTok y YouTube y anuncios de video (exigen subir el archivo binario; el conector solo envía JSON); lanzar en TikTok Ads; recibir WhatsApp o mensajes de Instagram (exigen webhook público y Doomsday es local); cobro en línea con tarjeta (necesita una pasarela) y firma certificada; Dropi por API; Higgsfield directo; bot de Discord conectado en vivo (se revisa a petición); compra de prueba en tiendas; un tema Shopify completo (son secciones que se añaden al tuyo); relojes distintos de Oura y Apple Health; paginación de informes de pauta de más de 500 filas.
