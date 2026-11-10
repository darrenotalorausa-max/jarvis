En **Apps conectadas** puedes enlazar Jarvis con cualquier servicio que ofrezca una API: tu tienda, pagos, anuncios, redes, documentos o herramientas propias.

### Cómo funciona

1. Abre **Apps conectadas → Catálogo** y pulsa **Conectar** en una plantilla (Shopify, Stripe, PayPal, Notion, Cloudflare, GitHub, Meta, TikTok, YouTube, Google Drive, Google Sheets, Gmail, WooCommerce, n8n) o en **API personalizada**.
2. Revisa la **URL base** y sustituye las partes en mayúsculas (TU-TIENDA, TU-SITIO) por las tuyas.
3. Pega la **credencial**. Se guarda en el almacén de credenciales de tu equipo, nunca en la base de datos ni en los respaldos.
4. Marca que revisaste las condiciones del servicio y guarda. Pulsa **Probar**.
5. En **Mis apps**, elige una acción, rellena sus variables y pulsa **Ejecutar**.

### Leer y escribir no son lo mismo

- **Lectura** (consultar pedidos, pagos, páginas, métricas): se ejecuta al momento y ves la respuesta.
- **Escritura** (crear, modificar, enviar, borrar): Jarvis crea un trabajo que **espera tu aprobación**. Verás la petición exacta —método, dirección y cuerpo— y solo se envía si la apruebas. La aprobación sirve una única vez y caduca.

Un modelo de IA nunca puede disparar una escritura: solo tú.

### Dónde sale cada credencial

| Servicio | Qué necesitas |
|---|---|
| Shopify | Token de una app personalizada de tu tienda (Configuración → Apps → Desarrollar apps). |
| Stripe | Clave restringida de solo lectura (Desarrolladores → Claves de API). |
| PayPal | Token de acceso obtenido con tu client ID y secreto; caduca en horas. |
| Notion | Secreto de una integración interna, compartida con las páginas que quieras leer. |
| Cloudflare | Token de API con permisos de lectura de zona. |
| GitHub | Token personal de acceso de solo lectura. |
| Meta (Facebook e Instagram) | Token de usuario del sistema con permisos de lectura de anuncios e Instagram. |
| TikTok | Token OAuth de tu app de TikTok for Developers. |
| YouTube | Clave de API de Google Cloud con YouTube Data API habilitada. |
| Google Drive, Sheets, Gmail | Client ID y secreto OAuth de tu propio proyecto de Google Cloud. |
| WooCommerce | Clave y secreto de consumidor (WooCommerce → Ajustes → Avanzado → API REST). |

Pide siempre el permiso mínimo: solo lectura si solo vas a consultar.

### Servicios con OAuth (Google y similares)

1. Crea un proyecto en la consola del proveedor y un cliente OAuth.
2. Registra como URL de redirección la que Jarvis te muestra en el formulario (termina en `/api/oauth/callback`).
3. Pega el client ID y el client secret, guarda y pulsa **Autorizar**. Se abrirá la página del proveedor; al aceptar, vuelves a Jarvis con la app conectada. El token se renueva solo.

### Añadir tus propias acciones

En **Editar → acciones (avanzado)** cada acción es un bloque con `id`, `label`, `method`, `path` (relativa a la URL base), `query`, `body` y `write`. Las partes entre llaves, como `{id}`, se convierten en campos del formulario. Todo lo que no sea GET se trata como escritura.

### Conectar otros programas a Jarvis

En la pestaña **Conectar otros programas a Jarvis** encontrarás la configuración para que Claude Desktop u otro cliente MCP use Jarvis como herramienta, y un token para enviarle órdenes desde n8n, Make, atajos del celular o un script.

### Límites que conviene saber

- Las plantillas siguen la documentación pública de cada servicio y **no se han comprobado con cuentas reales**: si un servicio cambia su API, edita la URL base o la acción.
- Cada servicio aplica sus propias cuotas y condiciones; Jarvis no las evita.
- No hay sincronización automática en segundo plano: las acciones se ejecutan cuando tú las pides.
