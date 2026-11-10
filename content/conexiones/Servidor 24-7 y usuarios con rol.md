Por defecto Jarvis vive en tu equipo y solo funciona mientras está abierto. Si quieres que los monitores, los avisos y las órdenes por Telegram funcionen siempre, instálalo en un equipo que no se apague: un mini PC en casa o un servidor privado.

### Opción A: un equipo siempre encendido en casa

1. Instala Jarvis ahí como siempre.
2. En su archivo `.env` define `JARVIS_HOST=0.0.0.0` y un `JARVIS_ACCESS_CODE` de 10 caracteres o más.
3. Inícialo. Desde tus otros dispositivos de la misma red entra con la dirección que muestra al arrancar y tu código.

### Opción B: servidor con Docker

En la carpeta de Jarvis:

```
echo JARVIS_ACCESS_CODE=un-codigo-largo-y-unico > .env
docker compose up -d --build
```

Los datos quedan en un volumen (`jarvis_data`) y las credenciales en otro (`jarvis_secrets`).

**Importante:** Jarvis sirve HTTP sin cifrar. No abras el puerto directamente a internet. Ponlo detrás de una VPN (Tailscale, WireGuard) o de un proxy inverso con HTTPS.

### Usuarios y roles

Con el acceso en red activo, en **Trabajos, uso y diagnóstico → Usuarios y roles** puedes crear cuentas:

- **Propietario** (tú, con el código de acceso): todo.
- **Equipo**: trabaja en los espacios que le asignes. No ve conexiones, apps, ajustes ni respaldos, y no aprueba envíos externos.
- **Cliente**: solo ve y comenta los entregables de sus espacios.

Los espacios personales nunca se comparten.

### Lo que no hace

- **No hay sincronización** entre un Jarvis en tu PC y otro en un servidor: son dos instalaciones con datos separados. Elige una como principal y entra a ella desde los demás dispositivos. Para mover datos de una a otra, usa **Respaldo y recuperación**.
- La configuración con Docker está escrita, pero **no se pudo ejecutar** durante el desarrollo. Pruébala antes de depender de ella.
