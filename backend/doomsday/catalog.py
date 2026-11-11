"""Catálogo declarativo de los 100 módulos de Doomsday (Laboratorio Estratégico, entrega 2).

Cada módulo declara: sus datos (tipos de registro), sus herramientas de cálculo (deterministas, sin IA) y sus acciones
(órdenes que la skill del módulo convierte en un entregable revisable). Todo módulo acepta además una «orden libre».
"""
from __future__ import annotations

from .kinds import field

CATEGORIES = {
    "P": ("Automatización personal y productividad", "personal"),
    "G": ("Sistemas internos de gestión empresarial", "interna"),
    "M": ("Marketing digital, publicidad y growth", "interna"),
    "C": ("Creación de contenido, storytelling y marca personal", "interna"),
    "V": ("Gestión de clientes, ventas y plataformas B2B", "clientes"),
    "S": ("Productos SaaS y software comercializable", "comercial"),
    "A": ("Agentes de IA y automatizaciones avanzadas", "interna"),
    "H": ("Salud física, aprendizaje y desarrollo personal", "personal"),
    "R": ("Espiritualidad, relaciones y organización social", "personal"),
    "X": ("Innovaciones transversales y poco exploradas", "interna"),
}
# Las cuatro capas del ecosistema (entrega 9): nunca comparten base ni credenciales. Cada una es un espacio.
LAYERS = {
    "personal": ("Personal", "personal", "Interfaz, brief, captura, salud, estudio y vida espiritual. Solo tú."),
    "interna": ("Interna · tiendas y pauta", "negocio", "Datos y operación de tus tiendas, pauta y contenido. Tú y el equipo."),
    "clientes": ("Clientes B2B", "cliente", "Entrega, reportes y comunicación con clientes y alumnos."),
    "comercial": ("Comercial", "marca", "Lo que se vende a terceros."),
}
AUTONOMY = {"A": "Solo lee y resume", "B": "Prepara y pide tu aprobación", "C": "Ejecuta acciones reversibles con límites", "D": "Encadena varios pasos"}


def A(id_: str, label: str, tarea: str, campos: list[str] | None = None, contexto: list[str] | None = None, herramienta: str | None = None,
      emite: str | None = None) -> dict:
    return {"id": id_, "label": label, "tarea": tarea, "campos": [field(c) for c in (campos or [])], "contexto": contexto, "herramienta": herramienta, "emite": emite}


MODULES: dict[str, dict] = {}


def M(id_, nombre, problema, solucion, funciones, usuarios, decision, esfuerzo, pts, *, nivel="B", kinds=(), tools=(), acciones=(), conexiones=(), widget=None):
    cat = id_[0]
    acts = [A("orden", "Orden libre", "Atiende la orden del usuario con el método de la skill y entrega el resultado más profesional posible.",
              ["orden:¿Qué necesitas?:textarea", "enlace:Enlace de referencia (opcional):url"])] + list(acciones)
    for a in acts:
        if a["contexto"] is None:
            a["contexto"] = list(kinds)
    MODULES[id_] = {"id": id_, "nombre": nombre, "categoria": cat, "capa": CATEGORIES[cat][1], "problema": problema, "solucion": solucion,
                    "funciones": [f.strip() for f in funciones.split(";")], "usuarios": usuarios, "decision_pdf": decision, "esfuerzo": esfuerzo, "puntos": pts,
                    "nivel": nivel, "kinds": list(kinds), "tools": list(tools), "acciones": acts, "conexiones": list(conexiones), "widget": widget}


# ---------- 1. Automatización personal y productividad
M("P01", "Auditor de suscripciones", "Pagas herramientas de IA sin saber cuáles usas", "cruce de cargos con uso real", "Inventario de cargos; uso por herramienta; lista de cancelación",
  "Yo", "AUTOMATIZAR", "S", 56, nivel="A", kinds=["dd_suscripcion"], tools=["suscripciones"],
  acciones=[A("auditar", "Auditar y proponer cancelaciones", "Con el inventario y el cálculo adjunto, decide qué cancelar, qué bajar de plan y qué conservar, con el ahorro mensual de cada decisión.",
              ["criterio:Criterio adicional (opcional):textarea"], herramienta="suscripciones")])
M("P02", "Bóveda de accesos", "Credenciales repartidas entre chats y notas", "gestor con colecciones por empresa", "Compartir sin revelar; 2FA; revocar al salir",
  "Yo, Eq", "COMPRAR", "S", 64, nivel="A", kinds=["dd_acceso"], widget="boveda",
  acciones=[A("higiene", "Revisión de higiene de accesos", "Revisa el inventario de accesos (sin secretos): qué falta con 2FA, qué está compartido de más y qué revocar al salir alguien.",
              ["persona:Persona que sale o entra (opcional)"])])
M("P03", "Triage de correo", "Correo rutinario mezclado con oportunidades", "clasificación y borradores", "Etiquetar; redactar borrador; resumen diario",
  "Yo", "INTEGRAR", "S", 60, kinds=["dd_mensaje"], conexiones=["gmail"],
  acciones=[A("clasificar", "Clasificar y redactar borradores", "Clasifica cada mensaje pendiente (oportunidad, cliente, rutina, ruido), prioriza y redacta el borrador de respuesta de los que lo merecen.",
              ["correos:Pega aquí los correos (opcional si ya están en la bandeja):textarea"], emite="dd_mensaje"),
            A("resumen", "Resumen diario", "Resume la bandeja: qué exige decisión hoy, qué puede esperar y qué se archiva.")])
M("P04", "Captura por voz", "Ideas que se pierden lejos del escritorio", "nota de voz transcrita y enrutada", "Transcribir; clasificar; enviar a su lista",
  "Yo", "AUTOMATIZAR", "S", 58, kinds=["dd_nota"], widget="voz",
  acciones=[A("enrutar", "Clasificar y enrutar capturas", "Convierte cada captura en un elemento limpio: tipo, texto reescrito sin perder sentido y lista de destino.",
              ["texto:Transcripción o notas sueltas:textarea"], emite="dd_nota")])
M("P05", "Runbooks ejecutables", "Repites la misma configuración de herramientas", "skills con pasos y verificación", "Checklist; ejecución guiada; prueba final",
  "Yo, Eq", "CONSTRUIR", "M", 65, kinds=["dd_runbook"],
  acciones=[A("crear", "Crear runbook", "Escribe el runbook: requisitos, pasos numerados con el resultado esperado de cada uno, puntos de fallo y prueba final verificable.",
              ["herramienta:Herramienta o proceso", "descripcion:Cómo lo haces hoy:textarea"], emite="dd_runbook")])
M("P06", "Organizador de archivos", "Descargas y recursos sin estructura", "reglas de nombre y carpeta", "Renombrar; mover; detectar duplicados",
  "Yo", "AUTOMATIZAR", "S", 46, nivel="A", kinds=["dd_regla_archivo"], tools=["duplicados"],
  acciones=[A("estructura", "Proponer estructura y reglas", "Propone estructura de carpetas, convención de nombres y reglas para los archivos listados.",
              ["listado:Lista de archivos o descripción:textarea"], herramienta="duplicados", emite="dd_regla_archivo")])
M("P07", "Brief diario del CEO", "Revisas seis paneles cada mañana", "un resumen con lo que requiere decisión", "Ventas y pauta de ayer; alertas; tres decisiones",
  "Yo", "CONSTRUIR", "M", 66, nivel="A", tools=["brief_ceo"],
  acciones=[A("brief", "Generar el brief de hoy", "Redacta el brief: cifras clave, alertas y exactamente tres decisiones pendientes con la opción recomendada. Solo usa los datos adjuntos.",
              herramienta="brief_ceo")])
M("P08", "Planificador de calendario", "Bloques de trabajo profundo que se rompen", "agenda automática", "Bloques; reprogramar; enlaces de cita",
  "Yo", "COMPRAR", "S", 52, kinds=["dd_bloque"], tools=["agenda"],
  acciones=[A("semana", "Planificar la semana", "Arma la semana en bloques protegiendo el trabajo profundo y reprograma lo que choque.",
              ["compromisos:Compromisos fijos y prioridades:textarea"], herramienta="agenda", emite="dd_bloque")])
M("P09", "Registro de decisiones", "Repites debates ya cerrados", "bitácora con contexto y fecha de revisión", "Plantilla; revisión a 30 días; búsqueda",
  "Yo", "AUTOMATIZAR", "S", 55, kinds=["dd_decision"],
  acciones=[A("registrar", "Registrar una decisión", "Estructura la decisión: contexto, opciones con sus costos, decisión, razón, qué la invalidaría y fecha de revisión.",
              ["decision:La decisión y cómo llegaste a ella:textarea"], emite="dd_decision")])
M("P10", "Documentador de procesos", "Nadie escribe los SOP", "de la grabación o el relato sale el procedimiento", "Grabar; transcribir; pasos numerados",
  "Yo, Eq", "COMPRAR", "S", 55, kinds=["dd_sop"],
  acciones=[A("sop", "Convertir en procedimiento", "Convierte el relato o transcripción en un SOP con pasos numerados, responsable, herramientas y prueba de que quedó bien.",
              ["relato:Transcripción o relato del proceso:textarea", "rol:Rol que lo ejecuta"], emite="dd_sop")])

# ---------- 2. Sistemas internos de gestión empresarial
M("G01", "Núcleo de datos", "Shopify, pauta y logística no se cruzan", "una base con datos diarios", "Conectores; modelo común; consultas",
  "Eq", "CONSTRUIR", "L", 67, nivel="A", kinds=["dd_pedido", "dd_gasto_pauta", "dd_liquidacion"], tools=["utilidad_cod"], conexiones=["shopify", "meta", "tiktok", "dropi"], widget="sync",
  acciones=[A("calidad", "Auditar calidad de datos", "Evalúa cobertura y calidad de los datos cargados: huecos de fechas, pedidos sin costo, campañas sin producto y qué importar para corregirlo.",
              herramienta="utilidad_cod")])
M("G02", "Utilidad real COD", "El ROAS no descuenta devoluciones ni fletes", "utilidad neta por producto y campaña", "Costo y flete por pedido; tasa de entrega; margen por anuncio",
  "Yo, Eq", "CONSTRUIR", "L", 75, nivel="A", kinds=["dd_pedido", "dd_gasto_pauta"], tools=["utilidad_cod", "equilibrio"], conexiones=["shopify", "meta"],
  acciones=[A("informe", "Informe de utilidad neta", "Interpreta el cálculo: qué productos y campañas ganan o pierden de verdad, por qué (entrega, flete, costo, pauta) y qué pausar, mantener o escalar.",
              ["desde:Desde:date", "hasta:Hasta:date"], herramienta="utilidad_cod")])
M("G03", "Aprovisionador de tiendas", "Cada tienda nueva repite la misma configuración", "plantilla que se aplica sola", "Tema y ajustes; mercados y pagos; verificación",
  "Eq", "CONSTRUIR", "M", 64, kinds=["dd_tienda", "dd_paso"], conexiones=["shopify"],
  acciones=[A("plan", "Plan de aprovisionamiento", "Genera la lista completa de configuración de la tienda nueva, en orden, con el valor exacto de cada ajuste y su verificación.",
              ["tienda:Nombre de la tienda", "mercado:País y moneda", "modelo:Modelo:select:cod|prepago|mixto", "notas:Particularidades:textarea"], emite="dd_paso")])
M("G04", "Fábrica de fichas", "Montar un producto toma horas", "de un enlace a una página en borrador", "Extraer datos; copy y secciones; publicar borrador",
  "Yo, Eq", "CONSTRUIR", "M", 78, kinds=["dd_producto"], tools=["cumplimiento", "oferta"], conexiones=["shopify"], widget="publicar",
  acciones=[A("ficha", "Generar ficha de producto", "Con los datos del proveedor (fuente adjunta), escribe la página completa: promesa, beneficios, secciones del tema, oferta y packs, preguntas frecuentes y revisión de cumplimiento.",
              ["enlace:Enlace del proveedor o producto:url", "producto:Nombre comercial", "mercado:Mercado y moneda", "precio:Precio de venta:number", "costo:Costo:number",
               "cliente:Cliente ideal y dolor principal:textarea"], emite="dd_producto")])
M("G05", "Contabilidad LLC", "Cierre anual y formularios", "libros al día", "Conciliar bancos; categorizar; reportes",
  "Yo", "COMPRAR", "S", 47, nivel="A", kinds=["dd_movimiento"], tools=["flujo_caja"],
  acciones=[A("cierre", "Preparar cierre del periodo", "Prepara el paquete para el contador: resumen por categoría, movimientos sin clasificar, pendientes de soporte y preguntas abiertas. No es asesoría fiscal.",
              ["periodo:Periodo"], herramienta="flujo_caja")])
M("G06", "Centro de mando", "Inventario manual que caduca", "solo lo que se actualice solo", "Dominios; tiendas; gastos",
  "Yo", "POSPONER", "M", 43, nivel="A", kinds=["dd_activo"], tools=["inventario"],
  acciones=[A("revision", "Revisión del inventario", "Señala vencimientos próximos, costos sin dueño y activos duplicados o sin uso.", herramienta="inventario")])
M("G07", "Monitor de salud de tiendas", "Checkout o píxel caídos sin aviso", "pruebas cada hora", "Página de producto; píxel; velocidad",
  "Eq", "CONSTRUIR", "S", 68, nivel="C", kinds=["dd_tienda", "dd_chequeo", "dd_alerta"], tools=["salud_tienda"],
  acciones=[A("diagnostico", "Diagnosticar fallas recientes", "Lee las comprobaciones y alertas: patrón de fallas, causa probable y qué revisar primero.")])
M("G08", "Conciliación de recaudo COD", "Recaudos y devoluciones sin cuadrar", "cruce pedido a pedido", "Importar liquidaciones; diferencias; reclamos",
  "Eq", "CONSTRUIR", "M", 63, nivel="A", kinds=["dd_pedido", "dd_liquidacion"], tools=["conciliacion_cod"],
  acciones=[A("reclamos", "Preparar reclamos", "Con las diferencias calculadas, redacta el reclamo por transportadora con el listado de pedidos, montos y evidencia requerida.",
              herramienta="conciliacion_cod")])
M("G09", "SOPs y onboarding", "Cada persona nueva te cuesta días", "base de procesos con pruebas", "Guías; videos; checklist por rol",
  "Eq", "COMPRAR", "S", 55, kinds=["dd_sop", "dd_paso"],
  acciones=[A("onboarding", "Plan de incorporación por rol", "Diseña el plan de los primeros 14 días para el rol: qué aprende, en qué orden, con qué SOP y la prueba que demuestra cada habilidad.",
              ["rol:Rol", "responsabilidades:Responsabilidades:textarea"], emite="dd_paso")])
M("G10", "Tablero de tareas", "Tareas en chats", "un gestor", "Asignar; fechas; estado", "Eq", "COMPRAR", "S", 50, kinds=["dd_tarea"], tools=["tareas"],
  acciones=[A("extraer", "Extraer tareas de un chat", "Extrae las tareas reales del texto: acción concreta, responsable, fecha y prioridad. Sin duplicar las ya existentes.",
              ["chat:Chat o notas:textarea"], emite="dd_tarea")])

# ---------- 3. Marketing digital, publicidad y growth
M("M01", "Guardián de pauta", "Anuncios que pierden mientras duermes", "reglas que pausan y avisan", "Pausa por CPA; alertas; registro",
  "Yo", "COMPRAR", "S", 72, nivel="C", kinds=["dd_regla_pauta", "dd_gasto_pauta", "dd_alerta"], tools=["guardian_pauta"], conexiones=["meta", "tiktok"], widget="pausa",
  acciones=[A("calibrar", "Calibrar reglas", "Propone el CPA límite y el gasto mínimo por producto a partir del margen y de los datos, cuidando no apagar ganadores en aprendizaje.",
              herramienta="guardian_pauta", emite="dd_regla_pauta")])
M("M02", "Lanzador masivo", "Subir 30 anuncios a mano", "carga por lotes", "Plantillas; nombres; multicanal",
  "Yo, Eq", "COMPRAR", "S", 68, kinds=["dd_creativo"], tools=["cumplimiento"], conexiones=["meta"],
  acciones=[A("lote", "Preparar lote de carga", "Arma la hoja de carga con los creativos aprobados: estructura de campaña, conjuntos, nombres consistentes, textos y enlaces con UTM.",
              ["producto:Producto", "plataforma:Plataforma:select:meta|tiktok|ambas", "presupuesto:Presupuesto diario por conjunto:number", "destino:URL de destino:url"])])
M("M03", "Inteligencia creativa", "No sabes qué elemento del anuncio gana", "etiquetado por hook y ángulo", "Etiquetar; cruzar con utilidad; informe",
  "Yo", "CONSTRUIR", "L", 68, nivel="A", kinds=["dd_creativo", "dd_gasto_pauta"], tools=["creativos"],
  acciones=[A("informe", "Informe de elementos ganadores", "Con el cruce adjunto, explica qué hooks, ángulos y formatos ganan, con qué tamaño de muestra, y redacta el brief para la siguiente tanda.",
              herramienta="creativos")])
M("M04", "Radar de productos", "Investigación manual de producto", "candidatos puntuados", "Fuentes; puntaje; ficha",
  "Yo, Eq", "CONSTRUIR", "M", 66, nivel="A", kinds=["dd_producto"], tools=["equilibrio"],
  acciones=[A("evaluar", "Evaluar candidatos", "Puntúa cada candidato con los criterios COD (margen, flete, demanda observable, saturación, riesgo de política y de devolución) y entrega las cinco mejores fichas.",
              ["candidatos:Candidatos (nombre, enlace, costo, precio):textarea", "enlace:Enlace a revisar (opcional):url"], emite="dd_producto")])
M("M05", "Vigía de competidores", "Revisar bibliotecas de anuncios a mano", "seguimiento automático", "Guardar; alertas; tablero",
  "Yo", "COMPRAR", "S", 58, nivel="A", kinds=["dd_competidor"],
  acciones=[A("analizar", "Analizar un competidor", "Analiza la página adjunta: oferta, ángulos, estructura, precio y lo que conviene probar. Solo lo que la fuente muestra.",
              ["enlace:Página o biblioteca del competidor:url", "foco:Qué quieres aprender:textarea"])])
M("M06", "Fábrica de variaciones", "Un ganador produce pocas variantes", "lotes de variaciones para revisar", "Hooks nuevos; formatos; cola de revisión",
  "Yo, Eq", "CONSTRUIR", "M", 77, kinds=["dd_creativo"], tools=["cumplimiento"], conexiones=["video"], widget="media",
  acciones=[A("variaciones", "Generar 20 variaciones", "Del anuncio ganador, genera exactamente 20 variaciones con la matriz hook × ángulo × formato, nombradas de forma consistente y listas para producir.",
              ["producto:Producto", "ganador:Guion o descripción del anuncio ganador:textarea", "por_que:Por qué crees que gana:textarea",
               "plataforma:Plataforma:select:meta|tiktok|ambas"], emite="dd_creativo")])
M("M07", "Laboratorio de ofertas", "Bundles y precios por intuición", "pruebas con cálculo de margen", "Calculadora; variantes; resultado",
  "Yo", "AUTOMATIZAR", "S", 64, nivel="A", kinds=["dd_oferta"], tools=["oferta"],
  acciones=[A("disenar", "Diseñar ofertas a probar", "Diseña tres estructuras de oferta (packs, ancla, regalo) con su margen calculado y la hipótesis que prueba cada una.",
              ["producto:Producto", "precio:Precio unitario:number", "costo:Costo unitario:number", "flete:Flete:number"], herramienta="oferta", emite="dd_oferta")])
M("M08", "Atribución server-side", "Señal perdida por el navegador", "eventos desde servidor", "CAPI; deduplicar; calidad",
  "Eq", "COMPRAR", "S", 57, kinds=["dd_tienda", "dd_paso"],
  acciones=[A("plan", "Plan de implementación y auditoría", "Entrega el plan de eventos servidor: eventos, parámetros, deduplicación por event_id, pruebas y cómo medir la calidad de coincidencia.",
              ["tienda:Tienda", "plataformas:Plataformas de pauta", "estado:Qué hay instalado hoy:textarea"], emite="dd_paso")])
M("M09", "Generador de advertoriales", "Cada advertorial se escribe desde cero", "plantillas en tu tema", "Ángulo; borrador; montaje",
  "Yo, Eq", "CONSTRUIR", "M", 65, kinds=["dd_pieza"], tools=["cumplimiento"],
  acciones=[A("advertorial", "Escribir advertorial", "Escribe el advertorial completo con el ángulo dado: titular, entrada, historia, mecanismo, prueba, oferta y cierre, por secciones del tema.",
              ["producto:Producto", "angulo:Ángulo:textarea", "lector:Lector y su problema:textarea", "pruebas:Pruebas reales disponibles:textarea"], emite="dd_pieza")])
M("M10", "Bitácora de experimentos", "Pruebas sin registro se repiten", "hipótesis y resultado", "Registro; veredicto; biblioteca",
  "Yo, Eq", "AUTOMATIZAR", "S", 61, nivel="A", kinds=["dd_experimento"], tools=["experimentos"],
  acciones=[A("disenar", "Diseñar un experimento", "Formula la hipótesis falsable, una sola variable, métrica de decisión, tamaño mínimo de muestra y regla de parada.",
              ["idea:Qué quieres probar:textarea"], emite="dd_experimento"),
            A("aprendizajes", "Resumen de aprendizajes", "Sintetiza lo aprendido de los experimentos cerrados y lo que ya no hay que volver a probar.", herramienta="experimentos")])

# ---------- 4. Creación de contenido, storytelling y marca personal
M("C01", "Banco de ideas", "Ideas dispersas", "cola priorizada con investigación", "Captura; ángulos; estado", "Yo", "AUTOMATIZAR", "S", 62, kinds=["dd_idea"],
  acciones=[A("ampliar", "Convertir temas en ideas con ángulo", "Convierte cada tema en ideas concretas con ángulo, formato, canal y prioridad según su potencial.",
              ["temas:Temas o notas:textarea"], emite="dd_idea")])
M("C02", "Perfil de voz y guion", "Los borradores de IA no suenan a ti", "perfil de voz más entrevista", "Perfil; preguntas; borrador",
  "Yo", "CONSTRUIR", "S", 72, kinds=["dd_voz", "dd_pieza"],
  acciones=[A("perfil", "Construir perfil de voz", "Extrae el perfil de voz de las transcripciones: rasgos, frases propias, estructura habitual y lo que nunca dice. Solo lo observable.",
              ["transcripciones:Transcripciones de tus mejores videos:textarea"], emite="dd_voz"),
            A("entrevista", "Preguntas de entrevista", "Formula las preguntas que necesitas responder para escribir el guion solo con tu material.", ["tema:Tema del video"]),
            A("guion", "Escribir guion con tus respuestas", "Escribe el guion usando únicamente las respuestas y el perfil de voz: hook, desarrollo, cierre y llamado.",
              ["tema:Tema", "respuestas:Tus respuestas a la entrevista:textarea", "formato:Formato:select:corto|largo|carrusel"], emite="dd_pieza")])
M("C03", "Evaluador de hooks", "Elegir hook a ojo", "comparación con tu histórico", "Variantes; puntaje; motivo", "Yo", "INTEGRAR", "S", 57, nivel="A", kinds=["dd_pieza"],
  acciones=[A("evaluar", "Puntuar hooks", "Puntúa cada hook (claridad, tensión, especificidad, promesa creíble, encaje con la voz) comparándolo con las piezas publicadas y sus vistas.",
              ["hooks:Hooks a evaluar (uno por línea):textarea", "tema:Tema del video"])])
M("C04", "Línea de clips", "Videos largos sin recortar", "clips automáticos", "Detectar; subtitular; exportar", "Yo, Eq", "COMPRAR", "S", 66, kinds=["dd_pieza"], widget="clip",
  acciones=[A("momentos", "Detectar momentos para clips", "De la transcripción, selecciona los momentos que funcionan solos como clip: inicio y fin, hook, título y por qué retiene.",
              ["transcripcion:Transcripción con tiempos:textarea"], emite="dd_pieza")])
M("C05", "Programador multiplataforma", "Publicar red por red", "una cola", "Programar; adaptar; calendario", "Yo", "COMPRAR", "S", 56, kinds=["dd_pieza"],
  acciones=[A("adaptar", "Adaptar y calendarizar", "Adapta la pieza a cada red (texto, duración, formato) y propone el calendario de la semana.",
              ["pieza:Pieza o guion:textarea", "redes:Redes"], emite="dd_pieza")])
M("C06", "Teleprompter", "Leer guion al grabar", "apuntador integrado", "Texto; velocidad; espejo", "Yo", "COMPRAR", "S", 45, nivel="A", kinds=["dd_pieza"], widget="teleprompter",
  acciones=[A("preparar", "Preparar guion para leer", "Reescribe el guion para lectura en voz alta: frases cortas, pausas marcadas y énfasis, sin cambiar el contenido.", ["guion:Guion:textarea"])])
M("C07", "Biblioteca de b-roll", "Material que no encuentras", "archivo etiquetado", "Etiquetas; búsqueda; proxies", "Yo", "POSPONER", "M", 46, nivel="A", kinds=["dd_conocimiento"],
  acciones=[A("etiquetar", "Etiquetar material", "Propone etiquetas consistentes (tema, plano, lugar, emoción) para el material descrito.", ["material:Descripción o lista del material:textarea"],
              emite="dd_conocimiento")])
M("C08", "Contenido a oportunidad", "Vistas que no se vuelven clientes", "enlaces medidos por video", "Enlace único; formulario; origen",
  "Yo", "AUTOMATIZAR", "S", 62, nivel="A", kinds=["dd_enlace", "dd_aplicacion"], tools=["utm"],
  acciones=[A("atribucion", "Informe de atribución", "Explica qué contenidos traen aplicaciones calificadas y cuáles solo vistas, con lo que conviene repetir.", herramienta="utm")])
M("C09", "Panel de clipping", "Pagos por vistas en hojas", "control de campañas", "Envíos; vistas; liquidación", "Eq", "CONSTRUIR", "L", 63, nivel="A", kinds=["dd_clip_pago"], tools=["clipping_pagos"],
  acciones=[A("liquidacion", "Liquidación del periodo", "Prepara la liquidación por clipper con el cálculo adjunto y señala envíos dudosos que requieren verificación.", herramienta="clipping_pagos")])
M("C10", "Archivo transcrito", "No recuerdas qué ya dijiste", "todo tu contenido buscable", "Transcribir; indexar; citar", "Yo", "CONSTRUIR", "S", 56, nivel="A", kinds=["dd_pieza"],
  acciones=[A("buscar", "¿Qué he dicho sobre…?", "Responde citando textualmente las piezas del archivo donde se trató el tema; si no consta, dilo.", ["tema:Tema o pregunta"])])

# ---------- 5. Gestión de clientes, ventas y plataformas B2B
M("V01", "Embudo de aplicación", "Leads sin calificar te quitan llamadas", "formulario con puntaje", "Preguntas; puntaje; agenda",
  "Yo", "AUTOMATIZAR", "S", 66, nivel="A", kinds=["dd_aplicacion"], tools=["embudo"],
  acciones=[A("formulario", "Diseñar formulario y reglas", "Diseña las preguntas del formulario, el puntaje de cada respuesta, el umbral para ver tu calendario y el recurso para los no calificados.",
              ["oferta:Tu oferta y cliente ideal:textarea", "minimo:Presupuesto mínimo aceptable:number"])])
M("V02", "Generador de propuestas", "Cada propuesta toma horas", "borrador desde la llamada", "Notas; alcance y precio; documento",
  "Yo", "CONSTRUIR", "S", 70, kinds=["dd_plan", "dd_caso"],
  acciones=[A("propuesta", "Propuesta desde la llamada", "De las notas de la llamada, redacta la propuesta: diagnóstico, alcance, exclusiones, plan y precio según tus planes vigentes. Solo cita casos autorizados.",
              ["empresa:Empresa", "notas:Notas o transcripción de la llamada:textarea", "plan:Plan a proponer"])])
M("V03", "Reportes de cliente", "Reportes manuales por cliente", "informe automático con comentario", "Datos; narrativa; envío tras aprobación",
  "Yo, B2B", "CONSTRUIR", "M", 67, kinds=["dd_cliente", "dd_entrega"],
  acciones=[A("reporte", "Reporte del periodo", "Redacta el reporte: resultados frente al periodo anterior, qué se hizo, por qué cambió cada cifra y próximos pasos. Sin adornar resultados malos.",
              ["cliente:Cliente", "periodo:Periodo", "datos:Datos del periodo (pegar tabla o cifras):textarea", "hecho:Trabajo realizado:textarea"], emite="dd_entrega")])
M("V04", "Onboarding en un clic", "Alta de cliente con diez pasos", "secuencia única", "Accesos; carpeta; kickoff", "Yo, B2B", "AUTOMATIZAR", "M", 56, kinds=["dd_paso", "dd_cliente"],
  acciones=[A("alta", "Secuencia de alta", "Genera la secuencia completa de alta: accesos a pedir, carpeta, mensaje de bienvenida, agenda del kickoff y responsables.",
              ["cliente:Cliente", "plan:Plan contratado", "notas:Particularidades:textarea"], emite="dd_paso")])
M("V05", "Bandeja unificada", "WhatsApp, correo y DM separados", "una bandeja con borradores", "Clasificar; borrador; escalar",
  "Yo, Eq", "COMPRAR", "M", 66, kinds=["dd_mensaje"], conexiones=["whatsapp"], widget="whatsapp",
  acciones=[A("borradores", "Clasificar y redactar borradores", "Clasifica cada mensaje nuevo y redacta el borrador de los rutinarios. Negociaciones y casos delicados se marcan para escalar, sin borrador.",
              ["mensajes:Pega los mensajes (opcional si ya están en la bandeja):textarea"], emite="dd_mensaje")])
M("V06", "Portal B2B acotado", "Entregables dispersos", "portal solo de entrega y reportes", "Recursos; reportes; estado", "B2B", "ADAPTAR", "L", 57, nivel="A", kinds=["dd_entrega", "dd_cliente"], widget="portal",
  acciones=[A("estado", "Estado de entregas por cliente", "Resume por cliente qué está entregado, en curso y pendiente de su aprobación.")])
M("V07", "CRM ligero", "Seguimiento en la cabeza", "pipeline", "Etapas; recordatorios; notas", "Yo", "COMPRAR", "S", 59, kinds=["dd_trato"], tools=["pipeline"],
  acciones=[A("seguimiento", "Plan de seguimiento", "Indica a quién escribir hoy, con qué mensaje y qué oportunidad está estancada, según el pipeline.", herramienta="pipeline")])
M("V08", "Contratos y cobro", "Firmas y cobros manuales", "firma y suscripción", "Plantilla; firma; cobro recurrente", "Yo, B2B", "COMPRAR", "S", 55, kinds=["dd_contrato", "dd_plan"],
  acciones=[A("contrato", "Borrador de contrato", "Redacta el borrador del acuerdo de servicios con alcance, exclusiones, pagos, terminación y confidencialidad. Marca lo que debe revisar un abogado.",
              ["cliente:Cliente", "plan:Plan", "condiciones:Condiciones particulares:textarea"], emite="dd_contrato")])
M("V09", "Alerta de churn", "Te enteras tarde de un cliente frío", "señales tempranas", "Resultados; silencio; alerta", "Yo", "AUTOMATIZAR", "S", 57, nivel="A", kinds=["dd_cliente"], tools=["churn"],
  acciones=[A("plan", "Plan de retención", "Para cada cliente en riesgo, propone la acción concreta de esta semana y el mensaje de contacto.", herramienta="churn")])
M("V10", "Bóveda de pruebas", "Tus cifras de venta no están verificadas", "casos con evidencia y permiso", "Captura; autorización; ficha", "Yo", "CONSTRUIR", "S", 62, kinds=["dd_caso"],
  acciones=[A("ficha", "Ficha de caso", "Redacta la ficha del caso solo con lo evidenciado: situación inicial, intervención, resultado medido, periodo y límites. Incluye el texto de autorización a pedir.",
              ["cliente:Cliente", "datos:Datos y evidencia disponibles:textarea"], emite="dd_caso")])

# ---------- 6. Productos SaaS y software comercializable
M("S01", "Tema Shopify propio", "Tiendas dependen de muchas apps de pago", "tema con reseñas, bundles y carrito nativos", "Secciones CRO; plantillas por nicho; sin apps",
  "Eq, Púb", "CONSTRUIR", "L", 71, kinds=["dd_tema_item"],
  acciones=[A("seccion", "Especificar una sección", "Escribe la especificación de la sección: objetivo CRO, ajustes del esquema, estados, accesibilidad, rendimiento y criterios de aceptación.",
              ["seccion:Sección", "reemplaza:App que reemplaza", "nicho:Nicho"], emite="dd_tema_item"),
            A("liquid", "Generar código Liquid", "Entrega el archivo de sección Liquid completo (HTML, esquema JSON, CSS con tokens y JS mínimo), accesible y sin dependencias.",
              ["seccion:Sección", "requisitos:Requisitos:textarea"])])
M("S02", "Utilidad COD como SaaS", "Tiendas COD de LATAM no ven su utilidad", "vender G02", "Conectar; tablero; alertas", "Púb", "POSPONER", "XL", 45, kinds=["dd_paquete", "dd_aplicacion"],
  acciones=[A("validar", "Plan de validación con pago anticipado", "Diseña la validación: a quién, con qué oferta, precio de preventa y la señal que justifica construir.", ["notas:Lo que ya sabes del mercado:textarea"])])
M("S03", "App de chat de producto", "Dudas frenan la compra", "chat de producto en tus tiendas", "Chat; sugerencias; registro", "Púb", "DESCARTAR", "L", 39, kinds=["dd_mensaje", "dd_conocimiento"],
  acciones=[A("base", "Base de respuestas del producto", "Escribe la base de preguntas y respuestas del producto para el chat, solo con datos confirmados.",
              ["producto:Producto", "datos:Datos confirmados del producto:textarea"], emite="dd_conocimiento")])
M("S04", "Riesgo COD", "Devoluciones sin confirmar", "puntaje de riesgo por pedido", "Historial; puntaje; reglas", "Púb", "POSPONER", "XL", 48, nivel="A", kinds=["dd_pedido"], tools=["riesgo_cod"],
  acciones=[A("reglas", "Reglas de confirmación", "Con el riesgo por ciudad y producto, define qué pedidos confirmar por llamada, cuáles por mensaje y cuáles despachar directo.", herramienta="riesgo_cod")])
M("S05", "Kit tienda lista", "Alumnos tardan semanas en montar", "tema + skills + guía", "Instalación; plantillas; curso", "Púb", "POSPONER", "M", 57, kinds=["dd_paquete"],
  acciones=[A("kit", "Definir el kit", "Define contenido, promesa realista, guía de instalación paso a paso y qué soporte incluye y cuál no.", ["publico:Alumno ideal:textarea"], emite="dd_paquete")])
M("S06", "Paquetes de skills", "Operadores quieren tus flujos", "skills empaquetadas", "Fichas; advertoriales; guiones", "Púb", "POSPONER", "S", 54, kinds=["dd_paquete"],
  acciones=[A("paquete", "Empaquetar skills", "Selecciona las skills probadas, escribe la ficha de cada una (para qué, entradas, salida, ejemplo) y la licencia de uso.",
              ["skills:Skills a incluir (IDs)", "publico:Comprador:textarea"], emite="dd_paquete")])
M("S07", "Herramientas imán", "Poco tráfico cualificado a tu oferta", "calculadoras gratis", "Margen COD; ROAS de equilibrio; captura de lead",
  "Púb", "CONSTRUIR", "S", 54, nivel="A", kinds=["dd_aplicacion"], tools=["equilibrio", "oferta", "escenarios"],
  acciones=[A("pagina", "Página de la calculadora", "Escribe la página de la herramienta gratuita: promesa, explicación del cálculo, interpretación del resultado y captura del lead sin fricción.",
              ["herramienta:Calculadora", "oferta:Oferta a la que lleva:textarea"])])
M("S08", "Plataforma de clipping", "Marcas pagan por vistas", "operación de campañas propia", "Campañas; verificación; pagos", "Púb", "DESCARTAR", "XL", 32, nivel="A", kinds=["dd_clip_pago"], tools=["clipping_pagos"],
  acciones=[A("campana", "Brief de campaña de clipping", "Redacta el brief: objetivo, reglas, pago por mil vistas, tope, criterios de verificación y causas de rechazo.",
              ["marca:Marca", "presupuesto:Presupuesto:number", "objetivo:Objetivo:textarea"])])
M("S09", "Reporteador white-label", "Agencias hacen reportes a mano", "reporte con tu marca", "Conectores; plantilla; marca", "Púb", "DESCARTAR", "XL", 33, kinds=["dd_entrega"],
  acciones=[A("plantilla", "Plantilla de reporte con marca", "Diseña la plantilla reutilizable: secciones, métricas por objetivo, comentario y tono de la marca.", ["agencia:Agencia o marca", "servicio:Servicio que reporta"])])
M("S10", "Tutor IA de academia", "Alumnos preguntan lo mismo", "tutor sobre tus cursos", "Respuestas con cita; ejercicios; progreso", "Púb", "POSPONER", "M", 60, nivel="A", kinds=["dd_conocimiento", "dd_mensaje"],
  acciones=[A("responder", "Responder con cita del curso", "Responde la pregunta citando la lección del material; si el material no lo cubre, dilo y deriva al instructor.", ["pregunta:Pregunta del alumno:textarea"]),
            A("ejercicios", "Ejercicios de una lección", "Crea ejercicios graduados con solución sobre la lección indicada.", ["leccion:Lección o tema"])])

# ---------- 7. Agentes de IA y automatizaciones avanzadas
M("A01", "Agente analista de pauta", "Analizar cuentas toma horas", "diagnóstico diario con propuestas", "Leer métricas; hipótesis; cambios propuestos",
  "Yo", "CONSTRUIR", "L", 65, kinds=["dd_gasto_pauta", "dd_pedido"], tools=["utilidad_cod", "guardian_pauta"], conexiones=["meta"],
  acciones=[A("diagnostico", "Diagnóstico diario", "Diagnostica la cuenta: qué cambió, hipótesis ordenadas por evidencia y cambios propuestos con el tamaño de muestra de cada uno. Solo las pausas son ejecutables; el resto espera aprobación.",
              herramienta="utilidad_cod")])
M("A02", "Agente de soporte", "Preguntas repetidas de compradores", "respuestas con datos del pedido", "Estado; preguntas frecuentes; escalar",
  "Eq", "COMPRAR", "M", 60, nivel="C", kinds=["dd_mensaje", "dd_conocimiento", "dd_pedido"],
  acciones=[A("responder", "Borradores de soporte", "Redacta la respuesta a cada comprador con el estado real del pedido y la base de respuestas. Reclamos, devoluciones de dinero y enojo se escalan.",
              ["mensajes:Mensajes de compradores:textarea"], emite="dd_mensaje")])
M("A03", "Agente SDR", "Prospección manual", "investigación y borrador por lead", "Investigar; redactar; cola de envío", "Yo", "POSPONER", "M", 62, kinds=["dd_prospecto"],
  acciones=[A("investigar", "Investigar y redactar borrador", "Investiga la empresa (fuente adjunta) y redacta un primer mensaje personal y breve. Nunca se envía solo: queda en cola para tu aprobación.",
              ["empresa:Empresa", "enlace:Web de la empresa:url", "oferta:Qué le ofreces:textarea"], emite="dd_prospecto")])
M("A04", "Agente QA de tienda", "Errores de página llegan a producción", "revisión antes de pautar", "Enlaces; precios; móvil",
  "Eq", "CONSTRUIR", "S", 64, nivel="A", kinds=["dd_qa"], tools=["salud_tienda", "cumplimiento"],
  acciones=[A("revisar", "Revisar página antes de pautar", "Revisa la página (fuente adjunta): coherencia de precio y oferta, promesas, enlaces, textos rotos, confianza y fricción de compra. Lista de fallas por gravedad.",
              ["enlace:Página a revisar:url", "precio:Precio que debe mostrar:number"], emite="dd_qa")])
M("A05", "Agente de investigación", "Estudiar mercado y cliente toma horas", "informe con fuentes", "Buscar; contrastar; resumir", "Yo", "AUTOMATIZAR", "S", 67, nivel="A", kinds=["dd_conocimiento"],
  acciones=[A("producto", "Investigación de producto", "Informe de producto con fuentes: demanda observable, comprador, competidores, precios vistos, objeciones y riesgos.",
              ["producto:Producto", "enlace:Fuente principal:url", "mercado:Mercado"]),
            A("competidor", "Investigación de competidor", "Informe del competidor con fuentes: oferta, posicionamiento, precios, canales y debilidades aprovechables.", ["enlace:Web del competidor:url"]),
            A("prospecto", "Investigación de prospecto B2B", "Informe del prospecto con fuentes: qué vende, a quién, señales de necesidad y por dónde entrar.", ["enlace:Web del prospecto:url", "oferta:Tu oferta:textarea"])])
M("A06", "Agente de novedades", "Entregas fallidas sin gestión", "contacto y reintento", "Clasificar; escribir; registrar", "Eq", "COMPRAR", "S", 47, nivel="C", kinds=["dd_pedido", "dd_mensaje"],
  acciones=[A("gestionar", "Gestionar novedades", "Clasifica cada novedad (dirección, ausente, rechazo, sin dinero) y redacta el mensaje al comprador y la instrucción a la transportadora.",
              ["novedades:Novedades (pedido, motivo):textarea"], emite="dd_mensaje")])
M("A07", "CI y revisión de código", "Código de IA sin pruebas", "revisión y pruebas en cada cambio", "Pruebas; revisión; bloqueo", "Eq", "INTEGRAR", "S", 59, nivel="A", kinds=["dd_tarea"],
  acciones=[A("revisar", "Revisar un cambio", "Revisa el diff: errores de lógica, casos sin cubrir, seguridad y qué pruebas faltan. Hallazgos por gravedad con la línea afectada.",
              ["diff:Diff o código:textarea", "contexto:Qué debe hacer:textarea"]),
            A("pruebas", "Plan de pruebas", "Escribe los casos de prueba (entrada, resultado esperado) que deben correr en cada cambio.", ["modulo:Módulo o función:textarea"])])
M("A08", "Orquestador de lanzamiento", "Lanzar producto encadena seis pasos", "agentes coordinados", "Investigar; página; creativos",
  "Yo", "POSPONER", "XL", 64, nivel="D", kinds=["dd_lanzamiento", "dd_producto", "dd_creativo"],
  acciones=[A("plan", "Plan de lanzamiento encadenado", "Planifica el lanzamiento paso a paso (A05 → G04 → X07 → M06 → M02 → G02) con la entrada, salida y punto de aprobación de cada etapa.",
              ["producto:Producto", "enlace:Enlace del producto:url", "tienda:Tienda"], emite="dd_lanzamiento")])
M("A09", "Agente financiero", "Conciliación y flujo de caja", "categorización y proyección", "Categorizar; proyectar; alertas", "Yo", "DESCARTAR", "L", 46, nivel="A", kinds=["dd_movimiento"], tools=["flujo_caja"],
  acciones=[A("proyeccion", "Proyección de caja", "Proyecta la caja a 8 semanas con el histórico, señala semanas críticas y qué decisión las evita. No mueve dinero ni accede a bancos.",
              herramienta="flujo_caja")])
M("A10", "Memoria organizacional", "Contexto repetido en cada chat", "base consultable", "Indexar; responder; citar", "Eq", "POSPONER", "M", 50, nivel="A", kinds=["dd_conocimiento"],
  acciones=[A("consultar", "Consultar la memoria", "Responde solo con lo que consta en la base, citando la nota; si no consta, dilo.", ["pregunta:Pregunta:textarea"]),
            A("registrar", "Convertir en nota de conocimiento", "Convierte el texto en notas atómicas, con tema y etiquetas, sin duplicar las existentes.", ["texto:Texto o conversación:textarea"], emite="dd_conocimiento")])

# ---------- 8. Salud física, aprendizaje y desarrollo personal
M("H01", "Registro de entrenamiento", "Progresión sin datos", "registro con progresión", "Series; progresión; historial", "Yo", "COMPRAR", "S", 56, nivel="A", kinds=["dd_serie"], tools=["entrenamiento"],
  acciones=[A("plan", "Ajustar la próxima semana", "Con la progresión calculada, propone la carga de la próxima semana por ejercicio. No sustituye a un profesional.", herramienta="entrenamiento")])
M("H02", "Sueño y recuperación", "Ajustas rutina sin medir", "tendencia de sueño y carga", "Sueño; carga; tendencia", "Yo", "COMPRAR", "S", 52, nivel="A", kinds=["dd_sueno"], tools=["sueno"],
  acciones=[A("lectura", "Lectura de la tendencia", "Interpreta la tendencia y sugiere ajustes de rutina. No es diagnóstico médico.", herramienta="sueno")])
M("H03", "Plan de comidas", "Decidir qué comer cada día", "plan semanal y lista", "Menú; lista; ajustes", "Yo", "AUTOMATIZAR", "S", 52, kinds=["dd_comida"],
  acciones=[A("semana", "Plan semanal y lista de mercado", "Arma el menú de la semana y la lista de mercado consolidada según objetivo, gustos y restricciones.",
              ["objetivo:Objetivo y calorías aproximadas", "gustos:Gustos y restricciones:textarea"], emite="dd_comida")])
M("H04", "Tutor de inglés", "Inglés para vender en EE. UU.", "práctica diaria", "Conversación; corrección; vocabulario de ventas", "Yo", "COMPRAR", "S", 62, nivel="A", kinds=["dd_practica"],
  acciones=[A("sesion", "Sesión de práctica de ventas", "Prepara la sesión: escenario de venta, diálogo modelo, frases clave y diez expresiones para repetir.", ["escenario:Escenario (llamada, objeción, cierre)"]),
            A("corregir", "Corregir mi respuesta", "Corrige el texto: errores, versión natural y por qué, más vocabulario de ventas útil.", ["texto:Tu texto o transcripción en inglés:textarea"], emite="dd_practica")])
M("H05", "Repaso espaciado", "Olvidas lo estudiado", "tarjetas", "Crear; repasar; estadísticas", "Yo", "ADAPTAR OSS", "S", 56, nivel="A", kinds=["flashcard"], widget="repaso",
  acciones=[A("tarjetas", "Crear tarjetas de un texto", "Crea tarjetas atómicas (una idea por tarjeta, pregunta precisa, respuesta breve) del material dado.",
              ["material:Material de estudio:textarea", "mazo:Mazo o tema"], emite="flashcard")])
M("H06", "Programación por proyectos", "Aprender código en abstracto", "aprender leyendo tus proyectos", "Explicación del cambio; ejercicios; revisión", "Yo", "AUTOMATIZAR", "S", 59, nivel="A", kinds=["dd_aprendizaje"],
  acciones=[A("explicar", "Explicar un cambio", "Explica el cambio línea a línea al nivel del lector, el concepto detrás y un ejercicio pequeño para comprobar que se entendió.",
              ["cambio:Diff o código:textarea", "nivel:Tu nivel:select:principiante|intermedio|avanzado"], emite="dd_aprendizaje")])
M("H07", "Asistente de investigación", "Leer mucho, retener poco", "resúmenes con fuentes", "Subir; preguntar; audio", "Yo", "COMPRAR", "S", 57, nivel="A", kinds=["dd_fuente"],
  acciones=[A("resumir", "Resumir una fuente", "Resume la fuente: tesis, argumentos, evidencia, límites y tres preguntas para pensar. Citas textuales verificables.",
              ["enlace:Enlace:url", "texto:O pega el texto:textarea"], emite="dd_fuente")])
M("H08", "Base de conocimiento", "Notas sin conexión", "un solo sistema", "Notas; enlaces; búsqueda", "Yo", "COMPRAR", "S", 54, nivel="A", kinds=["dd_conocimiento"],
  acciones=[A("conectar", "Conectar notas", "Encuentra relaciones entre las notas, propone enlaces y señala contradicciones o huecos.")])
M("H09", "Hábitos gamificados", "Rutina sin seguimiento", "rachas y puntos", "Rachas; puntos; resumen", "Yo", "COMPRAR", "S", 48, nivel="A", kinds=["dd_habito", "dd_habito_registro"], tools=["habitos"],
  acciones=[A("resumen", "Resumen semanal", "Resume la semana de hábitos y propone un único ajuste para la siguiente.", herramienta="habitos")])
M("H10", "Preparación académica", "Estudiar para examen sin plan", "plan y simulacros", "Diagnóstico; calendario; simulacros", "Yo", "AUTOMATIZAR", "S", 51, kinds=["dd_examen"],
  acciones=[A("plan", "Plan de estudio", "Arma el calendario hasta el examen con repasos espaciados y simulacros, priorizando lo más débil.", ["materia:Materia", "fecha:Fecha del examen:date", "temas:Temas y nivel:textarea"]),
            A("simulacro", "Simulacro", "Escribe un simulacro con preguntas del nivel del examen y la clave de respuestas explicada.", ["materia:Materia", "temas:Temas:textarea"])])

# ---------- 9. Espiritualidad, relaciones y organización social
M("R01", "Diario bíblico", "Lecturas y reflexiones sueltas", "lectura con notas", "Plan; notas; búsqueda", "Yo", "COMPRAR", "S", 57, nivel="A", kinds=["dd_lectura"],
  acciones=[A("plan", "Plan de lectura", "Propone un plan de lectura con pasajes por día y una pregunta de reflexión para cada uno.", ["objetivo:Libro, tema o duración"], emite="dd_lectura")])
M("R02", "Preparador de enseñanzas", "Preparar una enseñanza desde cero", "estructura y referencias cruzadas", "Pasajes; bosquejo; tus notas previas",
  "Yo", "AUTOMATIZAR", "S", 54, kinds=["dd_ensenanza", "dd_lectura"],
  acciones=[A("bosquejo", "Bosquejo de enseñanza", "Con la idea central que definió el usuario, propone bosquejo, pasajes de apoyo, referencias cruzadas y preguntas de aplicación. El mensaje lo decide él.",
              ["idea:Idea central (tuya):textarea", "pasaje:Pasaje base", "audiencia:Audiencia"], emite="dd_ensenanza")])
M("R03", "Hábitos espirituales", "Devocional sin seguimiento", "plan con recordatorio", "Plan; recordatorio; racha", "Yo", "COMPRAR", "S", 53, nivel="A", kinds=["dd_habito", "dd_habito_registro"], tools=["habitos"],
  acciones=[A("plan", "Plan devocional", "Propone un plan devocional realista para el tiempo disponible, con estructura de cada sesión.", ["tiempo:Minutos al día", "enfoque:Enfoque"])])
M("R04", "CRM personal", "Contactos valiosos que se enfrían", "fichas y recordatorios", "Ficha; último contacto; próxima acción", "Yo", "ADAPTAR OSS", "S", 61, nivel="A", kinds=["dd_contacto"], tools=["red"],
  acciones=[A("retomar", "A quién retomar esta semana", "Elige a quién escribir esta semana y sugiere un mensaje breve y genuino para cada uno, a partir de las notas.", herramienta="red")])
M("R05", "Notas post-reunión", "Acuerdos que se olvidan", "resumen y tareas", "Transcribir con consentimiento; resumen; tareas", "Yo", "COMPRAR", "S", 62, kinds=["dd_reunion", "dd_tarea"],
  acciones=[A("procesar", "Resumen, acuerdos y tareas", "De la transcripción, entrega resumen, decisiones, acuerdos con responsable y fecha, y preguntas abiertas.",
              ["transcripcion:Transcripción o notas:textarea", "asistentes:Asistentes"], emite="dd_tarea")])
M("R06", "Fechas importantes", "Cumpleaños olvidados", "calendario con aviso", "Fechas; aviso; idea de detalle", "Yo", "AUTOMATIZAR", "S", 48, nivel="A", kinds=["dd_fecha"], tools=["fechas"],
  acciones=[A("detalles", "Ideas de detalle", "Para las fechas próximas, propone un detalle personal según lo que se sabe de cada persona.", herramienta="fechas")])
M("R07", "Mapa de red", "Quién conoce a quién", "grafo de contactos", "Importar; relaciones; rutas", "Yo", "DESCARTAR", "L", 36, nivel="A", kinds=["dd_contacto"], tools=["red"],
  acciones=[A("ruta", "Ruta de presentación", "Con el grafo calculado, indica la mejor ruta para llegar a la persona y cómo pedir la presentación.", ["objetivo:A quién quieres llegar"], herramienta="red")])
M("R08", "Gestor de Discord", "Moderar y dar bienvenida a mano", "reglas y recursos de comunidad", "Bienvenida; roles; recursos", "Yo, Púb", "INTEGRAR", "S", 56, kinds=["dd_comunidad"],
  acciones=[A("estructura", "Estructura de la comunidad", "Diseña canales, roles, mensaje de bienvenida, reglas y respuestas a las preguntas frecuentes.", ["comunidad:Comunidad y propósito:textarea"], emite="dd_comunidad")])
M("R09", "Viajes con plan de contenido", "Viajas sin lista de tomas", "itinerario con plan de grabación", "Itinerario; tomas; publicaciones", "Yo", "AUTOMATIZAR", "S", 52, kinds=["dd_viaje"],
  acciones=[A("plan", "Itinerario y lista de tomas", "Arma el itinerario por día con la lista de tomas, los momentos de grabación y las piezas que salen del viaje.",
              ["destino:Destino", "fechas:Fechas", "historia:Historia que quieres contar:textarea"], emite="dd_viaje")])
M("R10", "Entrenador de ventas", "No revisas tus llamadas", "análisis de objeciones", "Transcripción; objeciones; mejoras", "Yo", "AUTOMATIZAR", "S", 58, nivel="A", kinds=["dd_reunion", "dd_practica"],
  acciones=[A("analizar", "Analizar una llamada", "Analiza la llamada: tiempo hablado, preguntas de descubrimiento, objeciones y cómo se manejaron, momento en que se perdió o ganó, y tres mejoras concretas.",
              ["transcripcion:Transcripción de la llamada:textarea"], emite="dd_practica")])

# ---------- 10. Innovaciones transversales
M("X01", "Capa de permisos y auditoría", "Agentes con llaves completas", "aprobar, limitar y registrar", "Cola de aprobación; límites; registro reversible",
  "Eq", "CONSTRUIR", "M", 63, nivel="A", kinds=["dd_permiso"], tools=["auditoria"],
  acciones=[A("revision", "Revisión de permisos", "Revisa el registro y los permisos: qué módulos piden más autonomía de la necesaria y qué límite falta.", herramienta="auditoria")])
M("X02", "Enrutador híbrido", "Costo de API en tareas simples", "enrutar a modelos baratos", "Reglas; caché; respaldo", "Eq", "POSPONER", "S", 46, nivel="A", kinds=["dd_ruta_modelo"], tools=["costos_ia"],
  acciones=[A("reglas", "Proponer reglas de enrutado", "Con el uso real, propone qué tareas enviar a modelos económicos o locales y cuáles exigen el mejor modelo.", herramienta="costos_ia", emite="dd_ruta_modelo")])
M("X03", "Observatorio de costos de IA", "No ves costo por proyecto", "tablero", "Uso; costo; alertas", "Yo", "DESCARTAR", "S", 49, nivel="A", tools=["costos_ia"],
  acciones=[A("lectura", "Lectura del gasto", "Explica dónde se va el gasto de IA y qué recortar sin perder calidad.", herramienta="costos_ia")])
M("X04", "Sistema de diseño", "Cada página reinventa estilos", "tokens y componentes por marca", "Colores; tipografías; componentes", "Eq", "CONSTRUIR", "M", 59, kinds=["dd_token"],
  acciones=[A("tokens", "Definir tokens de una marca", "Define los tokens de la marca (color, tipografía, espacio, radio) con contraste accesible y el uso de cada uno.",
              ["marca:Marca", "personalidad:Personalidad y referencias:textarea"], emite="dd_token")])
M("X05", "Copias de seguridad", "Una tienda o tema borrado es irrecuperable", "respaldo diario", "Tema en Git; datos de tienda; restauración", "Eq", "COMPRAR", "S", 54, nivel="A", kinds=["dd_respaldo"], tools=["respaldos"],
  acciones=[A("plan", "Plan de respaldo y restauración", "Define qué se respalda, cada cuánto, dónde y la prueba de restauración trimestral.", ["activos:Tiendas, temas y datos críticos:textarea"], emite="dd_respaldo")])
M("X06", "Skills versionadas", "Tus flujos viven en chats", "repositorio con pruebas", "Git; ejemplos de prueba; registro de cambios", "Yo, Eq", "CONSTRUIR", "S", 64, nivel="A", widget="skills",
  acciones=[A("mejorar", "Mejorar una skill", "Revisa la skill pegada: ambigüedades, criterios de calidad que faltan y casos de prueba. Devuelve la versión mejorada completa.",
              ["skill:Texto de la skill:textarea", "fallos:Fallos observados:textarea"])])
M("X07", "Detector de cumplimiento", "Un anuncio rechazado puede tumbar la cuenta", "revisión previa", "Promesas de salud; antes y después; políticas",
  "Yo, Eq, B2B", "CONSTRUIR", "S", 67, nivel="A", kinds=["dd_politica"], tools=["cumplimiento"],
  acciones=[A("revisar", "Revisar una pieza", "Evalúa el riesgo de la pieza frente a las políticas de anuncios, explica cada hallazgo y reescribe una versión de bajo riesgo que conserve la intención.",
              ["texto:Copy, guion o página:textarea", "categoria:Categoría:select:salud|belleza|finanzas|general", "plataforma:Plataforma:select:meta|tiktok|google|todas"],
              herramienta="cumplimiento")])
M("X08", "Redacción local de PII", "Datos de clientes en prompts", "filtro local", "Detectar; enmascarar; restaurar", "Eq", "DESCARTAR", "M", 44, nivel="A", tools=["pii"],
  acciones=[A("politica", "Política de datos personales", "Redacta la política interna breve: qué datos nunca van a un modelo, cómo enmascararlos y quién responde.", ["contexto:Tu operación:textarea"])])
M("X09", "Catálogo de automatizaciones", "Clientes B2B piden lo que ya usas", "paquetes de precio fijo", "Empaquetar; instalar; mantener", "B2B", "POSPONER", "M", 57, kinds=["dd_paquete"],
  acciones=[A("ficha", "Ficha de automatización vendible", "Escribe la ficha: problema, qué incluye, requisitos del cliente, precio fijo, plazo, mantenimiento y lo que no cubre.",
              ["automatizacion:Automatización", "evidencia:Resultado interno medido:textarea"], emite="dd_paquete")])
M("X10", "Simulador de escenarios", "Decides inversiones a ojo", "tres escenarios y punto de equilibrio", "Supuestos; tres escenarios; punto de equilibrio",
  "Yo", "AUTOMATIZAR", "S", 54, nivel="A", tools=["escenarios", "equilibrio"],
  acciones=[A("decision", "Analizar una inversión", "Estructura la decisión: supuestos explícitos, tres escenarios, qué tendría que ser verdad para ganar y la señal temprana para parar.",
              ["inversion:Inversión que evalúas:textarea"])])

# Funcionalidad propia (sin IA) de cada módulo: herramientas deterministas, tipos de dato y panel especial añadidos sobre la definición base.
EXTRA = {
    "P03": (["mensajes"], [], "gmail"), "P05": (["pasos", "runbooks"], ["dd_paso"], None), "P09": (["decisiones"], [], None), "P10": (["runbooks", "pasos"], ["dd_paso"], None),
    "G03": (["pasos"], [], None), "G09": (["pasos", "runbooks"], [], None), "M02": ([], [], "lanzar"), "M04": (["radar", "ficha_web"], [], None), "M05": (["vigia", "ficha_web"], ["dd_alerta"], None),
    "M08": (["pasos"], ["dd_pedido"], "capi"), "C01": (["ideas"], [], None), "C02": (["perfil_voz"], [], None), "C03": (["hooks"], [], None), "C05": ([], [], "redes"), "C07": (["buscar"], [], None),
    "C10": (["buscar", "perfil_voz"], [], None), "V02": (["propuesta", "casos"], [], None), "V03": (["reporte"], [], None), "V04": (["pasos"], [], None), "V05": (["mensajes"], [], None),
    "V08": (["contrato", "cobros"], ["dd_firma"], None), "V10": (["casos"], [], None), "S01": (["tema"], [], "tema"), "S02": (["validacion"], [], None), "S03": (["mensajes", "buscar"], [], None),
    "S05": (["paquete_skills", "tema"], [], None), "S06": (["paquete_skills"], [], None), "S09": (["reporte_marca"], [], None), "S10": (["buscar"], [], None), "A02": (["mensajes", "buscar"], [], None),
    "A03": (["prospectos", "ficha_web"], [], None), "A05": (["ficha_web", "extracto", "buscar"], ["dd_fuente"], None), "A06": (["mensajes"], [], None), "A07": (["revision_codigo"], [], None),
    "A08": (["lanzamientos", "pasos"], ["dd_paso"], None), "A10": (["buscar", "relacionadas"], [], None), "H01": ([], [], "salud"), "H02": ([], [], "salud"), "H03": (["comidas"], [], None),
    "H04": (["ingles"], ["flashcard"], None), "H06": (["revision_codigo"], [], None), "H07": (["extracto", "buscar"], [], None), "H08": (["buscar", "relacionadas"], [], None),
    "H10": (["plan_estudio"], ["dd_bloque"], None), "R01": (["lectura"], [], None), "R02": (["buscar"], [], "escritura"), "R05": (["reunion"], [], None), "R08": (["comunidad"], [], "discord"),
    "R09": (["viaje"], [], None), "R10": (["llamada"], [], None), "X04": (["tokens_css"], [], None), "X06": (["paquete_skills"], [], "skills"), "X09": (["paquete_skills"], [], None),
}
for _id, (_tools, _kinds, _widget) in EXTRA.items():
    MODULES[_id]["tools"] += [t for t in _tools if t not in MODULES[_id]["tools"]]
    MODULES[_id]["kinds"] += [k for k in _kinds if k not in MODULES[_id]["kinds"]]
    if _widget:
        MODULES[_id]["widget"] = _widget

assert len(MODULES) == 100, len(MODULES)

# Entrega 4: los 20 mejores proyectos, en orden.
TOP20 = ["G04", "M06", "G02", "M01", "C02", "S01", "V02", "M03", "G07", "M02", "X07", "V03", "A05", "G01", "M04", "V01", "V05", "P07", "C04", "A01"]


def public() -> dict:
    return {"categorias": {k: {"nombre": v[0], "capa": v[1]} for k, v in CATEGORIES.items()},
            "capas": {k: {"nombre": v[0], "tipo": v[1], "descripcion": v[2]} for k, v in LAYERS.items()}, "autonomia": AUTONOMY, "top20": TOP20,
            "modulos": list(MODULES.values())}
