Jarvis puede escribirte por WhatsApp usando la **Cloud API oficial de Meta**. Es más laborioso que Telegram y tiene una limitación importante, así que léela antes de empezar.

### La limitación de las 24 horas

Meta solo entrega **texto libre** si tú escribiste a ese número de empresa en las **últimas 24 horas**. Pasado ese tiempo exige plantillas aprobadas, que Jarvis todavía no envía. En la práctica: escribe «hola» al número de tu empresa una vez al día y los avisos llegarán. Si quieres avisos sin condiciones, usa Telegram o ntfy.

### Pasos

1. Entra en **developers.facebook.com**, crea una app de tipo **Business** y añade el producto **WhatsApp**.
2. En **WhatsApp → Configuración de la API** verás un número de prueba, su **Identificador de número de teléfono** (Phone number ID) y un **token de acceso**.
3. Añade tu propio número de celular como destinatario permitido y verifícalo con el código que te envían.
4. El token temporal caduca en horas. Para uso continuo crea un **usuario del sistema** en Meta Business y genera un token permanente con el permiso `whatsapp_business_messaging`.
5. En Jarvis: **Conexiones → Nueva conexión → WhatsApp Business**. Pega el token en **Credencial**, el **ID del número** y tu **número de destino** con prefijo de país y sin signos (ejemplo: `573001234567`).
6. Escribe «hola» desde tu WhatsApp al número de la empresa y pulsa **Guardar y probar conexión**.

### Notas

- Solo avisos salientes. Recibir órdenes por WhatsApp exige un servidor público con webhook, que una instalación local no tiene.
- Meta puede cobrar por conversaciones según el país y el tipo de mensaje: revisa sus precios vigentes. Si te cobran, marca la conexión como de pago.
- Este canal es para avisarte **a ti**. Jarvis no envía mensajes a clientes ni a terceros.

> No comprobado con una cuenta real de Meta.
