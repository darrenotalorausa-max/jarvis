Jarvis puede abrirse en **su propia ventana**, como cualquier programa, sin pestañas del navegador ni ventana de consola.

### Windows

1. Ejecuta **SETUP_JARVIS.cmd** una vez (si ya lo hiciste antes de esta versión, ejecútalo de nuevo).
2. Aparecerá el acceso directo **Jarvis OS** en tu escritorio. Doble clic para abrir.
3. Para cerrar, cierra la ventana: Jarvis y sus trabajos se detienen.

También puedes usar **START_JARVIS.cmd**: abre la misma ventana, pero deja una consola con los mensajes.

### macOS y Linux

```
./scripts/start.sh --app
```

### Si no se abre la ventana

La ventana usa el componente web del sistema (WebView2 en Windows, que viene con Windows 10 y 11 actualizados). Si no está disponible, Jarvis se abre en el navegador como antes y sigue funcionando igual. Para apagarlo en ese caso: **Trabajos, uso y diagnóstico → Diagnóstico → Apagar Jarvis**.

### Qué cambia y qué no

- Tus datos siguen en tu equipo, en la carpeta `data/`. Por dentro Jarvis sigue siendo el mismo: la ventana muestra su panel local.
- El dictado por voz del navegador puede no estar disponible en la ventana de aplicación. Usa el modo de voz **«servidor»** (transcripción con Groq o Whisper local) en Comando.
- Mientras la ventana esté cerrada, Jarvis no trabaja ni envía avisos. Para tenerlo siempre encendido, lee «Servidor 24-7 y usuarios con rol».

Nota: el modo ventana se programó y se probó su arranque, pero no pudo verse en un Windows real durante el desarrollo. Si algo falla, START_JARVIS.cmd muestra el motivo.
