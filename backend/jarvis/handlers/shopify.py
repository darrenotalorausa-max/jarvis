"""Constructor Shopify: sección Liquid autocontenida + plantilla JSON + contenido por campos + ZIP exportable.

Alcance real: una sección de página de producto para temas Online Store 2.0. No es una tienda completa,
no modifica ningún tema y no se conecta a Shopify: el usuario instala el paquete en una copia del tema.
"""
from __future__ import annotations
import html
import io
import json
import re
import zipfile
from pathlib import Path

from pydantic import BaseModel, Field

from .. import files, records, review
from ..jobs import JobError
from ..worker import handler
from .common import ask_json, available, norm

TEMPLATE = Path(__file__).parent.parent / "templates" / "jarvis-landing.liquid"
SECTION_NAME = "jarvis-landing"

CSS = """.jl{background:var(--jl-bg,#fff);color:var(--jl-text,#1a1a1a);padding:24px 16px;font-size:16px;line-height:1.55}
.jl *{box-sizing:border-box}
.jl__hero{display:grid;gap:24px;max-width:1100px;margin:0 auto}
.jl__media img,.jl__placeholder{width:100%;height:auto;border-radius:12px;display:block;background:#f1f1f1}
.jl__title{font-size:28px;line-height:1.2;margin:0 0 8px}
.jl__sub{margin:0 0 16px;opacity:.85}
.jl__price{font-size:22px;font-weight:700;margin:0 0 16px}
.jl__price-was{font-weight:400;opacity:.6;margin-left:8px}
.jl__form{display:grid;gap:10px;margin:0 0 16px}
.jl__label{font-size:14px;font-weight:600}
.jl__select{min-height:48px;padding:0 12px;border:1px solid currentColor;border-radius:8px;background:transparent;color:inherit;font-size:16px}
.jl__cta{min-height:52px;border:0;border-radius:8px;background:var(--jl-accent,#111);color:var(--jl-accent-text,#fff);font-size:17px;font-weight:700;cursor:pointer;padding:0 20px}
.jl__cta:focus-visible,.jl__select:focus-visible,.jl__faq summary:focus-visible{outline:3px solid var(--jl-accent,#111);outline-offset:3px}
.jl__cta[disabled]{opacity:.5;cursor:not-allowed}
.jl__conditions{font-size:14px;opacity:.85}
.jl__notice{padding:12px;border:1px dashed currentColor;border-radius:8px}
.jl__block{max-width:1100px;margin:40px auto 0}
.jl__h2{font-size:22px;margin:0 0 16px}
.jl__h3{font-size:17px;margin:0 0 6px}
.jl__grid{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.jl__card{border:1px solid rgba(128,128,128,.35);border-radius:12px;padding:16px}
.jl__card p,.jl__qa p,.jl__faq p{margin:0}
.jl__specs{margin:0;padding-left:20px;display:grid;gap:6px}
.jl__qa{padding:14px 0;border-top:1px solid rgba(128,128,128,.35)}
.jl__faq{border-top:1px solid rgba(128,128,128,.35);padding:14px 0}
.jl__faq summary{cursor:pointer;font-weight:600;min-height:32px}
.jl__faq p{padding-top:8px}
@media (min-width:750px){.jl{padding:48px 32px}.jl__hero{grid-template-columns:1fr 1fr;align-items:start;gap:48px}.jl__title{font-size:36px}.jl__grid{grid-template-columns:repeat(3,1fr)}}"""


class Benefit(BaseModel):
    title: str
    text: str
    support: str = Field(description="Cita textual de la especificación o condición aportada que respalda el beneficio")


class QA(BaseModel):
    question: str
    answer: str


class TestVariant(BaseModel):
    element: str
    a: str
    b: str
    hypothesis: str


class Copy(BaseModel):
    positioning: str
    headline: str
    subheadline: str
    cta_label: str = "Añadir al carrito"
    benefits: list[Benefit] = Field(default_factory=list)
    objections: list[QA] = Field(default_factory=list)
    faq: list[QA] = Field(default_factory=list)
    mobile_structure: list[str] = Field(default_factory=list)
    visual_directions: list[str] = Field(default_factory=list)
    test_variants: list[TestVariant] = Field(default_factory=list)


def _pairs(text: str) -> list[tuple[str, str]]:
    out = []
    for line in (text or "").splitlines():
        if line.strip():
            a, _, b = line.partition("|")
            out.append((a.strip(), b.strip()))
    return out


def missing_info(product: dict, image_count: int) -> list[str]:
    d = product["data"]
    checks = [("specs", "Especificaciones del producto"), ("price", "Precio"), ("audience", "Audiencia"), ("market", "Mercado de venta"),
              ("language", "Idioma"), ("conditions", "Condiciones de envío, devolución y garantía"), ("theme_target", "Tema objetivo (nombre y versión)")]
    out = [label for key, label in checks if d.get(key) in (None, "")]
    if not image_count:
        out.append("Imágenes del producto con derechos de uso")
    if d.get("compare_price") and d.get("price") and d["compare_price"] <= d["price"]:
        out.append("El precio de comparación no es mayor que el precio: se ignora")
    return out


def build_schema(defaults: dict) -> dict:
    T = lambda id_, label, default="": {"type": "text", "id": id_, "label": label, "default": default} if default else {"type": "text", "id": id_, "label": label}
    return {
        "name": "Jarvis · Página de producto", "tag": "section", "class": "jl-section", "limit": 1,
        "settings": [
            {"type": "product", "id": "product", "label": "Producto", "info": "En una plantilla de producto se usa el producto de la página."},
            T("heading", "Titular", defaults.get("heading", "")), T("subheading", "Subtítulo", defaults.get("subheading", "")),
            {"type": "image_picker", "id": "image", "label": "Imagen principal"},
            T("cta_label", "Texto del botón", defaults.get("cta_label") or "Añadir al carrito"), T("sold_out_label", "Texto sin existencias", "Agotado"),
            T("variant_label", "Etiqueta del selector de variante", "Variante"),
            T("no_product_text", "Aviso sin producto", "Selecciona un producto en los ajustes de la sección."),
            {"type": "richtext", "id": "conditions", "label": "Condiciones (envío, devolución, garantía)"},
            T("benefits_heading", "Título de beneficios", "Qué obtienes"), T("specs_heading", "Título de especificaciones", "Especificaciones"),
            T("objections_heading", "Título de dudas", "Antes de decidir"), T("faq_heading", "Título de preguntas frecuentes", "Preguntas frecuentes"),
            {"type": "color", "id": "color_bg", "label": "Fondo", "default": "#ffffff"}, {"type": "color", "id": "color_text", "label": "Texto", "default": "#1a1a1a"},
            {"type": "color", "id": "color_accent", "label": "Botón", "default": "#111111"}, {"type": "color", "id": "color_accent_text", "label": "Texto del botón", "default": "#ffffff"},
        ],
        "blocks": [
            {"type": "benefit", "name": "Beneficio", "settings": [{"type": "text", "id": "title", "label": "Título"}, {"type": "textarea", "id": "text", "label": "Texto"}]},
            {"type": "spec", "name": "Especificación", "settings": [{"type": "text", "id": "text", "label": "Texto"}]},
            {"type": "objection", "name": "Duda", "settings": [{"type": "text", "id": "question", "label": "Duda"}, {"type": "textarea", "id": "answer", "label": "Respuesta"}]},
            {"type": "faq", "name": "Pregunta frecuente", "settings": [{"type": "text", "id": "question", "label": "Pregunta"}, {"type": "textarea", "id": "answer", "label": "Respuesta"}]},
        ],
        "presets": [{"name": "Jarvis · Página de producto"}],
    }


def build_section() -> str:
    schema = json.dumps(build_schema({}), ensure_ascii=False, indent=2)
    return TEMPLATE.read_text(encoding="utf-8").replace("__CSS__", CSS).replace("__SCHEMA__", schema)


def build_template(fields: dict) -> dict:
    blocks, order = {}, []
    def add(type_, settings):
        bid = f"{type_}-{len(order) + 1}"
        blocks[bid] = {"type": type_, "settings": settings}
        order.append(bid)
    for b in fields["benefits"]:
        add("benefit", {"title": b["title"], "text": b["text"]})
    for s in fields["specs"]:
        add("spec", {"text": s})
    for o in fields["objections"]:
        add("objection", {"question": o["question"], "answer": o["answer"]})
    for q in fields["faq"]:
        add("faq", {"question": q["question"], "answer": q["answer"]})
    settings = {"heading": fields["heading"], "subheading": fields["subheading"], "cta_label": fields["cta_label"]}
    if fields["conditions"]:
        settings["conditions"] = "".join(f"<p>{html.escape(line)}</p>" for line in fields["conditions"].splitlines() if line.strip())
    return {"sections": {"main": {"type": SECTION_NAME, "blocks": blocks, "block_order": order, "settings": {k: v for k, v in settings.items() if v}}}, "order": ["main"]}


def render_preview(fields: dict, product: dict) -> str:
    """Vista previa aproximada en HTML estático con el mismo CSS. No es el render de Shopify ni del tema."""
    e = html.escape
    d = product["data"]
    price = f"{d['price']:g} {e(d.get('currency') or '')}" if d.get("price") is not None else "[precio pendiente]"
    was = f"<s class='jl__price-was'>{d['compare_price']:g}</s>" if d.get("compare_price") and d.get("price") and d["compare_price"] > d["price"] else ""
    block = lambda title, inner: f"<div class='jl__block'><h2 class='jl__h2'>{e(title)}</h2>{inner}</div>" if inner else ""
    benefits = "".join(f"<li class='jl__card'><h3 class='jl__h3'>{e(b['title'])}</h3><p>{e(b['text'])}</p></li>" for b in fields["benefits"])
    specs = "".join(f"<li>{e(s)}</li>" for s in fields["specs"])
    objections = "".join(f"<div class='jl__qa'><h3 class='jl__h3'>{e(o['question'])}</h3><p>{e(o['answer'])}</p></div>" for o in fields["objections"])
    faq = "".join(f"<details class='jl__faq'><summary>{e(q['question'])}</summary><p>{e(q['answer'])}</p></details>" for q in fields["faq"])
    cond = "".join(f"<p>{e(l)}</p>" for l in fields["conditions"].splitlines() if l.strip())
    return f"""<!doctype html><html lang="{e(d.get('language') or 'es')}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vista previa · {e(fields['heading'])}</title><style>body{{margin:0;font-family:system-ui,sans-serif}}.pv{{background:#fff3cd;color:#5c4400;padding:10px 16px;font-size:14px}}{CSS}</style></head><body>
<div class="pv">Vista previa aproximada generada por Jarvis OS. No es el render de Shopify: tipografías, cabecera, carrito e imágenes dependen del tema donde se instale.</div>
<div class="jl"><div class="jl__hero"><div class="jl__media"><div class="jl__placeholder" style="aspect-ratio:1/1;display:grid;place-items:center;color:#777">Imagen del producto</div></div>
<div class="jl__buy"><h1 class="jl__title">{e(fields['heading'])}</h1>{f"<p class='jl__sub'>{e(fields['subheading'])}</p>" if fields['subheading'] else ''}
<p class="jl__price"><span>{price}</span>{was}</p><div class="jl__form"><button class="jl__cta" type="button">{e(fields['cta_label'])}</button></div>
<div class="jl__conditions">{cond}</div></div></div>
{block('Qué obtienes', f"<ul class='jl__grid'>{benefits}</ul>" if benefits else '')}{block('Especificaciones', f"<ul class='jl__specs'>{specs}</ul>" if specs else '')}
{block('Antes de decidir', objections)}{block('Preguntas frecuentes', faq)}</div></body></html>"""


def liquid_balance_errors(liquid: str) -> list[str]:
    """Comprobación estructural mínima: etiquetas de bloque emparejadas y JSON de schema válido."""
    errors = []
    body = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", liquid, flags=re.S)
    for tag in ("if", "unless", "for", "form", "style", "stylesheet", "schema", "case", "capture"):
        opens = len(re.findall(r"\{%-?\s*" + tag + r"\b", body))
        closes = len(re.findall(r"\{%-?\s*end" + tag + r"\b", body))
        if opens != closes:
            errors.append(f"{tag}: {opens} aperturas y {closes} cierres")
    m = re.search(r"\{%\s*schema\s*%\}(.*?)\{%\s*endschema\s*%\}", liquid, flags=re.S)
    if not m:
        errors.append("falta el bloque schema")
    else:
        try:
            json.loads(m.group(1))
        except ValueError as exc:
            errors.append(f"schema no es JSON válido: {exc}")
    return errors


def inspect_theme(path: Path) -> dict:
    """Lee (sin modificar) un ZIP de tema aportado para informar de compatibilidad."""
    out = {"nombre": None, "version": None, "os2": False, "tiene_main_product": False, "conflicto": False, "notas": []}
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if ".." not in n and not n.startswith("/")]
            def find(suffix):
                return next((n for n in names if n.endswith(suffix)), None)
            out["os2"] = any(re.search(r"(^|/)templates/[^/]+\.json$", n) for n in names)
            out["tiene_main_product"] = bool(find("sections/main-product.liquid"))
            out["conflicto"] = bool(find(f"sections/{SECTION_NAME}.liquid"))
            ss = find("config/settings_schema.json")
            if ss and z.getinfo(ss).file_size < 2_000_000:
                try:
                    info = next((x for x in json.loads(z.read(ss)) if x.get("name") == "theme_info"), {})
                    out["nombre"], out["version"] = info.get("theme_name"), info.get("theme_version")
                except (ValueError, TypeError):
                    out["notas"].append("No se pudo leer settings_schema.json.")
    except (zipfile.BadZipFile, OSError):
        out["notas"].append("El archivo aportado no es un ZIP de tema válido.")
        return out
    if not out["os2"]:
        out["notas"].append("El tema no parece Online Store 2.0 (sin plantillas JSON): la plantilla incluida no funcionará; usa solo la sección.")
    if out["conflicto"]:
        out["notas"].append(f"El tema ya contiene sections/{SECTION_NAME}.liquid: renombra el archivo antes de subirlo para no sobrescribirlo.")
    return out


@handler("shopify_package")
def shopify_package(ctx) -> dict:
    p = ctx.params
    product = records.get(p.get("product_id") or "", ctx.space_id)
    if not product or product["kind"] != "product":
        raise JobError("El producto no existe en este espacio.")
    d = product["data"]
    images = [f for f in (files.get(fid, ctx.space_id) for fid in (p.get("image_file_ids") or [])) if f and (f["mime"] or "").startswith("image/")]
    missing = missing_info(product, len(images))
    specs = [s.strip() for s in (d.get("specs") or "").splitlines() if s.strip()]
    given_text = "\n".join([d.get("specs") or "", d.get("conditions") or "", d.get("benefits") or "", d.get("faq") or ""])
    fields = {"heading": product["title"], "subheading": "", "cta_label": "Añadir al carrito", "conditions": d.get("conditions") or "", "specs": specs,
              "benefits": [{"title": a, "text": b or a, "support": b} for a, b in _pairs(d.get("benefits"))], "objections": [],
              "faq": [{"question": a, "answer": b} for a, b in _pairs(d.get("faq")) if b]}
    extra = {"positioning": "", "mobile": [], "visual": [], "variants": [], "dropped": []}
    origin = "Contenido construido solo con los campos que aportaste (sin modelo de texto)."
    if p.get("use_ai", True) and available(ctx, "extraccion") and specs:
        ctx.stage("copy", 0.3, "Redactando copy a partir de las especificaciones")
        system = ("Redactas la página de un producto para Shopify en el idioma indicado. Persuasión basada en claridad, relevancia, demostración y evidencia. "
                  "Cada beneficio debe apoyarse en una especificación o condición aportada y citarla textualmente en 'support'. Prohibido: reseñas o testimonios, "
                  "urgencia o escasez falsas, resultados garantizados, cifras o certificaciones no aportadas. Si falta información, no la supongas. "
                  "mobile_structure describe el orden de bloques en móvil; visual_directions son indicaciones para fotos reales del producto; "
                  "test_variants propone variantes A/B con su hipótesis.")
        user = (f"Producto: {product['title']}\nTipo: {d.get('type') or ''}\nIdioma: {d.get('language') or 'es'}\nMercado: {d.get('market') or ''}\nAudiencia: {d.get('audience') or ''}\n"
                f"Precio: {d.get('price')} {d.get('currency') or ''}\n<fuente id=\"datos_del_producto\">\nEspecificaciones:\n{d.get('specs') or ''}\n\nCondiciones:\n{d.get('conditions') or ''}\n\n"
                f"Beneficios aportados (beneficio | respaldo):\n{d.get('benefits') or ''}\n</fuente>")
        cp, meta = ask_json(ctx, Copy, system=system, user=user, max_tokens=3000, prompt_version="shopify-v1")
        kept = []
        for b in cp.benefits:
            if len(norm(b.support)) >= 6 and norm(b.support) in norm(given_text):
                kept.append({"title": b.title, "text": b.text, "support": b.support})
            else:
                extra["dropped"].append(f"{b.title}: {b.text}")
        fields.update(heading=cp.headline or product["title"], subheading=cp.subheadline, cta_label=cp.cta_label or "Añadir al carrito",
                      benefits=kept or fields["benefits"], objections=[q.model_dump() for q in cp.objections],
                      faq=fields["faq"] or [q.model_dump() for q in cp.faq])
        extra.update(positioning=cp.positioning, mobile=cp.mobile_structure, visual=cp.visual_directions,
                     variants=[[t.element, t.a, t.b, t.hypothesis] for t in cp.test_variants])
        origin = f"Copy redactado con {meta['connection']} a partir de tus especificaciones; beneficios sin respaldo literal excluidos."
    ctx.stage("paquete", 0.7, "Construyendo sección, plantilla y ZIP")
    section = build_section()
    errors = liquid_balance_errors(section)
    if errors:
        raise JobError("La sección generada no superó la comprobación estructural: " + "; ".join(errors))
    template = build_template(fields)
    theme_info = None
    if p.get("theme_file_id"):
        tf = files.get(p["theme_file_id"], ctx.space_id)
        if tf:
            theme_info = inspect_theme(files.path_of(tf))
    assumptions = [
        "Paquete de UNA sección de página de producto para temas Online Store 2.0; no es una tienda ni un tema completo.",
        "No se ha probado dentro de tu tema: tipografías, anchos y carrito dependen de él. Instálalo siempre en un duplicado del tema.",
        "El botón usa el formulario estándar de producto (POST a /cart/add); el comportamiento posterior (carrito lateral, redirección) lo decide el tema.",
        "El selector de variantes es una lista simple; no actualiza precio ni imagen sin recargar.",
        "Precio, disponibilidad y variantes se leen del producto real en Shopify, no de este paquete.",
        "Las imágenes se incluyen en /assets-para-subir y deben subirse como medios del producto; la plantilla no puede referenciarlas automáticamente.",
        "No se generaron reseñas, urgencia ni escasez. Añádelas solo si son reales y verificables.",
    ]
    if theme_info:
        assumptions.append(f"Tema inspeccionado (solo lectura): {theme_info['nombre'] or 'nombre no detectado'} {theme_info['version'] or ''}. " + " ".join(theme_info["notas"]))
    else:
        assumptions.append("No se adjuntó ningún tema: la compatibilidad con tu tema concreto no está comprobada.")
    install = f"""# Instalación (en un duplicado del tema, nunca en el tema publicado)

1. En Shopify: Tienda online → Temas → ⋯ → **Duplicar** el tema que quieras usar. Trabaja sobre la copia.
2. En la copia: ⋯ → **Editar código**.
3. Carpeta `sections` → Añadir sección nueva → nómbrala `{SECTION_NAME}` y pega el contenido de `sections/{SECTION_NAME}.liquid`.
4. Carpeta `templates` → Añadir plantilla → tipo **product**, formato **JSON**, nombre `{SECTION_NAME}` → pega `templates/product.{SECTION_NAME}.json`.
5. En Productos, abre tu producto y en **Plantilla del tema** elige `{SECTION_NAME}`. Sube las imágenes de `assets-para-subir` como medios del producto.
6. Vista previa de la copia → comprueba en móvil: titular, precio, selector de variantes, botón, carrito y enlaces.
7. Solo cuando todo esté comprobado, publica la copia.

## Supuestos y límites
""" + "\n".join(f"- {a}" for a in assumptions) + "\n\n## Pruebas pendientes en tu tienda\n- Móvil y escritorio\n- Variantes y producto agotado\n- Flujo de carrito y pago en entorno de prueba\n- Eventos de analítica del tema\n"
    copy_md = (f"# {fields['heading']}\n\n{fields['subheading']}\n\n## Posicionamiento\n{extra['positioning'] or '[pendiente]'}\n\n## Beneficios\n"
               + "\n".join(f"- **{b['title']}** — {b['text']} _(respaldo: {b.get('support') or 'aportado por el usuario'})_" for b in fields["benefits"])
               + "\n\n## Dudas\n" + "\n".join(f"- **{o['question']}** {o['answer']}" for o in fields["objections"])
               + "\n\n## Preguntas frecuentes\n" + "\n".join(f"- **{q['question']}** {q['answer']}" for q in fields["faq"]) + "\n")
    preview = render_preview(fields, product)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"sections/{SECTION_NAME}.liquid", section)
        z.writestr(f"templates/product.{SECTION_NAME}.json", json.dumps(template, ensure_ascii=False, indent=2))
        z.writestr("content/fields.json", json.dumps({"producto": product["title"], "campos": fields, "extra": extra}, ensure_ascii=False, indent=2))
        z.writestr("content/copy.md", copy_md)
        z.writestr("INSTALL.md", install)
        z.writestr("preview.html", preview)
        for img in images:
            z.write(files.path_of(img), f"assets-para-subir/{img['name']}")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", product["title"]).strip("-").lower()[:40] or "producto"
    zf = files.save_bytes(ctx.space_id, f"shopify-{slug}.zip", buf.getvalue(), job_id=ctx.id)
    pf = files.save_bytes(ctx.space_id, f"shopify-{slug}-preview.html", preview.encode("utf-8"), job_id=ctx.id)
    sections = [
        {"key": "faltantes", "title": "Información que falta", "type": "list", "items": missing or ["Nada crítico detectado en los campos del producto"]},
        {"key": "posicionamiento", "title": "Posicionamiento y oferta", "type": "text",
         "body": (extra["positioning"] or "[pendiente: posicionamiento]") + f"\n\n**Titular:** {fields['heading']}\n\n**Subtítulo:** {fields['subheading'] or '—'}\n\n**Botón:** {fields['cta_label']}", "note": origin},
        {"key": "beneficios", "title": "Beneficios respaldados", "type": "table", "columns": ["Beneficio", "Texto", "Respaldo"],
         "rows": [[b["title"], b["text"], b.get("support") or ""] for b in fields["benefits"]]},
        {"key": "excluidos", "title": "Beneficios excluidos por falta de respaldo", "type": "list", "items": extra["dropped"] or ["Ninguno"]},
        {"key": "objeciones", "title": "Objeciones", "type": "table", "columns": ["Duda", "Respuesta"], "rows": [[o["question"], o["answer"]] for o in fields["objections"]]},
        {"key": "faq", "title": "Preguntas frecuentes", "type": "table", "columns": ["Pregunta", "Respuesta"], "rows": [[q["question"], q["answer"]] for q in fields["faq"]]},
        {"key": "movil", "title": "Estructura móvil", "type": "list", "items": extra["mobile"] or ["Imagen", "Titular y precio", "Botón de compra", "Condiciones", "Beneficios", "Especificaciones", "Dudas", "Preguntas frecuentes"]},
        {"key": "visual", "title": "Indicaciones visuales", "type": "list", "items": extra["visual"] or ["[pendiente: define las fotos reales del producto que necesitas]"]},
        {"key": "variantes", "title": "Variantes de prueba", "type": "table", "columns": ["Elemento", "A", "B", "Hipótesis"], "rows": extra["variants"]},
        {"key": "supuestos", "title": "Supuestos y límites", "type": "list", "items": assumptions},
        {"key": "archivos", "title": "Archivos", "type": "files", "items": [{"file_id": zf["id"], "name": zf["name"], "note": "Paquete ZIP con sección, plantilla, contenido e instrucciones"},
                                                                       {"file_id": pf["id"], "name": pf["name"], "note": "Vista previa aproximada (no es el render del tema)"}]},
    ]
    dv = review.create(ctx.space_id, "shopify", f"Paquete Shopify: {product['title']}", {"summary": origin, "sections": sections,
                       "meta": {"product_id": product["id"], "tema": theme_info}}, author="jarvis", job_id=ctx.id, project_id=product["project_id"],
                       brand_id=product["brand_id"], ref_id=product["id"])
    return {"mensaje": f"Paquete Shopify listo ({len(missing)} dato(s) pendiente(s)).", "deliverable_ids": [dv["id"]], "file_ids": [zf["id"], pf["id"]], "faltantes": missing}
