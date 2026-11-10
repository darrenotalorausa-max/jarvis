Punto de partida sensato para cada parte de Jarvis. Ajusta después con tus resultados.

### Primer día, en este orden

1. **Espacios:** uno Personal (solo local) y uno por negocio o cliente. No mezcles.
2. **Conexiones:** una IA (Gemini/Gemma u Ollama) y un buscador (Tavily o Brave). Pulsa «Guardar y probar conexión» en cada una.
3. **Avisos:** Telegram o ntfy para enterarte en el celular de lo que termina o te necesita.
4. **Marcas y biblioteca:** registra cada marca con su voz, audiencia y restricciones.
5. **Respaldo:** crea el primero y guárdalo fuera del equipo.

### Por sección

| Sección | Ajustes recomendados | Error habitual |
|---|---|---|
| **Comando Jarvis** | Voz de entrada «navegador» si usas Chrome o Edge; respuesta por voz del sistema; «enviar al soltar» desactivado hasta que confíes en la transcripción | Dictar órdenes largas: mejor frases cortas |
| **Centro de negocios** | Una misión = una acción con criterio de cierre medible. Prioriza P1 y limita a 5 abiertas por negocio | Marcar como hecho sin evidencia: Jarvis no lo permite |
| **Mesa de oportunidades** | 3–4 consultas y 5–6 páginas por investigación; frescura «último año»; indica país e idioma | Pedir 8 consultas y 15 páginas siempre: gasta cuota sin mejorar el resultado |
| **Leads B2B** | 6–8 candidatos por búsqueda; registra antes tus servicios y exclusiones | Buscar sin describir el servicio: no puede valorar el encaje |
| **Fábrica de contenido** | 5 piezas por lote; aporta hechos comprobados; aplica 1–2 skills, no más | Lotes de 20 sin hechos: todo queda «por verificar» |
| **Editor audiovisual** | Formato 9:16, encuadre «recorte» con punto de interés ajustado, audio normalizado activado; subtítulos incrustados solo tras revisar el texto | Exportar sin previsualizar el encuadre |
| **Constructor Shopify** | Rellena especificaciones y condiciones reales; instala siempre en un duplicado del tema | Añadir beneficios sin respaldo: se excluyen |
| **Clipping** | Preferencia de CPM en 1 o 1,5 USD; actualiza presupuesto y reglas cada semana | Estimar ingresos con vistas totales: solo cuentan las elegibles |
| **Revisión** | Envía a revisión, lee las comprobaciones y aprueba la versión; el envío externo se autoriza aparte | Editar después de aprobar: invalida la aprobación |
| **Operaciones y economía** | Importa el CSV mensual de pagos; un movimiento, un estado (proyectado → acordado → facturado → cobrado) | Duplicar el movimiento al cambiar de estado |
| **Espacio personal** | Empieza por tres hábitos y el registro de sueño; repaso de tarjetas diario de 10 minutos | Registrar todo desde el primer día y abandonarlo en una semana |
| **Conexiones** | Límite diario por debajo de tu cuota; presupuesto mensual en las de pago; gasto de pago desactivado hasta necesitarlo | Marcar capacidades que el modelo no soporta |
| **Sistema** | 2 trabajos simultáneos; respaldo semanal; revisa «Uso y costos» cada mes | No respaldar nunca |

### Rendimiento

- **Trabajos simultáneos:** 2 por defecto. Súbelo a 3–4 solo con proveedores de pago y buen equipo (`JARVIS_WORKER_CONCURRENCY` en `.env`). El video siempre va de uno en uno.
- **Caché:** las búsquedas se reutilizan unas horas y los análisis un día. Vacíala en Diagnóstico si necesitas datos recién consultados.
- **Modelos locales lentos:** baja el máximo de tokens o usa la nube para expedientes largos.

### Seguridad

- Deja `JARVIS_HOST` sin definir salvo que quieras el panel en tu celular, y entonces con código de acceso.
- No pegues claves en notas, chats ni documentos: solo en Conexiones.
- Revisa la auditoría (Diagnóstico) si algo te sorprende: registra aprobaciones, envíos, cambios de política y órdenes remotas.
