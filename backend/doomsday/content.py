"""Contenido integrado de Doomsday: plantillas de pasos, banco de frases y secciones Liquid. Texto fijo, sin IA.

Las listas de pasos son procedimientos generales del oficio; no afirman precios ni cuotas. Las secciones Liquid no se han probado todavía en una tienda real.
"""
from __future__ import annotations

Y, E = "Tú", "Equipo"
CHECKLISTS: dict[str, list[tuple[str, str]]] = {
    "tienda_shopify_cod": [
        ("Datos legales de la tienda: nombre, dirección y correo de contacto", Y), ("Políticas publicadas: envíos, devoluciones, privacidad y términos", Y),
        ("Mercado, moneda e impuestos del país de venta", Y), ("Pago contra entrega activado y probado; pasarela prepago si aplica", Y),
        ("Zonas y tarifas de envío por ciudad principal y resto", E), ("Tema instalado en un duplicado y ajustes de marca (logo, colores, tipografía)", E),
        ("Menús, página de inicio, contacto y seguimiento de pedido", E), ("Dominio conectado y certificado activo", Y), ("Correo del dominio y remitente de notificaciones", E),
        ("Píxel de Meta y de TikTok instalados; evento de compra verificado", E), ("Eventos de servidor (API de conversiones) con deduplicación", E),
        ("Formulario de pedido contra entrega: campos mínimos y validación de teléfono", E), ("Operador logístico conectado y bodega configurada", Y),
        ("Apps: solo las imprescindibles; quitar las de prueba", E), ("Notificaciones de pedido revisadas (texto y remitente)", E),
        ("Pedido de prueba completo en móvil: producto, formulario, confirmación y llegada al operador", Y), ("Velocidad de la página de producto medida en móvil", E),
        ("Tienda dada de alta en el monitor de salud (G07)", E), ("Copia del tema guardada y registrada en respaldos (X05)", E), ("Contraseña de la tienda retirada y revisión final", Y)],
    "alta_cliente_b2b": [
        ("Contrato aceptado y primer pago registrado", Y), ("Espacio del cliente creado en el portal (V06) y usuario con rol cliente", Y),
        ("Formulario de arranque enviado: oferta, márgenes, cliente ideal, histórico", Y), ("Acceso por invitación a la cuenta publicitaria (nunca por contraseña)", "Cliente"),
        ("Acceso por invitación a la tienda con permisos mínimos", "Cliente"), ("Acceso a analítica y a la página de la marca", "Cliente"),
        ("Carpeta compartida con materiales de marca y creativos existentes", "Cliente"), ("Canal y horario de comunicación acordados", Y),
        ("Llamada de arranque agendada con agenda de 30 minutos", Y), ("Auditoría inicial entregada con línea base de las métricas", E),
        ("Primer entregable y fecha comprometidos por escrito", Y), ("Fecha del primer reporte y cadencia", Y)],
    "incorporacion_equipo": [
        ("Accesos creados con el mínimo permiso y 2FA (P02)", Y), ("Presentación de los negocios y de quién decide qué", Y), ("Lee los procedimientos de su rol y pregunta dudas", "Persona nueva"),
        ("Observa la tarea principal hecha por quien la domina", "Persona nueva"), ("Hace la tarea acompañada y recibe correcciones", "Persona nueva"),
        ("Hace la tarea sola con revisión al final", "Persona nueva"), ("Prueba práctica: tarea real con criterio de calidad escrito", Y), ("Documenta una mejora al procedimiento", "Persona nueva"),
        ("Revisión a los 14 días: qué domina y qué falta", Y)],
    "eventos_servidor": [
        ("Inventario de eventos: vista de producto, carrito, inicio de compra, compra", E), ("Token de la API de conversiones generado y guardado en Apps conectadas", Y),
        ("Mismo identificador de evento en navegador y servidor para deduplicar", E), ("Datos de coincidencia permitidos: teléfono y correo siempre con hash", E),
        ("Prueba con la herramienta de eventos de la plataforma", E), ("Calidad de coincidencia revisada tras 3 días", E), ("Aviso de privacidad actualizado", Y),
        ("Envío de compras entregadas (COD) desde Doomsday activado en M08", Y)],
    "lanzamiento_producto": [
        ("Investigación con fuentes (A05) aprobada", Y), ("Punto de equilibrio calculado y candidato puntuado (M04)", Y), ("Ficha generada y aprobada (G04)", Y),
        ("Revisión de cumplimiento sin hallazgos graves (X07)", E), ("Página publicada en borrador y revisada en móvil (A04)", E), ("20 variaciones generadas y elegidas (M06)", Y),
        ("Creativos producidos y nombrados", E), ("Reglas de pauta con CPA límite (M01)", Y), ("Campaña creada en pausa y revisada (M02)", Y), ("Activación con presupuesto de prueba", Y),
        ("Lectura de utilidad neta a los 3 y 7 días (G02)", Y), ("Decisión registrada: escalar, corregir o detener (P09)", Y)],
    "restauracion_respaldo": [
        ("Elegir un respaldo de hace más de una semana", E), ("Restaurarlo en una instancia o tema de prueba, nunca sobre producción", E), ("Comprobar que abre y que los datos coinciden", E),
        ("Medir cuánto tardó la restauración", E), ("Anotar la fecha de la prueba en X05", E)],
    "procedimiento_nuevo": [
        ("Escribir el objetivo y el resultado verificable", Y), ("Listar accesos y herramientas necesarias", Y), ("Grabar o relatar el proceso real una vez", Y),
        ("Convertirlo en pasos numerados con el valor exacto de cada uno", E), ("Escribir la prueba final que demuestra que quedó bien", E), ("Hacer que otra persona lo ejecute sin ayuda", E),
        ("Corregir lo que no se entendió y publicarlo como vigente", Y)],
}

FRASES_EN: dict[str, list[tuple[str, str]]] = {
    "apertura": [("Gracias por tomarte el tiempo hoy.", "Thanks for taking the time today."), ("¿Te parece si te cuento cómo va a ser la llamada?", "Mind if I walk you through how this call will go?"),
                 ("Cuéntame un poco de tu negocio.", "Tell me a bit about your business."), ("¿Qué te llevó a agendar esta llamada?", "What made you book this call?"),
                 ("Antes de empezar, ¿hay algo que quieras cubrir sí o sí?", "Before we start, is there anything you definitely want to cover?")],
    "descubrimiento": [("¿Cuál es tu mayor cuello de botella ahora mismo?", "What's your biggest bottleneck right now?"), ("¿Qué has intentado hasta ahora?", "What have you tried so far?"),
                       ("¿Qué pasa si esto sigue igual seis meses?", "What happens if nothing changes in six months?"), ("¿Cómo mides el éxito?", "How do you measure success?"),
                       ("¿Quién más participa en esta decisión?", "Who else is involved in this decision?"), ("¿Cuánto facturas al mes, más o menos?", "Roughly how much revenue are you doing per month?"),
                       ("¿Por qué ahora?", "Why now?")],
    "propuesta": [("Con lo que me cuentas, esto es lo que haría.", "Based on what you've shared, here's what I'd do."), ("Esto incluye… y no incluye…", "This includes… and it doesn't include…"),
                  ("La inversión es de… al mes.", "The investment is… per month."), ("Empezaríamos el lunes.", "We'd kick off on Monday."), ("¿Tiene sentido hasta aquí?", "Does that make sense so far?")],
    "objeciones": [("Entiendo. ¿Qué es lo que más te preocupa?", "I hear you. What concerns you most?"), ("¿Es el precio o es que no ves el retorno?", "Is it the price, or is it that you don't see the return yet?"),
                   ("Tiene sentido querer pensarlo. ¿Qué necesitarías ver para decidir?", "It makes sense to think it over. What would you need to see to decide?"),
                   ("¿Con qué lo estás comparando?", "What are you comparing it against?"), ("No te puedo prometer resultados; sí te puedo mostrar el proceso.", "I can't promise results; I can show you the process."),
                   ("Si el tiempo no fuera un problema, ¿avanzarías?", "If timing weren't an issue, would you move forward?")],
    "cierre": [("¿Quieres que avancemos?", "Would you like to move forward?"), ("Te envío el acuerdo hoy mismo.", "I'll send the agreement over today."), ("¿Qué día te queda bien para arrancar?", "What day works for you to start?"),
               ("Quedo atento a cualquier duda.", "Let me know if any questions come up."), ("Gracias por la confianza.", "Thanks for trusting us with this.")],
}

TOMAS_VIAJE = ["Plano general de llegada (establece el lugar)", "Detalle de manos o comida (textura)", "Tú caminando de espaldas hacia el lugar", "Plano a cámara: qué viniste a buscar aquí",
               "Sonido ambiente de 20 segundos", "Hora dorada: plano abierto sin gente", "Un local hablando o trabajando (con su permiso)", "Transición: puerta, túnel o ventanilla",
               "Plano fijo de 10 segundos para texto en pantalla", "Cierre a cámara: qué aprendiste hoy"]

THEME_README = """# Secciones de Doomsday para tu tema Shopify

1. En Shopify: Tienda online → Temas → (tu tema) → Editar código.
2. Copia cada archivo `.liquid` de la carpeta `sections` a la carpeta «sections» del tema.
3. En el editor del tema, añade la sección desde «Añadir sección».

Pruébalas siempre en un duplicado del tema antes de publicarlas. No dependen de ninguna app.
"""


def _section(nombre: str, reemplaza: str, liquid: str) -> dict:
    return {"nombre": nombre, "reemplaza": reemplaza, "liquid": liquid.strip() + "\n"}


SECTIONS: dict[str, dict] = {
    "dd-packs": _section("Packs con precio por cantidad", "Apps de bundles y descuentos por cantidad", """
{%- comment -%} Doomsday · Packs: el comprador elige cuántas unidades lleva. Usa la cantidad del carrito; el descuento se configura en Shopify (Descuentos automáticos por cantidad). {%- endcomment -%}
{%- liquid
  assign p = section.settings.product | default: product
  assign v = p.selected_or_first_available_variant
-%}
{%- if p -%}
<div class="dd-packs page-width" style="--dd-accent: {{ section.settings.accent }};">
  {%- if section.settings.heading != blank -%}<h2 class="dd-packs__title">{{ section.settings.heading | escape }}</h2>{%- endif -%}
  {%- form 'product', p, class: 'dd-packs__form' -%}
    <input type="hidden" name="id" value="{{ v.id }}">
    <div class="dd-packs__list" role="radiogroup" aria-label="{{ section.settings.heading | escape }}">
      {%- for block in section.blocks -%}
        {%- liquid
          assign qty = block.settings.quantity
          assign total = v.price | times: qty
          assign off = total | times: block.settings.discount | divided_by: 100
          assign final = total | minus: off
        -%}
        <label class="dd-packs__item" {{ block.shopify_attributes }}>
          <input type="radio" name="quantity" value="{{ qty }}" {% if block.settings.featured %}checked{% endif %}>
          <span class="dd-packs__main">
            <span class="dd-packs__name">{{ block.settings.label | escape }}</span>
            {%- if block.settings.note != blank -%}<span class="dd-packs__note">{{ block.settings.note | escape }}</span>{%- endif -%}
          </span>
          <span class="dd-packs__price">
            {%- if block.settings.discount > 0 -%}<s>{{ total | money }}</s>{%- endif -%}
            <strong>{{ final | money }}</strong>
          </span>
          {%- if block.settings.featured -%}<span class="dd-packs__tag">{{ section.settings.featured_label | escape }}</span>{%- endif -%}
        </label>
      {%- endfor -%}
    </div>
    <button type="submit" class="dd-packs__btn" {% unless v.available %}disabled{% endunless %}>
      {%- if v.available -%}{{ section.settings.button | escape }}{%- else -%}{{ section.settings.sold_out | escape }}{%- endif -%}
    </button>
    {%- if section.settings.discount_note != blank -%}<p class="dd-packs__small">{{ section.settings.discount_note | escape }}</p>{%- endif -%}
  {%- endform -%}
</div>
{%- endif -%}
{% style %}
  .dd-packs { padding-block: 24px; max-width: 560px; }
  .dd-packs__title { font-size: 1.25rem; margin: 0 0 12px; }
  .dd-packs__list { display: grid; gap: 8px; }
  .dd-packs__item { position: relative; display: flex; align-items: center; gap: 12px; padding: 14px 16px; border: 1px solid rgba(0, 0, 0, 0.18); border-radius: 10px; cursor: pointer; }
  .dd-packs__item:has(input:checked) { border-color: var(--dd-accent); outline: 2px solid var(--dd-accent); outline-offset: -1px; }
  .dd-packs__item input { accent-color: var(--dd-accent); width: 18px; height: 18px; }
  .dd-packs__main { flex: 1; display: grid; }
  .dd-packs__name { font-weight: 600; }
  .dd-packs__note { font-size: 0.85rem; opacity: 0.75; }
  .dd-packs__price { display: grid; text-align: right; }
  .dd-packs__price s { font-size: 0.85rem; opacity: 0.6; }
  .dd-packs__tag { position: absolute; top: -10px; right: 12px; background: var(--dd-accent); color: #fff; font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
  .dd-packs__btn { width: 100%; margin-top: 14px; min-height: 52px; border: 0; border-radius: 10px; background: var(--dd-accent); color: #fff; font-size: 1.05rem; font-weight: 600; cursor: pointer; }
  .dd-packs__btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .dd-packs__btn:focus-visible, .dd-packs__item:focus-within { outline: 2px solid currentColor; outline-offset: 2px; }
  .dd-packs__small { font-size: 0.8rem; opacity: 0.7; margin: 8px 0 0; text-align: center; }
{% endstyle %}
{% schema %}
{
  "name": "DD · Packs por cantidad",
  "settings": [
    { "type": "product", "id": "product", "label": "Producto (vacío: el de la página)" },
    { "type": "text", "id": "heading", "label": "Título", "default": "Elige tu pack" },
    { "type": "text", "id": "button", "label": "Texto del botón", "default": "Pedir ahora" },
    { "type": "text", "id": "sold_out", "label": "Texto de agotado", "default": "Agotado" },
    { "type": "text", "id": "featured_label", "label": "Etiqueta del pack recomendado", "default": "Más elegido" },
    { "type": "text", "id": "discount_note", "label": "Nota bajo el botón", "info": "El descuento real se crea en Shopify → Descuentos (automático por cantidad). Esta sección solo lo muestra." },
    { "type": "color", "id": "accent", "label": "Color de acento", "default": "#1f6feb" }
  ],
  "blocks": [
    { "type": "pack", "name": "Pack", "settings": [
      { "type": "text", "id": "label", "label": "Nombre", "default": "1 unidad" },
      { "type": "text", "id": "note", "label": "Nota" },
      { "type": "range", "id": "quantity", "label": "Unidades", "min": 1, "max": 10, "step": 1, "default": 1 },
      { "type": "range", "id": "discount", "label": "Descuento mostrado (%)", "min": 0, "max": 60, "step": 5, "default": 0 },
      { "type": "checkbox", "id": "featured", "label": "Recomendado y preseleccionado", "default": false }
    ] }
  ],
  "max_blocks": 5,
  "presets": [ { "name": "DD · Packs por cantidad", "blocks": [ { "type": "pack" }, { "type": "pack", "settings": { "label": "2 unidades", "quantity": 2, "discount": 10, "featured": true } }, { "type": "pack", "settings": { "label": "3 unidades", "quantity": 3, "discount": 20 } } ] } ]
}
{% endschema %}
"""),
    "dd-resenas": _section("Reseñas nativas", "Apps de reseñas", """
{%- comment -%} Doomsday · Reseñas: se escriben como bloques en el editor del tema. Usa solo reseñas reales de compradores. {%- endcomment -%}
{%- liquid
  assign count = section.blocks.size
  assign sum = 0
  for block in section.blocks
    assign sum = sum | plus: block.settings.rating
  endfor
-%}
<div class="dd-rev page-width">
  <div class="dd-rev__head">
    <h2 class="dd-rev__title">{{ section.settings.heading | escape }}</h2>
    {%- if count > 0 -%}
      {%- assign avg = sum | times: 1.0 | divided_by: count | round: 1 -%}
      <p class="dd-rev__avg" aria-label="{{ avg }} de 5">{{ avg }} / 5 · {{ count }} {{ section.settings.count_label | escape }}</p>
    {%- endif -%}
  </div>
  {%- if count == 0 -%}
    <p class="dd-rev__empty">{{ section.settings.empty | escape }}</p>
  {%- else -%}
    <ul class="dd-rev__grid" role="list">
      {%- for block in section.blocks -%}
        <li class="dd-rev__card" {{ block.shopify_attributes }}>
          <p class="dd-rev__stars" aria-label="{{ block.settings.rating }} de 5">{%- for i in (1..5) -%}{%- if i <= block.settings.rating -%}★{%- else -%}☆{%- endif -%}{%- endfor -%}</p>
          {%- if block.settings.image != blank -%}
            {{ block.settings.image | image_url: width: 480 | image_tag: loading: 'lazy', class: 'dd-rev__img', alt: block.settings.author }}
          {%- endif -%}
          <p class="dd-rev__text">{{ block.settings.text | escape }}</p>
          <p class="dd-rev__author">{{ block.settings.author | escape }}{% if block.settings.verified %} · {{ section.settings.verified_label | escape }}{% endif %}</p>
        </li>
      {%- endfor -%}
    </ul>
  {%- endif -%}
</div>
{% style %}
  .dd-rev { padding-block: 32px; }
  .dd-rev__head { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: baseline; justify-content: space-between; margin-bottom: 16px; }
  .dd-rev__title { margin: 0; font-size: 1.4rem; }
  .dd-rev__avg { margin: 0; font-weight: 600; }
  .dd-rev__grid { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
  .dd-rev__card { padding: 16px; border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 12px; display: grid; gap: 8px; align-content: start; }
  .dd-rev__stars { margin: 0; letter-spacing: 2px; color: {{ section.settings.star }}; }
  .dd-rev__img { width: 100%; height: auto; border-radius: 8px; aspect-ratio: 1; object-fit: cover; }
  .dd-rev__text { margin: 0; }
  .dd-rev__author { margin: 0; font-size: 0.85rem; opacity: 0.7; }
  .dd-rev__empty { opacity: 0.7; }
{% endstyle %}
{% schema %}
{
  "name": "DD · Reseñas",
  "settings": [
    { "type": "text", "id": "heading", "label": "Título", "default": "Lo que dicen quienes ya lo tienen" },
    { "type": "text", "id": "count_label", "label": "Palabra tras el número", "default": "reseñas" },
    { "type": "text", "id": "verified_label", "label": "Etiqueta de compra verificada", "default": "Compra verificada" },
    { "type": "text", "id": "empty", "label": "Texto sin reseñas", "default": "Aún no hay reseñas de este producto." },
    { "type": "color", "id": "star", "label": "Color de las estrellas", "default": "#e0a100" }
  ],
  "blocks": [
    { "type": "review", "name": "Reseña", "settings": [
      { "type": "text", "id": "author", "label": "Nombre", "default": "Nombre del comprador" },
      { "type": "range", "id": "rating", "label": "Estrellas", "min": 1, "max": 5, "step": 1, "default": 5 },
      { "type": "textarea", "id": "text", "label": "Reseña", "info": "Copia el texto real del comprador. No inventes reseñas." },
      { "type": "image_picker", "id": "image", "label": "Foto (opcional)" },
      { "type": "checkbox", "id": "verified", "label": "Compra verificada", "default": true }
    ] }
  ],
  "presets": [ { "name": "DD · Reseñas" } ]
}
{% endschema %}
"""),
    "dd-preguntas": _section("Preguntas frecuentes", "Apps de FAQ y acordeones", """
{%- comment -%} Doomsday · Preguntas frecuentes con datos estructurados para buscadores. Sin JavaScript: usa details/summary. {%- endcomment -%}
<div class="dd-faq page-width">
  {%- if section.settings.heading != blank -%}<h2 class="dd-faq__title">{{ section.settings.heading | escape }}</h2>{%- endif -%}
  {%- for block in section.blocks -%}
    <details class="dd-faq__item" {{ block.shopify_attributes }}>
      <summary>{{ block.settings.question | escape }}</summary>
      <div class="dd-faq__answer">{{ block.settings.answer }}</div>
    </details>
  {%- endfor -%}
</div>
{%- if section.blocks.size > 0 -%}
<script type="application/ld+json">
{ "@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
  {%- for block in section.blocks -%}
    { "@type": "Question", "name": {{ block.settings.question | json }}, "acceptedAnswer": { "@type": "Answer", "text": {{ block.settings.answer | strip_html | json }} } }{% unless forloop.last %},{% endunless %}
  {%- endfor -%}
] }
</script>
{%- endif -%}
{% style %}
  .dd-faq { padding-block: 32px; max-width: 760px; }
  .dd-faq__title { font-size: 1.4rem; margin: 0 0 12px; }
  .dd-faq__item { border-bottom: 1px solid rgba(0, 0, 0, 0.14); }
  .dd-faq__item summary { cursor: pointer; padding: 16px 28px 16px 0; font-weight: 600; list-style: none; position: relative; }
  .dd-faq__item summary::-webkit-details-marker { display: none; }
  .dd-faq__item summary::after { content: "+"; position: absolute; right: 4px; top: 14px; font-size: 1.3rem; font-weight: 400; }
  .dd-faq__item[open] summary::after { content: "–"; }
  .dd-faq__item summary:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
  .dd-faq__answer { padding: 0 0 16px; }
{% endstyle %}
{% schema %}
{
  "name": "DD · Preguntas frecuentes",
  "settings": [ { "type": "text", "id": "heading", "label": "Título", "default": "Preguntas frecuentes" } ],
  "blocks": [ { "type": "question", "name": "Pregunta", "settings": [
    { "type": "text", "id": "question", "label": "Pregunta", "default": "¿Cuánto tarda el envío?" },
    { "type": "richtext", "id": "answer", "label": "Respuesta", "default": "<p>Escribe aquí la respuesta real.</p>" }
  ] } ],
  "presets": [ { "name": "DD · Preguntas frecuentes", "blocks": [ { "type": "question" }, { "type": "question" } ] } ]
}
{% endschema %}
"""),
    "dd-confianza": _section("Barra de confianza", "Apps de insignias y sellos", """
{%- comment -%} Doomsday · Barra de confianza: envío, pago y garantía. Escribe solo condiciones que cumples. {%- endcomment -%}
<div class="dd-trust page-width">
  <ul class="dd-trust__list" role="list">
    {%- for block in section.blocks -%}
      <li class="dd-trust__item" {{ block.shopify_attributes }}>
        {%- if block.settings.icon != blank -%}{{ block.settings.icon | image_url: width: 96 | image_tag: loading: 'lazy', class: 'dd-trust__icon', alt: '' }}{%- endif -%}
        <span><strong>{{ block.settings.title | escape }}</strong>{% if block.settings.text != blank %}<br><span class="dd-trust__text">{{ block.settings.text | escape }}</span>{% endif %}</span>
      </li>
    {%- endfor -%}
  </ul>
</div>
{% style %}
  .dd-trust { padding-block: 20px; }
  .dd-trust__list { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px 24px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
  .dd-trust__item { display: flex; gap: 12px; align-items: center; }
  .dd-trust__icon { width: 40px; height: 40px; object-fit: contain; flex: none; }
  .dd-trust__text { font-size: 0.85rem; opacity: 0.75; }
{% endstyle %}
{% schema %}
{
  "name": "DD · Barra de confianza",
  "blocks": [ { "type": "item", "name": "Elemento", "settings": [
    { "type": "image_picker", "id": "icon", "label": "Icono" },
    { "type": "text", "id": "title", "label": "Título", "default": "Pagas al recibir" },
    { "type": "text", "id": "text", "label": "Detalle" }
  ] } ],
  "max_blocks": 6,
  "presets": [ { "name": "DD · Barra de confianza", "blocks": [ { "type": "item" }, { "type": "item", "settings": { "title": "Envío a todo el país" } }, { "type": "item", "settings": { "title": "Cambios y devoluciones" } } ] } ]
}
{% endschema %}
"""),
    "dd-comprar-fijo": _section("Barra de compra fija en móvil", "Apps de sticky add to cart", """
{%- comment -%} Doomsday · Barra de compra fija: aparece al bajar por la página de producto. Sin librerías. {%- endcomment -%}
{%- if product -%}
{%- assign v = product.selected_or_first_available_variant -%}
<dd-sticky-buy class="dd-sticky" hidden>
  <div class="dd-sticky__in">
    <span class="dd-sticky__info"><strong>{{ product.title | escape }}</strong><span>{{ v.price | money }}</span></span>
    {%- form 'product', product, class: 'dd-sticky__form' -%}
      <input type="hidden" name="id" value="{{ v.id }}">
      <button type="submit" {% unless v.available %}disabled{% endunless %}>{% if v.available %}{{ section.settings.button | escape }}{% else %}{{ section.settings.sold_out | escape }}{% endif %}</button>
    {%- endform -%}
  </div>
</dd-sticky-buy>
<script>
  if (!customElements.get('dd-sticky-buy')) {
    customElements.define('dd-sticky-buy', class extends HTMLElement {
      connectedCallback() {
        const anchor = document.querySelector('form[action*="/cart/add"] [type="submit"]');
        if (!anchor || !('IntersectionObserver' in window)) return;
        new IntersectionObserver((entries) => { this.hidden = entries[0].isIntersecting; }).observe(anchor);
      }
    });
  }
</script>
{% style %}
  .dd-sticky { position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; background: {{ section.settings.background }}; color: {{ section.settings.text }}; border-top: 1px solid rgba(0, 0, 0, 0.12); padding: 10px 16px calc(10px + env(safe-area-inset-bottom)); }
  .dd-sticky[hidden] { display: none; }
  .dd-sticky__in { max-width: 720px; margin: 0 auto; display: flex; align-items: center; gap: 12px; }
  .dd-sticky__info { flex: 1; display: grid; min-width: 0; font-size: 0.9rem; }
  .dd-sticky__info strong { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dd-sticky__form button { min-height: 46px; padding: 0 22px; border: 0; border-radius: 10px; background: {{ section.settings.accent }}; color: #fff; font-weight: 600; cursor: pointer; }
  .dd-sticky__form button:disabled { opacity: 0.5; }
  @media (min-width: 990px) { .dd-sticky { display: {% if section.settings.desktop %}block{% else %}none{% endif %}; } }
{% endstyle %}
{%- endif -%}
{% schema %}
{
  "name": "DD · Compra fija",
  "settings": [
    { "type": "text", "id": "button", "label": "Texto del botón", "default": "Pedir ahora" },
    { "type": "text", "id": "sold_out", "label": "Texto de agotado", "default": "Agotado" },
    { "type": "checkbox", "id": "desktop", "label": "Mostrar también en escritorio", "default": false },
    { "type": "color", "id": "background", "label": "Fondo", "default": "#ffffff" },
    { "type": "color", "id": "text", "label": "Texto", "default": "#111111" },
    { "type": "color", "id": "accent", "label": "Botón", "default": "#1f6feb" }
  ],
  "enabled_on": { "templates": [ "product" ] },
  "presets": [ { "name": "DD · Compra fija" } ]
}
{% endschema %}
"""),
    "dd-comparativa": _section("Tabla comparativa", "Apps de tablas de comparación", """
{%- comment -%} Doomsday · Comparativa: tu producto frente a la alternativa genérica. No nombres marcas de terceros. {%- endcomment -%}
<div class="dd-cmp page-width">
  {%- if section.settings.heading != blank -%}<h2 class="dd-cmp__title">{{ section.settings.heading | escape }}</h2>{%- endif -%}
  <div class="dd-cmp__wrap" role="region" aria-label="{{ section.settings.heading | escape }}" tabindex="0">
    <table class="dd-cmp__table">
      <thead><tr><th scope="col"><span class="visually-hidden">Característica</span></th><th scope="col">{{ section.settings.ours | escape }}</th><th scope="col">{{ section.settings.theirs | escape }}</th></tr></thead>
      <tbody>
        {%- for block in section.blocks -%}
          <tr {{ block.shopify_attributes }}>
            <th scope="row">{{ block.settings.feature | escape }}</th>
            <td>{% if block.settings.ours_text != blank %}{{ block.settings.ours_text | escape }}{% elsif block.settings.ours %}Sí{% else %}No{% endif %}</td>
            <td>{% if block.settings.theirs_text != blank %}{{ block.settings.theirs_text | escape }}{% elsif block.settings.theirs %}Sí{% else %}No{% endif %}</td>
          </tr>
        {%- endfor -%}
      </tbody>
    </table>
  </div>
</div>
{% style %}
  .dd-cmp { padding-block: 32px; max-width: 760px; }
  .dd-cmp__title { font-size: 1.4rem; margin: 0 0 12px; }
  .dd-cmp__wrap { overflow-x: auto; }
  .dd-cmp__table { width: 100%; border-collapse: collapse; }
  .dd-cmp__table th, .dd-cmp__table td { padding: 12px 10px; text-align: left; border-bottom: 1px solid rgba(0, 0, 0, 0.12); }
  .dd-cmp__table thead th:nth-child(2), .dd-cmp__table td:nth-child(2) { background: {{ section.settings.highlight }}; font-weight: 600; }
{% endstyle %}
{% schema %}
{
  "name": "DD · Comparativa",
  "settings": [
    { "type": "text", "id": "heading", "label": "Título", "default": "Por qué elegir este" },
    { "type": "text", "id": "ours", "label": "Tu columna", "default": "Este producto" },
    { "type": "text", "id": "theirs", "label": "La otra columna", "default": "Alternativas comunes" },
    { "type": "color", "id": "highlight", "label": "Fondo de tu columna", "default": "#f1f6ff" }
  ],
  "blocks": [ { "type": "row", "name": "Fila", "settings": [
    { "type": "text", "id": "feature", "label": "Característica", "default": "Característica" },
    { "type": "checkbox", "id": "ours", "label": "Tu producto la tiene", "default": true },
    { "type": "text", "id": "ours_text", "label": "Texto en tu columna (opcional)" },
    { "type": "checkbox", "id": "theirs", "label": "La alternativa la tiene", "default": false },
    { "type": "text", "id": "theirs_text", "label": "Texto en la otra columna (opcional)" }
  ] } ],
  "presets": [ { "name": "DD · Comparativa", "blocks": [ { "type": "row" }, { "type": "row" }, { "type": "row" } ] } ]
}
{% endschema %}
"""),
}
