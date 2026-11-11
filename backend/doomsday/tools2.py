"""Segunda tanda de herramientas deterministas: dan funcionalidad propia (sin IA) a los módulos que solo tenían skill.

Búsqueda, puntajes por regla, plantillas de documentos, listas de pasos, análisis de transcripciones y de código, exportaciones.
Las que devuelven «secciones» pueden guardarse como entregable revisable desde el panel.
"""
from __future__ import annotations
import hashlib
import io
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date, timedelta

from jarvis import db, files, records, review, webfetch

from . import catalog, content, skills
from .tools import M, SIN_DATOS, T, _day, n, pct, r2, recs, tool


def _norm(s) -> str:
    import unicodedata
    return re.sub(r"[^a-z0-9ñ]+", " ", unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()).strip()


STOP = set("de la el en y a los las que un una por con para del se su al lo como mas o pero sus le ya es son fue ha me si no mi te tu yo muy este esta esto eso hay ser tiene todo cuando que the and to of in is it you for on".split())


def _words(s) -> list[str]:
    return [w for w in _norm(s).split() if len(w) > 2 and w not in STOP]


def _text(rec: dict) -> str:
    return " \n".join([rec["title"]] + [" ".join(v) if isinstance(v, list) else str(v) for v in rec["data"].values() if isinstance(v, (str, list)) and v])


def S(titulo: str, contenido: str) -> dict:
    return {"titulo": titulo, "contenido": contenido}


# ---------- Búsqueda en los datos del módulo (C10, A10, H08, C07, S10, S03, H07, A05)

@tool("buscar", "Buscar en los datos de este módulo", ["consulta:Qué buscas"], auto=False)
def buscar(space_id, inp):
    q = _words(inp.get("consulta"))
    if not q:
        raise ValueError("Escribe qué buscas.")
    mod = catalog.MODULES.get(str(inp.get("_module") or ""))
    kinds_ = mod["kinds"] if mod else ["dd_conocimiento", "dd_pieza", "dd_fuente"]
    hits = []
    for kind in kinds_:
        for r in recs(space_id, kind):
            txt = _text(r)
            low = _norm(txt)
            score = sum(low.count(w) + 3 * _norm(r["title"]).count(w) for w in q)
            if all(w in low for w in q) or score >= len(q) * 2:
                m = re.search(re.escape(q[0]), _norm(txt))
                pos = max(0, txt.lower().find(q[0][:5]) - 80) if m else 0
                hits.append((score + (5 if all(w in low for w in q) else 0), [r["title"], records.KINDS[kind]["label"], txt[pos:pos + 240].replace("\n", " "), r["data"].get("fecha") or r["created_at"][:10]]))
    hits.sort(key=lambda h: -h[0])
    return {"resumen": f"{len(hits)} coincidencias por texto exacto (sin IA). Cada fila cita el fragmento donde aparece.",
            "metricas": [M("Coincidencias", len(hits))], "tablas": [T("Resultados", ["Registro", "Tipo", "Fragmento", "Fecha"], [h[1] for h in hits[:40]])],
            "alertas": [] if hits else ["Nada coincide. Si no consta aquí, no está registrado."]}


@tool("relacionadas", "Notas relacionadas y huérfanas")
def relacionadas(space_id, inp):
    notas = recs(space_id, "dd_conocimiento")
    if len(notas) < 2:
        return {"resumen": "Hacen falta al menos dos notas."}
    bags = {r["id"]: (r, set(_words(_text(r))) | {f"#{_norm(t)}" for t in r["data"].get("etiquetas") or []}) for r in notas}
    filas, solos = [], []
    for rid, (r, bag) in bags.items():
        best = sorted(((len(bag & b2) / (len(bag | b2) or 1), r2_["title"]) for i2, (r2_, b2) in bags.items() if i2 != rid), reverse=True)[:2]
        if best and best[0][0] >= 0.12:
            filas.append([r["title"], best[0][1], f"{best[0][0] * 100:.0f} %", best[1][1] if len(best) > 1 and best[1][0] >= 0.12 else ""])
        else:
            solos.append([r["title"], r["data"].get("tema") or ""])
    return {"resumen": "Parecido por palabras y etiquetas compartidas. Las notas sin relación son candidatas a enlazar o archivar.",
            "metricas": [M("Notas", len(notas)), M("Sin relación", len(solos), "amber" if solos else "ok")],
            "tablas": [T("Enlaces sugeridos", ["Nota", "Más parecida", "Parecido", "Segunda"], filas[:80]), T("Notas sueltas", ["Nota", "Tema"], solos[:60])]}


# ---------- Contenido: voz, hooks, ideas

@tool("perfil_voz", "Perfil de voz medido en tus transcripciones")
def perfil_voz(space_id, inp):
    textos = [r["data"].get("texto") or "" for r in recs(space_id, "dd_pieza") if len(r["data"].get("texto") or "") > 200]
    if not textos:
        return {"resumen": "Carga en «Datos» las transcripciones de tus videos como piezas (campo «Texto»). " + SIN_DATOS}
    frases = [f.strip() for t in textos for f in re.split(r"(?<=[.!?…])\s+|\n+", t) if len(f.strip()) > 3]
    largo = [len(f.split()) for f in frases]
    palabras = [w for t in textos for w in _words(t)]
    bi = Counter(" ".join(p) for t in textos for p in zip(_norm(t).split(), _norm(t).split()[1:], _norm(t).split()[2:]) if not all(w in STOP for w in p))
    aperturas = [re.split(r"(?<=[.!?])\s", t.strip())[0][:140] for t in textos]
    preg = sum(1 for f in frases if "?" in f)
    tu = sum(len(re.findall(r"\b(tu|tus|te|ti|usted)\b", _norm(t))) for t in textos)
    yo = sum(len(re.findall(r"\b(yo|mi|me|mis)\b", _norm(t))) for t in textos)
    return {"resumen": "Medido sobre tus textos, sin IA: es la base objetiva del perfil. La skill C02 escribe con estos rasgos.",
            "metricas": [M("Piezas analizadas", len(textos)), M("Palabras por frase", r2(sum(largo) / len(largo))), M("Frases con pregunta", f"{pct(preg, len(frases))} %"),
                         M("Le hablas al espectador (tú) por cada «yo»", r2(tu / yo) if yo else "sin «yo»")],
            "tablas": [T("Frases que repites (3 palabras)", ["Frase", "Veces"], [[k, v] for k, v in bi.most_common(25) if v > 1]),
                       T("Palabras más tuyas", ["Palabra", "Veces"], Counter(palabras).most_common(30)), T("Cómo abres", ["Primera frase"], [[a] for a in aperturas[:20]])],
            "secciones": [S("Rasgos medidos", f"- Frases de {sum(largo) / len(largo):.0f} palabras de media.\n- {pct(preg, len(frases))} % de las frases son preguntas.\n"
                                                + "\n".join(f"- Repite «{k}» ({v} veces)." for k, v in bi.most_common(8) if v > 1))]}


PODER = ("nadie", "nunca", "error", "secreto", "verdad", "dejé", "deje", "perdí", "perdi", "gané", "gane", "por qué", "por que", "cómo", "como", "sin", "antes", "deja de", "no hagas")


def _hook_score(h: str) -> tuple[int, str]:
    w = h.split()
    p, mot = 0, []
    if 4 <= len(w) <= 14:
        p += 20
    else:
        mot.append("demasiado largo" if len(w) > 14 else "demasiado corto")
    if re.search(r"\d", h):
        p, mot = p + 20, mot + ["cifra concreta"]
    if "?" in h or re.match(r"^(por que|como|que|cual|sabias)", _norm(h)):
        p, mot = p + 15, mot + ["abre una pregunta"]
    if re.search(r"\b(tu|tus|te|ti)\b", _norm(h)):
        p, mot = p + 15, mot + ["habla al espectador"]
    if any(k in h.lower() for k in PODER):
        p, mot = p + 15, mot + ["tensión o contraste"]
    if not re.search(r"\b(increible|brutal|mejor del mundo|te va a volar la cabeza|no creeras)\b", _norm(h)):
        p += 15
    else:
        mot.append("promesa hueca")
    return min(p, 100), ", ".join(mot)


@tool("hooks", "Puntuar hooks por regla y contra tu histórico", ["hooks:Hooks (uno por línea):textarea"], auto=False)
def hooks(space_id, inp):
    lista = [h.strip(" -•\t") for h in str(inp.get("hooks") or "").splitlines() if len(h.strip()) > 5][:40]
    if not lista:
        raise ValueError("Pega al menos un hook.")
    hist = sorted([r for r in recs(space_id, "dd_pieza") if n(r["data"].get("vistas")) and r["data"].get("texto")], key=lambda r: -n(r["data"]["vistas"]))
    top = [set(_words(re.split(r"(?<=[.!?])\s", r["data"]["texto"].strip())[0])) for r in hist[:max(3, len(hist) // 4)]]
    filas = []
    for h in lista:
        p, mot = _hook_score(h)
        par = max((len(set(_words(h)) & t) / (len(set(_words(h)) | t) or 1) for t in top), default=0)
        filas.append([h, p + (10 if par >= 0.2 else 0), mot, f"{par * 100:.0f} %" if top else "sin histórico"])
    filas.sort(key=lambda f: -f[1])
    return {"resumen": "Regla fija: longitud, cifra, pregunta, segunda persona, tensión y ausencia de promesa hueca. Suma 10 si se parece a las aperturas de tus piezas más vistas.",
            "tablas": [T("Ranking", ["Hook", "Puntaje", "Por qué", "Parecido a tus mejores"], filas)], "metricas": [M("Mejor puntaje", filas[0][1], "ok")]}


@tool("ideas", "Cola de ideas priorizada")
def ideas(space_id, inp):
    its = [i for i in recs(space_id, "dd_idea") if i["status"] not in ("publicada", "descartada")]
    if not its:
        return {"resumen": SIN_DATOS}
    filas = []
    for i in its:
        d = i["data"]
        p = {"alta": 50, "media": 30, "baja": 10}.get(d.get("prioridad") or "", 20) + (15 if d.get("angulo") else 0) + (10 if d.get("formato") else 0) + (10 if d.get("canal") else 0)
        edad = (date.today() - date.fromisoformat(i["created_at"][:10])).days
        filas.append([i["title"], i["status"], p - min(15, edad // 14 * 5), d.get("angulo") or "FALTA ÁNGULO", f"{edad} días"])
    filas.sort(key=lambda f: -f[2])
    est = Counter(i["status"] for i in its)
    return {"resumen": "Prioridad declarada, más completitud (ángulo, formato, canal), menos antigüedad sin avanzar.",
            "metricas": [M("En cola", len(its)), M("Sin ángulo", sum(1 for f in filas if f[3] == "FALTA ÁNGULO"), "amber"), M("En guion", est["en_guion"])],
            "tablas": [T("Qué grabar primero", ["Idea", "Estado", "Puntaje", "Ángulo", "Antigüedad"], filas[:60])]}


# ---------- Producto, competidores y web

@tool("radar", "Puntaje COD de candidatos", ["entrega:Tasa de entrega esperada (%):number", "flete:Flete por defecto:number"])
def radar(space_id, inp):
    prods = [p for p in recs(space_id, "dd_producto") if p["status"] in ("candidato", "en_prueba")]
    if not prods:
        return {"resumen": SIN_DATOS}
    e, flete_def, filas = n(inp.get("entrega"), 65) / 100, n(inp.get("flete"), 0), []
    for p in prods:
        d = p["data"]
        precio, costo, flete = n(d.get("precio")), n(d.get("costo")), n(d.get("flete")) or flete_def
        if not precio or not costo:
            filas.append([p["title"], None, None, None, 0, "faltan precio o costo"])
            continue
        margen = e * (precio - costo - flete) - (1 - e) * 2 * flete
        mult = precio / costo
        s = min(40, max(0, margen / precio * 100)) + min(25, max(0, (mult - 2) * 12.5)) + (15 if flete and flete / precio <= 0.15 else 5 if flete else 0) + (10 if d.get("angulo") else 0) + (10 if d.get("nicho") else 0)
        records.update(p["id"], space_id, {"data": {"puntaje": round(s)}})
        filas.append([p["title"], r2(mult), r2(margen), r2(margen), round(s), "pasa" if s >= 60 and margen > 0 else "no pasa"])
    filas.sort(key=lambda f: -f[4])
    return {"resumen": f"Con entrega del {e * 100:.0f} %: margen por pedido despachado (40), múltiplo sobre costo (25), flete ligero (15), ángulo y nicho definidos (20). El puntaje queda guardado en cada producto.",
            "tablas": [T("Candidatos", ["Producto", "Múltiplo", "Margen por pedido", "CPA de equilibrio", "Puntaje", "Veredicto"], filas)],
            "metricas": [M("Candidatos", len(filas)), M("Pasan", sum(1 for f in filas if f[5] == "pasa"), "ok")]}


def _page(url: str) -> dict:
    page = webfetch.fetch_page(url)
    if page["status"] != "ok":
        raise ValueError(f"No se pudo leer la página: {page.get('note') or page['status']}")
    return page


def web_facts(url: str) -> dict:
    page = _page(url)
    text, links = page.get("text") or "", [str(l) for l in page.get("links") or []]
    low = (text + " " + " ".join(links)).lower()
    redes = sorted({m.group(1) for l in links for m in [re.search(r"(instagram|facebook|tiktok|youtube|linkedin|wa\.me|whatsapp)\.", l)] if m})
    precios = re.findall(r"(?:\$|usd|cop|€)\s?\d[\d.,]{2,}", text, flags=re.I)[:12]
    return {"url": page["url"], "titulo": page.get("title") or "", "descripcion": page.get("description") or "", "palabras": len(text.split()),
            "plataforma": "Shopify" if "shopify" in low else "WooCommerce" if "woocommerce" in low or "wp-content" in low else "no identificada", "redes": redes, "precios": precios,
            "correos": sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[a-z.]{2,}", text)))[:5], "hash": hashlib.sha256(text.encode()).hexdigest()[:16], "texto": text}


@tool("ficha_web", "Ficha objetiva de una web", ["enlace:Web a analizar:url"], auto=False)
def ficha_web(space_id, inp):
    if not inp.get("enlace"):
        raise ValueError("Indica la web.")
    f = web_facts(str(inp["enlace"]))
    frases = [x.strip() for x in re.split(r"(?<=[.!?])\s+", f["texto"]) if 40 < len(x) < 220][:6]
    return {"resumen": "Hechos leídos de la página pública, sin IA ni inferencias. Respeta robots.txt.",
            "metricas": [M("Plataforma", f["plataforma"]), M("Palabras", f["palabras"]), M("Precios vistos", len(f["precios"])), M("Redes enlazadas", len(f["redes"]))],
            "tablas": [T("Datos", ["Dato", "Valor"], [["Título", f["titulo"]], ["Descripción", f["descripcion"]], ["Precios", ", ".join(f["precios"])], ["Redes", ", ".join(f["redes"])],
                                                     ["Contacto público", ", ".join(f["correos"])]]), T("Primeras afirmaciones", ["Texto"], [[x] for x in frases])],
            "secciones": [S("Ficha", f"**{f['titulo']}** ({f['url']})\n{f['descripcion']}\n- Plataforma: {f['plataforma']}\n- Precios vistos: {', '.join(f['precios']) or 'ninguno'}\n- Redes: {', '.join(f['redes']) or 'ninguna'}")]}


@tool("vigia", "Revisar cambios en competidores", auto=False)
def vigia(space_id, inp):
    comps = [c for c in recs(space_id, "dd_competidor", "siguiendo") if c["data"].get("url")]
    if not comps:
        return {"resumen": "Registra competidores con su URL en «Datos»."}
    filas, alertas = [], []
    for c in comps[:25]:
        try:
            f = web_facts(c["data"]["url"])
        except ValueError as exc:
            filas.append([c["title"], "no se pudo leer", str(exc)[:80], ""])
            continue
        prev, prev_p = c["data"].get("huella"), c["data"].get("precios_vistos") or ""
        precios = ", ".join(f["precios"][:6])
        estado = "primera lectura" if not prev else "sin cambios" if prev == f["hash"] else "CAMBIÓ"
        if estado == "CAMBIÓ":
            detalle = f"precios: {prev_p or '—'} → {precios or '—'}" if precios != prev_p else "cambió el texto de la página"
            alertas.append(f"{c['title']}: {detalle}.")
            records.create(space_id, "dd_alerta", f"Cambio en {c['title']}", {"origen": "M05", "fecha": date.today().isoformat(), "detalle": detalle})
        records.update(c["id"], space_id, {"data": {"huella": f["hash"], "precios_vistos": precios, "revisado": date.today().isoformat()}})
        filas.append([c["title"], estado, precios, f["titulo"][:60]])
    return {"resumen": "Lee la página pública de cada competidor y la compara con la última lectura. Los cambios quedan como alerta.",
            "metricas": [M("Revisados", len(filas)), M("Con cambios", len(alertas), "amber" if alertas else "ok")],
            "tablas": [T("Competidores", ["Competidor", "Estado", "Precios vistos", "Título"], filas)], "alertas": alertas}


@tool("extracto", "Resumen extractivo de un texto o enlace", ["enlace:Enlace:url", "texto:O pega el texto:textarea", "frases:Número de frases:number"], auto=False)
def extracto(space_id, inp):
    titulo, texto = "Texto pegado", str(inp.get("texto") or "")
    if inp.get("enlace"):
        p = _page(str(inp["enlace"]))
        titulo, texto = p.get("title") or p["url"], p.get("text") or ""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n+", texto) if 40 <= len(f.strip()) <= 400]
    if len(frases) < 3:
        raise ValueError("El texto es demasiado corto para resumirlo.")
    freq = Counter(_words(texto))
    k = max(3, min(15, int(n(inp.get("frases"), 7))))
    punt = sorted(((sum(freq[w] for w in set(_words(f))) / (len(_words(f)) + 5), i) for i, f in enumerate(frases)), reverse=True)[:k]
    elegidas = [frases[i] for _, i in sorted(punt, key=lambda x: x[1])]
    rec = records.create(space_id, "dd_fuente", titulo[:200], {"url": inp.get("enlace") or None, "texto": texto[:20000], "resumen": "\n".join(f"- {f}" for f in elegidas)}, status="resumido")
    return {"resumen": f"Frases textuales del original elegidas por la frecuencia de sus términos (sin IA, sin reescribir). Guardado en «Fuentes de estudio» ({rec['id']}).",
            "metricas": [M("Palabras del original", len(texto.split())), M("Frases elegidas", len(elegidas))],
            "tablas": [T("Términos centrales", ["Término", "Veces"], freq.most_common(15))], "secciones": [S(f"Extracto de «{titulo[:80]}»", "\n".join(f"- {f}" for f in elegidas))]}


# ---------- Documentos por plantilla (V02, V03, V08, V10, X09): mismos datos, mismo documento

def _plan(space_id: str, nombre: str) -> dict:
    planes = recs(space_id, "dd_plan", "vigente")
    p = next((x for x in planes if _norm(x["title"]) == _norm(nombre)), None) or (planes[0] if len(planes) == 1 and not nombre else None)
    if not p:
        raise ValueError("Registra tus planes de servicio en «Datos» (alcance, exclusiones, precio) y elige uno por su nombre. Planes vigentes: " + (", ".join(x["title"] for x in planes) or "ninguno"))
    return p


def _lista(texto: str) -> str:
    return "\n".join(f"- {l.strip(' -•')}" for l in str(texto or "").splitlines() if l.strip()) or "- [por definir]"


@tool("propuesta", "Propuesta desde tus planes y casos", ["empresa:Empresa", "plan:Plan (nombre)", "problema:Problema del cliente en sus palabras:textarea",
                                                        "objetivo:Resultado buscado y cómo se mide:textarea", "inicio:Fecha de inicio:date"], auto=False)
def propuesta(space_id, inp):
    if not inp.get("empresa"):
        raise ValueError("Indica la empresa.")
    p = _plan(space_id, str(inp.get("plan") or ""))
    d = p["data"]
    casos = [c for c in recs(space_id, "dd_caso", "autorizado") if c["data"].get("autorizado")]
    sec = [S("Diagnóstico", str(inp.get("problema") or "[por definir: problema del cliente en sus palabras]")),
           S("Objetivo y medición", str(inp.get("objetivo") or "[por definir]")),
           S(f"Alcance · {p['title']}", _lista(d.get("alcance"))), S("Lo que no incluye", _lista(d.get("exclusiones"))),
           S("Inversión y condiciones", f"- Inversión: {n(d.get('precio')):,.0f}{' · ' + d['duracion'] if d.get('duracion') else ''}\n{_lista(d.get('condiciones'))}"),
           S("Casos verificados", "\n".join(f"- **{c['data'].get('cliente') or c['title']}**: {c['data'].get('resultado')} ({c['data'].get('fecha') or 'sin fecha'})" for c in casos[:3])
             or "Aún no hay casos autorizados en la bóveda de pruebas; no se cita ninguno."),
           S("Siguiente paso", f"Confirmar esta propuesta para iniciar el {inp.get('inicio') or '[fecha por definir]'}. Vigencia: 15 días.")]
    return {"resumen": f"Armada con el plan «{p['title']}» y solo con casos autorizados ({len(casos)}). Guárdala como entregable para revisarla y enviarla.",
            "metricas": [M("Plan", p["title"]), M("Inversión", r2(n(d.get("precio")))), M("Casos citados", min(3, len(casos)))], "secciones": sec, "titulo_doc": f"Propuesta para {inp['empresa']}"}


@tool("contrato", "Contrato de servicios desde tu plan", ["cliente:Cliente (razón social)", "plan:Plan (nombre)", "inicio:Inicio:date", "pago:Forma y fecha de pago",
                                                         "ciudad:Ciudad y país de ley aplicable"], auto=False)
def contrato(space_id, inp):
    if not inp.get("cliente"):
        raise ValueError("Indica el cliente.")
    p = _plan(space_id, str(inp.get("plan") or ""))
    d = p["data"]
    sec = [S("1. Partes", f"Entre **[tu razón social]** («el Prestador») y **{inp['cliente']}** («el Cliente»)."),
           S("2. Objeto y alcance", _lista(d.get("alcance"))), S("3. Exclusiones", _lista(d.get("exclusiones"))),
           S("4. Plazo", f"Inicia el {inp.get('inicio') or '[por definir]'}{' con duración de ' + d['duracion'] if d.get('duracion') else ''}. Se renueva por periodos iguales salvo aviso con 15 días."),
           S("5. Honorarios", f"{n(d.get('precio')):,.0f} por periodo. {inp.get('pago') or '[forma y fecha de pago por definir]'}. El retraso de más de 10 días suspende el servicio."),
           S("6. Terminación", "Cualquiera de las partes puede terminar con 15 días de aviso escrito. Los honorarios causados no son reembolsables."),
           S("7. Propiedad intelectual", "Los entregables pagados son del Cliente. Las herramientas, plantillas y métodos del Prestador siguen siendo suyos."),
           S("8. Confidencialidad y datos", "Las partes mantienen en reserva la información de la otra y tratan los datos personales solo para ejecutar este contrato."),
           S("9. Responsabilidad", "El Prestador se obliga a los medios descritos, no a un resultado comercial. Su responsabilidad se limita a lo pagado en los últimos tres meses."),
           S("10. Ley aplicable", f"{inp.get('ciudad') or '[por definir]'}."),
           S("Revisión legal", "Plantilla general: [por definir] hazla revisar por un abogado de tu jurisdicción antes de firmar. No es asesoría legal.")]
    if not any(c["title"] == f"{inp['cliente']} · {p['title']}" for c in recs(space_id, "dd_contrato")):
        records.create(space_id, "dd_contrato", f"{inp['cliente']} · {p['title']}", {"cliente": inp["cliente"], "tipo": p["title"], "valor": d.get("precio"), "recurrente": True, "firma": None})
    return {"resumen": "Borrador desde tu plan vigente; el contrato quedó registrado en «Datos». Guárdalo como entregable, apruébalo y el cliente podrá aceptarlo desde su acceso.",
            "secciones": sec, "titulo_doc": f"Contrato de servicios · {inp['cliente']}", "metricas": [M("Plan", p["title"]), M("Valor por periodo", r2(n(d.get("precio"))))]}


@tool("cobros", "Cobros del mes y vencimientos")
def cobros(space_id, inp):
    cs = [c for c in recs(space_id, "dd_contrato") if c["status"] in ("firmado", "enviado")]
    if not cs:
        return {"resumen": SIN_DATOS}
    hoy, filas = date.today(), []
    for c in cs:
        d, v = c["data"], _day(c["data"].get("vence"))
        pagado = _day(d.get("ultimo_pago"))
        al_dia = bool(pagado and (pagado.year, pagado.month) == (hoy.year, hoy.month))
        estado = "al día" if al_dia else "sin firmar" if c["status"] == "enviado" else "por cobrar este mes" if d.get("recurrente") else "pago único pendiente"
        if v and v < hoy:
            estado = "contrato vencido"
        filas.append([c["title"], r2(n(d.get("valor"))), "sí" if d.get("recurrente") else "no", pagado.isoformat() if pagado else "nunca", v.isoformat() if v else "", estado])
    mrr = sum(f[1] for f in filas if f[2] == "sí" and f[5] != "contrato vencido")
    pend = sum(f[1] for f in filas if "cobrar" in f[5] or "pendiente" in f[5])
    return {"resumen": "Registra cada pago en el contrato (campo «Último pago»). Doomsday lleva el control; el dinero lo mueve tu banco o pasarela.",
            "metricas": [M("Ingreso recurrente mensual", r2(mrr), "ok"), M("Por cobrar", r2(pend), "amber" if pend else "ok"), M("Sin firmar", sum(1 for f in filas if f[5] == "sin firmar"), "amber")],
            "tablas": [T("Contratos", ["Contrato", "Valor", "Recurrente", "Último pago", "Vence", "Estado"], filas)],
            "alertas": [f"{f[0]}: {f[5]}." for f in filas if f[5] in ("contrato vencido", "sin firmar")]}


@tool("reporte", "Reporte de cliente desde cifras", ["cliente:Cliente", "periodo:Periodo", "cifras:Cifras (una por línea: métrica; actual; anterior):textarea",
                                                    "hecho:Trabajo realizado (uno por línea):textarea", "siguiente:Próximos pasos (uno por línea):textarea"], auto=False)
def reporte(space_id, inp):
    filas = []
    for l in str(inp.get("cifras") or "").splitlines():
        p = [x.strip() for x in re.split(r"[;|\t]", l)]
        if len(p) >= 2 and p[0]:
            a, b = n(p[1], None), n(p[2], None) if len(p) > 2 else None
            filas.append([p[0], a, b, pct(a - b, abs(b)) if a is not None and b else None])
    if not inp.get("cliente") or not filas:
        raise ValueError("Indica el cliente y al menos una cifra con el formato «métrica; actual; anterior».")
    sube, baja = [f for f in filas if (f[3] or 0) > 0], [f for f in filas if (f[3] or 0) < 0]
    sec = [S("Resumen", f"{len(sube)} métricas mejoran y {len(baja)} empeoran frente al periodo anterior." + (f" La mayor caída es {min(baja, key=lambda f: f[3])[0]} ({min(baja, key=lambda f: f[3])[3]} %)." if baja else "")),
           S("Trabajo realizado", _lista(inp.get("hecho"))), S("Qué no funcionó", "\n".join(f"- {f[0]}: {f[3]} %. [por definir: causa y cambio]" for f in baja) or "- Ninguna métrica empeoró."),
           S("Próximos pasos", _lista(inp.get("siguiente")))]
    return {"resumen": "Variaciones calculadas con tus cifras; las causas quedan marcadas para que las completes. Guárdalo como entregable.",
            "tablas": [T("Resultados", ["Métrica", "Actual", "Anterior", "Variación %"], filas)], "secciones": sec, "titulo_doc": f"Reporte {inp.get('periodo') or ''} · {inp['cliente']}",
            "metricas": [M("Mejoran", len(sube), "ok"), M("Empeoran", len(baja), "bad" if baja else "ok")]}


@tool("casos", "Estado de la bóveda de pruebas")
def casos(space_id, inp):
    cs = recs(space_id, "dd_caso")
    if not cs:
        return {"resumen": SIN_DATOS}
    filas = [[c["title"], c["data"].get("cliente"), "sí" if c["data"].get("evidencia_url") else "FALTA", "sí" if c["data"].get("autorizado") else "FALTA",
              "utilizable" if c["data"].get("evidencia_url") and c["data"].get("autorizado") and c["status"] == "autorizado" else "no usar todavía"] for c in cs]
    return {"resumen": "Un caso solo se puede citar si tiene evidencia enlazada, autorización del cliente y estado «autorizado». Las propuestas solo usan esos.",
            "metricas": [M("Casos", len(cs)), M("Utilizables", sum(1 for f in filas if f[4] == "utilizable"), "ok"), M("Sin autorización", sum(1 for f in filas if f[3] == "FALTA"), "amber")],
            "tablas": [T("Casos", ["Caso", "Cliente", "Evidencia", "Autorización", "Uso"], filas)]}


# ---------- Listas de pasos ejecutables (P05, P10, G03, G09, V04, M08, A08)

@tool("pasos", "Listas de pasos: crear desde plantilla y ver avance", ["plantilla:Plantilla:select:" + "|".join(content.CHECKLISTS), "nombre:Para quién (tienda, cliente, persona o producto)"])
def pasos(space_id, inp):
    creado = ""
    if inp.get("plantilla") and inp.get("nombre"):
        grupo, tpl = str(inp["nombre"]).strip()[:80], content.CHECKLISTS[inp["plantilla"]]
        if any(p["data"].get("cliente") == grupo and p["data"].get("plantilla") == inp["plantilla"] for p in recs(space_id, "dd_paso")):
            raise ValueError(f"«{grupo}» ya tiene esa lista de pasos.")
        for i, (paso, resp) in enumerate(tpl, 1):
            records.create(space_id, "dd_paso", f"{i:02d}. {paso}"[:290], {"cliente": grupo, "paso": paso, "responsable": resp, "plantilla": inp["plantilla"]})
        creado = f"Creados {len(tpl)} pasos para «{grupo}». "
    ps = recs(space_id, "dd_paso")
    if not ps:
        return {"resumen": "Elige una plantilla y un nombre para crear la lista de pasos. " + SIN_DATOS}
    g = defaultdict(lambda: [0, 0, ""])
    for p in sorted(ps, key=lambda x: x["title"]):
        k = p["data"].get("cliente") or "(sin grupo)"
        g[k][0] += 1
        g[k][1] += p["status"] == "hecho"
        if p["status"] != "hecho" and not g[k][2]:
            g[k][2] = p["title"]
    filas = [[k, v[1], v[0], f"{pct(v[1], v[0])} %", v[2] or "completo"] for k, v in g.items()]
    return {"resumen": creado + "Marca cada paso como «hecho» en «Datos». El avance se calcula solo.",
            "metricas": [M("Listas", len(filas)), M("Completas", sum(1 for f in filas if f[1] == f[2]), "ok"), M("Pasos pendientes", sum(f[2] - f[1] for f in filas), "amber")],
            "tablas": [T("Avance", ["Lista", "Hechos", "Total", "Avance", "Siguiente paso"], sorted(filas, key=lambda f: f[1] / f[2]))]}


@tool("runbooks", "Runbooks y procedimientos: cobertura y vigencia")
def runbooks(space_id, inp):
    rb, sop = recs(space_id, "dd_runbook"), recs(space_id, "dd_sop")
    if not rb and not sop:
        return {"resumen": SIN_DATOS}
    hoy, filas = date.today(), []
    for r in rb:
        u = _day(r["data"].get("ultima_ejecucion"))
        filas.append([r["title"], "runbook", r["data"].get("herramienta"), len([l for l in (r["data"].get("pasos") or "").splitlines() if l.strip()]), "sí" if r["data"].get("verificacion") else "FALTA",
                      u.isoformat() if u else "nunca", "revisar" if not u or (hoy - u).days > 90 else "vigente"])
    for r in sop:
        filas.append([r["title"], "procedimiento", r["data"].get("rol"), len([l for l in (r["data"].get("pasos") or "").splitlines() if l.strip()]), "sí" if r["data"].get("prueba") else "FALTA", "", r["status"]])
    roles = Counter(r["data"].get("rol") or "(sin rol)" for r in sop)
    return {"resumen": "Un runbook sin prueba final o sin ejecutar en 90 días se marca para revisar.",
            "metricas": [M("Documentos", len(filas)), M("Sin prueba final", sum(1 for f in filas if f[4] == "FALTA"), "amber"), M("Por revisar", sum(1 for f in filas if f[6] in ("revisar", "borrador", "obsoleto")), "amber")],
            "tablas": [T("Documentos", ["Documento", "Tipo", "Herramienta o rol", "Pasos", "Prueba final", "Última ejecución", "Estado"], filas), T("Procedimientos por rol", ["Rol", "Cantidad"], roles.most_common())]}


@tool("decisiones", "Decisiones por revisar")
def decisiones(space_id, inp):
    ds = recs(space_id, "dd_decision")
    if not ds:
        return {"resumen": SIN_DATOS}
    hoy = date.today()
    venc = [[d["title"], d["data"].get("revisar"), (hoy - _day(d["data"]["revisar"])).days] for d in ds if d["status"] != "revisada" and _day(d["data"].get("revisar")) and _day(d["data"]["revisar"]) <= hoy]
    sin = [[d["title"]] for d in ds if d["status"] != "revisada" and not d["data"].get("revisar")]
    return {"metricas": [M("Decisiones", len(ds)), M("Toca revisar", len(venc), "amber" if venc else "ok"), M("Sin fecha de revisión", len(sin), "amber" if sin else "ok")],
            "tablas": [T("Toca revisar", ["Decisión", "Fecha de revisión", "Días de atraso"], sorted(venc, key=lambda f: -f[2])), T("Sin fecha de revisión", ["Decisión"], sin)]}


# ---------- Mensajes: clasificación por regla y borrador por plantilla (P03, V05, A02, A06, S03)

REGLAS_MSG = [("queja", r"\b(estafa|denuncia|pesim|horrible|devuelvan|reembolso|nunca llego|no ha llegado|enganad|mentira|demanda)"),
              ("novedad_entrega", r"\b(direccion|no estaba|ausente|reprogram|rechaz|novedad|transportadora|guia)\b"),
              ("estado_pedido", r"\b(pedido|orden|envio|cuando llega|donde esta|rastreo|seguimiento)\b"),
              ("venta", r"\b(precio|cuanto cuesta|cuanto vale|comprar|disponible|talla|color|medidas|pago contra entrega|descuento)\b"),
              ("oportunidad", r"\b(cotizacion|propuesta|presupuesto|agencia|colaboracion|contratar|servicio|reunion|llamada)\b"),
              ("administrativo", r"\b(factura|recibo|pago|renovacion|suscripcion|vencimiento|cuenta de cobro)\b"),
              ("ruido", r"\b(unsubscribe|darse de baja|newsletter|promocion|oferta exclusiva|no-reply|noreply)\b")]
PLANTILLAS_MSG = {
    "estado_pedido": "Hola{nombre}. Tu pedido {ref} está: {estado}.{extra} Cualquier cosa, escríbenos por aquí.",
    "novedad_entrega": "Hola{nombre}. Tuvimos una novedad con la entrega de tu pedido {ref}. ¿Nos confirmas la dirección y un horario en que haya alguien para recibirlo? Lo reprogramamos enseguida.",
    "venta": "Hola{nombre}. Gracias por escribir. {faq}",
}
ESTADOS_HUMANOS = {"entregado": "entregado", "en_transito": "en camino", "confirmado": "confirmado y por despachar", "pendiente": "recibido, pendiente de confirmar", "devuelto": "devuelto", "cancelado": "cancelado"}


def clasificar_mensaje(texto: str) -> str:
    t = _norm(texto)
    return next((k for k, rx in REGLAS_MSG if re.search(rx, t)), "otro")


@tool("mensajes", "Clasificar la bandeja y preparar borradores por plantilla")
def mensajes(space_id, inp):
    ms = recs(space_id, "dd_mensaje", "nuevo")
    if not ms:
        return {"resumen": "No hay mensajes nuevos en la bandeja."}
    pedidos = {str(o["data"].get("ref") or "").lstrip("#"): o for o in recs(space_id, "dd_pedido")}
    faqs = recs(space_id, "dd_conocimiento", "vigente")
    filas = []
    for m in ms:
        txt = f"{m['title']} {m['data'].get('texto') or ''}"
        clase = clasificar_mensaje(txt)
        borrador, estado = "", "nuevo"
        nombre = f" {m['data']['remitente'].split()[0]}" if m["data"].get("remitente") and "@" not in m["data"]["remitente"] else ""
        ref = next((r for r in re.findall(r"#?(\w{3,20})", txt) if r in pedidos), None)
        if clase in ("estado_pedido", "novedad_entrega") and ref:
            o = pedidos[ref]
            borrador = PLANTILLAS_MSG[clase].format(nombre=nombre, ref=f"#{ref}", estado=ESTADOS_HUMANOS.get(o["status"], o["status"]), extra="")
        elif clase == "venta" and faqs:
            q = set(_words(txt))
            best = max(faqs, key=lambda f: len(q & set(_words(_text(f)))))
            if len(q & set(_words(_text(best)))) >= 2:
                borrador = PLANTILLAS_MSG["venta"].format(nombre=nombre, faq=(best["data"].get("contenido") or "")[:500])
        if clase in ("queja", "oportunidad"):
            estado = "escalado"
        elif borrador:
            estado = "borrador_listo"
        records.update(m["id"], space_id, {"status": estado, "data": {"clasificacion": clase, **({"borrador": borrador} if borrador else {})}})
        filas.append([m["title"], m["data"].get("canal"), clase, estado.replace("_", " "), borrador[:90]])
    c = Counter(f[3] for f in filas)
    return {"resumen": "Regla fija por palabras clave. Con el número de pedido responde su estado real; las preguntas de venta usan tu base de respuestas; quejas y oportunidades se escalan a ti sin borrador.",
            "metricas": [M("Clasificados", len(filas)), M("Con borrador listo", c["borrador listo"], "ok"), M("Escalados a ti", c["escalado"], "amber" if c["escalado"] else "ok"), M("Sin plantilla", c["nuevo"])],
            "tablas": [T("Bandeja", ["Mensaje", "Canal", "Clasificación", "Estado", "Borrador"], filas)]}


# ---------- Transcripciones: reuniones y llamadas de venta

@tool("reunion", "Extraer acuerdos y tareas de una transcripción", ["transcripcion:Transcripción o notas:textarea", "titulo:Reunión"], auto=False)
def reunion(space_id, inp):
    txt = str(inp.get("transcripcion") or "")
    if len(txt) < 40:
        raise ValueError("Pega la transcripción.")
    rx = re.compile(r"\b(voy a|vamos a|me encargo|se encarga|queda en|quedamos en|hay que|tiene que|tenemos que|enviar|mandar|revisar|preparar|agendar|para el|antes del|pendiente|acordamos|decidimos)\b", re.I)
    lineas = [l.strip(" -•\t") for l in re.split(r"\n+|(?<=[.!?])\s+", txt) if l.strip()]
    acc = [l for l in lineas if rx.search(l) and 15 < len(l) < 300]
    dec = [l for l in acc if re.search(r"\b(acordamos|decidimos|queda en|quedamos en)\b", l, re.I)]
    creadas = 0
    for l in [a for a in acc if a not in dec][:25]:
        quien = re.match(r"^([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)\s*[:,]", l)
        records.create(space_id, "dd_tarea", l[:200], {"responsable": quien.group(1) if quien else None, "notas": f"De la reunión: {inp.get('titulo') or date.today().isoformat()}"})
        creadas += 1
    records.create(space_id, "dd_reunion", str(inp.get("titulo") or f"Reunión {date.today().isoformat()}")[:200],
                   {"fecha": date.today().isoformat(), "consentimiento": True, "transcripcion": txt[:30000], "tareas": "\n".join(acc[:40]), "resumen": "\n".join(dec[:10])}, status="procesada")
    return {"resumen": f"Extracción por frases de compromiso (sin IA): {creadas} tareas creadas en «Tareas» y la reunión quedó guardada. Revisa responsables y fechas.",
            "metricas": [M("Frases analizadas", len(lineas)), M("Compromisos", len(acc)), M("Decisiones", len(dec))],
            "tablas": [T("Decisiones y acuerdos", ["Texto"], [[d] for d in dec]), T("Tareas detectadas", ["Texto"], [[a] for a in acc if a not in dec][:40])]}


OBJECIONES = {"precio": r"\b(caro|costoso|precio|presupuesto|no me alcanza|descuento)\b", "tiempo": r"\b(no tengo tiempo|mas adelante|ahora no|el proximo mes|despues)\b",
              "pensarlo": r"\b(pensarlo|pensar|consultarlo|lo hablo|te aviso|dejame ver)\b", "socio": r"\b(mi socio|mi esposa|mi esposo|mi jefe|la junta)\b",
              "confianza": r"\b(garantia|y si no funciona|ya probe|me estafaron|resultados reales|casos)\b"}


@tool("llamada", "Análisis de una llamada de venta", ["transcripcion:Transcripción con «Yo:» y «Cliente:» por línea:textarea"], auto=False)
def llamada(space_id, inp):
    txt = str(inp.get("transcripcion") or "")
    turnos = re.findall(r"^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,20}):\s*(.+)$", txt, flags=re.M)
    if len(turnos) < 4:
        raise ValueError("La transcripción necesita turnos marcados, por ejemplo «Yo: …» y «Cliente: …» en líneas separadas.")
    yo = next((s for s, _ in turnos if _norm(s) in ("yo", "vendedor", "asesor", "closer")), turnos[0][0])
    pal = Counter()
    for s, t in turnos:
        pal["yo" if s == yo else "cliente"] += len(t.split())
    mias = [t for s, t in turnos if s == yo]
    preguntas = [t for t in mias if "?" in t]
    abiertas = [t for t in preguntas if re.match(r"^\W*(que|como|por que|cual|cuando|cuentame|donde)", _norm(t))]
    obj = [[k, t[:160]] for s, t in turnos if s != yo for k, rx in OBJECIONES.items() if re.search(rx, _norm(t))]
    muletillas = Counter(re.findall(r"\b(o sea|basicamente|digamos|la verdad|eh|este|como que|literal)\b", _norm(" ".join(mias))))
    ratio = pct(pal["yo"], pal["yo"] + pal["cliente"])
    mejoras = []
    if (ratio or 0) > 55:
        mejoras.append(f"Hablaste el {ratio} % del tiempo: en descubrimiento apunta a menos del 45 %.")
    if len(abiertas) < 5:
        mejoras.append(f"Solo {len(abiertas)} preguntas abiertas: prepara cinco antes de la próxima llamada.")
    if obj and not any(re.search(r"\b(entiendo|tiene sentido|cuentame mas|que te preocupa)\b", _norm(t)) for t in mias):
        mejoras.append("Ante las objeciones no hubo una frase de validación antes de responder.")
    records.create(space_id, "dd_practica", f"Llamada {date.today().isoformat()}", {"fecha": date.today().isoformat(), "tema": "llamada de venta", "transcripcion": txt[:30000], "correcciones": "\n".join(mejoras)}, status="hecha")
    return {"resumen": "Medición directa de la transcripción, sin IA. La llamada quedó guardada en «Prácticas».",
            "metricas": [M("Tú hablaste", f"{ratio} %", "bad" if (ratio or 0) > 55 else "ok"), M("Preguntas tuyas", len(preguntas)), M("Preguntas abiertas", len(abiertas), "amber" if len(abiertas) < 5 else "ok"), M("Objeciones", len(obj))],
            "tablas": [T("Objeciones del cliente", ["Tipo", "Frase"], obj), T("Muletillas", ["Muletilla", "Veces"], muletillas.most_common(8))], "alertas": mejoras}


# ---------- Código: lectura de un diff (A07, H06)

SECRETOS = [("clave o token", r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"][^'\"\s]{8,}"), ("clave privada", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            ("token de proveedor", r"\b(sk-[A-Za-z0-9]{20,}|shpat_[a-f0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16})\b")]


@tool("revision_codigo", "Revisión automática de un diff", ["diff:Diff unificado (git diff):textarea"], auto=False)
def revision_codigo(space_id, inp):
    diff = str(inp.get("diff") or "")
    if "@@" not in diff and "+++" not in diff:
        raise ValueError("Pega la salida de «git diff».")
    archivo, stats, hall, pruebas = "", defaultdict(lambda: [0, 0]), [], False
    for l in diff.splitlines():
        if l.startswith("+++ "):
            archivo = l[4:].replace("b/", "", 1)
            pruebas = pruebas or "test" in archivo.lower()
        elif l.startswith("+") and not l.startswith("+++"):
            stats[archivo][0] += 1
            code = l[1:]
            for nombre, rx in SECRETOS:
                if re.search(rx, code):
                    hall.append(["alta", nombre, archivo, code.strip()[:60] + "…"])
            for nombre, rx in (("depuración olvidada", r"\b(console\.log|print\(|debugger|pdb\.set_trace|breakpoint\(\))"), ("pendiente sin resolver", r"\b(TODO|FIXME|XXX|HACK)\b"),
                               ("excepción silenciada", r"except\s*:\s*$|except Exception:\s*pass|catch\s*\(\w*\)\s*\{\s*\}"), ("ejecución dinámica", r"\b(eval|exec)\(|shell=True|os\.system\("),
                               ("SQL armado con texto", r"(execute|query)\(\s*f?['\"].*(\+|\{|%s\s*%)")):
                if re.search(rx, code) and "test" not in archivo.lower():
                    hall.append(["media" if nombre in ("ejecución dinámica", "SQL armado con texto", "excepción silenciada") else "baja", nombre, archivo, code.strip()[:80]])
            if len(code) > 180:
                hall.append(["baja", "línea de más de 180 caracteres", archivo, code.strip()[:60] + "…"])
        elif l.startswith("-") and not l.startswith("---"):
            stats[archivo][1] += 1
    tot = sum(v[0] for v in stats.values())
    if tot > 30 and not pruebas:
        hall.insert(0, ["media", "cambio sin pruebas", "(todo el diff)", f"{tot} líneas nuevas y ningún archivo de pruebas tocado"])
    hall.sort(key=lambda h: ["alta", "media", "baja"].index(h[0]))
    return {"resumen": "Revisión por patrones (sin IA): secretos, depuración, excepciones silenciadas, ejecución dinámica y falta de pruebas. La revisión de lógica la hace la skill.",
            "metricas": [M("Archivos", len(stats)), M("Líneas añadidas", tot), M("Líneas quitadas", sum(v[1] for v in stats.values())), M("Hallazgos graves", sum(1 for h in hall if h[0] == "alta"), "bad" if any(h[0] == "alta" for h in hall) else "ok")],
            "tablas": [T("Hallazgos", ["Gravedad", "Regla", "Archivo", "Línea"], hall[:80]), T("Archivos", ["Archivo", "Añadidas", "Quitadas"], [[k, v[0], v[1]] for k, v in stats.items()])],
            "alertas": ["Hay un posible secreto en el cambio: no lo subas."] if any(h[0] == "alta" for h in hall) else []}


# ---------- Diseño, paquetes y exportaciones

def _lum(hexc: str) -> float | None:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (hexc or "").strip())
    if not m:
        return None
    ch = [int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


@tool("tokens_css", "Tokens a CSS y contraste", ["marca:Marca"])
def tokens_css(space_id, inp):
    toks = [t for t in recs(space_id, "dd_token", "vigente") if not inp.get("marca") or _norm(t["data"].get("marca")) == _norm(inp["marca"])]
    if not toks:
        return {"resumen": SIN_DATOS}
    css = ":root {\n" + "\n".join(f"  --{re.sub(r'[^a-z0-9]+', '-', _norm(t['title'])).strip('-')}: {t['data'].get('valor')};" + (f"  /* {t['data']['uso']} */" if t["data"].get("uso") else "") for t in toks) + "\n}"
    col = [(t["title"], t["data"].get("valor")) for t in toks if t["data"].get("tipo") == "color" and _lum(t["data"].get("valor") or "") is not None]
    fondos = [c for c in col if re.search(r"fondo|superficie|ground|background|base", _norm(c[0]))] or col[:1]
    filas = []
    for nom, val in col:
        for fn, fv in fondos:
            if nom != fn:
                a, b = sorted((_lum(val), _lum(fv)), reverse=True)
                ratio = (a + 0.05) / (b + 0.05)
                filas.append([nom, fn, r2(ratio), "AA texto" if ratio >= 4.5 else "solo texto grande o bordes" if ratio >= 3 else "NO cumple"])
    return {"resumen": "Variables CSS listas para pegar en tu tema y contraste WCAG de cada color sobre tus fondos.",
            "texto": css, "metricas": [M("Tokens", len(toks)), M("Pares que no cumplen", sum(1 for f in filas if f[3] == "NO cumple"), "bad" if any(f[3] == "NO cumple" for f in filas) else "ok")],
            "tablas": [T("Contraste", ["Color", "Sobre", "Relación", "Resultado"], sorted(filas, key=lambda f: f[2]))]}


def _zip_file(space_id: str, name: str, entries: dict[str, str]) -> dict:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, text in entries.items():
            z.writestr(path, text)
    return files.save_bytes(space_id, name, buf.getvalue(), origin="job", meta={"paquete": True})


@tool("paquete_skills", "Empaquetar skills en un .zip", ["skills:Códigos de módulo (ej. G04, M06, X07)", "nombre:Nombre del paquete", "licencia:Licencia de uso:textarea"], auto=False)
def paquete_skills(space_id, inp):
    ids = [i for i in re.findall(r"[A-Z]\d\d", str(inp.get("skills") or "").upper()) if i in catalog.MODULES]
    if not ids:
        raise ValueError("Indica al menos un código de módulo válido, por ejemplo G04.")
    nombre = re.sub(r"[^\w\- ]+", "", str(inp.get("nombre") or "paquete-skills"))[:50].strip() or "paquete-skills"
    ent = {"LEEME.md": f"# {nombre}\n\nSkills incluidas:\n" + "\n".join(f"- {i} · {catalog.MODULES[i]['nombre']}: {catalog.MODULES[i]['solucion']}" for i in ids) +
           "\n\n## Cómo usarlas\nCada archivo es una skill: rol, método, estándar y prohibiciones. Impórtalas en Doomsday (Skills → Importar) o pégalas como instrucciones del sistema en tu asistente.\n",
           "LICENCIA.md": str(inp.get("licencia") or "Uso interno del comprador. No se permite la reventa ni la redistribución.")}
    for i in ids:
        s = skills.get(i)
        ent[f"skills/{i}.md"] = f"## {i} · {catalog.MODULES[i]['nombre']}\n{s['texto']}\n"
    f = _zip_file(space_id, f"{nombre}.zip", ent)
    propias = sum(1 for i in ids if skills.get(i)["origen"] == "propia")
    return {"resumen": f"Paquete creado en los archivos del espacio: {f['name']} ({len(ids)} skills, {propias} tuyas). Descárgalo desde el enlace.",
            "archivo": {"id": f["id"], "name": f["name"]}, "metricas": [M("Skills", len(ids)), M("Con tu versión", propias)],
            "alertas": [] if propias == len(ids) else ["Algunas skills son las integradas, no tu versión probada: vende solo lo que usas."]}


@tool("tema", "Secciones del tema Shopify listas para instalar", ["secciones:Secciones (vacío = todas)"])
def tema(space_id, inp):
    pedidas = [s for s in content.SECTIONS if not inp.get("secciones") or s in str(inp["secciones"])]
    filas = [[k, v["nombre"], v["reemplaza"], len(v["liquid"].splitlines())] for k, v in content.SECTIONS.items()]
    out = {"resumen": "Secciones Liquid autocontenidas (Online Store 2.0), sin apps ni librerías. Se instalan copiándolas a la carpeta «sections» de tu tema o con la subida de abajo. No sustituyen a un tema completo: se añaden al tuyo.",
           "metricas": [M("Secciones", len(content.SECTIONS))], "tablas": [T("Secciones incluidas", ["Archivo", "Sección", "App que reemplaza", "Líneas"], filas)]}
    if inp.get("_descargar"):
        f = _zip_file(space_id, "doomsday-secciones-tema.zip", {**{f"sections/{k}.liquid": content.SECTIONS[k]["liquid"] for k in pedidas}, "LEEME.md": content.THEME_README})
        out["archivo"] = {"id": f["id"], "name": f["name"]}
    return out


@tool("validacion", "Semáforo de validación con pago anticipado", ["meta:Pagos anticipados necesarios:number"])
def validacion(space_id, inp):
    apps = recs(space_id, "dd_aplicacion")
    meta = int(n(inp.get("meta"), 10))
    pagos = [a for a in apps if a["status"] == "cerrada"]
    return {"resumen": f"Regla del plan: sin {meta} pagos anticipados no se construye. Registra cada interesado como aplicación y márcala «cerrada» solo cuando pague.",
            "metricas": [M("Interesados", len(apps)), M("Pagos anticipados", len(pagos), "ok" if len(pagos) >= meta else "amber"), M("Decisión", "construir" if len(pagos) >= meta else "no construir todavía", "ok" if len(pagos) >= meta else "bad")],
            "tablas": [T("Interesados", ["Interesado", "Estado", "Origen"], [[a["title"], a["status"], a["data"].get("origen")] for a in apps[:100]])]}


def brand_html(d: dict, toks: list[dict], marca: str) -> str:
    import html as H
    col = {re.sub(r"[^a-z]+", "", _norm(t["title"])): t["data"].get("valor") for t in toks if t["data"].get("tipo") == "color"}
    fondo, tinta, acento = col.get("fondo") or "#ffffff", col.get("tinta") or col.get("texto") or "#16181d", col.get("acento") or col.get("primario") or "#2b5cff"
    fuente = next((t["data"].get("valor") for t in toks if t["data"].get("tipo") == "tipografia"), "system-ui, sans-serif")
    body = [f"<header><p class='m'>{H.escape(marca)}</p><h1>{H.escape(d['title'])}</h1></header>"]
    for s in d["version"]["content"]["sections"]:
        if s["key"] in ("comprobaciones", "supuestos", "preguntas", "cumplimiento"):
            continue
        body.append(f"<h2>{H.escape(s['title'])}</h2>")
        if s["type"] == "table":
            body.append("<table><tr>" + "".join(f"<th>{H.escape(str(c))}</th>" for c in s["columns"]) + "</tr>" +
                        "".join("<tr>" + "".join(f"<td>{H.escape('' if c is None else str(c))}</td>" for c in r) + "</tr>" for r in s["rows"]) + "</table>")
        elif s["type"] == "list":
            body.append("<ul>" + "".join(f"<li>{H.escape(str(i))}</li>" for i in s["items"]) + "</ul>")
        else:
            body.append("".join(f"<p>{H.escape(l)}</p>" for l in s["body"].splitlines() if l.strip()))
    css = (f"body{{margin:0;background:{fondo};color:{tinta};font-family:{fuente};line-height:1.6}}main{{max-width:820px;margin:0 auto;padding:48px 24px}}"
           f"h1{{font-size:30px;margin:4px 0 32px}}h2{{font-size:17px;margin:32px 0 8px;color:{acento}}}.m{{letter-spacing:.14em;text-transform:uppercase;font-size:12px;margin:0;color:{acento}}}"
           f"table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid {tinta}22}}@media print{{main{{padding:0}}}}")
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{H.escape(d['title'])}</title><style>{css}</style></head><body><main>{''.join(body)}</main></body></html>"


@tool("reporte_marca", "Exportar un entregable con la marca del cliente", ["entregable:ID del entregable", "marca:Marca (tokens del sistema de diseño)"], auto=False)
def reporte_marca(space_id, inp):
    d = review.detail(str(inp.get("entregable") or ""), space_id)
    if not d:
        raise ValueError("Indica el ID de un entregable de este espacio (lo ves en Entregables).")
    marca = str(inp.get("marca") or "").strip()
    toks = [t for s in db.query("SELECT id FROM spaces WHERE archived=0") for t in recs(s["id"], "dd_token", "vigente") if marca and _norm(t["data"].get("marca")) == _norm(marca)]
    f = files.save_bytes(space_id, f"{re.sub(r'[^\w\- ]+', '', d['title'])[:60].strip() or 'reporte'}.html", brand_html(d, toks, marca or "").encode(), origin="job", meta={"marca": marca})
    return {"resumen": f"HTML autocontenido con {'los colores y tipografía de «' + marca + '»' if toks else 'estilo neutro (no hay tokens de esa marca en X04)'}. Ábrelo e imprímelo a PDF desde el navegador.",
            "archivo": {"id": f["id"], "name": f["name"]}, "metricas": [M("Tokens de marca aplicados", len(toks))]}


# ---------- Personal: estudio, lectura, comidas, inglés, viaje

@tool("plan_estudio", "Calendario de estudio con repasos", ["materia:Materia", "fecha:Fecha del examen:date", "temas:Temas (uno por línea, el más débil primero):textarea"], auto=False)
def plan_estudio(space_id, inp):
    temas, fin = [t.strip(" -•") for t in str(inp.get("temas") or "").splitlines() if t.strip()], _day(inp.get("fecha"))
    dias = (fin - date.today()).days if fin else 0
    if not temas or dias < 2:
        raise ValueError("Indica los temas y una fecha de examen al menos dos días adelante.")
    nuevos = max(1, dias - max(2, dias // 5))  # los últimos días son solo repaso y simulacro
    plan = defaultdict(list)
    for i, t in enumerate(temas):
        d0 = date.today() + timedelta(days=int(i * nuevos / len(temas)))
        plan[d0].append(f"Estudiar: {t}")
        for gap in (1, 3, 7, 14):
            if d0 + timedelta(days=gap) < fin:
                plan[d0 + timedelta(days=gap)].append(f"Repasar: {t}")
    for k in range(1, max(2, dias // 5) + 1):
        plan[fin - timedelta(days=k)].append("Simulacro cronometrado y revisión de errores")
    filas = [[d.isoformat(), "; ".join(v)] for d, v in sorted(plan.items()) if d >= date.today()]
    for d, v in filas:
        records.create(space_id, "dd_bloque", f"{inp.get('materia') or 'Estudio'} · {d}", {"dia": d, "tipo": "profundo", "notas": v[:900]})
    records.create(space_id, "dd_examen", str(inp.get("materia") or "Examen"), {"materia": inp.get("materia"), "fecha_examen": fin.isoformat(), "temas": "\n".join(temas)})
    return {"resumen": f"Cada tema se estudia una vez y se repasa a 1, 3, 7 y 14 días; el tramo final es simulacro. {len(filas)} bloques creados en «Bloques de agenda».",
            "metricas": [M("Días", dias), M("Temas", len(temas)), M("Bloques", len(filas))], "tablas": [T("Calendario", ["Día", "Qué hacer"], filas)]}


@tool("lectura", "Plan de lectura y constancia", ["pasajes:Pasajes o capítulos (uno por línea):textarea", "inicio:Empezar el:date"])
def lectura(space_id, inp):
    creado = ""
    pas = [p.strip(" -•") for p in str(inp.get("pasajes") or "").splitlines() if p.strip()]
    if pas:
        d0 = _day(inp.get("inicio")) or date.today()
        for i, p in enumerate(pas[:400]):
            records.create(space_id, "dd_lectura", p[:200], {"fecha": (d0 + timedelta(days=i)).isoformat(), "pasaje": p}, status="planificado")
        creado = f"Plan creado: {len(pas)} días desde el {d0.isoformat()}. "
    ls = recs(space_id, "dd_lectura")
    if not ls:
        return {"resumen": "Escribe los pasajes (uno por día) para crear el plan. " + SIN_DATOS}
    hechos = {_day(l["data"].get("fecha")) for l in ls if l["status"] == "hecho"}
    racha, d = 0, date.today() if date.today() in hechos else date.today() - timedelta(days=1)
    while d in hechos:
        racha, d = racha + 1, d - timedelta(days=1)
    hoy = [[l["data"].get("pasaje") or l["title"], l["data"].get("fecha")] for l in ls if l["status"] == "planificado" and (_day(l["data"].get("fecha")) or date.max) <= date.today()]
    return {"resumen": creado + "Marca cada lectura como «hecho» y escribe tu reflexión en «Datos».",
            "metricas": [M("Racha", f"{racha} días", "ok" if racha else None), M("Leídos", len(hechos)), M("Pendientes hasta hoy", len(hoy), "amber" if hoy else "ok")],
            "tablas": [T("Toca leer", ["Pasaje", "Fecha"], sorted(hoy, key=lambda f: f[1] or "")[:20])]}


@tool("comidas", "Totales del plan y lista de mercado")
def comidas(space_id, inp):
    cs = recs(space_id, "dd_comida")
    if not cs:
        return {"resumen": SIN_DATOS}
    dia, lista = defaultdict(lambda: [0.0, 0.0, 0]), Counter()
    for c in cs:
        k = c["data"].get("dia") or "(sin día)"
        dia[k][0] += n(c["data"].get("calorias"))
        dia[k][1] += n(c["data"].get("proteina"))
        dia[k][2] += 1
        for ing in re.split(r"[,\n;]", c["data"].get("ingredientes") or ""):
            if ing.strip():
                lista[ing.strip().lower()] += 1
    return {"resumen": "Suma de lo que registraste por día y lista consolidada de los ingredientes de cada plato.",
            "metricas": [M("Comidas", len(cs)), M("Calorías medias por día", r2(sum(v[0] for v in dia.values()) / len(dia))), M("Proteína media por día", r2(sum(v[1] for v in dia.values()) / len(dia)))],
            "tablas": [T("Por día", ["Día", "Calorías", "Proteína (g)", "Comidas"], [[k, r2(v[0]), r2(v[1]), v[2]] for k, v in dia.items()]),
                       T("Lista de mercado", ["Ingrediente", "Veces en la semana"], lista.most_common(80))]}


@tool("ingles", "Banco de frases de venta en inglés", ["tema:Situación:select:" + "|".join(content.FRASES_EN)])
def ingles(space_id, inp):
    creadas = 0
    if inp.get("tema"):
        ya = {c["title"] for c in recs(space_id, "flashcard")}
        for es, en in content.FRASES_EN[inp["tema"]]:
            if es not in ya:
                records.create(space_id, "flashcard", es, {"deck": f"Inglés de ventas · {inp['tema']}", "back": en})
                creadas += 1
    pr = recs(space_id, "dd_practica")
    return {"resumen": (f"{creadas} tarjetas nuevas en el repaso espaciado (mazo «Inglés de ventas · {inp['tema']}»). " if inp.get("tema") else "Elige una situación para cargar sus frases como tarjetas. ")
            + "Practícalas en H05 Repaso espaciado.",
            "metricas": [M("Situaciones disponibles", len(content.FRASES_EN)), M("Frases en total", sum(len(v) for v in content.FRASES_EN.values())), M("Prácticas registradas", len(pr))],
            "tablas": [T("Frases de la situación", ["Español", "Inglés"], [list(p) for p in content.FRASES_EN.get(inp.get("tema") or "", [])])]}


@tool("viaje", "Esqueleto de itinerario y lista de tomas", ["destino:Destino", "inicio:Inicio:date", "fin:Fin:date"], auto=False)
def viaje(space_id, inp):
    a, b = _day(inp.get("inicio")), _day(inp.get("fin"))
    if not inp.get("destino") or not a or not b or b < a or (b - a).days > 60:
        raise ValueError("Indica destino y fechas válidas (hasta 60 días).")
    dias = [(a + timedelta(days=i)) for i in range((b - a).days + 1)]
    iti = "\n".join(f"{d.isoformat()} · {'Llegada: ' if i == 0 else 'Regreso: ' if i == len(dias) - 1 else ''}[lugar] · mañana [toma] · hora dorada [toma] · noche [nota de voz del día]" for i, d in enumerate(dias))
    records.create(space_id, "dd_viaje", str(inp["destino"])[:200], {"destino": inp["destino"], "inicio": a.isoformat(), "fin": b.isoformat(), "itinerario": iti, "tomas": "\n".join(content.TOMAS_VIAJE)})
    return {"resumen": f"Viaje creado en «Datos» con {len(dias)} días y la lista base de tomas. Completa los lugares; la skill R09 lo convierte en historia.",
            "metricas": [M("Días", len(dias)), M("Faltan", f"{(a - date.today()).days} días")], "tablas": [T("Tomas base", ["Toma"], [[t] for t in content.TOMAS_VIAJE])]}


@tool("lanzamientos", "Tablero de lanzamientos")
def lanzamientos(space_id, inp):
    ls = recs(space_id, "dd_lanzamiento")
    if not ls:
        return {"resumen": SIN_DATOS}
    etapas = records.KINDS["dd_lanzamiento"]["statuses"]
    filas = [[l["title"], l["status"], f"{etapas.index(l['status']) + 1} de {len(etapas)}", (date.today() - date.fromisoformat(l["updated_at"][:10])).days,
              {"investigacion": "A05", "pagina": "G04", "creativos": "M06", "cumplimiento": "X07", "publicacion": "M02", "medicion": "G02"}.get(l["status"], "")] for l in ls]
    return {"resumen": "Cada etapa se hace en su módulo y exige tu aprobación antes de pasar a la siguiente.",
            "metricas": [M("Lanzamientos", len(ls)), M("Estancados más de 7 días", sum(1 for f in filas if f[3] > 7 and f[1] != "cerrado"), "amber")],
            "tablas": [T("Lanzamientos", ["Lanzamiento", "Etapa", "Avance", "Días en la etapa", "Módulo de la etapa"], filas)]}


@tool("prospectos", "Embudo de prospección")
def prospectos(space_id, inp):
    ps = recs(space_id, "dd_prospecto")
    if not ps:
        return {"resumen": SIN_DATOS}
    c = Counter(p["status"] for p in ps)
    env = c["enviado"] + c["respondio"]
    return {"resumen": "Ningún mensaje sale solo: cada borrador se revisa y se envía a mano o con aprobación.",
            "metricas": [M("Prospectos", len(ps)), M("Borradores por revisar", c["borrador_listo"], "amber" if c["borrador_listo"] else "ok"), M("Enviados", env), M("Tasa de respuesta", f"{pct(c['respondio'], env)} %" if env else "sin envíos")],
            "tablas": [T("Por etapa", ["Etapa", "Cantidad"], c.most_common())]}


@tool("comunidad", "Estructura de la comunidad")
def comunidad(space_id, inp):
    cs = recs(space_id, "dd_comunidad")
    if not cs:
        return {"resumen": SIN_DATOS}
    c = Counter(x["data"].get("tipo") or "otro" for x in cs)
    return {"resumen": "Lo marcado como «activo» es lo que se aplica al servidor de Discord con el panel de abajo.",
            "metricas": [M("Elementos", len(cs)), M("Canales", c["canal"]), M("Roles", c["rol"]), M("Activos", sum(1 for x in cs if x["status"] == "activo"), "ok")],
            "tablas": [T("Elementos", ["Elemento", "Tipo", "Estado"], [[x["title"], x["data"].get("tipo"), x["status"]] for x in cs])]}
