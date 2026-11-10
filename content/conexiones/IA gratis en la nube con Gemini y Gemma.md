Google ofrece por su API tanto los modelos **Gemini** como los modelos abiertos **Gemma**, con una misma clave. Muchas cuentas tienen un nivel gratuito con límites por minuto y por día; esos límites los decide Google para tu cuenta y pueden cambiar, así que Jarvis no los da por supuestos: los ves en tu panel de AI Studio.

### 1. Consigue la clave

1. Entra en **aistudio.google.com** con tu cuenta de Google.
2. Abre **Get API key** (Obtener clave de API) y pulsa **Create API key**.
3. Copia la clave. Trátala como una contraseña: no la pegues en chats ni documentos.

### 2. Conéctala en Jarvis

1. **Conexiones → Nueva conexión → Gemini Developer API**.
2. Pega la clave en **Credencial**. La URL ya viene puesta.
3. Pulsa **Listar modelos disponibles** y elige uno de la lista real de tu cuenta.
4. Marca **Habilitada** y acepta las condiciones del proveedor.
5. Pulsa **Guardar y probar conexión**. Si responde, queda «Operativa».
6. En **Proyectos → Espacios**, pon tu espacio de negocio en **Nube permitida** (por defecto solo admite proveedores locales).

### 3. Qué modelo elegir

| Familia | Cuándo usarla | Ten en cuenta |
|---|---|---|
| **Gemma** (los que empiezan por `gemma-`) | Redacción, resúmenes, lotes de contenido | Las versiones antiguas (Gemma 3) no aceptan instrucción de sistema ni modo JSON; Jarvis lo detecta y reintenta en modo compatible, pero el JSON sale menos fiable |
| **Gemini Flash** | Extracción estructurada: expedientes, leads, propuestas | Suele ser el más equilibrado para el trabajo diario |
| **Gemini Pro** | Análisis largos | Cuota gratuita más pequeña o de pago, según tu cuenta |

Los nombres exactos cambian con el tiempo: usa siempre los que aparezcan en «Listar modelos disponibles».

### 4. Si algo falla

| Mensaje en Jarvis | Qué significa |
|---|---|
| Credencial inválida | La clave está mal copiada o fue eliminada |
| Sin permiso | Ese modelo no está habilitado para tu cuenta o región |
| Cuota agotada | Llegaste al límite gratuito; Jarvis espera y reintenta solo, nunca cambia a pago |
| No compatible | El modelo ya no existe: vuelve a listar y elige otro |

### 5. Privacidad y costo

- Lo que envías a un proveedor en la nube sale de tu equipo. Revisa en las condiciones de Google si los datos del nivel gratuito pueden usarse para mejorar sus modelos.
- Tu espacio **Personal** no usa la nube salvo que lo autorices expresamente en la conexión («También datos de espacios personales»).
- No marques la conexión como «de pago» si usas el nivel gratuito. Si activas facturación en Google, márcala, pon tus precios y un presupuesto mensual.

> Pasos descritos según la documentación pública de Google; no se han podido comprobar con una clave real desde el entorno donde se construyó Jarvis.
