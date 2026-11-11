"""Registros tipados por espacio. Cada tipo declara su esquema; la interfaz genera formularios a partir de él."""
from __future__ import annotations
import csv
import io
from datetime import date

from . import db
from .util import dumps, loads, new_id, now_iso


def F(name, label, type_="text", **kw):
    return {"name": name, "label": label, "type": type_, **kw}


PROJECT_TYPES = ["ecommerce", "infoproducto", "servicio_b2b", "clipping", "marca_personal", "otro"]

KINDS: dict[str, dict] = {
    # --- Proyectos, marcas y biblioteca
    "project": {"label": "Proyecto", "plural": "Proyectos", "module": "proyectos", "statuses": ["activo", "pausado", "cerrado"], "fields": [
        F("type", "Tipo de negocio", "select", options=PROJECT_TYPES), F("description", "Descripción", "textarea"),
        F("owner", "Responsable"), F("start_date", "Inicio", "date"), F("due_date", "Fecha objetivo", "date"),
        F("budget", "Presupuesto", "number"), F("currency", "Moneda")]},
    "brand": {"label": "Marca", "plural": "Marcas", "module": "proyectos", "statuses": ["activa", "pausada"], "fields": [
        F("description", "Descripción", "textarea"), F("voice", "Voz y tono", "textarea"), F("audience", "Audiencia", "textarea"),
        F("market", "Mercado"), F("language", "Idioma"), F("restrictions", "Restricciones y temas vetados", "textarea")]},
    "brand_asset": {"label": "Elemento de biblioteca", "plural": "Biblioteca de marca", "module": "proyectos", "statuses": ["vigente", "retirado"], "fields": [
        F("type", "Tipo", "select", options=["voz", "pilar", "ejemplo", "historia_real", "fuente", "permiso"], required=True),
        F("body", "Contenido", "textarea"), F("source_url", "Fuente (URL)", "url"),
        F("permission", "Permiso de uso", "select", options=["propio", "autorizado", "sin_confirmar"], required=True),
        F("permission_note", "Detalle del permiso")]},
    "service": {"label": "Servicio", "plural": "Servicios que ofrezco", "module": "leads", "statuses": ["activo", "retirado"], "fields": [
        F("description", "Descripción", "textarea"), F("deliverables", "Entregables típicos", "textarea"),
        F("price_from", "Precio desde", "number"), F("currency", "Moneda"), F("timeline", "Plazo típico")]},
    # --- Operaciones
    "milestone": {"label": "Hito", "plural": "Hitos", "module": "operaciones", "statuses": ["pendiente", "en_curso", "hecho"], "fields": [
        F("due_date", "Fecha", "date"), F("owner", "Responsable"), F("notes", "Notas", "textarea")]},
    "brief": {"label": "Brief", "plural": "Briefs", "module": "operaciones", "statuses": ["borrador", "listo", "producido"], "fields": [
        F("objective", "Objetivo", "select", options=["viralidad", "confianza", "captacion", "ventas"]),
        F("channel", "Canal"), F("audience", "Audiencia", "textarea"), F("product", "Producto u oferta", "textarea"),
        F("references", "Referencias", "textarea"), F("facts", "Hechos comprobados (uno por línea)", "textarea"),
        F("count", "Piezas", "number"), F("notes", "Notas", "textarea")]},
    "delivery": {"label": "Entrega", "plural": "Entregas", "module": "operaciones", "statuses": ["pendiente", "entregado", "aceptado"], "fields": [
        F("client", "Cliente"), F("due_date", "Fecha", "date"), F("owner", "Responsable"), F("link", "Enlace o ubicación"),
        F("notes", "Notas", "textarea")]},
    "capacity": {"label": "Capacidad", "plural": "Capacidad", "module": "operaciones", "statuses": ["vigente"], "fields": [
        F("owner", "Persona o recurso", required=True), F("week", "Semana (lunes)", "date"),
        F("hours_available", "Horas disponibles", "number"), F("notes", "Notas", "textarea")]},
    # --- Economía
    "transaction": {"label": "Movimiento", "plural": "Movimientos", "module": "economia", "statuses": ["vigente", "anulado"], "fields": [
        F("type", "Tipo", "select", options=["ingreso", "gasto", "credito", "suscripcion"], required=True),
        F("stage", "Estado económico", "select", options=["proyectado", "acordado", "facturado", "cobrado", "pagado"], required=True),
        F("amount", "Importe", "number", required=True), F("currency", "Moneda"), F("date", "Fecha", "date"),
        F("counterparty", "Contraparte"), F("category", "Categoría"), F("external_id", "Referencia externa"),
        F("notes", "Notas", "textarea")]},
    "time_entry": {"label": "Tiempo", "plural": "Registro de tiempo", "module": "economia", "statuses": ["vigente"], "fields": [
        F("date", "Fecha", "date"), F("hours", "Horas", "number", required=True), F("owner", "Persona"), F("notes", "Notas", "textarea")]},
    # --- Clipping
    "campaign": {"label": "Campaña de clipping", "plural": "Campañas", "module": "clipping",
                 "statuses": ["evaluando", "activa", "pausada", "finalizada", "descartada"], "fields": [
        F("source_url", "Fuente (URL)", "url"), F("source_date", "Fecha de la fuente", "date"), F("organizer", "Organizador"),
        F("cpm_usd", "CPM (USD por 1.000 vistas válidas)", "number"), F("budget_usd", "Presupuesto (USD)", "number"),
        F("budget_updated", "Presupuesto actualizado el", "date"), F("countries", "Países", "tags"), F("platforms", "Plataformas", "tags"),
        F("accounts_rules", "Requisitos de cuentas", "textarea"), F("valid_views_rules", "Qué cuenta como vista válida", "textarea"),
        F("restrictions", "Restricciones de contenido", "textarea"), F("start_date", "Inicio", "date"), F("end_date", "Fin", "date"),
        F("approval_process", "Proceso de aprobación", "textarea"), F("min_views", "Mínimo de vistas", "number"),
        F("min_payout_usd", "Retiro mínimo (USD)", "number"), F("payout_method", "Método de retiro"),
        F("rules_updated", "Reglas revisadas el", "date"), F("notes", "Notas", "textarea")]},
    "clip": {"label": "Clip", "plural": "Clips publicados", "module": "clipping", "statuses": ["publicado", "retirado"], "fields": [
        F("campaign_id", "Campaña", "ref", ref="campaign", required=True), F("url", "URL del clip", "url"), F("platform", "Plataforma"),
        F("published", "Publicado el", "date"), F("views_total", "Vistas totales", "number"),
        F("views_eligible", "Vistas elegibles/aceptadas", "number"), F("approved_usd", "Importe aprobado (USD)", "number"),
        F("paid_usd", "Importe cobrado (USD)", "number"),
        F("review_status", "Revisión del organizador", "select", options=["pendiente", "aprobado", "rechazado"]),
        F("rejection_reason", "Motivo de rechazo"), F("video_project_id", "Proyecto de video", "ref", ref="video_project"),
        F("updated_on", "Datos actualizados el", "date")]},
    # --- Leads
    "lead": {"label": "Lead", "plural": "Leads", "module": "leads",
             "statuses": ["nuevo", "investigado", "propuesta_lista", "en_revision", "exportado", "descartado"], "fields": [
        F("website", "Web", "url"), F("domain", "Dominio"), F("source_url", "Fuente", "url"), F("source_date", "Fecha de consulta", "date"),
        F("public_channel", "Canal comercial publicado"), F("segment", "Segmento"),
        F("observation", "Observación verificable", "textarea"), F("evidence", "Evidencia (cita textual)", "textarea"),
        F("hypotheses", "Hipótesis", "textarea"), F("unknowns", "Desconocidos", "textarea"),
        F("service", "Servicio propuesto"), F("sample", "Muestra gratuita", "textarea"), F("offer", "Oferta pagada", "textarea"),
        F("owner", "Responsable"), F("next_action", "Próxima acción"), F("next_action_date", "Fecha próxima acción", "date")]},
    "exclusion": {"label": "Exclusión", "plural": "Exclusiones", "module": "leads", "statuses": ["vigente"], "fields": [
        F("domain", "Dominio o nombre a excluir", required=True), F("reason", "Motivo")]},
    # --- Shopify
    "product": {"label": "Producto", "plural": "Productos", "module": "shopify", "statuses": ["borrador", "listo"], "fields": [
        F("type", "Tipo", "select", options=["fisico", "digital", "servicio", "software"]),
        F("specs", "Especificaciones (una por línea)", "textarea"), F("price", "Precio", "number"),
        F("compare_price", "Precio de comparación (solo si es real)", "number"), F("currency", "Moneda"),
        F("audience", "Audiencia", "textarea"), F("market", "Mercado"), F("language", "Idioma"),
        F("conditions", "Condiciones (envío, devolución, garantía)", "textarea"),
        F("benefits", "Beneficios con respaldo (uno por línea: beneficio | respaldo)", "textarea"),
        F("faq", "Preguntas frecuentes (una por línea: pregunta | respuesta)", "textarea"),
        F("theme_target", "Tema objetivo"), F("handle", "Handle del producto en Shopify")]},
    # --- Experimentos
    "experiment": {"label": "Experimento", "plural": "Experimentos", "module": "revision", "statuses": ["planificado", "en_curso", "concluido"], "fields": [
        F("hypothesis", "Hipótesis", "textarea", required=True), F("variable", "Variable"), F("version_a", "Versión A"),
        F("version_b", "Versión B"), F("limit", "Límite (presupuesto, muestras o tiempo)"), F("window_start", "Inicio de ventana", "date"),
        F("window_end", "Fin de ventana", "date"), F("metric", "Métrica"), F("result", "Resultado observado", "textarea"),
        F("decision", "Decisión", "textarea")]},
    "metric_entry": {"label": "Medición", "plural": "Mediciones", "module": "revision", "statuses": ["vigente"], "fields": [
        F("experiment_id", "Experimento", "ref", ref="experiment", required=True), F("date", "Fecha", "date"),
        F("variant", "Variante"), F("metric", "Métrica"), F("value", "Valor", "number", required=True), F("source", "Origen del dato")]},
    # --- Espacio personal
    "task": {"label": "Tarea", "plural": "Tareas", "module": "personal", "statuses": ["pendiente", "en_curso", "hecha"], "fields": [
        F("due_date", "Fecha", "date"), F("priority", "Prioridad", "select", options=["alta", "media", "baja"]), F("notes", "Notas", "textarea")]},
    "capture": {"label": "Captura", "plural": "Capturas rápidas", "module": "personal", "statuses": ["nueva", "procesada"], "fields": [
        F("body", "Texto", "textarea"), F("origin", "Origen", "select", options=["texto", "voz"])]},
    "focus_block": {"label": "Bloque de enfoque", "plural": "Bloques de enfoque", "module": "personal", "statuses": ["planificado", "completado", "omitido"], "fields": [
        F("date", "Fecha", "date"), F("start_time", "Hora de inicio"), F("minutes", "Minutos", "number"),
        F("goal", "Objetivo", "textarea"), F("interruptions", "Interrupciones", "number"), F("outcome", "Resultado", "textarea")]},
    "habit": {"label": "Hábito", "plural": "Hábitos", "module": "personal", "statuses": ["activo", "pausado"], "fields": [
        F("frequency", "Frecuencia", "select", options=["diario", "semanal"]), F("target", "Meta"), F("notes", "Notas", "textarea")]},
    "habit_log": {"label": "Registro de hábito", "plural": "Registros de hábitos", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("habit_id", "Hábito", "ref", ref="habit", required=True), F("date", "Fecha", "date", required=True),
        F("done", "Cumplido", "bool"), F("note", "Nota")]},
    "activity": {"label": "Actividad y descanso", "plural": "Actividad y descanso", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("date", "Fecha", "date"), F("type", "Tipo de actividad"), F("minutes", "Minutos", "number"),
        F("intensity", "Intensidad", "select", options=["suave", "moderada", "alta"]), F("sleep_hours", "Horas de sueño", "number"),
        F("notes", "Notas", "textarea")]},
    "journal": {"label": "Entrada de diario", "plural": "Diario privado", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("date", "Fecha", "date"), F("mood", "Ánimo (1 bajo – 5 alto)", "select", options=["1", "2", "3", "4", "5"]), F("body", "Texto", "textarea")]},
    "reading": {"label": "Lectura o aprendizaje", "plural": "Lecturas y aprendizaje", "module": "personal", "statuses": ["pendiente", "en_curso", "terminado"], "fields": [
        F("author", "Autor o fuente"), F("type", "Tipo", "select", options=["libro", "curso", "articulo", "otro"]),
        F("progress", "Progreso"), F("notes", "Notas", "textarea"), F("takeaways", "Aprendizajes", "textarea")]},
    "reflection": {"label": "Reflexión", "plural": "Reflexión y vida espiritual", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("date", "Fecha", "date"), F("practice", "Práctica", "select", options=["reflexion", "oracion", "meditacion", "gratitud", "otra"]),
        F("minutes", "Minutos", "number"), F("body", "Texto", "textarea")]},
    # --- Centro de negocios (motor de misiones)
    "mission": {"label": "Misión", "plural": "Misiones", "module": "negocios",
                "statuses": ["pendiente", "preparada", "en_cola", "ejecutando", "esperando_integracion", "esperando_datos", "esperando_aprobacion",
                             "verificacion", "completada_verificada", "fallida", "cancelada", "no_aplica"], "fields": [
        F("business", "Negocio", "select", options=["ecom", "b2b", "clip", "brands", "otro"], required=True),
        F("section", "Sección", "select", options=["A_base_estable", "B_por_lanzamiento", "C_ciclo_diario", "D_revisiones", "E_etapas_de_crecimiento", "F_automatizaciones"], required=True),
        F("instance", "Instancia (lanzamiento, ciclo o revisión)"), F("priority", "Prioridad", "select", options=["P1", "P2", "P3"]),
        F("action", "Acción", "textarea"), F("how", "Cómo", "textarea"), F("deliverable", "Entregable", "textarea"),
        F("closure", "Criterio de cierre", "textarea"), F("ai_part", "Qué hace la IA", "textarea"), F("human_part", "Intervención humana", "textarea"),
        F("trigger", "Activación"), F("dependency", "Dependencia (descriptiva, sin validar)"), F("owner", "Responsable"),
        F("level", "Nivel de automatización", "select", options=["automatica", "semiautomatica", "humana", "bloqueada_por_integracion"]),
        F("evidence", "Evidencia verificable (enlace, ID de entregable o archivo)", "textarea"), F("result", "Resultado real del negocio", "textarea"),
        F("next_step", "Próximo paso"), F("source_ref", "Referencia a la fuente original")]},
    "decision": {"label": "Decisión", "plural": "Decisiones", "module": "negocios", "statuses": ["abierta", "revisada"], "fields": [
        F("business", "Negocio", "select", options=["ecom", "b2b", "clip", "brands", "otro"]),
        F("verdict", "Decisión", "select", options=["continuar", "corregir", "detener", "ampliar"], required=True),
        F("hypothesis", "Hipótesis", "textarea", required=True), F("limit", "Límite (dinero, tiempo o muestras)"),
        F("window", "Ventana de evaluación"), F("evidence", "Evidencia y fuente del dato", "textarea"), F("review_date", "Fecha de revisión", "date")]},
    "monitor": {"label": "Monitor", "plural": "Monitores proactivos", "module": "negocios", "statuses": ["activo", "pausado"], "free_merge": True, "fields": [
        F("type", "Qué vigila", "select", options=["tareas_vencidas", "vencimientos", "suscripciones", "presupuesto", "clipping", "trabajos_fallidos", "por_aprobar", "sitio_web", "resumen_diario"], required=True),
        F("every_hours", "Cada cuántas horas", "number"), F("url", "URL (solo para «sitio web»)", "url"), F("days", "Días de antelación (vencimientos)", "number"),
        F("hour", "Hora del resumen diario (0–23)", "number"), F("notify", "Avisar al celular", "bool"), F("last_run", "Última ejecución"), F("last_result", "Último resultado")]},
    "memory": {"label": "Recuerdo", "plural": "Memoria de Jarvis", "module": "proyectos", "statuses": ["activo"], "fields": [
        F("body", "Detalle (si el título no basta)", "textarea"),
        F("category", "Tipo", "select", options=["preferencia", "negocio", "marca", "persona", "decision", "otro"]),
        F("use_in_jobs", "Usarlo también en los trabajos (contenido, propuestas, expedientes)", "bool"), F("source", "Origen")]},
    "schedule": {"label": "Agente con horario", "plural": "Agentes con horario", "module": "negocios", "statuses": ["activo", "pausado"], "free_merge": True, "fields": [
        F("order", "Orden para Jarvis", "textarea", required=True),
        F("frequency", "Frecuencia", "select", options=["diario", "semanal", "intervalo"], required=True),
        F("hour", "Hora del día (0–23)", "number"), F("weekday", "Día (si es semanal)", "select", options=["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]),
        F("every_hours", "Cada cuántas horas (si es por intervalo)", "number"), F("notify", "Avisar al celular con el resultado", "bool"),
        F("last_run", "Última ejecución"), F("last_result", "Último resultado")]},
    "alert": {"label": "Alerta", "plural": "Alertas", "module": "negocios", "statuses": ["nueva", "vista", "resuelta"], "fields": [
        F("type", "Tipo"), F("detected", "Detectada"), F("monitor_id", "Monitor", "ref", ref="monitor"), F("notes", "Notas", "textarea")]},
    # --- Segundo cerebro
    "note": {"label": "Nota", "plural": "Notas", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("body", "Contenido", "textarea"), F("tags", "Etiquetas", "tags"), F("source", "Fuente o enlace"), F("area", "Área", "select", options=["mente", "cuerpo", "espiritu", "economia", "negocio", "otra"])]},
    "skill": {"label": "Habilidad", "plural": "Habilidades por aprender", "module": "personal", "statuses": ["pendiente", "en_curso", "practicando", "dominada"], "fields": [
        F("why", "Para qué la quiero", "textarea"), F("plan", "Plan de práctica", "textarea"), F("resources", "Recursos", "textarea"),
        F("weekly_hours", "Horas por semana", "number"), F("next_review", "Próximo repaso", "date"), F("guide", "Guía de la biblioteca")]},
    # --- HEALTH OS (cuerpo)
    "workout": {"label": "Entrenamiento", "plural": "Entrenamientos", "module": "personal", "statuses": ["hecho", "planificado", "omitido"], "private": True, "fields": [
        F("date", "Fecha", "date"), F("type", "Tipo", "select", options=["fuerza", "cardio", "movilidad", "deporte", "otro"]), F("minutes", "Minutos", "number"),
        F("exercises", "Ejercicios (uno por línea: ejercicio | series x repeticiones | carga)", "textarea"),
        F("effort", "Esfuerzo percibido", "select", options=["suave", "moderado", "alto", "maximo"]),
        F("recovery", "Cómo llegué (recuperación)", "select", options=["fresco", "normal", "cansado", "dolorido"]), F("notes", "Notas", "textarea")]},
    "meal": {"label": "Comida", "plural": "Plan de comidas", "module": "personal", "statuses": ["planificada", "hecha"], "private": True, "fields": [
        F("date", "Fecha", "date"), F("meal", "Momento", "select", options=["desayuno", "comida", "cena", "snack"]), F("ingredients", "Ingredientes", "textarea"),
        F("calories", "Calorías (si las conoces)", "number"), F("protein_g", "Proteína (g)", "number"), F("cost", "Costo", "number"), F("notes", "Receta o notas", "textarea")]},
    "pantry": {"label": "Producto", "plural": "Despensa y lista de mercado", "module": "personal", "statuses": ["en_casa", "por_comprar", "agotado"], "private": True, "fields": [
        F("quantity", "Cantidad", "number"), F("unit", "Unidad"), F("expiry", "Caduca", "date"), F("store", "Dónde comprarlo"), F("est_cost", "Costo estimado", "number")]},
    "sleep": {"label": "Noche", "plural": "Sueño", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("date", "Fecha (la mañana en que despiertas)", "date", required=True), F("bedtime", "Hora de acostarte"), F("wake_time", "Hora de despertar"),
        F("hours", "Horas dormidas", "number", required=True), F("quality", "Calidad", "select", options=["1", "2", "3", "4", "5"]),
        F("naps_minutes", "Siestas (min)", "number"), F("notes", "Notas", "textarea")]},
    "wardrobe": {"label": "Prenda", "plural": "Armario", "module": "personal", "statuses": ["en_uso", "retirada"], "private": True, "fields": [
        F("category", "Categoría", "select", options=["superior", "inferior", "calzado", "abrigo", "accesorio", "formal", "deporte"]), F("color", "Color"),
        F("season", "Temporada"), F("combos", "Combina con", "textarea"), F("photo_file_id", "ID de la foto (súbela en Proyectos → Archivos)"), F("notes", "Notas", "textarea")]},
    "care_routine": {"label": "Rutina de cuidado", "plural": "Cuidado personal", "module": "personal", "statuses": ["activa", "pausada"], "private": True, "fields": [
        F("frequency", "Frecuencia"), F("steps", "Pasos", "textarea"), F("products", "Productos", "textarea"), F("next_date", "Próxima cita o recordatorio", "date")]},
    "health_record": {"label": "Registro de salud", "plural": "Historial de salud", "module": "personal", "statuses": ["vigente", "resuelto"], "private": True, "fields": [
        F("type", "Tipo", "select", options=["cita", "resultado", "medicamento", "vacuna", "pregunta_para_el_medico", "otro"], required=True), F("date", "Fecha", "date"),
        F("professional", "Profesional o centro"), F("detail", "Detalle", "textarea"), F("next_date", "Próxima fecha", "date"), F("file_id", "ID del archivo adjunto")]},
    # --- MIND OS
    "flashcard": {"label": "Tarjeta", "plural": "Tarjetas de repaso", "module": "personal", "statuses": ["activa", "suspendida"], "fields": [
        F("deck", "Mazo o tema"), F("back", "Respuesta", "textarea", required=True), F("due", "Próximo repaso", "date"),
        F("interval_days", "Intervalo (días)", "number"), F("ease", "Facilidad", "number"), F("reps", "Repasos seguidos", "number")]},
    "choice": {"label": "Decisión personal", "plural": "Decisiones", "module": "personal", "statuses": ["abierta", "decidida", "evaluada"], "private": True, "fields": [
        F("options", "Alternativas (una por línea)", "textarea", required=True), F("criteria", "Qué importa de verdad", "textarea"),
        F("pros_cons", "Ventajas y desventajas", "textarea"), F("risks", "Riesgos y qué haría si salen mal", "textarea"),
        F("chosen", "Qué decidí"), F("reason", "Por qué (con lo que sabía entonces)", "textarea"), F("review_date", "Cuándo la evalúo", "date"), F("outcome", "Qué pasó", "textarea")]},
    # --- FAITH OS
    "devotional": {"label": "Tiempo devocional", "plural": "Lectura y devocional", "module": "personal", "statuses": ["hecho", "planificado"], "private": True, "fields": [
        F("date", "Fecha", "date"), F("passage", "Pasaje (referencia)"), F("type", "Tipo", "select", options=["lectura", "devocional", "estudio", "memorizacion"]),
        F("minutes", "Minutos", "number"), F("notes", "Mis anotaciones", "textarea")]},
    "prayer": {"label": "Oración", "plural": "Diario de oración", "module": "personal", "statuses": ["abierta", "en_seguimiento", "respondida"], "private": True, "fields": [
        F("type", "Tipo", "select", options=["peticion", "agradecimiento", "intercesion", "confesion"]), F("date", "Fecha", "date"),
        F("body", "Texto", "textarea"), F("follow_up", "Seguimiento", "textarea")]},
    "study_note": {"label": "Nota de estudio", "plural": "Estudio bíblico", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("passage", "Pasaje"), F("topic", "Tema"), F("source", "Traducción o comentario consultado (cítalo)"),
        F("text", "Texto citado", "textarea"), F("body", "Mi interpretación y preguntas", "textarea")]},
    "ministry_event": {"label": "Actividad", "plural": "Comunidad y ministerio", "module": "personal", "statuses": ["planificada", "realizada", "cancelada"], "fields": [
        F("date", "Fecha", "date"), F("place", "Lugar"), F("team", "Equipo responsable"), F("volunteers", "Voluntarios y tareas", "textarea"),
        F("materials", "Materiales", "textarea"), F("consent", "Consentimiento para guardar datos de participantes", "select", options=["no_se_guardan_datos", "consentimiento_obtenido"]),
        F("notes", "Notas", "textarea")]},
    # --- WEALTH OS
    "account": {"label": "Cuenta", "plural": "Cuentas, activos y deudas", "module": "personal", "statuses": ["activa", "cerrada"], "private": True, "fields": [
        F("type", "Tipo", "select", options=["efectivo", "banco", "inversion", "propiedad", "otro_activo", "tarjeta", "prestamo", "otra_deuda"], required=True),
        F("balance", "Saldo (deudas en positivo)", "number", required=True), F("currency", "Moneda"), F("updated", "Saldo actualizado el", "date"), F("notes", "Notas", "textarea")]},
    "budget": {"label": "Presupuesto", "plural": "Presupuesto mensual", "module": "personal", "statuses": ["vigente"], "private": True, "fields": [
        F("category", "Categoría (igual que en tus movimientos)", required=True), F("monthly_limit", "Límite mensual", "number", required=True), F("currency", "Moneda")]},
    "investment": {"label": "Inversión", "plural": "Inversiones", "module": "personal", "statuses": ["abierta", "cerrada"], "private": True, "fields": [
        F("asset_type", "Tipo de activo", "select", options=["renta_fija", "fondos_indexados", "acciones", "inmuebles", "negocio", "cripto", "otro"]),
        F("invested", "Aportado", "number"), F("current_value", "Valor actual", "number"), F("currency", "Moneda"), F("valued_on", "Valorado el", "date"),
        F("risk", "Riesgo", "select", options=["bajo", "medio", "alto"]), F("thesis", "Tesis: por qué la tengo y cuándo saldría", "textarea"), F("review_date", "Revisar el", "date")]},
    "subscription": {"label": "Suscripción", "plural": "Suscripciones", "module": "personal", "statuses": ["activa", "cancelada"], "fields": [
        F("amount", "Importe", "number", required=True), F("currency", "Moneda"), F("period", "Periodo", "select", options=["mensual", "anual", "otro"]),
        F("renewal_date", "Próxima renovación", "date"), F("category", "Categoría"), F("last_used", "Último uso", "date"),
        F("needed", "¿La necesito?", "select", options=["si", "dudoso", "no"]), F("notes", "Notas", "textarea")]},
    "admin_doc": {"label": "Documento", "plural": "Contratos y administración", "module": "personal", "statuses": ["pendiente", "vigente", "cumplido"], "fields": [
        F("type", "Tipo", "select", options=["contrato", "factura", "obligacion", "licencia", "poliza", "documento"], required=True), F("counterparty", "Contraparte"),
        F("amount", "Importe", "number"), F("currency", "Moneda"), F("due_date", "Vence o se renueva", "date"), F("file_id", "ID del archivo adjunto"),
        F("checklist", "Lista de revisión (para tu abogado o contador)", "textarea"), F("notes", "Notas", "textarea")]},
    # --- Editor audiovisual (estructura propia validada en handlers.video)
    "video_project": {"label": "Proyecto de video", "plural": "Proyectos de video", "module": "video", "statuses": ["en_edicion", "exportado"], "free_data": True, "fields": [
        F("mode", "Modo", "select", options=["clipping", "publicidad", "marca_personal", "formacion"])]},
}


class RecordError(ValueError):
    pass


def schema() -> dict:
    return {k: {kk: vv for kk, vv in v.items()} for k, v in KINDS.items()}


def _coerce(field: dict, value):
    t = field["type"]
    if value is None or value == "":
        return None
    if t == "number":
        try:
            return float(str(value).replace(",", ".").replace(" ", "")) if not isinstance(value, (int, float)) else value
        except ValueError:
            raise RecordError(f"«{field['label']}» debe ser un número.")
    if t == "bool":
        return value in (True, 1, "1", "true", "True", "sí", "si", "x")
    if t == "date":
        s = str(value).strip()[:10]
        try:
            date.fromisoformat(s)
        except ValueError:
            raise RecordError(f"«{field['label']}» debe ser una fecha AAAA-MM-DD.")
        return s
    if t == "tags":
        if isinstance(value, str):
            value = [v.strip() for v in value.replace(";", ",").split(",")]
        return [str(v) for v in value if str(v).strip()]
    if t == "select":
        if value not in field.get("options", []):
            raise RecordError(f"«{field['label']}»: valor no permitido ({value}).")
        return value
    if t == "url":
        s = str(value).strip()
        if not s.lower().startswith(("http://", "https://")):
            raise RecordError(f"«{field['label']}» debe ser una URL http(s).")
        return s
    return str(value)


def validate(kind: str, data: dict, partial: bool = False) -> dict:
    spec = KINDS.get(kind)
    if not spec:
        raise RecordError(f"Tipo de registro desconocido: {kind}")
    if spec.get("free_data"):
        return data
    out = {}
    for f in spec["fields"]:
        if f["name"] in data:
            out[f["name"]] = _coerce(f, data[f["name"]])
        if f.get("required") and not partial and out.get(f["name"]) in (None, "", []):
            raise RecordError(f"Falta el campo obligatorio «{f['label']}».")
    return out


def _row(row: dict | None) -> dict | None:
    if row:
        row["data"] = loads(row["data"], {})
        row["archived"] = bool(row["archived"])
    return row


def get(record_id: str, space_id: str | None = None) -> dict | None:
    row = _row(db.one("SELECT * FROM records WHERE id=?", (record_id,)))
    if row and space_id and row["space_id"] != space_id:
        return None  # nunca se cruza la frontera de un espacio
    return row


def list_records(space_id: str, kind: str, *, archived: bool = False, project_id: str | None = None, brand_id: str | None = None,
                 status: str | None = None, q: str | None = None, limit: int = 1000) -> list[dict]:
    sql, params = "SELECT * FROM records WHERE space_id=? AND kind=? AND archived=?", [space_id, kind, int(archived)]
    for col, val in (("project_id", project_id), ("brand_id", brand_id), ("status", status)):
        if val:
            sql += f" AND {col}=?"
            params.append(val)
    if q:
        sql += " AND (title LIKE ? OR data LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    return [_row(r) for r in db.query(sql + " ORDER BY created_at DESC, rowid DESC LIMIT ?", (*params, limit))]


def _check_rules(kind: str, status: str | None, data: dict) -> None:
    """Reglas de negocio por tipo. Una misión no puede darse por completada y verificada sin criterio de cierre y evidencia."""
    if kind == "mission" and status == "completada_verificada":
        if not (data.get("closure") or "").strip() or not (data.get("evidence") or "").strip():
            raise RecordError("Para marcar una misión como «completada verificada» hacen falta su criterio de cierre y una evidencia verificable.")


def _check_refs(space_id: str, project_id, brand_id, data: dict, kind: str) -> None:
    refs = [(project_id, "project"), (brand_id, "brand")]
    refs += [(data.get(f["name"]), f["ref"]) for f in KINDS[kind]["fields"] if f["type"] == "ref"]
    for rid, rkind in refs:
        if rid:
            ref = get(rid, space_id)
            if not ref or ref["kind"] != rkind:
                raise RecordError("La referencia indicada no existe en este espacio.")


def create(space_id: str, kind: str, title: str, data: dict | None = None, *, status: str | None = None,
           project_id: str | None = None, brand_id: str | None = None) -> dict:
    if not (title or "").strip():
        raise RecordError("El título es obligatorio.")
    if not db.one("SELECT id FROM spaces WHERE id=?", (space_id,)):
        raise RecordError("El espacio no existe.")
    clean = validate(kind, data or {})
    spec = KINDS[kind]
    status = status or spec["statuses"][0]
    if status not in spec["statuses"]:
        raise RecordError("Estado no permitido.")
    _check_refs(space_id, project_id, brand_id, clean, kind)
    _check_rules(kind, status, clean)
    rid = new_id(kind[:3])
    db.execute("INSERT INTO records(id,space_id,kind,title,status,project_id,brand_id,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (rid, space_id, kind, title.strip()[:300], status, project_id or None, brand_id or None, dumps(clean), now_iso(), now_iso()))
    return get(rid)


def update(record_id: str, space_id: str, patch: dict) -> dict:
    rec = get(record_id, space_id)
    if not rec:
        raise KeyError(record_id)
    spec = KINDS[rec["kind"]]
    sets, params = [], []
    if "title" in patch:
        if not (patch["title"] or "").strip():
            raise RecordError("El título es obligatorio.")
        sets.append("title=?")
        params.append(patch["title"].strip()[:300])
    if "status" in patch:
        if patch["status"] not in spec["statuses"]:
            raise RecordError("Estado no permitido.")
        sets.append("status=?")
        params.append(patch["status"])
    data = rec["data"]
    if "data" in patch:
        data = patch["data"] if spec.get("free_data") else {**rec["data"], **validate(rec["kind"], patch["data"], partial=True)}
        if spec.get("free_merge"):  # claves internas que no forman parte del esquema visible
            data.update({k: patch["data"][k] for k in ("seen", "runs") if k in patch["data"]})
        sets.append("data=?")
        params.append(dumps(data))
    for col in ("project_id", "brand_id"):
        if col in patch:
            sets.append(f"{col}=?")
            params.append(patch[col] or None)
    if "archived" in patch:
        sets.append("archived=?")
        params.append(int(bool(patch["archived"])))
    _check_refs(space_id, patch.get("project_id", rec["project_id"]), patch.get("brand_id", rec["brand_id"]), data, rec["kind"])
    _check_rules(rec["kind"], patch.get("status", rec["status"]), data)
    if sets:
        db.execute(f"UPDATE records SET {','.join(sets)}, updated_at=? WHERE id=?", (*params, now_iso(), record_id))
    return get(record_id)


def export_csv(space_id: str, kind: str, include_archived: bool = True) -> str:
    spec = KINDS[kind]
    rows = list_records(space_id, kind, archived=False, limit=100000)
    if include_archived:
        rows += list_records(space_id, kind, archived=True, limit=100000)
    names = [f["name"] for f in spec["fields"]]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "titulo", "estado", "proyecto_id", "marca_id", *names, "archivado", "creado", "actualizado"])
    for r in rows:
        vals = [", ".join(v) if isinstance(v := r["data"].get(n), list) else ("" if v is None else v) for n in names]
        w.writerow([r["id"], r["title"], r["status"], r["project_id"] or "", r["brand_id"] or "", *vals, int(r["archived"]), r["created_at"], r["updated_at"]])
    return buf.getvalue()


# ---------- Importación CSV con mapeo de columnas y detección de duplicados

def parse_csv(text: str) -> tuple[list[str], list[dict]]:
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h]
    return headers, [dict(r) for r in reader]


def _dup_key(kind: str, title: str, data: dict) -> str:
    if kind == "transaction":
        if data.get("external_id"):
            return f"ext:{data['external_id']}"
        return "|".join(str(x or "").strip().lower() for x in (data.get("date"), data.get("amount"), data.get("type"), data.get("stage"), data.get("counterparty"), title))
    if kind == "lead":
        return f"dom:{(data.get('domain') or title).strip().lower()}"
    return "|".join([title.strip().lower()] + [str(data.get(k) or "").strip().lower() for k in ("date", "url", "source_url", "campaign_id")])


def import_csv(space_id: str, kind: str, text: str, mapping: dict, *, commit: bool = False, defaults: dict | None = None,
               project_id: str | None = None, skip_duplicates: bool = True) -> dict:
    """mapping: {columna_csv: campo}. Campos especiales: 'title', 'status'. Sin commit solo previsualiza."""
    spec = KINDS.get(kind)
    if not spec or spec.get("free_data"):
        raise RecordError("Este tipo no admite importación CSV.")
    headers, rows = parse_csv(text)
    valid_fields = {f["name"] for f in spec["fields"]} | {"title", "status"}
    mapping = {c: f for c, f in mapping.items() if f in valid_fields and c in headers}
    if "title" not in mapping.values():
        raise RecordError("Asigna una columna al título.")
    existing = {_dup_key(kind, r["title"], r["data"]) for r in list_records(space_id, kind, limit=100000)}
    preview, created, dupes, errors = [], 0, 0, 0
    seen = set()
    for i, raw in enumerate(rows, start=2):
        item = {"fila": i}
        try:
            data = dict(defaults or {})
            title, status = "", None
            for col, field in mapping.items():
                val = (raw.get(col) or "").strip()
                if field == "title":
                    title = val
                elif field == "status":
                    status = val or None
                elif val != "":
                    data[field] = val
            if not title:
                raise RecordError("Fila sin título.")
            clean = validate(kind, data)
            key = _dup_key(kind, title, clean)
            item.update(title=title, data=clean)
            if key in existing or key in seen:
                item["estado"] = "duplicado"
                dupes += 1
                if skip_duplicates:
                    preview.append(item)
                    continue
            seen.add(key)
            if commit:
                create(space_id, kind, title, clean, status=status if status in spec["statuses"] else None, project_id=project_id)
            item.setdefault("estado", "nuevo")
            created += 1
        except RecordError as exc:
            item.update(estado="error", error=str(exc))
            errors += 1
        preview.append(item)
    return {"columnas": headers, "filas": len(rows), "nuevos": created, "duplicados": dupes, "errores": errors,
            "aplicado": commit, "detalle": preview[:200]}
