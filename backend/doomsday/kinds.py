"""Tipos de registro de Doomsday. Se añaden a `jarvis.records.KINDS`; la interfaz genera los formularios desde aquí.

Formato de campo: "nombre:Etiqueta[:tipo[:op1|op2]]". Tipos: text, textarea, number, bool, date, select, tags, url.
"""
from __future__ import annotations

from jarvis import records


def field(spec: str) -> dict:
    parts = spec.split(":")
    name, label = parts[0], parts[1]
    type_ = parts[2] if len(parts) > 2 and parts[2] else "text"
    f = records.F(name, label, type_)
    if type_ == "select":
        f["options"] = parts[3].split("|")
    return f


def K(label: str, plural: str, statuses: str, *fields: str) -> dict:
    return {"label": label, "plural": plural, "module": "doomsday", "statuses": statuses.split("|"), "fields": [field(f) for f in fields]}


KINDS: dict[str, dict] = {
    # --- Núcleo de datos de tiendas y pauta (G01)
    "dd_pedido": K("Pedido", "Pedidos", "entregado|devuelto|en_transito|confirmado|pendiente|cancelado",
                   "ref:ID del pedido", "fecha:Fecha:date", "tienda:Tienda", "producto:Producto", "campana:Campaña", "ciudad:Ciudad",
                   "unidades:Unidades:number", "precio:Precio cobrado:number", "costo_producto:Costo del producto:number", "flete:Flete de ida:number",
                   "flete_devolucion:Flete de devolución:number", "comision:Comisiones y recaudo:number",
                   "tel_hash:Huella del teléfono (no el número)", "capi_enviado:Compra enviada a la plataforma de anuncios:bool"),
    "dd_gasto_pauta": K("Gasto de pauta", "Gasto de pauta", "vigente",
                        "fecha:Fecha:date", "plataforma:Plataforma:select:meta|tiktok|google|otra", "cuenta:Cuenta", "campana:Campaña", "anuncio:Anuncio",
                        "producto:Producto", "gasto:Gasto:number", "compras:Compras reportadas:number", "impresiones:Impresiones:number", "clics:Clics:number",
                        "ref_campana:ID de campaña en la plataforma", "ref_anuncio:ID de anuncio en la plataforma"),
    "dd_liquidacion": K("Liquidación", "Liquidaciones de recaudo", "pendiente|liquidada|en_reclamo",
                        "fecha:Fecha:date", "transportadora:Transportadora o plataforma", "ref_pedido:ID del pedido", "valor_recaudado:Valor recaudado:number",
                        "valor_liquidado:Valor liquidado:number", "nota:Nota:textarea"),
    "dd_producto": K("Producto", "Productos", "candidato|en_prueba|ganador|descartado",
                     "proveedor_url:Enlace del proveedor:url", "nicho:Nicho", "costo:Costo:number", "precio:Precio de venta:number", "flete:Flete:number",
                     "angulo:Ángulo de venta:textarea", "puntaje:Puntaje:number", "notas:Notas:textarea"),
    "dd_tienda": K("Tienda", "Tiendas", "activa|pausada", "url:URL:url", "plataforma:Plataforma", "mercado:Mercado", "tema:Tema", "pixel:ID de píxel esperado"),
    "dd_chequeo": K("Comprobación", "Comprobaciones de salud", "ok|falla", "fecha:Fecha:date", "tienda:Tienda", "resultado:Resultado", "detalle:Detalle:textarea"),
    "dd_alerta": K("Alerta", "Alertas", "nueva|vista|resuelta", "origen:Módulo de origen", "fecha:Fecha:date", "detalle:Detalle:textarea"),
    "dd_activo": K("Activo", "Inventario de activos", "activo|inactivo", "tipo:Tipo:select:dominio|tienda|cuenta|herramienta|gasto", "proveedor:Proveedor",
                   "costo_mensual:Costo mensual:number", "vence:Vence:date", "notas:Notas:textarea"),
    "dd_movimiento": K("Movimiento", "Movimientos", "por_conciliar|conciliado", "fecha:Fecha:date", "cuenta:Cuenta", "empresa:Empresa", "concepto:Concepto",
                       "categoria:Categoría", "monto:Monto (negativo = salida):number"),
    "dd_tarea": K("Tarea", "Tareas", "pendiente|en_curso|bloqueada|hecha", "responsable:Responsable", "vence:Vence:date",
                  "prioridad:Prioridad:select:alta|media|baja", "notas:Notas:textarea"),
    "dd_sop": K("Procedimiento", "Procedimientos", "borrador|vigente|obsoleto", "rol:Rol", "pasos:Pasos:textarea", "video:Video:url", "prueba:Prueba de que quedó bien:textarea"),
    # --- Marketing y pauta
    "dd_regla_pauta": K("Regla de pauta", "Reglas de pauta", "activa|pausada", "plataforma:Plataforma:select:meta|tiktok|google|todas", "producto:Producto (vacío = todos)",
                        "cpa_limite:CPA límite:number", "gasto_minimo:Gasto mínimo antes de evaluar:number", "accion:Acción:select:pausar|avisar|proponer_subir"),
    "dd_creativo": K("Creativo", "Creativos", "por_revisar|aprobado|descartado|publicado|ganador", "producto:Producto", "origen:Anuncio de origen", "hook:Hook:textarea",
                     "angulo:Ángulo", "formato:Formato", "plataforma:Plataforma", "guion:Guion o descripción:textarea", "nombre_archivo:Nombre de archivo", "imagen_url:URL de la imagen (https pública):url"),
    "dd_experimento": K("Experimento", "Bitácora de experimentos", "planeado|corriendo|cerrado", "hipotesis:Hipótesis:textarea", "variable:Variable que cambia",
                        "metrica:Métrica de decisión", "inicio:Inicio:date", "fin:Fin:date", "resultado:Resultado observado:textarea",
                        "veredicto:Veredicto:select:gano|perdio|inconcluso"),
    "dd_competidor": K("Competidor", "Competidores", "siguiendo|archivado", "url:Biblioteca o tienda:url", "plataforma:Plataforma", "nicho:Nicho", "notas:Qué observar:textarea",
                       "huella:Huella de la última lectura", "precios_vistos:Precios vistos", "revisado:Última revisión:date"),
    "dd_oferta": K("Oferta", "Ofertas", "idea|en_prueba|ganadora|descartada", "producto:Producto", "precio:Precio:number", "costo:Costo:number",
                   "variantes:Variantes y bundles:textarea", "resultado:Resultado:textarea"),
    "dd_enlace": K("Enlace medido", "Enlaces medidos", "activo|archivado", "destino:Destino:url", "fuente:Fuente", "medio:Medio", "campana:Campaña", "contenido:Contenido o video",
                   "enlace:Enlace final:url", "clics:Clics:number", "leads:Leads:number"),
    "dd_politica": K("Regla de política", "Reglas de cumplimiento propias", "vigente|retirada", "plataforma:Plataforma:select:meta|tiktok|google|todas", "categoria:Categoría",
                     "regla:Qué no se puede decir o mostrar:textarea", "fuente:Fuente:url"),
    # --- Contenido y marca personal
    "dd_idea": K("Idea", "Banco de ideas", "capturada|investigada|en_guion|grabada|publicada|descartada", "angulo:Ángulo", "formato:Formato", "canal:Canal",
                 "prioridad:Prioridad:select:alta|media|baja", "notas:Notas:textarea"),
    "dd_pieza": K("Pieza", "Piezas de contenido", "borrador|por_revisar|aprobado|publicado", "tipo:Tipo:select:guion|clip|transcripcion|advertorial|carrusel|post",
                  "canal:Canal", "url:Enlace:url", "fecha:Fecha:date", "vistas:Vistas:number", "texto:Texto:textarea"),
    "dd_voz": K("Perfil de voz", "Perfiles de voz", "vigente|retirado", "rasgos:Rasgos de la voz:textarea", "frases:Frases y muletillas propias:textarea",
                "evitar:Lo que nunca dice:textarea", "estructura:Estructura habitual:textarea"),
    "dd_clip_pago": K("Envío de clip", "Envíos de clipping", "enviado|verificado|pagado|rechazado", "clipper:Clipper", "campana:Campaña", "url:Enlace:url",
                      "fecha:Fecha:date", "vistas:Vistas verificadas:number", "cpm:Pago por mil vistas:number", "tope:Tope de pago:number"),
    # --- Clientes y ventas B2B
    "dd_aplicacion": K("Aplicación", "Aplicaciones de prospectos", "nueva|calificada|no_calificada|agendada|cerrada", "empresa:Empresa", "contacto:Contacto",
                       "presupuesto:Presupuesto mensual:number", "urgencia:Urgencia:select:alta|media|baja", "decisor:Decide la compra:bool", "factura:Facturación mensual:number",
                       "necesidad:Necesidad:textarea", "origen:Origen (enlace o contenido)", "puntaje:Puntaje:number"),
    "dd_plan": K("Plan de servicio", "Planes de servicio", "vigente|retirado", "alcance:Alcance:textarea", "exclusiones:Exclusiones:textarea", "precio:Precio:number",
                 "duracion:Duración", "condiciones:Condiciones:textarea"),
    "dd_cliente": K("Cliente", "Clientes B2B", "activo|en_riesgo|pausado|perdido", "empresa:Empresa", "plan:Plan", "mensualidad:Mensualidad:number", "inicio:Inicio:date",
                    "ultimo_contacto:Último contacto:date", "resultado:Tendencia de resultados:select:mejora|estable|baja", "pagos_al_dia:Pagos al día:bool", "notas:Notas:textarea"),
    "dd_caso": K("Caso con evidencia", "Bóveda de pruebas", "por_verificar|verificado|autorizado", "cliente:Cliente", "resultado:Resultado medido:textarea",
                 "evidencia_url:Evidencia:url", "autorizado:Autorizó su uso público:bool", "fecha:Fecha:date"),
    "dd_mensaje": K("Mensaje", "Bandeja de mensajes", "nuevo|borrador_listo|respondido|escalado", "canal:Canal:select:whatsapp|correo|instagram|discord|otro",
                    "remitente:Remitente", "fecha:Fecha:date", "texto:Mensaje:textarea", "clasificacion:Clasificación", "borrador:Borrador de respuesta:textarea", "ref:ID externo"),
    "dd_trato": K("Oportunidad", "Pipeline", "prospecto|contactado|llamada|propuesta|negociacion|ganado|perdido", "empresa:Empresa", "contacto:Contacto", "valor:Valor:number",
                  "proxima_accion:Próxima acción", "fecha_proxima:Fecha de la próxima acción:date", "notas:Notas:textarea"),
    "dd_contrato": K("Contrato", "Contratos y cobros", "borrador|enviado|firmado|vencido", "cliente:Cliente", "tipo:Tipo", "valor:Valor:number", "recurrente:Cobro recurrente:bool",
                     "firma:Firma:date", "vence:Vence:date", "ultimo_pago:Último pago recibido:date", "enlace:Enlace:url"),
    "dd_paso": K("Paso", "Pasos de alta", "pendiente|hecho", "cliente:Cliente o tienda", "paso:Paso", "responsable:Responsable", "fecha:Fecha:date", "plantilla:Plantilla de origen"),
    "dd_firma": K("Aceptación", "Aceptaciones electrónicas", "vigente", "entregable:Documento", "version:Versión:number", "huella:Huella del texto aceptado", "nombre:Nombre de quien acepta",
                  "usuario:Usuario", "fecha:Fecha y hora", "ip:Dirección de origen"),
    "dd_entrega": K("Entrega", "Entregas del portal", "en_curso|entregado|aprobado", "cliente:Cliente", "tipo:Tipo:select:recurso|reporte|estado", "enlace:Enlace:url",
                    "fecha:Fecha:date", "notas:Notas:textarea"),
    "dd_prospecto": K("Prospecto", "Prospectos", "por_investigar|investigado|borrador_listo|enviado|respondio", "empresa:Empresa", "web:Web:url", "contacto:Contacto",
                      "investigacion:Investigación:textarea", "borrador:Borrador:textarea"),
    # --- Productos comercializables
    "dd_tema_item": K("Elemento del tema", "Tema Shopify", "pendiente|en_desarrollo|probada|publicada", "tipo:Tipo:select:seccion|plantilla|ajuste", "nicho:Nicho",
                      "reemplaza:App que reemplaza", "notas:Notas:textarea"),
    "dd_paquete": K("Paquete", "Paquetes para vender", "idea|armado|validado|en_venta", "publico:Público", "contenido:Qué incluye:textarea", "precio:Precio:number",
                    "validacion:Evidencia de demanda:textarea"),
    # --- Agentes
    "dd_qa": K("Revisión de página", "Revisiones de QA", "pendiente|ok|con_fallas", "url:Página:url", "movil:Revisada en móvil:bool", "hallazgos:Hallazgos:textarea"),
    "dd_lanzamiento": K("Lanzamiento", "Lanzamientos", "investigacion|pagina|creativos|cumplimiento|publicacion|medicion|cerrado", "producto:Producto", "tienda:Tienda",
                        "notas:Notas:textarea"),
    "dd_conocimiento": K("Nota de conocimiento", "Base de conocimiento", "vigente|obsoleto", "tema:Tema", "fuente:Fuente:url", "etiquetas:Etiquetas:tags", "contenido:Contenido:textarea"),
    # --- Personal y productividad
    "dd_suscripcion": K("Suscripción", "Suscripciones", "activa|por_cancelar|cancelada", "proveedor:Proveedor", "categoria:Categoría", "costo_mensual:Costo mensual (USD):number",
                        "uso:Uso real:select:diario|semanal|raro|nulo", "proyecto:Proyecto que la usa", "renueva:Renueva:date"),
    "dd_acceso": K("Acceso", "Bóveda de accesos", "activo|revocado", "coleccion:Empresa o colección", "usuario:Usuario", "url:URL:url", "tiene_2fa:Con 2FA:bool",
                   "compartido_con:Compartido con:tags"),
    "dd_nota": K("Nota", "Capturas y notas", "capturada|procesada", "tipo:Tipo:select:idea|tarea|nota|reflexion|reunion", "fecha:Fecha:date", "destino:Lista de destino",
                 "texto:Texto:textarea"),
    "dd_runbook": K("Runbook", "Runbooks", "vigente|obsoleto", "herramienta:Herramienta", "pasos:Pasos:textarea", "verificacion:Prueba final:textarea", "ultima_ejecucion:Última ejecución:date"),
    "dd_regla_archivo": K("Regla de archivo", "Reglas de archivos", "activa|pausada", "patron:Si el nombre contiene", "carpeta:Carpeta de destino", "formato:Formato de nombre"),
    "dd_bloque": K("Bloque", "Bloques de agenda", "planeado|hecho|movido", "dia:Día:date", "inicio:Inicio (HH:MM)", "fin:Fin (HH:MM)",
                   "tipo:Tipo:select:profundo|reunion|admin|personal", "notas:Notas"),
    "dd_decision": K("Decisión", "Registro de decisiones", "abierta|decidida|revisada", "contexto:Contexto:textarea", "opciones:Opciones consideradas:textarea",
                     "decision:Decisión y razón:textarea", "revisar:Revisar el:date"),
    # --- Salud, aprendizaje y desarrollo
    "dd_serie": K("Serie", "Registro de entrenamiento", "hecho", "fecha:Fecha:date", "ejercicio:Ejercicio", "peso:Peso (kg):number", "reps:Repeticiones:number",
                  "series:Series:number", "rpe:Esfuerzo percibido (1-10):number"),
    "dd_sueno": K("Noche", "Sueño y recuperación", "vigente", "fecha:Fecha:date", "horas:Horas dormidas:number", "calidad:Calidad (1-10):number",
                  "carga:Carga del día (1-10):number", "notas:Notas"),
    "dd_comida": K("Comida", "Plan de comidas", "planificada|hecha", "dia:Día", "comida:Comida:select:desayuno|almuerzo|cena|snack", "plato:Plato",
                   "calorias:Calorías:number", "proteina:Proteína (g):number", "ingredientes:Ingredientes (separados por coma):textarea"),
    "dd_practica": K("Práctica", "Prácticas", "pendiente|hecha", "fecha:Fecha:date", "tema:Tema", "transcripcion:Transcripción:textarea",
                     "correcciones:Correcciones:textarea", "vocabulario:Vocabulario:textarea"),
    "dd_aprendizaje": K("Cambio estudiado", "Aprendizaje por proyectos", "pendiente|entendido", "repo:Proyecto", "cambio:Cambio o diff:textarea",
                        "explicacion:Explicación:textarea", "ejercicio:Ejercicio:textarea"),
    "dd_fuente": K("Fuente", "Fuentes de estudio", "por_leer|resumido", "url:Enlace:url", "texto:Texto:textarea", "resumen:Resumen:textarea"),
    "dd_habito": K("Hábito", "Hábitos", "activo|pausado", "frecuencia:Frecuencia:select:diaria|semanal", "puntos:Puntos por cumplir:number", "area:Área"),
    "dd_habito_registro": K("Cumplimiento", "Cumplimientos de hábitos", "hecho", "habito:Hábito", "fecha:Fecha:date"),
    "dd_examen": K("Examen", "Preparación académica", "preparando|presentado", "materia:Materia", "fecha_examen:Fecha del examen:date", "temas:Temas:textarea",
                   "nivel:Nivel actual:select:bajo|medio|alto"),
    # --- Espiritualidad, relaciones y organización social
    "dd_lectura": K("Lectura", "Diario bíblico", "hecho|planificado", "fecha:Fecha:date", "pasaje:Pasaje", "reflexion:Reflexión:textarea"),
    "dd_ensenanza": K("Enseñanza", "Enseñanzas", "borrador|lista|dada", "fecha:Fecha:date", "pasajes:Pasajes", "idea_central:Idea central (la decides tú):textarea",
                      "bosquejo:Bosquejo:textarea"),
    "dd_contacto": K("Contacto", "Contactos", "activo|frio|archivado", "relacion:Relación", "empresa:Empresa", "ultimo_contacto:Último contacto:date",
                     "proxima_accion:Próxima acción", "conoce_a:Conoce a:tags", "notas:Notas:textarea"),
    "dd_reunion": K("Reunión", "Reuniones", "por_procesar|procesada", "fecha:Fecha:date", "asistentes:Asistentes", "consentimiento:Avisé de la grabación:bool",
                    "transcripcion:Transcripción:textarea", "resumen:Resumen:textarea", "tareas:Tareas y acuerdos:textarea"),
    "dd_fecha": K("Fecha importante", "Fechas importantes", "activa|archivada", "persona:Persona", "fecha:Fecha:date",
                  "tipo:Tipo:select:cumpleanos|aniversario|otro", "idea:Idea de detalle:textarea"),
    "dd_comunidad": K("Recurso de comunidad", "Comunidad", "borrador|activo", "tipo:Tipo:select:canal|rol|bienvenida|regla|recurso", "contenido:Contenido o tema del canal:textarea"),
    "dd_viaje": K("Viaje", "Viajes", "planeado|hecho", "destino:Destino", "inicio:Inicio:date", "fin:Fin:date", "itinerario:Itinerario:textarea", "tomas:Lista de tomas:textarea"),
    # --- Infraestructura transversal
    "dd_permiso": K("Permiso", "Permisos de agentes", "vigente|retirado", "modulo:Módulo", "nivel:Nivel de autonomía:select:A|B|C|D", "limite:Límite", "notas:Notas"),
    "dd_ruta_modelo": K("Regla de enrutado", "Reglas de enrutado", "vigente|retirada", "tarea:Tipo de tarea", "modelo:Modelo preferido", "motivo:Motivo"),
    "dd_token": K("Token de diseño", "Sistema de diseño", "vigente|retirado", "marca:Marca", "tipo:Tipo:select:color|tipografia|espacio|radio|componente", "valor:Valor", "uso:Uso"),
    "dd_respaldo": K("Respaldo", "Copias de seguridad", "al_dia|atrasado", "objetivo:Qué se respalda", "frecuencia:Frecuencia", "ultimo:Último respaldo:date", "ubicacion:Ubicación"),
}


def register() -> None:
    """Idempotente: añade los tipos de Doomsday al registro del motor."""
    for name, spec in KINDS.items():
        records.KINDS.setdefault(name, spec)
