# Estado de implementación

Fecha: 2026-11-10 · Versión 0.1.0. Este documento distingue lo comprobado de lo que solo está escrito.

**Cómo se comprobó:** 70 pruebas automáticas del backend (`pytest`, con FFmpeg real y proveedores simulados solo en las pruebas)
y un recorrido en navegador real (Chromium, `frontend/e2e/smoke.cjs`) sobre una instalación limpia en Linux.
**No se ha ejecutado nada en Windows ni contra proveedores reales** (no había credenciales ni acceso de red a ellos).

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
| Instalación Unix | `scripts/setup.sh` + `scripts/start.sh` desde un clon limpio (ver ACCEPTANCE.md) |

## B. Implementado, sin comprobar con credenciales o entorno reales

| Elemento | Qué falta comprobar |
|---|---|
| `START_JARVIS.cmd` / `SETUP_JARVIS.cmd` | **Nunca se han ejecutado en Windows.** Escritos sin bloques con paréntesis y en ASCII para minimizar riesgos |
| Almacén de credenciales de Windows y macOS (`keyring`) | Solo se probó la alternativa en archivo (Linux sin almacén). `pywin32-ctypes` se añadió al lock a mano |
| Gemini, Groq, API compatible con OpenAI | Adaptadores probados con respuestas simuladas según su formato documentado; sin llamadas reales |
| Ollama | Probado contra un servidor local que imita su API por HTTP real; no contra Ollama ni un modelo real |
| Brave Search, Tavily | Formato verificado solo por resultados de búsqueda sobre su documentación (no se pudo abrir la documentación oficial desde el entorno de desarrollo). `count`/`freshness` de Brave y `time_range` de Tavily requieren confirmación |
| ElevenLabs (voz) | Petición según documentación (`/v1/text-to-speech/{voice_id}`, `/v2/voices`); sin llamada real |
| Transcripción (endpoint `/audio/transcriptions`, faster-whisper) | Sin llamada real ni modelo local descargado |
| Voz en el navegador (pulsar para hablar, lectura de respuestas) | El navegador de pruebas no ofrece reconocimiento ni micrófono. Probado solo el respaldo a texto y que el micrófono no aparece abierto |
| Sección Shopify | Validada estructuralmente; **no instalada en una tienda ni en un tema real** |
| Calidad de los resultados con modelos reales | Los prompts no se han evaluado con ningún modelo real |

## C. Dependencia externa pendiente (la pones tú)

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

- Envío de mensajes, publicación en redes, activación de campañas o cambios de presupuesto (excluido a propósito en esta versión).
- Conexión con la API de Shopify (subida a tema borrador o copia): solo exportación ZIP. Tampoco un tema completo de tienda.
- Generación de imágenes o video por API: se entregan prompts y paquete de producción.
- Exportación nativa a Premiere, Resolve u otros editores.
- Integraciones bancarias, conciliación contable y conectores de analítica.
- Escucha permanente por palabra clave, clonación de voz.
- Varios usuarios, permisos por persona y sincronización entre equipos.
