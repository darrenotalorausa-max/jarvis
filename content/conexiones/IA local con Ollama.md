Ollama ejecuta modelos en tu propio equipo: sin clave, sin cuota y sin que nada salga de tu ordenador. Es la opción que Jarvis usa primero.

### 1. Instala Ollama

1. Descárgalo de **ollama.com** e instálalo.
2. Abre una terminal y descarga un modelo, por ejemplo: `ollama pull gemma3` (mira en ollama.com/library los modelos y tamaños disponibles).
3. Comprueba que responde: `ollama run gemma3 "hola"`.

### 2. Conéctalo

1. **Conexiones → Nueva conexión → Ollama (local)**. La URL `http://127.0.0.1:11434` ya viene puesta.
2. **Listar modelos disponibles** y elige el que descargaste.
3. **Guardar y probar conexión**.

### 3. Qué esperar según tu equipo

| Memoria disponible | Tamaño de modelo razonable | Uso |
|---|---|---|
| 8 GB de RAM | 1–4 mil millones de parámetros | Resúmenes y órdenes sencillas |
| 16 GB de RAM | 7–12 mil millones | Redacción y extracción aceptables |
| GPU con 12 GB o más | 12–27 mil millones | Calidad cercana a la nube, mucho más rápido |

Sin GPU funciona, pero lento: un expediente puede tardar minutos. Si un modelo pequeño devuelve JSON defectuoso, Jarvis lo rechaza y te lo dice; prueba uno mayor o usa la nube para ese trabajo.

### 4. Problemas habituales

- **«No se pudo conectar»:** Ollama no está abierto. Ábrelo y vuelve a probar.
- **«No compatible»:** el nombre del modelo no coincide con ninguno descargado.
