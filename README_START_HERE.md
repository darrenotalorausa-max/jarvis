# Jarvis OS · Empieza aquí

Mesa de oportunidades + fábrica de ejecución, en tu equipo. Una sola aplicación local: investigas, documentas evidencia,
preparas materiales, revisas, apruebas, exportas y registras resultados. Tus datos se quedan en esta carpeta.

> Estado real de cada función: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).
> Lo que **no** se ha podido comprobar todavía (lanzador de Windows, proveedores con credenciales reales, voz con micrófono)
> está indicado allí sin maquillar.

## 1. Requisitos

| Programa | Para qué | Instalación en Windows |
|---|---|---|
| **Python 3.11 o superior** | Motor de la aplicación | <https://www.python.org/downloads/> (marca «Add python.exe to PATH») o `winget install Python.Python.3.12` |
| **Node.js 18 o superior** | Solo para compilar la interfaz la primera vez | <https://nodejs.org/> o `winget install OpenJS.NodeJS.LTS` |
| **FFmpeg** (opcional) | Editor audiovisual | `winget install Gyan.FFmpeg` (compilación enlazada desde <https://ffmpeg.org/download.html>) |

`winget` descarga desde los orígenes del fabricante y verifica la huella del instalador. No hace falta ser administrador,
ni cambiar la política de PowerShell, ni desactivar el antivirus. Sin FFmpeg todo funciona salvo el editor de video.

## 2. Instalar y arrancar

**Windows:** doble clic en **`START_JARVIS.cmd`**. La primera vez prepara todo y crea el acceso directo **Jarvis OS** en tu escritorio; desde entonces Jarvis se abre en su propia ventana, como un programa. Si la ventana no está disponible en tu equipo, se abre en el navegador.
La primera vez prepara todo (entorno de Python, dependencias con versiones fijadas e interfaz) y tarda unos minutos;
después abre <http://127.0.0.1:8765> en tu navegador. Si falta algún requisito, la ventana te dice cuál y cómo instalarlo.

**macOS / Linux:**

```bash
./scripts/start.sh
```

- **Detener:** `Ctrl+C` en la ventana del lanzador (detiene la aplicación y el worker de forma limpia).
- **Si cierras la ventana a la fuerza:** los trabajos que estuvieran ejecutándose vuelven solos a la cola al reabrir.
- **Reinstalar o actualizar la interfaz:** `SETUP_JARVIS.cmd rebuild` (o `./scripts/setup.sh rebuild`).
- **Puerto ocupado u otros ajustes:** copia `.env.example` como `.env` y cambia `JARVIS_PORT`. En `.env` nunca van claves.

## 3. Primer inicio (5 pasos guiados)

1. Tu nombre y tus negocios → se crean un espacio **Personal** y uno de **negocio**, separados.
2. Registra una marca o un proyecto.
3. Añade un proveedor y pulsa «Guardar y probar conexión» (opcional).
4. Política de costo (pago desactivado) y de datos del espacio.
5. Recorrido real: con búsqueda, una investigación pequeña; sin ella, tarea + documento versionado + exportación.

## 4. Qué conectar y dónde (pantalla **Conexiones**)

| Para | Conexión | Qué necesitas |
|---|---|---|
| Redactar, analizar, interpretar órdenes libres | **Ollama** (local), **Gemini**, **Groq** o cualquier **API compatible con OpenAI** | Ollama instalado con un modelo, o una clave de API |
| Investigar oportunidades y buscar leads | **Tavily** o **Brave Search** | Clave de API |
| Transcribir video u órdenes de voz | Groq/compatible con modelo de audio, o **faster-whisper** local | Clave, o `pip install faster-whisper` en `.venv` |
| Voz de respuesta de mayor calidad | **ElevenLabs** (opcional) | Clave y un voice ID que tengas derecho a usar |
| Llevar entregables aprobados a tu CRM | **Webhook de exportación** | URL de entrada de tu sistema |

Las claves se guardan en el almacén de credenciales del sistema operativo (en Windows, el Administrador de credenciales),
nunca en la base de datos, en el navegador ni en los respaldos. Los modelos se eligen de la lista real de tu cuenta
(«Listar modelos disponibles»): Jarvis no trae ningún modelo fijado. Detalle por proveedor: [`docs/PROVIDER_MATRIX.md`](docs/PROVIDER_MATRIX.md).

Tener una clave no garantiza acceso a todos los modelos ni que el uso sea gratuito: la prueba de conexión te dice qué
responde de verdad, y la factura de tu proveedor es siempre la referencia.

### Guías dentro de Jarvis

En **Biblioteca → Conectar Jarvis** tienes el paso a paso de cada conexión (qué IA elegir gratis o de pago, Gemini y Gemma, Ollama,
Groq, búsqueda, Telegram, WhatsApp, ntfy, voz y uso desde el celular) y en **Ajustes recomendados** la configuración sugerida de
cada sección. Pulsa `Ctrl K` para buscar cualquier módulo o guía.

### Avisos y órdenes desde el celular

- **Telegram** (recomendado): avisos cuando un trabajo termina, falla o te necesita, y órdenes escribiendo a tu bot.
- **ntfy:** notificaciones push simples. **WhatsApp:** avisos por la API oficial de Meta, con su ventana de 24 horas.
- **Panel completo en el navegador del celular:** misma wifi, con código de acceso (ver `.env.example`).

## 5. Qué funciona sin ninguna API

Espacios, proyectos, marcas y biblioteca · archivos · tareas, capturas, enfoque, hábitos, actividad, diario, lecturas y
reflexión · revisión, versiones, comentarios, aprobaciones y exportación · importación CSV con mapeo y duplicados ·
economía y clipping (cálculos) · **editor de video completo con FFmpeg** (salvo transcripción) · paquete Shopify a partir
de tus propios campos · investigación a partir de URLs o archivos (evidencia sin análisis) · comandos directos de Jarvis
(«resume lo pendiente», «tarea: …», «cancela ese trabajo», «costos y cuotas») · respaldo y restauración.

Lo que necesita IA te dice qué le falta y espera («Esperando configuración»); nunca fabrica un resultado.

## 6. Carpetas

| Carpeta | Contenido |
|---|---|
| `data/` | Base de datos (`jarvis.db`) y archivos subidos o generados. **Es lo que debes respaldar.** |
| `exports/` | Lo que exportas (Markdown, JSON, CSV, copias de archivos) y `exports/backups/` |
| `logs/` | `api.log`, `worker.log`, `worker.out.log` (sin claves) |

## 7. Respaldar y recuperar

**Trabajos, uso y diagnóstico → Respaldo y recuperación.**

- **Crear respaldo:** genera un ZIP en `exports/backups/` con la base de datos, tus archivos y un manifiesto con huellas.
  No contiene credenciales. Cópialo fuera del equipo.
- **Restaurar:** eliges el ZIP, Jarvis valida formato, rutas y huellas, te muestra qué contiene y qué va a reemplazar, y
  exige escribir `RESTAURAR`. Antes guarda automáticamente una copia del estado actual (`…antes-de-restaurar…zip`).
- **Límites:** las credenciales no viajan en el respaldo (tendrás que reintroducirlas en otro equipo); un respaldo de una
  versión más nueva de Jarvis se rechaza; `exports/` no forma parte del respaldo.

## 8. Recorrido recomendado para comprobarlo todo

1. `START_JARVIS.cmd` → completa el primer inicio (al abrir suena el encendido; se desactiva en «Sonido»).
1. **Centro de negocios:** crea una misión, intenta marcarla «completada verificada» sin evidencia (lo impide) y pulsa «Pausar todos los agentes».
1. **Espacio personal:** registra una noche de sueño, una cuenta y una tarjeta de repaso; mira el Tablero.
1. **Biblioteca:** abre una guía, carga una skill propia y aplícala en Fábrica de contenido.
2. **Comando:** escribe `tarea: probar Jarvis`, luego `Resume lo pendiente`.
3. **Editor audiovisual:** crea un proyecto, importa un video corto, marca inicio/fin, «Añadir segmento», marca 9:16 y 1:1,
   «Previsualizar encuadre aquí», «Exportar segmentos» → abre el entregable.
4. **Revisión:** «Editar» → guarda como v2 → «Aprobar v2» → «Exportar Markdown».
5. **Constructor Shopify:** crea un producto con especificaciones → «Generar paquete» → pestaña «Paquetes generados».
6. **Operaciones → Movimientos:** importa un CSV de tu sistema de pagos, asigna columnas, previsualiza e importa.
7. **Clipping:** crea una campaña y un clip con vistas totales y elegibles; mira los cinco estados separados y las alertas.
8. **Conexiones:** añade un proveedor, «Guardar y probar conexión». Con búsqueda + texto: **Mesa de oportunidades** →
   «Investigar» → expediente con fuentes y fechas → «Convertir en proyecto».
9. **Leads:** «Buscar empresas» → «Preparar propuesta» → revísala (el precio queda «por definir» si no lo indicas).
10. **Comando (voz):** mantén pulsado el micrófono, suelta, corrige la transcripción y envía.
11. **Sistema → Respaldo:** crea un respaldo y restáuralo.

## 9. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| «El puerto 8765 ya está en uso» | Jarvis ya está abierto (entra en la dirección indicada) o cambia `JARVIS_PORT` en `.env` |
| Un trabajo queda en «Esperando configuración» | Lee el motivo en el trabajo; al guardar o probar la conexión se reanuda solo |
| «Esperando cuota» | El proveedor limitó el uso; se reintenta a la hora indicada. No se cambia a pago automáticamente |
| Los trabajos no avanzan | Diagnóstico → «Worker». Cierra y vuelve a abrir con el lanzador; revisa `logs/worker.out.log` |
| La voz no funciona | Abre «Voz» en Comando: el navegador puede no ofrecer reconocimiento. El texto funciona siempre |
| Quiero empezar de cero | Cierra Jarvis y renombra la carpeta `data/` (no la borres hasta estar seguro) |

Pruebas automáticas (desarrollo): `backend` → `..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` y
`..\.venv\Scripts\python.exe -m pytest tests -q`. Más detalle en [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md).

## Novedades de esta versión

- **Apps conectadas:** conecta Shopify, Stripe, PayPal, Notion, Cloudflare, GitHub, Meta, TikTok, YouTube, Google Drive, Sheets, Gmail, WooCommerce, n8n o cualquier API. Leer es inmediato; escribir requiere que apruebes la petición exacta.
- **Claude y ChatGPT** como modelos (Conexiones) y Jarvis como herramienta de tu asistente (MCP).
- **Monitores** que vigilan y avisan al celular, **usuarios con rol**, **importación de Apple Health y de extractos bancarios**, **tutor** que convierte un archivo en ruta de estudio, **preguntas a tus notas** y **texto bíblico** que tú cargas.
- **Servidor 24/7** opcional con Docker.
- **Imágenes y video por API**, **memoria a largo plazo** («recuerda que…»), **agentes con horario**, **voz manos libres** («Jarvis, …») y **aprobar o rechazar desde Telegram**.

Cada una tiene su guía en la Biblioteca. Lo que no se ha podido probar con cuentas reales está en `docs/IMPLEMENTATION_STATUS.md`.
