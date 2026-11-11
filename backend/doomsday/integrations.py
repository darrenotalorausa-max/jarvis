"""Integraciones de Doomsday con plataformas externas, siempre a través del conector universal del motor.

Leer (GET) no requiere aprobación. Todo lo que modifica un sistema externo (pausar un anuncio, enviar un WhatsApp, crear un producto)
se encola como `connector_action`: queda esperando la aprobación del dueño, ligada al hash exacto de la petición y de un solo uso.
Las plantillas de TikTok Ads y WhatsApp no se han validado con una cuenta real: si un formato difiere, se ajusta aquí.
"""
from __future__ import annotations
import csv
import html
import io
import re
import unicodedata
from datetime import date, timedelta

from fastapi import APIRouter, Body, File, Form, UploadFile

from jarvis import connections, connectors, db, files, jobs, records, review
from jarvis.connectors import A
from jarvis.handlers import video as video_h
from jarvis.jobs import JobError
from jarvis.providers.base import ProviderError
from jarvis.worker import handler

from . import catalog

router = APIRouter(prefix="/api/dd")

GASTO_META = A("dd_gasto_diario", "Gasto diario por anuncio", "GET", "/{cuenta_publicitaria}/insights",
               query={"level": "ad", "time_increment": "1", "limit": "500", "fields": "campaign_id,campaign_name,ad_id,ad_name,spend,impressions,clicks,actions",
                      "time_range": "{rango}"})
PRESETS = {
    "meta_ads": {"label": "Meta Ads (gasto, pausa y reanudación)", "base_url": "https://graph.facebook.com/v26.0", "auth": {"type": "bearer"},
                 "credential": "Token de usuario del sistema con ads_read (y ads_management si quieres pausar desde Doomsday).",
                 "actions": [A("cuentas_publicitarias", "Cuentas publicitarias", "GET", "/me/adaccounts", query={"fields": "name,account_status,currency"}), GASTO_META,
                             A("dd_pausar", "Pausar campaña, conjunto o anuncio", "POST", "/{objeto_id}", True, body={"status": "PAUSED"}),
                             A("dd_reanudar", "Reanudar campaña, conjunto o anuncio", "POST", "/{objeto_id}", True, body={"status": "ACTIVE"})]},
    "tiktok_ads": {"label": "TikTok Ads (Marketing API)", "base_url": "https://business-api.tiktok.com/open_api/v1.3", "auth": {"type": "header", "name": "Access-Token"},
                   "credential": "Token de acceso de larga duración de tu app en TikTok for Business, con permiso de informes (y de gestión de anuncios para pausar).",
                   "actions": [A("dd_gasto_diario", "Gasto diario por anuncio", "GET", "/report/integrated/get/",
                                 query={"advertiser_id": "{cuenta_publicitaria}", "report_type": "BASIC", "data_level": "AUCTION_AD", "dimensions": '["ad_id","stat_time_day"]',
                                        "metrics": '["campaign_id","campaign_name","ad_name","spend","impressions","clicks","conversion"]', "start_date": "{desde}", "end_date": "{hasta}",
                                        "page_size": "1000"}),
                               A("dd_pausar", "Pausar anuncio", "POST", "/ad/status/update/", True,
                                 body={"advertiser_id": "{cuenta_publicitaria}", "ad_ids": ["{objeto_id}"], "operation_status": "DISABLE"})]},
    "whatsapp": {"label": "WhatsApp Business (Cloud API)", "base_url": "https://graph.facebook.com/v26.0", "auth": {"type": "bearer"},
                 "credential": "Token permanente de usuario del sistema con whatsapp_business_messaging.",
                 "actions": [A("dd_enviar_texto", "Enviar mensaje de texto", "POST", "/{numero_id}/messages", True,
                               body={"messaging_product": "whatsapp", "to": "{telefono}", "type": "text", "text": {"body": "{mensaje}"}})]},
}
SHOPIFY_EXTRA = [
    A("dd_producto_borrador", "Crear producto en borrador con ficha completa", "POST", "/products.json", True,
      body={"product": {"title": "{titulo}", "body_html": "{descripcion}", "status": "draft", "variants": [{"price": "{precio}"}],
                        "metafields_global_title_tag": "{meta_titulo}", "metafields_global_description_tag": "{meta_descripcion}"}}),
    A("dd_producto_borrador_imagen", "Crear producto en borrador con ficha completa e imagen", "POST", "/products.json", True,
      body={"product": {"title": "{titulo}", "body_html": "{descripcion}", "status": "draft", "variants": [{"price": "{precio}"}], "images": [{"src": "{imagen}"}],
                        "metafields_global_title_tag": "{meta_titulo}", "metafields_global_description_tag": "{meta_descripcion}"}}),
]


def register() -> None:
    """Añade las plantillas de Doomsday al catálogo de apps conectadas del motor. Idempotente."""
    for k, v in PRESETS.items():
        connectors.PRESETS.setdefault(k, v)
    have = {a["id"] for a in connectors.PRESETS["shopify"]["actions"]}
    connectors.PRESETS["shopify"]["actions"] += [a for a in SHOPIFY_EXTRA if a["id"] not in have]


def _conn(conn_id: str) -> dict:
    conn = connections.get(str(conn_id or ""))
    if not conn or conn["provider"] != "api" or not conn["enabled"] or not conn["terms_accepted"]:
        raise ValueError("Elige una conexión habilitada en Apps conectadas.")
    conn["options"] = connectors.validate_options(conn["options"])
    return conn


def ensure_action(conn: dict, action: dict) -> dict:
    """Si la conexión se creó antes de existir esta acción, se la añade (misma URL base y credencial; no cambia permisos externos)."""
    if not any(a["id"] == action["id"] for a in conn["options"]["actions"]):
        connections.update(conn["id"], {"options": {**conn["options"], "actions": conn["options"]["actions"] + [action]}})
        conn = _conn(conn["id"])
    return conn


def _space(module: str, space: str | None) -> str:
    from .app import _module, _space_of
    return _space_of(_module(module), space)


def request_write(conn: dict, action: dict, variables: dict, space_id: str, title: str) -> dict:
    conn = ensure_action(conn, action)
    try:
        preview = connectors.build(conn, connectors.action_of(conn, action["id"]), variables)
    except ProviderError as exc:
        raise ValueError(exc.message)
    job, created = jobs.enqueue(space_id, "connector_action", title[:200], {"connection_id": conn["id"], "action_id": action["id"], "variables": variables}, max_attempts=1)
    return {"job": job, "created": created, "preview": preview}


def _read(conn: dict, action: dict, variables: dict) -> dict:
    conn = ensure_action(conn, action)
    try:
        return connectors.execute(conn, action["id"], variables).get("json") or {}
    except ProviderError as exc:
        connections.record_error(conn, exc)
        raise


# ---------- Gasto de pauta: Meta y TikTok → dd_gasto_pauta

def _guess_product(space_id: str, campaign: str) -> str | None:
    """Asigna producto si su nombre aparece en el de la campaña (así la utilidad se cruza sola). Si no, queda vacío para completarlo."""
    low = (campaign or "").lower()
    names = sorted({o["data"].get("producto") for o in records.list_records(space_id, "dd_pedido", limit=5000) if o["data"].get("producto")} |
                   {p["title"] for p in records.list_records(space_id, "dd_producto", limit=2000)}, key=len, reverse=True)
    return next((n for n in names if len(n) >= 3 and n.lower() in low), None)


def _upsert_spend(space_id: str, rows: list[dict]) -> tuple[int, int]:
    existing = {(r["data"].get("fecha"), r["data"].get("plataforma"), r["data"].get("ref_anuncio")): r for r in records.list_records(space_id, "dd_gasto_pauta", limit=50000)
                if r["data"].get("ref_anuncio")}
    nuevos = actualizados = 0
    for row in rows:
        key = (row["fecha"], row["plataforma"], row["ref_anuncio"])
        row["producto"] = _guess_product(space_id, row.get("campana") or "")
        data = {k: v for k, v in row.items() if v not in (None, "")}
        if key in existing:
            records.update(existing[key]["id"], space_id, {"data": data})
            actualizados += 1
        else:
            records.create(space_id, "dd_gasto_pauta", f"{row.get('anuncio') or row.get('campana') or row['ref_anuncio']} · {row['fecha']}"[:200], data)
            nuevos += 1
    return nuevos, actualizados


def _purchases(actions) -> float:
    best = 0.0
    for a in actions or []:
        if a.get("action_type") in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase", "onsite_web_purchase"):
            try:
                best = max(best, float(a.get("value") or 0))
            except ValueError:
                pass
    return best


@router.post("/sync/ads")
def sync_ads(body: dict = Body(...)):
    conn, plat, cuenta = _conn(body.get("connection_id")), body.get("plataforma"), str(body.get("cuenta") or "").strip()
    if plat not in ("meta", "tiktok") or not cuenta:
        raise ValueError("Indica la plataforma (meta o tiktok) y el ID de la cuenta publicitaria.")
    dias = max(1, min(30, int(body.get("dias") or 7)))
    desde, hasta = (date.today() - timedelta(days=dias - 1)).isoformat(), date.today().isoformat()
    sid, rows = _space("G01", body.get("space")), []
    if plat == "meta":
        cuenta = cuenta if cuenta.startswith("act_") else f"act_{cuenta}"
        res = _read(conn, GASTO_META, {"cuenta_publicitaria": cuenta, "rango": f'{{"since":"{desde}","until":"{hasta}"}}'})
        if not isinstance(res.get("data"), list):
            raise ValueError("Meta no devolvió datos de rendimiento. Comprueba el ID de la cuenta y el permiso ads_read del token.")
        for r in res["data"]:
            rows.append({"fecha": r.get("date_start"), "plataforma": "meta", "cuenta": cuenta, "campana": r.get("campaign_name"), "anuncio": r.get("ad_name"),
                         "ref_campana": r.get("campaign_id"), "ref_anuncio": r.get("ad_id"), "gasto": r.get("spend"), "impresiones": r.get("impressions"),
                         "clics": r.get("clicks"), "compras": _purchases(r.get("actions"))})
        truncado = bool((res.get("paging") or {}).get("next"))
    else:
        res = _read(conn, PRESETS["tiktok_ads"]["actions"][0], {"cuenta_publicitaria": cuenta, "desde": desde, "hasta": hasta})
        lista = (res.get("data") or {}).get("list")
        if res.get("code") not in (0, None) or not isinstance(lista, list):
            raise ValueError(f"TikTok no devolvió el informe: {str(res.get('message') or 'respuesta inesperada')[:200]}")
        for r in lista:
            d, m = r.get("dimensions") or {}, r.get("metrics") or {}
            rows.append({"fecha": str(d.get("stat_time_day") or "")[:10], "plataforma": "tiktok", "cuenta": cuenta, "campana": m.get("campaign_name"), "anuncio": m.get("ad_name"),
                         "ref_campana": m.get("campaign_id"), "ref_anuncio": d.get("ad_id"), "gasto": m.get("spend"), "impresiones": m.get("impressions"),
                         "clics": m.get("clicks"), "compras": m.get("conversion")})
        truncado = ((res.get("data") or {}).get("page_info") or {}).get("total_page", 1) > 1
    rows = [r for r in rows if r["fecha"] and r["ref_anuncio"]]
    nuevos, actualizados = _upsert_spend(sid, rows)
    db.audit("dd_sync_ads", conn["id"], {"plataforma": plat, "filas": len(rows), "nuevos": nuevos})
    sin = sum(1 for r in rows if not r.get("producto"))
    return {"filas": len(rows), "nuevos": nuevos, "actualizados": actualizados, "periodo": f"{desde} a {hasta}",
            "nota": ("Hay más páginas de resultados: reduce los días para traerlo completo. " if truncado else "") +
                    (f"{sin} filas quedaron sin producto: pon el nombre del producto en la campaña o complétalo en «Datos» para cruzar la utilidad." if sin else "")}


@router.post("/ads/pause")
def ads_pause(body: dict = Body(...)):
    conn, plat, obj = _conn(body.get("connection_id")), body.get("plataforma"), str(body.get("objeto_id") or "").strip()
    if plat not in ("meta", "tiktok") or not re.fullmatch(r"\d{5,30}", obj):
        raise ValueError("Indica la plataforma y el ID numérico de la campaña, conjunto o anuncio.")
    reanudar = bool(body.get("reanudar")) and plat == "meta"
    action = PRESETS["meta_ads"]["actions"][3 if reanudar else 2] if plat == "meta" else PRESETS["tiktok_ads"]["actions"][1]
    variables = {"objeto_id": obj}
    if plat == "tiktok":
        if not str(body.get("cuenta") or "").strip():
            raise ValueError("TikTok necesita el ID del anunciante.")
        variables["cuenta_publicitaria"] = str(body["cuenta"]).strip()
    nombre = str(body.get("nombre") or obj)[:80]
    return request_write(conn, action, variables, _space("M01", body.get("space")), f"{'Reanudar' if reanudar else 'Pausar'} en {plat}: {nombre}")


# ---------- WhatsApp: solo envío, siempre con aprobación

@router.post("/whatsapp/send")
def whatsapp_send(body: dict = Body(...)):
    conn = _conn(body.get("connection_id"))
    tel, msg, numero = re.sub(r"\D", "", str(body.get("telefono") or "")), str(body.get("mensaje") or "").strip(), re.sub(r"\D", "", str(body.get("numero_id") or ""))
    if not (8 <= len(tel) <= 15) or not msg or not numero:
        raise ValueError("Indica el ID del número de WhatsApp Business, el teléfono con código de país y el mensaje.")
    out = request_write(conn, PRESETS["whatsapp"]["actions"][0], {"numero_id": numero, "telefono": tel, "mensaje": msg[:4000]}, _space("V05", body.get("space")), f"WhatsApp a …{tel[-4:]}")
    if body.get("record_id"):
        rec = records.get(str(body["record_id"]), out["job"]["space_id"])
        if rec and rec["kind"] == "dd_mensaje":
            records.update(rec["id"], rec["space_id"], {"data": {"borrador": msg}})
    return out


# ---------- Operador logístico (Dropi u otro): su exportación actualiza estados, fletes y liquidaciones

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


COLS = {
    "ref": ("id", "id pedido", "pedido", "numero de pedido", "numero pedido", "orden", "numero de orden", "id orden", "order", "order id", "nombre del pedido", "referencia"),
    "estado": ("estado", "estatus", "status", "estado del pedido", "estado de la orden", "estado guia", "estado de la guia"),
    "fecha": ("fecha", "fecha de pedido", "fecha pedido", "fecha de creacion", "fecha creacion", "created at", "fecha de orden"),
    "ciudad": ("ciudad", "ciudad destino", "ciudad de destino", "municipio"),
    "producto": ("producto", "productos", "nombre del producto", "nombre producto", "articulo"),
    "unidades": ("cantidad", "unidades", "cantidad de productos"),
    "precio": ("valor", "total", "valor total", "total de la orden", "valor de la orden", "valor del pedido", "precio", "valor recaudo", "valor a recaudar", "total orden"),
    "costo_producto": ("costo", "costo producto", "costo del producto", "precio proveedor", "valor proveedor", "costo proveedor"),
    "flete": ("flete", "valor flete", "costo flete", "precio flete", "costo de envio", "valor envio", "envio"),
    "flete_devolucion": ("flete devolucion", "costo devolucion", "valor devolucion", "costo devolucion flete"),
    "comision": ("comision", "comisiones", "comision plataforma", "fee"),
    "transportadora": ("transportadora", "transportador", "carrier", "empresa de envio"),
    "valor_liquidado": ("valor liquidado", "liquidado", "valor pagado", "pagado", "utilidad pagada", "ganancia", "valor transferido", "transferido"),
}


def _estado(texto: str) -> str | None:
    t = _norm(texto)
    for clave, estado in (("entregad", "entregado"), ("devol", "devuelto"), ("rechaz", "devuelto"), ("cancel", "cancelado"), ("anulad", "cancelado"),
                          ("transito", "en_transito"), ("despach", "en_transito"), ("reparto", "en_transito"), ("novedad", "en_transito"), ("guia", "en_transito"),
                          ("oficina", "en_transito"), ("confirm", "confirmado"), ("pendiente", "pendiente")):
        if clave in t:
            return estado
    return None


def _money(v) -> float | None:
    s = re.sub(r"[^\d,.\-]", "", str(v or ""))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def import_logistics(space_id: str, text: str, commit: bool) -> dict:
    sample = text[:4000]
    delim = max(";,\t|", key=sample.count)
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=delim))
    if len(rows) < 2:
        raise ValueError("El archivo no tiene filas. Exporta los pedidos como CSV desde tu operador logístico.")
    head = [_norm(h) for h in rows[0]]
    col = {}
    for campo, alias in COLS.items():
        idx = next((i for i, h in enumerate(head) if h in alias), None)
        if idx is not None:
            col[campo] = idx
    if "ref" not in col or "estado" not in col:
        raise ValueError("No se reconocieron las columnas del ID del pedido y del estado. Columnas encontradas: " + ", ".join(rows[0][:25]))
    existing = {str(o["data"].get("ref") or o["title"]).strip().lstrip("#"): o for o in records.list_records(space_id, "dd_pedido", limit=50000)}
    liq = {l["data"].get("ref_pedido") for l in records.list_records(space_id, "dd_liquidacion", limit=50000)}
    out = {"filas": 0, "actualizados": 0, "nuevos": 0, "liquidaciones": 0, "sin_estado": 0}
    for r in rows[1:20001]:
        get = lambda c: (r[col[c]].strip() if c in col and col[c] < len(r) else "")
        ref = get("ref").lstrip("#")
        if not ref:
            continue
        out["filas"] += 1
        estado = _estado(get("estado"))
        if not estado:
            out["sin_estado"] += 1
        data = {k: v for k, v in {"ciudad": get("ciudad"), "producto": get("producto"), "fecha": get("fecha")[:10] if re.match(r"\d{4}-\d{2}-\d{2}", get("fecha")) else "",
                                  **{k: _money(get(k)) for k in ("precio", "costo_producto", "flete", "flete_devolucion", "comision", "unidades")}}.items() if v not in (None, "")}
        prev = existing.get(ref)
        if prev:
            out["actualizados"] += 1
            if commit:
                # Lo que ya estaba cargado a mano no se pisa con vacíos; el estado logístico sí manda.
                records.update(prev["id"], space_id, {**({"status": estado} if estado else {}), "data": {k: v for k, v in data.items() if k not in ("producto", "fecha") or not prev["data"].get(k)}})
        else:
            out["nuevos"] += 1
            if commit:
                records.create(space_id, "dd_pedido", ref, {"ref": ref, **data}, status=estado or "pendiente")
        pagado = _money(get("valor_liquidado"))
        if pagado and ref not in liq:
            out["liquidaciones"] += 1
            if commit:
                records.create(space_id, "dd_liquidacion", f"Liquidación {ref}", {"ref_pedido": ref, "valor_liquidado": pagado, "valor_recaudado": _money(get("precio")),
                                                                                  "transportadora": get("transportadora")}, status="liquidada")
                liq.add(ref)
    out["columnas"] = {k: rows[0][i] for k, i in col.items()}
    out["ignoradas"] = [h for i, h in enumerate(rows[0]) if i not in col.values()][:30]
    out["guardado"] = commit
    if commit:
        db.audit("dd_import_logistica", space_id, {k: out[k] for k in ("filas", "actualizados", "nuevos", "liquidaciones")})
    return out


@router.post("/import/logistica")
def import_logistica(file: UploadFile = File(...), commit: str = Form(""), space: str = Form("")):
    raw = file.file.read(30_000_000)
    if (file.filename or "").lower().endswith((".xlsx", ".xls")):
        raise ValueError("Sube el archivo en CSV: en Excel, «Guardar como» → CSV (delimitado por comas).")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return import_logistics(_space("G01", space or None), text, commit == "1")


# ---------- G04: borrador completo en Shopify a partir de una ficha APROBADA

_NO_PUBLICAR = {"comprobaciones", "supuestos", "limitaciones", "preguntas", "cumplimiento", "elementos", "indicadores", "alertas", "resumen"}


def _inline(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(t))


def to_html(sections: list[dict]) -> str:
    out = []
    for s in sections:
        if s["key"] in _NO_PUBLICAR or s["key"].startswith("calculo") or s["type"] != "text" or not s["body"].strip():
            continue
        out.append(f"<h2>{html.escape(s['title'])}</h2>")
        lista = []
        for line in s["body"].splitlines() + [""]:
            item = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)", line)
            if item:
                lista.append(f"<li>{_inline(item.group(1))}</li>")
                continue
            if lista:
                out.append("<ul>" + "".join(lista) + "</ul>")
                lista = []
            if line.strip():
                h = re.match(r"^#{1,4}\s+(.*)", line)
                out.append(f"<h3>{_inline(h.group(1))}</h3>" if h else f"<p>{_inline(line.strip())}</p>")
    return "\n".join(out)


@router.post("/publish/shopify")
def publish_shopify(body: dict = Body(...)):
    conn = _conn(body.get("connection_id"))
    sid = _space("G04", body.get("space"))
    d = review.detail(str(body.get("deliverable_id") or ""), sid)
    if not d or d["kind"] != "dd" or d["ref_id"] != "G04":
        raise KeyError("entregable")
    if d["status"] != "aprobado":
        raise ValueError("Aprueba primero la ficha en Revisión: solo se publica una versión aprobada.")
    content = d["version"]["content"]
    cuerpo = to_html(content["sections"])
    if len(cuerpo) < 80:
        raise ValueError("La ficha aprobada no tiene secciones de texto que publicar.")
    precio = body.get("precio")
    try:
        precio = f"{float(str(precio).replace(',', '.')):.2f}"
    except (TypeError, ValueError):
        raise ValueError("Indica el precio de venta.")
    titulo = str(body.get("titulo") or d["title"].split(" · ", 1)[-1]).strip()[:250]
    imagen = str(body.get("imagen") or "").strip()
    if imagen and not re.match(r"^https://\S+$", imagen):
        raise ValueError("La imagen debe ser una URL https pública.")
    variables = {"titulo": titulo, "descripcion": cuerpo, "precio": precio, "meta_titulo": titulo[:70], "meta_descripcion": re.sub(r"\s+", " ", content.get("summary") or titulo)[:300]}
    if imagen:
        variables["imagen"] = imagen
    out = request_write(conn, SHOPIFY_EXTRA[1 if imagen else 0], variables, sid, f"Shopify: borrador de «{titulo[:60]}» (ficha v{d['version']['version']})")
    return {**out, "secciones": cuerpo.count("<h2>"), "caracteres": len(cuerpo)}


# ---------- M06: producir el video o la imagen de un creativo APROBADO (gasta saldo: solo a petición del dueño)

@router.post("/creativos/{rec_id}/generar")
def creativo_generar(rec_id: str, body: dict = Body(default={})):
    rec = records.get(rec_id)
    if not rec or rec["kind"] != "dd_creativo":
        raise KeyError(rec_id)
    if rec["status"] not in ("aprobado", "publicado", "ganador"):
        raise ValueError("Aprueba primero el creativo (estado «aprobado»): no se produce nada sin revisar.")
    d, kind = rec["data"], "image" if body.get("kind") == "image" else "video"
    prompt = "\n".join(x for x in [f"Anuncio vertical para {d.get('producto')}." if d.get("producto") else "", f"Formato: {d['formato']}." if d.get("formato") else "",
                                    f"Primeros segundos: {d['hook']}" if d.get("hook") else "", d.get("guion") or "", str(body.get("indicacion") or "")] if x).strip()
    if len(prompt) < 20:
        raise ValueError("El creativo necesita hook o guion para poder producirse.")
    job, created = jobs.enqueue(rec["space_id"], "media_generate", f"M06 · {'Video' if kind == 'video' else 'Imagen'} de {rec['title']}"[:200],
                                {"kind": kind, "prompt": prompt[:3000], "aspect": "9:16", "seconds": max(2, min(20, int(body.get("seconds") or 8))), "module": "M06", "record_id": rec_id})
    return {"job": job, "created": created}


# ---------- C04: recortar el clip de verdad con FFmpeg

def _secs(v) -> float:
    s = str(v or "").strip().replace(",", ".")
    try:
        parts = [float(p) for p in s.split(":")]
    except ValueError:
        raise JobError("Indica los tiempos en segundos o como mm:ss.")
    if not parts or len(parts) > 3:
        raise JobError("Indica los tiempos en segundos o como mm:ss.")
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


@handler("dd_clip")
def dd_clip(ctx):
    p = ctx.params
    src = files.get(str(p.get("file_id") or ""), ctx.space_id)
    if not src or not src["name"].lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".m4v")):
        raise JobError("Elige un video subido a este espacio (mp4, mov, mkv o webm).")
    ini, fin = _secs(p.get("inicio")), _secs(p.get("fin"))
    dur = float(video_h.probe(files.path_of(src)).get("duration") or 0)
    if not (0 <= ini < fin) or fin - ini > 600 or (dur and ini >= dur):
        raise JobError("El inicio debe ser menor que el fin, dentro del video, y el clip no puede superar 10 minutos.")
    fin = min(fin, dur) if dur else fin
    work = video_h._workdir(ctx)
    out = work / "clip.mp4"
    vf = ["-vf", "crop='min(iw,ih*9/16)':ih,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"] if p.get("vertical") else []
    ctx.stage("recorte", 0.3, f"Recortando de {ini:.1f} s a {fin:.1f} s")
    code, err = ctx.run_proc([video_h.binary("ffmpeg"), "-v", "error", "-y", "-ss", f"{ini:.3f}", "-i", str(files.path_of(src)), "-t", f"{fin - ini:.3f}", *vf,
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", str(out)], timeout=1500)
    if code != 0 or not out.is_file():
        raise JobError(f"FFmpeg no pudo recortar el clip: {err[-300:]}")
    nombre = re.sub(r"[^\w\- ]+", "", str(p.get("titulo") or f"{src['name'].rsplit('.', 1)[0]} {int(ini)}-{int(fin)}"))[:80].strip() or "clip"
    f = files.adopt(ctx.space_id, out, f"{nombre}.mp4", job_id=ctx.id, meta={"media": "video", "origen": src["id"], "inicio": ini, "fin": fin, "vertical": bool(p.get("vertical"))})
    d = review.create(ctx.space_id, "dd", f"C04 · Clip: {nombre}", {"summary": f"Clip de {fin - ini:.1f} s recortado de «{src['name']}».", "sections": [
        {"key": "resumen", "title": "Resumen", "type": "text", "body": f"Recortado de {ini:.1f} s a {fin:.1f} s{' en vertical 9:16' if p.get('vertical') else ''}, sin IA."},
        {"key": "archivos", "title": "Archivo", "type": "files", "items": [{"file_id": f["id"], "name": f["name"], "note": "Clip"}]}],
        "meta": {"modulo": "C04", "accion": "recortar"}}, author="doomsday", job_id=ctx.id, ref_id="C04")
    return {"mensaje": "Clip recortado", "deliverable_ids": [d["id"]], "file_ids": [f["id"]]}


@router.post("/clip")
def clip(body: dict = Body(...)):
    sid = _space("C04", body.get("space"))
    if not files.get(str(body.get("file_id") or ""), sid):
        raise ValueError("Elige un video subido a este espacio.")
    job, created = jobs.enqueue(sid, "dd_clip", f"C04 · Recortar clip {body.get('inicio')}–{body.get('fin')}",
                                {"module": "C04", "file_id": body["file_id"], "inicio": body.get("inicio"), "fin": body.get("fin"), "vertical": bool(body.get("vertical")), "titulo": body.get("titulo")})
    return {"job": job, "created": created}


# ---------- V06: un espacio por cliente (cada cliente ve solo lo suyo con un usuario de rol «cliente»)

@router.get("/clients")
def clients():
    return db.query("SELECT s.id, s.name, s.created_at, (SELECT COUNT(*) FROM deliverables d WHERE d.space_id=s.id AND d.archived=0) entregables "
                    "FROM spaces s WHERE s.kind='cliente' AND s.archived=0 ORDER BY s.created_at")


@router.post("/clients")
def client_create(body: dict = Body(...)):
    name = str(body.get("nombre") or "").strip()
    if len(name) < 2:
        raise ValueError("Indica el nombre del cliente.")
    if db.one("SELECT id FROM spaces WHERE kind='cliente' AND name=? AND archived=0", (name,)):
        raise ValueError("Ya existe un espacio para ese cliente.")
    from jarvis.util import new_id, now_iso
    sid = new_id("esp")
    db.execute("INSERT INTO spaces(id,name,kind,ai_policy,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (sid, name[:120], "cliente", "nube_permitida", "Cliente B2B (Doomsday)", now_iso(), now_iso()))
    db.audit("dd_cliente_espacio", sid, {"nombre": name})
    return {"id": sid, "name": name}


LAYER_KIND = {k: v[1] for k, v in catalog.LAYERS.items()}
