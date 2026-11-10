Con un bot propio de Telegram, Jarvis te avisa en el celular cuando un trabajo termina, falla o queda esperando, y puedes darle órdenes escribiéndole. Es gratuito y no requiere servidor.

### 1. Crea tu bot

1. En Telegram, abre un chat con **@BotFather**.
2. Envía `/newbot`, ponle nombre y un usuario que termine en `bot`.
3. BotFather te da un **token** (algo como `123456:ABC…`). Es la credencial.

### 2. Averigua tu chat ID

1. Abre el chat con tu bot nuevo y envíale cualquier mensaje (por ejemplo, «hola»).
2. Escribe a **@userinfobot** y te dirá tu ID numérico. Ese número es tu **chat ID**.

### 3. Conéctalo

1. **Conexiones → Nueva conexión → Telegram**.
2. Pega el token en **Credencial** y tu número en **Chat ID**.
3. Elige qué eventos quieres recibir.
4. Marca **Habilitada**, acepta las condiciones y pulsa **Guardar y probar conexión**: debe llegarte un mensaje de prueba.

### 4. Órdenes desde el celular (opcional)

Activa **Aceptar órdenes desde este chat** y elige el espacio sobre el que actúan. Después escribe a tu bot, por ejemplo:

- `resume lo pendiente`
- `tarea: llamar al proveedor`
- `busca oportunidades en accesorios para gatos`
- `estado de los trabajos`
- `pausa los agentes` / `reanuda los agentes`

Jarvis solo obedece al chat ID que configuraste e ignora a cualquier otro. Las órdenes remotas solo usan herramientas internas: no envían, publican ni gastan nada. Jarvis debe estar abierto en tu equipo para leerlas.

### Qué se envía

Título del trabajo, estado y motivo. Nunca el contenido de un entregable ni datos de tu espacio Personal (salvo que lo autorices en la conexión).
