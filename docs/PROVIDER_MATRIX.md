# Matriz de proveedores

Los adaptadores están en `backend/jarvis/providers/`. Ningún ID de modelo, precio o cuota está fijado en el código:
el modelo se elige del listado real de la cuenta y los precios los introduce el usuario.

| Proveedor | Capacidades | URL por defecto | Autenticación | Endpoints usados | Estado de comprobación |
|---|---|---|---|---|---|
| Ollama (local) | Texto, JSON, visión* | `http://127.0.0.1:11434` | — | `GET /api/tags`, `POST /api/chat` (`format: json`) | Servidor simulado por HTTP real |
| Gemini Developer API | Texto, JSON, visión* | `https://generativelanguage.googleapis.com/v1beta` | Cabecera `x-goog-api-key` | `GET /models`, `POST /models/{modelo}:generateContent` (`responseMimeType`) | Respuestas simuladas |
| Groq | Texto, JSON, transcripción*, visión* | `https://api.groq.com/openai/v1` | `Authorization: Bearer` | `GET /models`, `POST /chat/completions`, `POST /audio/transcriptions` | Respuestas simuladas |
| API compatible con OpenAI | Texto; JSON, visión y transcripción* | (la indicas tú) | `Authorization: Bearer` | Igual que Groq; reintenta con `max_completion_tokens` si el modelo rechaza `max_tokens` | Respuestas simuladas |
| Claude (Anthropic) | Texto, JSON, visión* | API de Anthropic | Clave de API (SDK oficial `anthropic`) | `messages.create`, listado de modelos | Respuestas simuladas |
| OpenAI | Texto, JSON, visión*, transcripción* | `https://api.openai.com/v1` | `Authorization: Bearer` | Igual que «compatible con OpenAI» | Respuestas simuladas |
| Conector universal (`api`) | Acciones declarativas sobre cualquier API REST | (según plantilla) | Bearer, cabecera, parámetro, Basic u OAuth 2.0 (código + renovación) | Los definidos en cada plantilla de `connectors.PRESETS` | Servidor simulado; **ninguna plantilla probada con cuenta real** |
| Brave Search API | Búsqueda | `https://api.search.brave.com` | `X-Subscription-Token` | `GET /res/v1/web/search` (`q`, `count`, `country`, `search_lang`, `freshness`) | Respuestas simuladas |
| Tavily | Búsqueda | `https://api.tavily.com` | `Authorization: Bearer` | `POST /search` (`query`, `max_results`, `search_depth`, `time_range`) | Respuestas simuladas |
| ElevenLabs | Voz | `https://api.elevenlabs.io` | `xi-api-key` | `GET /v2/voices`, `POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` | Sin llamada real |
| faster-whisper (local) | Transcripción | — | — | Paquete opcional de Python | Sin modelo descargado |
| Telegram | Avisos y órdenes | `https://api.telegram.org` | Token del bot en la ruta | `POST /bot<token>/sendMessage`, `GET /bot<token>/getUpdates` | Respuestas simuladas |
| WhatsApp Cloud API | Avisos (solo salientes) | `https://graph.facebook.com/v26.0` | `Authorization: Bearer` | `POST /{phone_number_id}/messages` (texto libre; exige ventana de 24 h) | Respuestas simuladas |
| ntfy | Avisos push | `https://ntfy.sh` | Opcional `Authorization: Bearer` | `POST /{tema}` con cabecera `Title` | Respuestas simuladas |
| Webhook de exportación | Envío externo | (la indicas tú) | — | `POST` JSON del entregable aprobado | Destino simulado |

\* Capacidad opcional: márcala en la conexión solo si tu modelo la soporta. «Compatible con OpenAI» describe el formato de la
petición, no las capacidades del proveedor.

## Traducción de errores

| Respuesta del proveedor | Estado en Jarvis | Efecto |
|---|---|---|
| Falta la clave | No configurada | No se usa |
| 401 | Credencial inválida | Se prueba la siguiente conexión; el trabajo espera configuración si no hay otra |
| 403 | Sin permiso | Igual |
| 402, 429 | Cuota agotada | Conexión bloqueada hasta `Retry-After` (o 5 min); el trabajo pasa a «Esperando cuota» |
| 404, 405, 501 | No compatible | Modelo o endpoint inexistente |
| Timeout, red, 5xx | Error | Hasta 2 reintentos con espera; luego siguiente conexión |
| Proveedor en la nube sin condiciones aceptadas | Condiciones sin aceptar | No se usa |

## Costos y cuotas

- Categorías separadas en **Uso y costos**: texto, búsqueda, voz/transcripción; la ejecución local no tiene costo de API.
- **Cuota configurada** = límites por minuto/día que pones tú. **Cuota confirmada** = cabeceras `x-ratelimit-*` observadas.
- Conexión de pago: requiere activar el gasto en Conexiones y un presupuesto mensual; se reserva la estimación antes de llamar
  y se concilia con los tokens reportados. La factura del proveedor es la referencia definitiva.
- Una suscripción de chat o los créditos de una aplicación no equivalen a acceso por API.

## Pendiente de verificar con documentación oficial y claves reales

La red del entorno de desarrollo bloqueó el acceso directo a la documentación de los proveedores; los formatos se
contrastaron con resultados de búsqueda sobre esas páginas. Antes de confiar en una integración, usa «Guardar y probar
conexión» y revisa:

- Brave: nombre y máximo de `count`, valores de `freshness` (`pd`, `pw`, `pm`, `py`) y forma de `web.results`.
- Tavily: nombre y valores de `time_range` y presencia de `published_date`.
- Gemini: `usageMetadata` y `supportedGenerationMethods` en el listado de modelos.
- ElevenLabs: paginación de `/v2/voices` (solo se lee la primera página de 100).
