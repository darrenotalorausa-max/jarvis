Hay tres maneras, de menos a más completas.

### 1. Solo avisos

Conecta **ntfy** o **Telegram**. Jarvis te avisa cuando un trabajo termina, falla o necesita algo de ti.

### 2. Avisos y órdenes

Con **Telegram** y la opción «Aceptar órdenes» puedes pedirle resúmenes, crear tareas, lanzar investigaciones o pausar los agentes desde cualquier lugar. Tu equipo debe estar encendido con Jarvis abierto.

### 3. El panel completo en el navegador del celular (misma wifi)

Jarvis solo escucha en tu propio equipo por seguridad. Para abrirlo a los dispositivos de tu red:

1. Copia `.env.example` como `.env` en la carpeta de Jarvis.
2. Añade estas dos líneas (elige tu propio código, 10 caracteres o más):

```
JARVIS_HOST=0.0.0.0
JARVIS_ACCESS_CODE=un-codigo-largo-y-tuyo
```

3. Reinicia Jarvis. La ventana del lanzador muestra la dirección para el celular, algo como `http://192.168.1.20:8765/`.
4. Ábrela en el navegador del celular, introduce el código y añádela a la pantalla de inicio.

**Precauciones:**

- La conexión dentro de tu red **no va cifrada**. Úsalo solo en la wifi de tu casa u oficina, nunca en redes públicas ni abriendo puertos del router hacia internet.
- Windows puede preguntar si permites el acceso de Python en redes privadas: acepta solo «redes privadas».
- Sin código de acceso, Jarvis se niega a arrancar en este modo.
- Para acceso desde fuera de casa de forma segura hace falta una red privada tipo VPN (por ejemplo Tailscale o WireGuard); eso queda fuera de lo que Jarvis configura por ti.
