Groq sirve modelos abiertos a gran velocidad con una API de formato OpenAI. Útil para texto rápido y para **transcribir audio** (videos y órdenes de voz).

### Pasos

1. Crea una cuenta en **console.groq.com** y genera una clave en **API Keys**.
2. **Conexiones → Nueva conexión → Groq**. Pega la clave.
3. **Listar modelos disponibles** y elige un modelo de texto.
4. Para transcribir: marca la capacidad **Transcripción** y escribe en **Modelo de transcripción** el ID exacto de un modelo de audio de tu lista (los de la familia Whisper).
5. **Guardar y probar conexión**.

### Notas

- Los límites gratuitos por minuto y día dependen de tu cuenta; Jarvis muestra la cuota que Groq informa en sus cabeceras cuando la envía.
- La transcripción envía el audio a Groq. Si prefieres que no salga de tu equipo, usa la transcripción local (faster-whisper).
