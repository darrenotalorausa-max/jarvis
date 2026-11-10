Guía para elegir. **No incluye precios ni cuotas en cifras**: cambian a menudo y dependen de tu cuenta, y Jarvis no pudo consultarlos al construirse. Mira siempre la página de precios oficial antes de decidir.

### Regla general

1. Empieza **gratis**: Gemini/Gemma en la nube, o Ollama en tu equipo.
2. Añade **búsqueda** (Tavily o Brave) para que la Mesa de oportunidades y los leads funcionen.
3. Pasa a **pago** solo cuando un trabajo concreto lo pida, con un presupuesto mensual puesto en la conexión.

### Opciones sin costo de entrada

| Opción | Qué da | Puntos fuertes | Límites |
|---|---|---|---|
| **Google AI Studio (Gemini y Gemma)** | Texto, JSON y visión por API | Nivel gratuito amplio para empezar; una sola clave | Cuotas por minuto y día; revisa el uso de tus datos en el nivel gratuito |
| **Ollama (local)** | Texto y JSON en tu equipo | Privado, sin cuota, sin internet | Calidad y velocidad dependen de tu hardware |
| **Groq** | Texto rápido y transcripción | Muy veloz; modelos abiertos; transcripción de audio | Cuota gratuita limitada |
| **OpenRouter, Together y similares** | Muchos modelos con una clave (formato OpenAI) | Algunos modelos marcados como gratuitos; cambiar de modelo sin cambiar de proveedor | Los gratuitos tienen límites estrictos y pueden desaparecer |
| **faster-whisper (local)** | Transcripción en tu equipo | Privado y sin cuota | Lento sin GPU |

### Opciones de pago que suelen compensar

| Opción | Para qué merece la pena | Cómo se conecta en Jarvis |
|---|---|---|
| **Claude (API de Anthropic)** | Redacción cuidada, análisis de documentos largos, instrucciones complejas | Conexión «API compatible con OpenAI» con la URL de compatibilidad que indique su documentación |
| **GPT (API de OpenAI)** | Extracción estructurada fiable, visión | «API compatible con OpenAI», URL `https://api.openai.com/v1` |
| **Gemini de pago** | Contextos muy largos, visión y bajo costo por volumen | Misma conexión de Gemini; marca «de pago» |
| **ElevenLabs** | Voz de respuesta natural | Conexión ElevenLabs |

**Importante:** una suscripción de chat (ChatGPT Plus, Claude Pro, Gemini Advanced) **no incluye** acceso por API. La API se contrata y factura aparte, por uso. Las cuentas compartidas de terceros tampoco dan clave de API.

### Qué modelo para qué trabajo

| Trabajo en Jarvis | Qué necesita | Recomendación |
|---|---|---|
| Órdenes libres a Jarvis | Rápido y barato | Modelo pequeño o local |
| Expedientes de oportunidad | JSON fiable y citas exactas | Modelo de gama media o alta; evita los muy pequeños |
| Leads y propuestas | JSON fiable, buen español | Gama media |
| Lotes de contenido | Creatividad y voz de marca | Gama media o alta; aplica tus skills |
| Describir imágenes | Visión | Un modelo que la soporte de verdad (márcala solo si es así) |
| Transcripción | Audio | Groq o faster-whisper |

### Ajustes de la conexión que más importan

| Ajuste | Valor de partida | Por qué |
|---|---|---|
| Máximo de tokens de salida | 2048–4096 | Los expedientes y lotes necesitan espacio; menos corta el JSON |
| Tiempo máximo | 60 s en nube, 180–300 s en local | Los modelos locales tardan más |
| Concurrencia | 1 en gratis o local; 2–3 en pago | Evita agotar la cuota por minuto |
| Límite por minuto y por día | Un poco por debajo de la cuota de tu cuenta | Jarvis se detiene antes de que el proveedor te bloquee |
| Presupuesto mensual | Obligatorio en conexiones de pago | Sin él, Jarvis no la usa |
| Política de datos | «Solo datos de negocio» | Tu espacio personal no sale a la nube |

### Orden que sigue Jarvis

Local primero, después nube sin costo declarado y, solo si activaste el gasto y queda presupuesto, de pago. Si no hay ninguna disponible, el trabajo espera y te dice por qué. Nunca cambia a pago por su cuenta.
