"""Herramientas deterministas de Doomsday: calculan con los registros del espacio, sin IA y sin inventar datos.

Cada herramienta devuelve {resumen, metricas, tablas, alertas}. Si faltan datos lo dice: nunca rellena con ejemplos.
Las acciones de los módulos pueden adjuntar este resultado al modelo como evidencia para que lo interprete.
"""
from __future__ import annotations
import json
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from jarvis import db, records, router, security, webfetch

from .kinds import field

TOOLS: dict[str, dict] = {}


def tool(id_: str, label: str, campos: list[str] | None = None, auto: bool = True):
    """auto=True: puede ejecutarse solo con los registros (sin entradas obligatorias)."""
    def deco(fn):
        TOOLS[id_] = {"id": id_, "label": label, "campos": [field(c) for c in (campos or [])], "auto": auto, "fn": fn}
        return fn
    return deco


def run(tool_id: str, space_id: str, inputs: dict | None = None) -> dict:
    if tool_id not in TOOLS:
        raise KeyError(tool_id)
    out = TOOLS[tool_id]["fn"](space_id, inputs or {})
    return {"herramienta": tool_id, "titulo": TOOLS[tool_id]["label"], "resumen": "", "metricas": [], "tablas": [], "alertas": [], **out}


# Herramientas que cambian registros al ejecutarse: nunca se lanzan solas (ni al abrir el panel ni como evidencia de una orden libre).
ESCRIBEN = {"embudo", "churn", "utm", "salud_tienda", "mensajes", "radar", "vigia", "extracto", "contrato", "reunion", "llamada", "plan_estudio", "viaje", "paquete_skills", "reporte_marca"}


def public() -> list[dict]:
    return [{**{k: v for k, v in t.items() if k != "fn"}, "escribe": t["id"] in ESCRIBEN or bool(t["campos"]) and t["id"] in ("pasos", "lectura", "ingles")} for t in TOOLS.values()]


# ---------- utilidades

def recs(space_id: str, kind: str, status: str | None = None) -> list[dict]:
    return records.list_records(space_id, kind, status=status, limit=5000)


def n(v, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else default
    except ValueError:
        return default


def r2(v: float) -> float:
    return round(v, 2)


def pct(a: float, b: float) -> float | None:
    return round(100 * a / b, 1) if b else None


def _day(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _in_range(rec: dict, inp: dict, key: str = "fecha") -> bool:
    d = _day(rec["data"].get(key))
    lo, hi = _day(inp.get("desde")), _day(inp.get("hasta"))
    return not ((lo and (not d or d < lo)) or (hi and (not d or d > hi)))


def M(label, valor, tono=None) -> dict:
    return {"label": label, "valor": valor, "tono": tono}


def T(titulo, columnas, filas) -> dict:
    return {"titulo": titulo, "columnas": columnas, "filas": filas}


SIN_DATOS = "Aún no hay datos cargados para este cálculo. Importa o registra los datos en la pestaña «Datos»; no se muestran cifras de ejemplo."


# ---------- G02 · utilidad real COD (también G01, P07, A01)

def _utilidad(space_id: str, inp: dict) -> dict:
    """Agrega pedidos y gasto de pauta. La utilidad de un pedido solo se realiza si se entrega; un devuelto cuesta flete de ida y de vuelta."""
    orders = [o for o in recs(space_id, "dd_pedido") if _in_range(o, inp)]
    spend = [s for s in recs(space_id, "dd_gasto_pauta") if _in_range(s, inp)]
    by: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    camp: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    city: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    sin_costo = 0
    for o in orders:
        d, st = o["data"], o["status"]
        if st == "cancelado":
            continue
        keys = [(by, d.get("producto") or "(sin producto)"), (camp, d.get("campana") or "(sin campaña)"), (city, d.get("ciudad") or "(sin ciudad)")]
        u = n(d.get("unidades"), 1) or 1
        if st == "entregado" and not n(d.get("costo_producto")):
            sin_costo += 1
        for bucket, k in keys:
            b = bucket[k]
            b["pedidos"] += 1
            if st == "entregado":
                b["entregados"] += 1
                b["ingreso"] += n(d.get("precio"))
                b["costo"] += n(d.get("costo_producto")) * u + n(d.get("flete")) + n(d.get("comision"))
            elif st == "devuelto":
                b["devueltos"] += 1
                b["costo"] += n(d.get("flete")) + n(d.get("flete_devolucion"))
            else:
                b["abiertos"] += 1
    for s in spend:
        d = s["data"]
        by[d.get("producto") or "(sin producto)"]["pauta"] += n(d.get("gasto"))
        camp[d.get("campana") or "(sin campaña)"]["pauta"] += n(d.get("gasto"))

    def rows(bucket):
        out = []
        for k, b in bucket.items():
            cerrados = b["entregados"] + b["devueltos"]
            util = b["ingreso"] - b["costo"] - b["pauta"]
            out.append([k, int(b["pedidos"]), int(b["entregados"]), int(b["devueltos"]), pct(b["entregados"], cerrados), r2(b["ingreso"]), r2(b["costo"]), r2(b["pauta"]),
                        r2(util), pct(util, b["ingreso"]), r2(b["pauta"] / b["entregados"]) if b["entregados"] else None])
        return sorted(out, key=lambda r: r[8])
    return {"orders": orders, "spend": spend, "productos": rows(by), "campanas": rows(camp), "ciudades": rows(city), "sin_costo": sin_costo}


COLS_UTIL = ["", "Pedidos", "Entregados", "Devueltos", "% entrega", "Ingreso", "Costos", "Pauta", "Utilidad neta", "% margen", "CPA real"]


@tool("utilidad_cod", "Utilidad neta COD por producto, campaña y ciudad", ["desde:Desde:date", "hasta:Hasta:date"])
def utilidad_cod(space_id, inp):
    u = _utilidad(space_id, inp)
    if not u["orders"] and not u["spend"]:
        return {"resumen": SIN_DATOS}
    tot = [sum(r[i] or 0 for r in u["productos"]) for i in range(1, 9)]
    cerrados = tot[1] + tot[2]
    alertas = [f"«{r[0]}» pierde {abs(r[8]):,.0f} en el periodo con {r[2]} entregados: revisar antes de seguir pautando." for r in u["productos"] if r[8] < 0 and (r[2] + r[3]) >= 5]
    if u["sin_costo"]:
        alertas.append(f"{u['sin_costo']} {'pedido entregado no tiene' if u['sin_costo'] == 1 else 'pedidos entregados no tienen'} costo de producto: la utilidad está sobrestimada.")
    abiertos = sum(1 for o in u["orders"] if o["status"] in ("en_transito", "confirmado", "pendiente"))
    if abiertos:
        alertas.append(f"{abiertos} pedidos siguen abiertos (sin entrega ni devolución): la utilidad del periodo aún no es definitiva.")
    return {"resumen": "Utilidad neta = ingreso de pedidos entregados − costo de producto − fletes (incluida la devolución) − comisiones − pauta. Los pedidos abiertos no suman ingreso.",
            "metricas": [M("Utilidad neta", r2(tot[7]), "bad" if tot[7] < 0 else "ok"), M("Ingreso entregado", r2(tot[4])), M("Pauta", r2(tot[6])),
                         M("Tasa de entrega", f"{pct(tot[1], cerrados)} %" if cerrados else "sin pedidos cerrados"), M("Pedidos", int(tot[0]))],
            "tablas": [T("Por producto", ["Producto", *COLS_UTIL[1:]], u["productos"]), T("Por campaña", ["Campaña", *COLS_UTIL[1:]], u["campanas"]),
                       T("Por ciudad", ["Ciudad", *COLS_UTIL[1:]], [r for r in u["ciudades"] if r[1] >= 3][:40])],
            "alertas": alertas}


@tool("equilibrio", "Punto de equilibrio COD: CPA y ROAS", ["precio:Precio de venta:number", "costo:Costo del producto:number", "flete:Flete de ida:number",
                                                           "flete_devolucion:Flete de devolución:number", "entrega:Tasa de entrega (%):number", "comision:Comisión por pedido:number"], auto=False)
def equilibrio(space_id, inp):
    precio, costo, flete, fdev, com = (n(inp.get(k)) for k in ("precio", "costo", "flete", "flete_devolucion", "comision"))
    e = n(inp.get("entrega"), 100) / 100
    if precio <= 0 or not 0 < e <= 1:
        raise ValueError("Indica el precio de venta y una tasa de entrega entre 1 y 100.")
    # Por pedido despachado: se cobra solo lo entregado; lo devuelto cuesta dos fletes.
    margen = e * (precio - costo - flete - com) - (1 - e) * (flete + fdev)
    alertas = ["Con estos números cada pedido despachado pierde dinero antes de pagar pauta."] if margen <= 0 else []
    return {"resumen": "Margen esperado por pedido despachado antes de pauta. El CPA de equilibrio es el máximo que puedes pagar por pedido sin perder.",
            "metricas": [M("Margen por pedido despachado", r2(margen), "bad" if margen <= 0 else "ok"), M("CPA de equilibrio", r2(max(margen, 0))),
                         M("ROAS de equilibrio (sobre venta generada)", r2(precio / margen) if margen > 0 else "no alcanzable"),
                         M("Margen si todo se entregara", r2(precio - costo - flete - com))], "alertas": alertas}


@tool("oferta", "Calculadora de ofertas y packs", ["precio:Precio unitario:number", "costo:Costo unitario:number", "flete:Flete por pedido:number",
                                                  "entrega:Tasa de entrega (%):number", "cpa:CPA esperado:number", "packs:Packs a comparar (ej. 1,2,3)", "descuento:Descuento por unidad adicional (%):number"], auto=False)
def oferta(space_id, inp):
    precio, costo, flete, cpa = (n(inp.get(k)) for k in ("precio", "costo", "flete", "cpa"))
    e, desc = n(inp.get("entrega"), 100) / 100, n(inp.get("descuento")) / 100
    if precio <= 0:
        raise ValueError("Indica el precio unitario.")
    filas = []
    for q in [int(x) for x in re.findall(r"\d+", str(inp.get("packs") or "1,2,3"))][:8] or [1, 2, 3]:
        pvp = precio + precio * (1 - desc) * (q - 1)
        margen = e * (pvp - costo * q - flete) - (1 - e) * 2 * flete - cpa
        filas.append([f"{q} unidad{'es' if q > 1 else ''}", r2(pvp), r2(pvp / q), r2(costo * q), r2(margen), pct(margen, pvp)])
    mejor = max(filas, key=lambda f: f[4])
    return {"resumen": f"Margen neto esperado por pedido despachado, con la tasa de entrega y el CPA indicados. El mayor margen es «{mejor[0]}».",
            "tablas": [T("Comparación de packs", ["Pack", "Precio", "Precio por unidad", "Costo", "Margen neto por pedido", "% margen"], filas)],
            "alertas": [f"«{f[0]}» deja margen negativo." for f in filas if f[4] < 0]}


@tool("escenarios", "Simulador de tres escenarios", ["inversion:Inversión inicial:number", "ingreso_mensual:Ingreso mensual esperado:number", "costo_mensual:Costo mensual:number",
                                                    "meses:Horizonte (meses):number", "variacion:Variación entre escenarios (%):number"], auto=False)
def escenarios(space_id, inp):
    inv, ing, cost = n(inp.get("inversion")), n(inp.get("ingreso_mensual")), n(inp.get("costo_mensual"))
    meses, var = int(n(inp.get("meses"), 12) or 12), n(inp.get("variacion"), 30) / 100
    if ing <= 0:
        raise ValueError("Indica el ingreso mensual esperado.")
    filas = []
    for nombre, f in (("Pesimista", 1 - var), ("Base", 1.0), ("Optimista", 1 + var)):
        neto = ing * f - cost
        filas.append([nombre, r2(ing * f), r2(neto), r2(neto * meses - inv), f"{inv / neto:.1f} meses" if neto > 0 else "nunca"])
    return {"resumen": "Los escenarios varían solo el ingreso; los costos se mantienen. El punto de equilibrio es el mes en que se recupera la inversión.",
            "tablas": [T("Escenarios", ["Escenario", "Ingreso mensual", "Neto mensual", f"Resultado a {meses} meses", "Recupera la inversión en"], filas)],
            "alertas": ["En el escenario pesimista la inversión no se recupera."] if filas[0][2] <= 0 else []}


# ---------- G08 · conciliación de recaudo

@tool("conciliacion_cod", "Conciliación de recaudo contra liquidaciones")
def conciliacion_cod(space_id, inp):
    orders, liqs = recs(space_id, "dd_pedido", "entregado"), recs(space_id, "dd_liquidacion")
    if not orders and not liqs:
        return {"resumen": SIN_DATOS}
    liq = defaultdict(float)
    for l in liqs:
        liq[str(l["data"].get("ref_pedido") or "").strip()] += n(l["data"].get("valor_liquidado"))
    difs, falta, tot_esp, tot_liq = [], [], 0.0, 0.0
    for o in orders:
        ref, esperado = str(o["data"].get("ref") or o["title"]).strip(), n(o["data"].get("precio")) - n(o["data"].get("flete")) - n(o["data"].get("comision"))
        tot_esp += esperado
        if ref not in liq:
            falta.append([ref, o["data"].get("fecha"), r2(esperado)])
            continue
        tot_liq += liq[ref]
        if abs(liq[ref] - esperado) > 1:
            difs.append([ref, o["data"].get("fecha"), r2(esperado), r2(liq[ref]), r2(liq[ref] - esperado)])
    refs = {str(o["data"].get("ref") or o["title"]).strip() for o in orders}
    huerfanas = [[k, r2(v)] for k, v in liq.items() if k not in refs]
    return {"resumen": "Esperado por pedido entregado = precio − flete − comisión. Se compara con lo liquidado para el mismo ID de pedido.",
            "metricas": [M("Esperado", r2(tot_esp)), M("Liquidado", r2(tot_liq)), M("Sin liquidar", r2(sum(f[2] for f in falta)), "amber" if falta else "ok"),
                         M("Diferencia en liquidados", r2(sum(d[4] for d in difs)), "bad" if difs else "ok")],
            "tablas": [T("Entregados sin liquidación", ["Pedido", "Fecha", "Esperado"], falta[:200]),
                       T("Liquidados con diferencia", ["Pedido", "Fecha", "Esperado", "Liquidado", "Diferencia"], difs[:200]),
                       T("Liquidaciones sin pedido entregado", ["Pedido", "Liquidado"], huerfanas[:100])],
            "alertas": [f"{len(falta)} pedidos entregados no aparecen en ninguna liquidación."] if falta else []}


# ---------- M01 · guardián de pauta

@tool("guardian_pauta", "Evaluación de reglas de pauta", ["dias:Ventana (días):number"])
def guardian_pauta(space_id, inp):
    reglas, dias = recs(space_id, "dd_regla_pauta", "activa"), int(n(inp.get("dias"), 3) or 3)
    desde = (date.today() - timedelta(days=dias)).isoformat()
    spend = [s for s in recs(space_id, "dd_gasto_pauta") if (s["data"].get("fecha") or "") >= desde]
    if not spend:
        return {"resumen": f"No hay gasto de pauta registrado en los últimos {dias} días. " + SIN_DATOS}
    agg: dict = defaultdict(lambda: defaultdict(float))
    for s in spend:
        d = s["data"]
        k = (d.get("plataforma") or "", d.get("producto") or "", d.get("campana") or "(sin campaña)")
        agg[k]["gasto"] += n(d.get("gasto"))
        agg[k]["compras"] += n(d.get("compras"))
        agg[k]["ref"] = d.get("ref_campana") or agg[k].get("ref") or ""
    filas, props = [], []
    for (plat, prod, campana), a in agg.items():
        cpa = a["gasto"] / a["compras"] if a["compras"] else None
        regla = next((r for r in reglas if r["data"].get("plataforma") in (plat, "todas", None, "") and (not r["data"].get("producto") or r["data"]["producto"] == prod)), None)
        veredicto = "sin regla"
        if regla:
            lim, minimo, accion = n(regla["data"].get("cpa_limite")), n(regla["data"].get("gasto_minimo")), regla["data"].get("accion") or "avisar"
            if a["gasto"] < minimo:
                veredicto = "en aprendizaje (bajo el gasto mínimo)"
            elif cpa is None or cpa > lim:
                veredicto = f"{accion}: {'sin compras' if cpa is None else f'CPA {cpa:,.0f}'} sobre el límite {lim:,.0f}"
                props.append(f"{campana}: {veredicto}.")
            elif accion == "proponer_subir" and cpa < lim * 0.7:
                veredicto = "proponer subir presupuesto (requiere tu aprobación)"
                props.append(f"{campana}: CPA {cpa:,.0f}, 30 % bajo el límite; candidata a subir presupuesto.")
            else:
                veredicto = "dentro del límite"
        filas.append([campana, plat, prod, r2(a["gasto"]), int(a["compras"]), r2(cpa) if cpa else None, veredicto, a["ref"] or None])
    return {"resumen": f"Reglas activas evaluadas sobre los últimos {dias} días. Pausar es reversible; subir presupuesto siempre queda como propuesta.",
            "metricas": [M("Campañas evaluadas", len(filas)), M("Sobre el límite", len(props), "bad" if props else "ok"), M("Reglas activas", len(reglas), None if reglas else "amber")],
            "tablas": [T("Campañas", ["Campaña", "Plataforma", "Producto", "Gasto", "Compras", "CPA", "Veredicto", "ID de campaña"], sorted(filas, key=lambda f: -f[3]))],
            "alertas": props + ([] if reglas else ["No hay reglas activas: define el CPA límite por producto en la pestaña «Datos»."])}


@tool("creativos", "Rendimiento por hook, ángulo y formato")
def creativos(space_id, inp):
    crea = {c["data"].get("nombre_archivo") or c["title"]: c for c in recs(space_id, "dd_creativo")}
    spend = recs(space_id, "dd_gasto_pauta")
    if not crea or not spend:
        return {"resumen": "Hace falta al menos un creativo etiquetado y gasto de pauta cuyo campo «Anuncio» coincida con el nombre de archivo del creativo. " + SIN_DATOS}
    tablas, sin = [], 0
    for dim, label in (("hook", "Hook"), ("angulo", "Ángulo"), ("formato", "Formato")):
        agg = defaultdict(lambda: defaultdict(float))
        for s in spend:
            c = crea.get(s["data"].get("anuncio") or "")
            if not c:
                sin += 1
                continue
            k = (c["data"].get(dim) or "(sin etiquetar)")[:80]
            agg[k]["gasto"] += n(s["data"].get("gasto"))
            agg[k]["compras"] += n(s["data"].get("compras"))
            agg[k]["clics"] += n(s["data"].get("clics"))
            agg[k]["imp"] += n(s["data"].get("impresiones"))
        filas = [[k, r2(a["gasto"]), int(a["compras"]), r2(a["gasto"] / a["compras"]) if a["compras"] else None, pct(a["clics"], a["imp"]),
                  "suficiente" if a["compras"] >= 20 else "muestra pequeña"] for k, a in agg.items()]
        tablas.append(T(f"Por {label.lower()}", [label, "Gasto", "Compras", "CPA", "CTR %", "Muestra"], sorted(filas, key=lambda f: (f[3] is None, f[3] or 0))))
    return {"resumen": "Cruce de gasto de pauta con las etiquetas de cada creativo. Con menos de 20 compras, una diferencia no es concluyente.",
            "tablas": tablas, "alertas": [f"{sin // 3} filas de gasto no coinciden con ningún creativo etiquetado."] if sin else []}


@tool("experimentos", "Resumen de la bitácora de experimentos")
def experimentos(space_id, inp):
    exps = recs(space_id, "dd_experimento")
    if not exps:
        return {"resumen": SIN_DATOS}
    cerr = [e for e in exps if e["status"] == "cerrado"]
    c = defaultdict(int)
    for e in cerr:
        c[e["data"].get("veredicto") or "sin veredicto"] += 1
    largos = [e["title"] for e in exps if e["status"] == "corriendo" and (_day(e["data"].get("inicio")) or date.today()) < date.today() - timedelta(days=21)]
    return {"metricas": [M("Experimentos", len(exps)), M("Cerrados", len(cerr)), M("Ganaron", c["gano"], "ok"), M("Inconclusos", c["inconcluso"], "amber" if c["inconcluso"] else None)],
            "tablas": [T("Cerrados", ["Experimento", "Variable", "Métrica", "Veredicto", "Resultado"],
                         [[e["title"], e["data"].get("variable"), e["data"].get("metrica"), e["data"].get("veredicto"), e["data"].get("resultado")] for e in cerr[:100]])],
            "alertas": [f"«{t}» lleva más de 21 días corriendo sin cerrarse." for t in largos]}


# ---------- X07 · cumplimiento de anuncios (reglas deterministas; la skill añade el juicio)

REGLAS_CUMPLIMIENTO = [
    ("alta", "Promesa de curar o tratar", r"\b(cura|curar|elimina|eliminar|trata|tratar|sana|revierte|desaparece)\b.{0,40}\b(diabetes|artritis|c[aá]ncer|hipertensi[oó]n|ansiedad|depresi[oó]n|insomnio|psoriasis|acn[eé]|hongos|dolor|enfermedad|infecci[oó]n)\b"),
    ("alta", "Resultado garantizado", r"\b(garantizad[oa]s?|100 ?% (efectiv|segur|garantiz)|resultados? asegurad|sin riesgo alguno|funciona siempre)"),
    ("alta", "Antes y después o transformación corporal", r"\b(antes y despu[eé]s|antes\s*/\s*despu[eé]s|transformaci[oó]n en \d+ d[ií]as)\b"),
    ("alta", "Pérdida de peso con cifra y plazo", r"\b(baja|pierde|adelgaza|quema)\b.{0,25}\b\d+ ?(kg|kilos|libras|lb)\b.{0,30}\b(d[ií]as?|semanas?|mes(es)?)\b"),
    ("alta", "Alude a un atributo personal del lector", r"\b(¿?(sufres|padeces|tienes|est[aá]s)\b.{0,25}\b(sobrepeso|gord[oa]|deprimid[oa]|calv[oa]|endeudad[oa]|diabetes|acn[eé]|ansiedad|soler[oa])|tu (diabetes|sobrepeso|calvicie|deuda|depresi[oó]n|acn[eé]))"),
    ("media", "Afirmación médica o de autoridad sin respaldo", r"\b(cl[ií]nicamente (probado|comprobado)|aprobado por (la )?(fda|invima|cofepris|anmat)|recomendado por (m[eé]dicos|doctores|dermat[oó]logos)|cient[ií]ficamente (probado|comprobado))\b"),
    ("media", "Urgencia o escasez no verificable", r"\b(solo por hoy|[uú]ltimas? (unidades|horas)|se agota|quedan (solo )?\d+|oferta termina (hoy|en))\b"),
    ("media", "Promesa de ingresos", r"\b(gana|genera|factura)\b.{0,25}(\$|usd|d[oó]lares|pesos|millones).{0,30}\b(d[ií]a|semana|mes|sin esfuerzo|desde casa)\b"),
    ("media", "Lenguaje absoluto", r"\b(el mejor del mundo|milagros[oa]|m[aá]gic[oa]|instant[aá]ne[oa]|para siempre|definitiv[oa]mente elimina)\b"),
    ("baja", "Comparación con marca o competidor", r"\b(mejor que|a diferencia de|supera a)\b.{0,30}\b[A-Z][a-zA-Z]+"),
    ("baja", "Testimonio con resultado concreto", r"[\"«“].{0,120}\b(baj[eé]|perd[ií]|gan[eé]|me cur[oó]|desapareci[oó])\b.{0,120}[\"»”]"),
]


def scan_cumplimiento(texto: str, extra: list[dict] | None = None) -> list[list]:
    out = []
    for sev, nombre, rx in REGLAS_CUMPLIMIENTO:
        for m in re.finditer(rx, texto, flags=re.I | re.S):
            out.append([sev, nombre, texto[max(0, m.start() - 30):m.end() + 30].replace("\n", " ").strip()])
    for r in extra or []:
        for frase in [f.strip() for f in re.split(r"[\n;]", r["data"].get("regla") or "") if len(f.strip()) > 3]:
            if frase.lower() in texto.lower():
                out.append(["media", f"Regla propia: {r['title']}", frase])
    return out


@tool("cumplimiento", "Revisión de cumplimiento de anuncios", ["texto:Copy, guion o página:textarea"], auto=False)
def cumplimiento(space_id, inp):
    texto = str(inp.get("texto") or inp.get("ganador") or inp.get("guion") or "")
    if len(texto.strip()) < 15:
        raise ValueError("Pega el texto a revisar.")
    hall = scan_cumplimiento(texto, recs(space_id, "dd_politica", "vigente"))
    altas = sum(1 for h in hall if h[0] == "alta")
    nivel = "alto" if altas else "medio" if hall else "bajo"
    return {"resumen": "Revisión por patrones conocidos de rechazo. Reduce el riesgo; no garantiza la aprobación: las políticas cambian y la plataforma decide.",
            "metricas": [M("Riesgo", nivel, {"alto": "bad", "medio": "amber", "bajo": "ok"}[nivel]), M("Hallazgos", len(hall)), M("Graves", altas, "bad" if altas else "ok")],
            "tablas": [T("Hallazgos", ["Gravedad", "Regla", "Fragmento"], sorted(hall, key=lambda h: ["alta", "media", "baja"].index(h[0])))],
            "alertas": ["No publiques esta pieza sin corregir los hallazgos graves."] if altas else []}


# ---------- X08 · datos personales

_PII = [("correo", r"[\w.+-]+@[\w-]+\.[\w.-]+"), ("tarjeta", r"\b(?:\d[ -]?){13,19}\b"), ("telefono", r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?)?\d{3}[ -]?\d{4}(?!\d)"),
        ("documento", r"\b(?:c\.?c\.?|c[eé]dula|dni|nit|rut|curp|rfc)\.?:? ?#? ?[\d.\-]{6,15}\b"),
        ("direccion", r"\b(?:calle|carrera|cra|cll|avenida|av|transversal|diagonal|kr)\.? ?\d+[a-z]? ?(?:#|no\.?|n°)? ?\d+[a-z]?(?: ?- ?\d+)?")]


def mask_pii(texto: str) -> tuple[str, dict[str, str]]:
    mapa: dict[str, str] = {}
    for tipo, rx in _PII:
        def sub(m, tipo=tipo):
            key = f"[{tipo.upper()}_{sum(1 for k in mapa if k.startswith('[' + tipo.upper())) + 1}]"
            mapa[key] = m.group(0)
            return key
        texto = re.sub(rx, sub, texto, flags=re.I)
    return texto, mapa


@tool("pii", "Enmascarar datos personales antes de usar un modelo", ["texto:Texto con datos de clientes:textarea"], auto=False)
def pii(space_id, inp):
    masked, mapa = mask_pii(str(inp.get("texto") or ""))
    cuenta = defaultdict(int)
    for k in mapa:
        cuenta[k.strip("[]").rsplit("_", 1)[0].lower()] += 1
    return {"resumen": "El texto enmascarado puede pegarse en un prompt. El mapa para restaurar solo se devuelve aquí: no se guarda en ningún lado.",
            "metricas": [M("Datos enmascarados", len(mapa))] + [M(k, v) for k, v in cuenta.items()],
            "texto": masked, "mapa": mapa, "alertas": [] if mapa else ["No se detectaron datos personales con los patrones conocidos; revisa nombres propios a mano."]}


# ---------- G07 · salud de tiendas

def check_store(url: str, pixel: str = "") -> dict:
    """Una petición GET a la página pública. No hace compras ni envía formularios."""
    url = security.check_public_url(url)
    t0 = time.monotonic()
    raw = b""
    with webfetch._client() as cli, cli.stream("GET", url) as resp:
        if not webfetch._peer_is_public(resp):
            raise security.SecurityError("La conexión terminó en una dirección privada; descartada.")
        for chunk in resp.iter_bytes():
            raw += chunk
            if len(raw) > 800_000:
                break
    ms = int((time.monotonic() - t0) * 1000)
    html = raw.decode(resp.encoding or "utf-8", "replace") if resp.status_code < 400 else ""
    low = html.lower()
    checks = [("Responde", resp.status_code < 400, f"HTTP {resp.status_code}"), ("Rápida (menos de 3 s)", ms < 3000, f"{ms} ms"),
              ("Píxel de Meta o TikTok presente", ("fbq(" in low or "connect.facebook.net" in low or "ttq." in low or "analytics.tiktok.com" in low) and (not pixel or pixel in html),
               "encontrado" if ("fbq(" in low or "ttq." in low) else "no se ve en el HTML"),
              ("Botón o formulario de compra", any(k in low for k in ("/cart/add", "add-to-cart", "addtocart", 'name="add"', "checkout", "comprar", "pedir ahora", "releasit", "cod-form")), ""),
              ("Sin mensaje de error o cierre", not any(k in low for k in ("this store is unavailable", "tienda no disponible", "password-page", "opening soon", "liquid error")), "")]
    parts = urlsplit(url)
    if "cdn.shopify.com" in low and "/products/" in parts.path:
        # Tienda Shopify: el producto debe estar disponible para la venta y el carrito debe responder. Solo lecturas: no se crea ningún pedido.
        base = f"{parts.scheme}://{parts.netloc}"
        st, body = _get(f"{base}{parts.path.rstrip('/').split('?')[0]}.js")
        try:
            prod = json.loads(body) if st == 200 else None
        except ValueError:
            prod = None
        checks.append(("Producto disponible para la venta", bool(prod and prod.get("available")), "agotado o no publicado" if prod and not prod.get("available") else "" if prod else f"HTTP {st}"))
        st, _ = _get(f"{base}/cart.js")
        checks.append(("El carrito responde", st == 200, f"HTTP {st}"))
    return {"url": url, "ok": all(c[1] for c in checks), "ms": ms, "checks": checks}


def _get(url: str) -> tuple[int, str]:
    url = security.check_public_url(url)
    raw = b""
    with webfetch._client() as cli, cli.stream("GET", url) as resp:
        if not webfetch._peer_is_public(resp):
            raise security.SecurityError("La conexión terminó en una dirección privada; descartada.")
        for chunk in resp.iter_bytes():
            raw += chunk
            if len(raw) > 400_000:
                break
    return resp.status_code, raw.decode("utf-8", "replace")


@tool("salud_tienda", "Comprobación de salud de una tienda o página", ["enlace:URL de la página de producto:url", "pixel:ID de píxel esperado (opcional)"], auto=False)
def salud_tienda(space_id, inp):
    if not inp.get("enlace"):
        raise ValueError("Indica la URL a comprobar.")
    res = check_store(str(inp["enlace"]), str(inp.get("pixel") or ""))
    fallas = [c[0] for c in res["checks"] if not c[1]]
    records.create(space_id, "dd_chequeo", f"{webfetch.domain_of(res['url'])} · {'ok' if res['ok'] else 'falla'}",
                   {"fecha": date.today().isoformat(), "tienda": res["url"], "resultado": "ok" if res["ok"] else ", ".join(fallas),
                    "detalle": "\n".join(f"{'✓' if c[1] else '✗'} {c[0]} {c[2]}".strip() for c in res["checks"])}, status="ok" if res["ok"] else "falla")
    return {"resumen": "Comprobación determinista de la página pública, solo con lecturas. En tiendas Shopify verifica además que el producto esté a la venta y que el carrito responda. No hace una compra de prueba: crearía pedidos reales.",
            "metricas": [M("Estado", "sana" if res["ok"] else "con fallas", "ok" if res["ok"] else "bad"), M("Tiempo de respuesta", f"{res['ms']} ms")],
            "tablas": [T("Comprobaciones", ["Comprobación", "Resultado", "Detalle"], [[c[0], "ok" if c[1] else "FALLA", c[2]] for c in res["checks"]])],
            "alertas": [f"Falla: {f}" for f in fallas]}


def run_store_checks() -> int:
    """Ronda horaria del worker: comprueba cada tienda activa y deja una alerta si falla. Respeta la pausa global de agentes."""
    if db.get_setting("agents_paused", False):
        return 0
    done = 0
    for sp in db.query("SELECT id FROM spaces WHERE archived=0"):
        for t in recs(sp["id"], "dd_tienda", "activa"):
            if not t["data"].get("url"):
                continue
            try:
                res = salud_tienda(sp["id"], {"enlace": t["data"]["url"], "pixel": t["data"].get("pixel") or ""})
            except Exception as exc:  # red caída o URL rechazada: también es una falla que avisar
                res = {"alertas": [f"No se pudo comprobar: {type(exc).__name__}"]}
            done += 1
            if res["alertas"]:
                records.create(sp["id"], "dd_alerta", f"Tienda con fallas: {t['title']}", {"origen": "G07", "fecha": date.today().isoformat(), "detalle": "\n".join(res["alertas"])})
    return done


# ---------- Ventas y clientes

@tool("embudo", "Puntaje de aplicaciones", ["minimo:Presupuesto mínimo:number", "umbral:Puntaje para calificar (0-100):number"])
def embudo(space_id, inp):
    apps = recs(space_id, "dd_aplicacion")
    if not apps:
        return {"resumen": SIN_DATOS}
    minimo, umbral, filas = n(inp.get("minimo"), 500), n(inp.get("umbral"), 60), []
    for a in apps:
        d = a["data"]
        p = min(40, 40 * n(d.get("presupuesto")) / minimo) if minimo else 0
        p += {"alta": 25, "media": 12, "baja": 0}.get(d.get("urgencia") or "", 0) + (20 if d.get("decisor") else 0) + (15 if len(d.get("necesidad") or "") > 60 else 5 if d.get("necesidad") else 0)
        p = round(p)
        if a["status"] == "nueva":
            records.update(a["id"], space_id, {"status": "calificada" if p >= umbral else "no_calificada", "data": {"puntaje": p}})
        filas.append([a["title"], d.get("empresa"), r2(n(d.get("presupuesto"))), d.get("urgencia"), "sí" if d.get("decisor") else "no", p, "califica" if p >= umbral else "recurso gratuito"])
    cal = sum(1 for f in filas if f[5] >= umbral)
    return {"resumen": f"Regla fija: presupuesto (40), urgencia (25), decide la compra (20) y necesidad descrita (15). Califica con {umbral:.0f} o más. Las aplicaciones nuevas quedaron clasificadas.",
            "metricas": [M("Aplicaciones", len(filas)), M("Califican", cal, "ok"), M("Tasa de calificación", f"{pct(cal, len(filas))} %")],
            "tablas": [T("Aplicaciones", ["Aplicación", "Empresa", "Presupuesto", "Urgencia", "Decide", "Puntaje", "Destino"], sorted(filas, key=lambda f: -f[5]))]}


@tool("churn", "Señales tempranas de pérdida de clientes")
def churn(space_id, inp):
    cl = [c for c in recs(space_id, "dd_cliente") if c["status"] in ("activo", "en_riesgo")]
    if not cl:
        return {"resumen": SIN_DATOS}
    filas = []
    for c in cl:
        d, s, mot = c["data"], 0, []
        dias = (date.today() - (_day(d.get("ultimo_contacto")) or date.today())).days if d.get("ultimo_contacto") else None
        if dias is None:
            s, mot = s + 20, mot + ["sin fecha de último contacto"]
        elif dias > 14:
            s, mot = s + min(40, dias), mot + [f"{dias} días de silencio"]
        if d.get("resultado") == "baja":
            s, mot = s + 35, mot + ["resultados a la baja"]
        if d.get("pagos_al_dia") is False:
            s, mot = s + 25, mot + ["pago atrasado"]
        filas.append([c["title"], r2(n(d.get("mensualidad"))), s, "alto" if s >= 50 else "medio" if s >= 25 else "bajo", "; ".join(mot) or "sin señales"])
        if s >= 50 and c["status"] == "activo":
            records.update(c["id"], space_id, {"status": "en_riesgo"})
    riesgo = [f for f in filas if f[2] >= 50]
    return {"resumen": "Señales: silencio de más de 14 días, resultados a la baja y pagos atrasados. Los clientes de riesgo alto quedaron marcados «en riesgo».",
            "metricas": [M("Clientes activos", len(filas)), M("En riesgo alto", len(riesgo), "bad" if riesgo else "ok"), M("Mensualidad en riesgo", r2(sum(f[1] for f in riesgo)), "amber" if riesgo else None)],
            "tablas": [T("Clientes", ["Cliente", "Mensualidad", "Puntaje de riesgo", "Riesgo", "Señales"], sorted(filas, key=lambda f: -f[2]))],
            "alertas": [f"{f[0]}: {f[4]}." for f in riesgo]}


@tool("pipeline", "Estado del pipeline")
def pipeline(space_id, inp):
    tr = recs(space_id, "dd_trato")
    if not tr:
        return {"resumen": SIN_DATOS}
    etapas, hoy, venc = defaultdict(lambda: [0, 0.0]), date.today(), []
    for t in tr:
        etapas[t["status"]][0] += 1
        etapas[t["status"]][1] += n(t["data"].get("valor"))
        f = _day(t["data"].get("fecha_proxima"))
        if t["status"] not in ("ganado", "perdido") and (not f or f <= hoy):
            venc.append([t["title"], t["status"], t["data"].get("proxima_accion") or "sin próxima acción", f.isoformat() if f else "sin fecha"])
    abiertos = sum(v[1] for k, v in etapas.items() if k not in ("ganado", "perdido"))
    cerr = etapas["ganado"][0] + etapas["perdido"][0]
    return {"metricas": [M("Valor abierto", r2(abiertos)), M("Ganado", r2(etapas["ganado"][1]), "ok"), M("Tasa de cierre", f"{pct(etapas['ganado'][0], cerr)} %" if cerr else "sin cierres"),
                         M("Seguimientos vencidos", len(venc), "amber" if venc else "ok")],
            "tablas": [T("Por etapa", ["Etapa", "Oportunidades", "Valor"], [[k, v[0], r2(v[1])] for k, v in etapas.items()]),
                       T("Requieren acción hoy", ["Oportunidad", "Etapa", "Próxima acción", "Fecha"], venc)],
            "alertas": [f"{len(venc)} oportunidades sin seguimiento al día."] if venc else []}


@tool("utm", "Enlace medido y atribución de contenido", ["destino:URL de destino:url", "fuente:Fuente (instagram, youtube…)", "medio:Medio (organico, bio, historia…)",
                                                         "campana:Campaña", "contenido:Video o pieza"])
def utm(space_id, inp):
    out: dict = {}
    if inp.get("destino"):
        from urllib.parse import urlencode
        slug = lambda s: re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")
        q = {k: slug(inp.get(v)) for k, v in (("utm_source", "fuente"), ("utm_medium", "medio"), ("utm_campaign", "campana"), ("utm_content", "contenido")) if slug(inp.get(v))}
        if "utm_source" not in q:
            raise ValueError("Indica al menos la fuente.")
        link = f"{inp['destino']}{'&' if '?' in str(inp['destino']) else '?'}{urlencode(q)}"
        records.create(space_id, "dd_enlace", q.get("utm_content") or q["utm_source"], {"destino": inp["destino"], "fuente": q.get("utm_source"), "medio": q.get("utm_medium"),
                                                                                         "campana": q.get("utm_campaign"), "contenido": q.get("utm_content"), "enlace": link})
        out["texto"] = link
    apps, cuenta = recs(space_id, "dd_aplicacion"), defaultdict(lambda: [0, 0])
    for a in apps:
        k = a["data"].get("origen") or "(sin origen)"
        cuenta[k][0] += 1
        cuenta[k][1] += a["status"] in ("calificada", "agendada", "cerrada")
    return {**out, "resumen": "El enlace generado queda guardado. La atribución cuenta las aplicaciones cuyo campo «Origen» coincide con el contenido del enlace.",
            "tablas": [T("Aplicaciones por origen", ["Origen", "Aplicaciones", "Calificadas"], sorted([[k, v[0], v[1]] for k, v in cuenta.items()], key=lambda f: -f[2]))] if apps else []}


@tool("clipping_pagos", "Liquidación de clipping por vistas")
def clipping_pagos(space_id, inp):
    envs = recs(space_id, "dd_clip_pago")
    if not envs:
        return {"resumen": SIN_DATOS}
    por, filas = defaultdict(lambda: [0, 0.0, 0.0]), []
    for e in envs:
        d = e["data"]
        bruto = n(d.get("vistas")) / 1000 * n(d.get("cpm"))
        pago = min(bruto, n(d.get("tope"))) if n(d.get("tope")) else bruto
        if e["status"] == "verificado":
            p = por[d.get("clipper") or "(sin clipper)"]
            p[0], p[1], p[2] = p[0] + 1, p[1] + n(d.get("vistas")), p[2] + pago
        filas.append([e["title"], d.get("clipper"), d.get("campana"), int(n(d.get("vistas"))), r2(pago), e["status"]])
    return {"resumen": "Pago = vistas verificadas ÷ 1000 × pago por mil, con tope por envío. Solo los envíos en estado «verificado» entran en la liquidación.",
            "metricas": [M("Por pagar", r2(sum(p[2] for p in por.values())), "amber"), M("Envíos verificados", sum(p[0] for p in por.values())),
                         M("Sin verificar", sum(1 for e in envs if e["status"] == "enviado"))],
            "tablas": [T("Liquidación por clipper", ["Clipper", "Envíos", "Vistas", "A pagar"], [[k, v[0], int(v[1]), r2(v[2])] for k, v in por.items()]),
                       T("Envíos", ["Envío", "Clipper", "Campaña", "Vistas", "Pago calculado", "Estado"], filas[:300])]}


@tool("riesgo_cod", "Riesgo de devolución por ciudad y producto")
def riesgo_cod(space_id, inp):
    u = _utilidad(space_id, inp)
    if not u["orders"]:
        return {"resumen": SIN_DATOS}
    def rows(src):
        return sorted([[r[0], r[2] + r[3], r[3], pct(r[3], r[2] + r[3]), "confirmar por llamada" if (pct(r[3], r[2] + r[3]) or 0) >= 40 else "confirmar por mensaje"
                        if (pct(r[3], r[2] + r[3]) or 0) >= 25 else "despacho directo"] for r in src if r[2] + r[3] >= 5], key=lambda f: -(f[3] or 0))
    return {"resumen": "Tasa de devolución histórica con al menos 5 pedidos cerrados. Regla: 40 % o más, llamada; 25 % o más, mensaje.",
            "tablas": [T("Por ciudad", ["Ciudad", "Cerrados", "Devueltos", "% devolución", "Regla sugerida"], rows(u["ciudades"])),
                       T("Por producto", ["Producto", "Cerrados", "Devueltos", "% devolución", "Regla sugerida"], rows(u["productos"]))]}


# ---------- Finanzas, inventario y operación

@tool("flujo_caja", "Flujo de caja por mes y categoría")
def flujo_caja(space_id, inp):
    mov = recs(space_id, "dd_movimiento")
    if not mov:
        return {"resumen": SIN_DATOS}
    mes, cat, sin = defaultdict(lambda: [0.0, 0.0]), defaultdict(float), 0
    for m in mov:
        d, v = m["data"], n(m["data"].get("monto"))
        mes[(d.get("fecha") or "sin fecha")[:7]][0 if v >= 0 else 1] += v
        cat[d.get("categoria") or "(sin categoría)"] += v
        sin += not d.get("categoria")
    filas = [[k, r2(v[0]), r2(v[1]), r2(v[0] + v[1])] for k, v in sorted(mes.items())]
    ult = [f[3] for f in filas[-3:]]
    return {"resumen": "Entradas y salidas según los movimientos registrados. El promedio usa los últimos tres meses con datos. No es contabilidad oficial.",
            "metricas": [M("Neto acumulado", r2(sum(f[3] for f in filas))), M("Promedio mensual reciente", r2(sum(ult) / len(ult)), "bad" if sum(ult) < 0 else "ok"),
                         M("Sin categoría", sin, "amber" if sin else "ok"), M("Por conciliar", sum(1 for m in mov if m["status"] == "por_conciliar"))],
            "tablas": [T("Por mes", ["Mes", "Entradas", "Salidas", "Neto"], filas), T("Por categoría", ["Categoría", "Total"], sorted([[k, r2(v)] for k, v in cat.items()], key=lambda f: f[1]))]}


@tool("suscripciones", "Auditoría de suscripciones")
def suscripciones(space_id, inp):
    subs = [s for s in recs(space_id, "dd_suscripcion") if s["status"] != "cancelada"]
    if not subs:
        return {"resumen": SIN_DATOS}
    filas = [[s["title"], s["data"].get("categoria"), r2(n(s["data"].get("costo_mensual"))), s["data"].get("uso") or "sin dato", s["data"].get("proyecto") or "ninguno",
              "cancelar" if s["data"].get("uso") == "nulo" else "revisar" if s["data"].get("uso") in ("raro", None, "") or not s["data"].get("proyecto") else "conservar"] for s in subs]
    total, ahorro = sum(f[2] for f in filas), sum(f[2] for f in filas if f[5] == "cancelar")
    dup = defaultdict(list)
    for f in filas:
        if f[1]:
            dup[f[1]].append(f[0])
    return {"resumen": "Regla: uso nulo se cancela; uso raro o sin proyecto asignado se revisa. Las categorías con varias herramientas son candidatas a consolidar.",
            "metricas": [M("Gasto mensual", r2(total)), M("Ahorro inmediato", r2(ahorro), "ok" if ahorro else None), M("En revisión", r2(sum(f[2] for f in filas if f[5] == "revisar")), "amber")],
            "tablas": [T("Suscripciones", ["Herramienta", "Categoría", "Costo mensual", "Uso", "Proyecto", "Decisión sugerida"], sorted(filas, key=lambda f: -f[2]))],
            "alertas": [f"«{k}» tiene {len(v)} herramientas: {', '.join(v)}." for k, v in dup.items() if len(v) > 1]}


@tool("inventario", "Inventario de activos y vencimientos")
def inventario(space_id, inp):
    act = recs(space_id, "dd_activo", "activo")
    if not act:
        return {"resumen": SIN_DATOS}
    tipos, prox = defaultdict(lambda: [0, 0.0]), []
    for a in act:
        tipos[a["data"].get("tipo") or "otro"][0] += 1
        tipos[a["data"].get("tipo") or "otro"][1] += n(a["data"].get("costo_mensual"))
        v = _day(a["data"].get("vence"))
        if v and v <= date.today() + timedelta(days=30):
            prox.append([a["title"], a["data"].get("tipo"), v.isoformat(), (v - date.today()).days])
    return {"metricas": [M("Activos", len(act)), M("Costo mensual", r2(sum(v[1] for v in tipos.values()))), M("Vencen en 30 días", len(prox), "amber" if prox else "ok")],
            "tablas": [T("Por tipo", ["Tipo", "Cantidad", "Costo mensual"], [[k, v[0], r2(v[1])] for k, v in tipos.items()]),
                       T("Vencimientos próximos", ["Activo", "Tipo", "Vence", "Días"], sorted(prox, key=lambda f: f[3]))],
            "alertas": [f"«{p[0]}» vence en {p[3]} días." for p in prox if p[3] <= 7]}


@tool("tareas", "Estado del tablero de tareas")
def tareas(space_id, inp):
    ts = [t for t in recs(space_id, "dd_tarea") if t["status"] != "hecha"]
    if not ts:
        return {"resumen": "No hay tareas abiertas."}
    venc = [[t["title"], t["data"].get("responsable"), t["data"].get("vence"), t["status"]] for t in ts if (_day(t["data"].get("vence")) or date.max) < date.today()]
    por = defaultdict(int)
    for t in ts:
        por[t["data"].get("responsable") or "(sin responsable)"] += 1
    return {"metricas": [M("Abiertas", len(ts)), M("Vencidas", len(venc), "bad" if venc else "ok"), M("Bloqueadas", sum(1 for t in ts if t["status"] == "bloqueada"), "amber")],
            "tablas": [T("Vencidas", ["Tarea", "Responsable", "Vencía", "Estado"], venc), T("Carga por persona", ["Responsable", "Abiertas"], sorted(por.items(), key=lambda x: -x[1]))]}


@tool("agenda", "Resumen de bloques de la semana")
def agenda(space_id, inp):
    bl = [b for b in recs(space_id, "dd_bloque") if (_day(b["data"].get("dia")) or date.min) >= date.today() - timedelta(days=7)]
    if not bl:
        return {"resumen": "No hay bloques registrados en la semana."}
    def horas(b):
        try:
            a, z = (datetime.strptime(b["data"][k], "%H:%M") for k in ("inicio", "fin"))
            return max(0.0, (z - a).seconds / 3600)
        except (KeyError, ValueError, TypeError):
            return 0.0
    tipo = defaultdict(float)
    for b in bl:
        tipo[b["data"].get("tipo") or "otro"] += horas(b)
    mov = sum(1 for b in bl if b["status"] == "movido")
    return {"metricas": [M("Horas de trabajo profundo", r2(tipo["profundo"]), "ok"), M("Horas en reuniones", r2(tipo["reunion"])), M("Bloques movidos", mov, "amber" if mov else "ok")],
            "tablas": [T("Horas por tipo", ["Tipo", "Horas"], [[k, r2(v)] for k, v in tipo.items()])]}


@tool("duplicados", "Archivos duplicados del espacio")
def duplicados(space_id, inp):
    rows = db.query("SELECT name, sha256, size FROM files WHERE space_id=? AND archived=0", (space_id,))
    if not rows:
        return {"resumen": "No hay archivos subidos en este espacio."}
    g = defaultdict(list)
    for r in rows:
        g[r["sha256"]].append(r)
    dup = [[", ".join(x["name"] for x in v), len(v), v[0]["size"] * (len(v) - 1)] for v in g.values() if len(v) > 1 and v[0]["sha256"]]
    return {"metricas": [M("Archivos", len(rows)), M("Grupos duplicados", len(dup), "amber" if dup else "ok"), M("Bytes recuperables", sum(d[2] for d in dup))],
            "tablas": [T("Duplicados exactos (mismo contenido)", ["Archivos", "Copias", "Bytes de sobra"], dup)]}


# ---------- Personal

@tool("habitos", "Rachas y puntos de hábitos")
def habitos(space_id, inp):
    habs, regs = recs(space_id, "dd_habito", "activo"), recs(space_id, "dd_habito_registro")
    if not habs:
        return {"resumen": SIN_DATOS}
    dias = defaultdict(set)
    for r in regs:
        if _day(r["data"].get("fecha")):
            dias[r["data"].get("habito") or r["title"]].add(_day(r["data"]["fecha"]))
    filas, hoy = [], date.today()
    for h in habs:
        ds, racha, d = dias[h["title"]], 0, hoy if hoy in dias[h["title"]] else hoy - timedelta(days=1)
        while d in ds:
            racha, d = racha + 1, d - timedelta(days=1)
        sem = sum(1 for x in ds if x > hoy - timedelta(days=7))
        filas.append([h["title"], racha, sem, int(sem * n(h["data"].get("puntos"), 1)), "hecho" if hoy in ds else "pendiente hoy"])
    return {"metricas": [M("Puntos de la semana", sum(f[3] for f in filas), "ok"), M("Mejor racha", max(f[1] for f in filas)), M("Pendientes hoy", sum(1 for f in filas if f[4] != "hecho"), "amber")],
            "tablas": [T("Hábitos", ["Hábito", "Racha (días)", "Últimos 7 días", "Puntos", "Hoy"], filas)]}


@tool("fechas", "Fechas importantes próximas", ["dias:Días hacia adelante:number"])
def fechas(space_id, inp):
    fs, hoy, lim, filas = recs(space_id, "dd_fecha", "activa"), date.today(), int(n(inp.get("dias"), 30) or 30), []
    if not fs:
        return {"resumen": SIN_DATOS}
    for f in fs:
        d = _day(f["data"].get("fecha"))
        if not d:
            continue
        try:
            prox = d.replace(year=hoy.year)
        except ValueError:
            prox = d.replace(year=hoy.year, day=28)
        if prox < hoy:
            prox = prox.replace(year=hoy.year + 1)
        if (prox - hoy).days <= lim:
            filas.append([f["data"].get("persona") or f["title"], f["data"].get("tipo"), prox.isoformat(), (prox - hoy).days, f["data"].get("idea") or ""])
    return {"metricas": [M(f"En los próximos {lim} días", len(filas), "amber" if filas else "ok")],
            "tablas": [T("Próximas", ["Persona", "Tipo", "Fecha", "Faltan (días)", "Idea de detalle"], sorted(filas, key=lambda f: f[3]))],
            "alertas": [f"{f[0]}: faltan {f[3]} días." for f in filas if f[3] <= 3]}


@tool("entrenamiento", "Progresión de entrenamiento")
def entrenamiento(space_id, inp):
    ser = recs(space_id, "dd_serie")
    if not ser:
        return {"resumen": SIN_DATOS}
    ej = defaultdict(list)
    for s in ser:
        d = s["data"]
        if n(d.get("peso")) and n(d.get("reps")):
            ej[d.get("ejercicio") or s["title"]].append((d.get("fecha") or "", n(d["peso"]) * (1 + n(d["reps"]) / 30), n(d["peso"]) * n(d["reps"]) * (n(d.get("series"), 1) or 1)))
    filas = []
    for k, v in ej.items():
        v.sort()
        filas.append([k, len(v), r2(v[0][1]), r2(v[-1][1]), pct(v[-1][1] - v[0][1], v[0][1]), r2(sum(x[2] for x in v[-3:]) / len(v[-3:])), v[-1][0]])
    return {"resumen": "Fuerza estimada con la fórmula de Epley (peso × (1 + repeticiones ÷ 30)). Volumen = peso × repeticiones × series.",
            "tablas": [T("Por ejercicio", ["Ejercicio", "Sesiones", "1RM estimado inicial", "1RM estimado actual", "Cambio %", "Volumen medio reciente", "Última sesión"], filas)],
            "alertas": [f"«{f[0]}» no progresa (cambio {f[4]} % en {f[1]} sesiones)." for f in filas if f[1] >= 4 and (f[4] or 0) <= 0]}


@tool("sueno", "Tendencia de sueño y recuperación")
def sueno(space_id, inp):
    # Incluye las noches importadas de Apple Health (tipo «sleep» del motor), sin duplicar fechas.
    propias = recs(space_id, "dd_sueno")
    fechas = {x["data"].get("fecha") for x in propias}
    ns = sorted(propias + [{"data": {"fecha": x["data"].get("date"), "horas": x["data"].get("hours"), "calidad": x["data"].get("quality")}} for x in recs(space_id, "sleep")
                           if x["data"].get("date") not in fechas], key=lambda x: x["data"].get("fecha") or "")
    if len(ns) < 3:
        return {"resumen": "Hacen falta al menos tres noches registradas para ver una tendencia."}
    h = [n(x["data"].get("horas")) for x in ns]
    ult, ant = h[-7:], h[-14:-7]
    media, media_ant = sum(ult) / len(ult), (sum(ant) / len(ant) if ant else None)
    cortas = [x["data"].get("fecha") for x in ns[-7:] if n(x["data"].get("horas")) < 6]
    return {"resumen": "Promedios simples de lo registrado. No es un diagnóstico.",
            "metricas": [M("Promedio últimos 7", f"{media:.1f} h", "bad" if media < 6.5 else "ok"), M("Promedio 7 anteriores", f"{media_ant:.1f} h" if media_ant else "sin datos"),
                         M("Noches de menos de 6 h", len(cortas), "amber" if cortas else "ok")],
            "tablas": [T("Últimas noches", ["Fecha", "Horas", "Calidad", "Carga del día"], [[x["data"].get("fecha"), x["data"].get("horas"), x["data"].get("calidad"), x["data"].get("carga")] for x in ns[-14:]])]}


@tool("red", "Contactos por retomar y rutas de presentación", ["objetivo:Persona a la que quieres llegar (opcional)"])
def red(space_id, inp):
    cs = recs(space_id, "dd_contacto")
    if not cs:
        return {"resumen": SIN_DATOS}
    hoy, frios, grafo = date.today(), [], defaultdict(set)
    for c in cs:
        for o in c["data"].get("conoce_a") or []:
            grafo[c["title"]].add(o)
            grafo[o].add(c["title"])
        d = _day(c["data"].get("ultimo_contacto"))
        if c["status"] != "archivado" and (not d or (hoy - d).days > 45):
            frios.append([c["title"], c["data"].get("relacion"), d.isoformat() if d else "nunca", (hoy - d).days if d else None, c["data"].get("proxima_accion") or ""])
    tablas = [T("Sin contacto en más de 45 días", ["Contacto", "Relación", "Último contacto", "Días", "Próxima acción"], sorted(frios, key=lambda f: -(f[3] or 9999))[:60])]
    obj = str(inp.get("objetivo") or "").strip()
    if obj:
        ruta, vistos, cola = None, {"yo"}, [["yo"]]
        directos = {c["title"] for c in cs}
        while cola and not ruta:
            p = cola.pop(0)
            for nx in (directos if p[-1] == "yo" else grafo[p[-1]]):
                if nx.lower() == obj.lower():
                    ruta = p + [nx]
                    break
                if nx not in vistos:
                    vistos.add(nx)
                    cola.append(p + [nx])
        tablas.insert(0, T(f"Ruta hacia {obj}", ["Paso", "Persona"], [[i, x] for i, x in enumerate(ruta[1:], 1)] if ruta else [["—", "No hay ruta con los contactos registrados"]]))
    return {"metricas": [M("Contactos", len(cs)), M("Por retomar", len(frios), "amber" if frios else "ok")], "tablas": tablas}


# ---------- Infraestructura

@tool("costos_ia", "Uso y costo estimado de IA del mes")
def costos_ia(space_id, inp):
    u = router.usage_summary()
    if not u["por_conexion"]:
        return {"resumen": "Aún no hay llamadas a proveedores de IA este mes."}
    total = sum(c["costo_estimado_usd"] or 0 for c in u["por_conexion"])
    return {"resumen": u["nota"],
            "metricas": [M("Costo estimado del mes (USD)", r2(total)), M("Llamadas", sum(c["llamadas"] for c in u["por_conexion"])),
                         M("Respuestas desde caché", sum(c["en_cache"] or 0 for c in u["por_conexion"]), "ok")],
            "tablas": [T("Por conexión", ["Conexión", "Proveedor", "Llamadas", "En caché", "Tokens", "Costo estimado USD", "Errores"],
                         [[c["name"], c["provider"], c["llamadas"], c["en_cache"], c["tokens"], r2(c["costo_estimado_usd"] or 0), c["errores"]] for c in u["por_conexion"]]),
                       T("Por tipo de tarea", ["Categoría", "Llamadas", "Tokens de entrada", "Tokens de salida", "Costo estimado USD"],
                         [[c["category"], c["llamadas"], c["tokens_in"], c["tokens_out"], r2(c["costo_estimado_usd"] or 0)] for c in u["por_categoria"]])]}


@tool("auditoria", "Registro de acciones y aprobaciones")
def auditoria(space_id, inp):
    rows = db.query("SELECT ts, actor, action, target FROM audit ORDER BY id DESC LIMIT 80")
    pend = db.one("SELECT COUNT(*) c FROM jobs WHERE status='waiting_approval'")["c"]
    aprob = db.one("SELECT COUNT(*) c FROM approvals")["c"]
    return {"resumen": "Todo agente prepara y pide aprobación (nivel B). Las acciones externas se aprueban una a una, ligadas a la versión o a la petición exacta.",
            "metricas": [M("Esperando tu aprobación", pend, "amber" if pend else "ok"), M("Aprobaciones registradas", aprob), M("Agentes en pausa", "sí" if db.get_setting("agents_paused", False) else "no")],
            "tablas": [T("Últimas acciones registradas", ["Fecha", "Actor", "Acción", "Objeto"], [[r["ts"], r["actor"], r["action"], r["target"]] for r in rows])]}


@tool("respaldos", "Estado de las copias de seguridad")
def respaldos(space_id, inp):
    from jarvis import backup
    propios = backup.list_backups()
    rs = recs(space_id, "dd_respaldo")
    atras = [[r["title"], r["data"].get("frecuencia"), r["data"].get("ultimo")] for r in rs if (date.today() - (_day(r["data"].get("ultimo")) or date.min)).days > 7]
    return {"resumen": "Las copias de Doomsday se crean desde Sistema → Respaldos. Los demás objetivos (temas, tiendas) se registran aquí con la fecha de su último respaldo.",
            "metricas": [M("Copias de Doomsday", len(propios)), M("Objetivos registrados", len(rs)), M("Atrasados (más de 7 días)", len(atras), "bad" if atras else "ok")],
            "tablas": [T("Atrasados", ["Objetivo", "Frecuencia", "Último respaldo"], atras)]}


@tool("brief_ceo", "Datos del brief diario")
def brief_ceo(space_id, inp):
    """Reúne lo que requiere decisión. Lee el espacio interno (tiendas y pauta) además del actual, sin copiar datos entre espacios."""
    spaces = db.get_setting("dd_spaces", {}) or {}
    interno = spaces.get("interna") or space_id
    ayer = (date.today() - timedelta(days=1)).isoformat()
    u = _utilidad(interno, {"desde": ayer, "hasta": ayer})
    u7 = _utilidad(interno, {"desde": (date.today() - timedelta(days=7)).isoformat()})
    alertas = [[a["title"], a["data"].get("origen"), a["data"].get("fecha")] for sid in set(spaces.values()) | {space_id} for a in recs(sid, "dd_alerta", "nueva")]
    pend = db.query("SELECT title, status FROM jobs WHERE status IN ('waiting_approval','waiting_config','failed') ORDER BY updated_at DESC LIMIT 15")
    rev = db.query("SELECT title FROM deliverables WHERE status IN ('borrador','en_revision') AND archived=0 ORDER BY updated_at DESC LIMIT 15")
    pierden = [r for r in u7["productos"] if r[8] < 0 and r[2] + r[3] >= 5]
    return {"resumen": "Datos de ayer y de los últimos 7 días del espacio interno, más lo que espera tu decisión en todo Doomsday. Si una cifra falta es porque no hay datos cargados.",
            "metricas": [M("Pedidos de ayer", len([o for o in u["orders"] if o["status"] != "cancelado"])), M("Pauta de ayer", r2(sum(n(s["data"].get("gasto")) for s in u["spend"]))),
                         M("Utilidad neta 7 días", r2(sum(r[8] for r in u7["productos"])) if u7["productos"] else "sin datos", "bad" if pierden else None),
                         M("Alertas nuevas", len(alertas), "amber" if alertas else "ok"), M("Entregables por revisar", len(rev), "amber" if rev else "ok")],
            "tablas": [T("Productos que pierden (7 días)", ["Producto", *COLS_UTIL[1:]], pierden), T("Alertas nuevas", ["Alerta", "Módulo", "Fecha"], alertas[:20]),
                       T("Trabajos que esperan", ["Trabajo", "Estado"], [[p["title"], p["status"]] for p in pend]), T("Entregables por revisar", ["Entregable"], [[r["title"]] for r in rev])],
            "alertas": [f"«{r[0]}» pierde {abs(r[8]):,.0f} en 7 días." for r in pierden]}
