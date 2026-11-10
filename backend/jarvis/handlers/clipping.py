"""Clipping: importación de campañas desde URL y cálculo honesto de estados (vistas, estimado, aprobado, cobrado)."""
from __future__ import annotations
from datetime import date

from pydantic import BaseModel, Field

from .. import records, webfetch
from ..jobs import JobError
from ..worker import handler
from .common import ask_json, available, quote_in_text, save_source

STALE_DAYS = 14


class CampaignFields(BaseModel):
    name: str
    organizer: str = ""
    cpm_usd: float | None = None
    cpm_quote: str = Field(default="", description="Cita textual donde aparece el CPM")
    budget_usd: float | None = None
    budget_quote: str = ""
    platforms: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    valid_views_rules: str = ""
    restrictions: str = ""
    approval_process: str = ""
    min_payout_usd: float | None = None
    payout_method: str = ""


@handler("clipping_import_url")
def clipping_import_url(ctx) -> dict:
    url = (ctx.params.get("url") or "").strip()
    if not url:
        raise JobError("Indica la URL de la campaña.")
    ctx.stage("lectura", 0.2, "Leyendo la página de la campaña")
    page = webfetch.fetch_page(url)
    if page["status"] != "ok":
        save_source(ctx, url=url, title=url, provider="URL aportada", status=page["status"], note=page.get("note", ""))
        raise JobError(f"No se pudo leer la página ({page.get('note')}). Registra la campaña manualmente.")
    src = save_source(ctx, url=page["url"], title=page.get("title") or url, provider="URL aportada", text=page["text"], snippet=page["text"][:300])
    today = date.today().isoformat()
    data = {"source_url": page["url"], "source_date": today, "rules_updated": today}
    title = (page.get("title") or url)[:150]
    note = "Importada sin extracción automática: completa los campos a mano."
    if available(ctx, "extraccion"):
        ctx.stage("extraccion", 0.6, "Extrayendo condiciones")
        system = ("Extrae las condiciones de una campaña de clipping remunerado a partir del texto de su página. Si un dato no aparece, déjalo vacío o null. "
                  "Para CPM y presupuesto incluye la cita textual exacta donde aparecen. No calcules ni supongas valores.")
        f, _ = ask_json(ctx, CampaignFields, system=system, user=f"<fuente id=\"S1\" url=\"{page['url']}\">\n{page['text'][:6000].replace('</fuente>', '')}\n</fuente>",
                        max_tokens=900, prompt_version="clipping-v1")
        title = f.name[:150] or title
        unverified = []
        if f.cpm_usd is not None:
            if quote_in_text(f.cpm_quote, page["text"]):
                data["cpm_usd"] = f.cpm_usd
            else:
                unverified.append("CPM")
        if f.budget_usd is not None:
            if quote_in_text(f.budget_quote, page["text"]):
                data.update(budget_usd=f.budget_usd, budget_updated=today)
            else:
                unverified.append("presupuesto")
        data.update(organizer=f.organizer, platforms=f.platforms, countries=f.countries, valid_views_rules=f.valid_views_rules, restrictions=f.restrictions,
                    approval_process=f.approval_process, payout_method=f.payout_method)
        if f.min_payout_usd is not None:
            data["min_payout_usd"] = f.min_payout_usd
        note = "Extraída automáticamente; verifica cada campo contra la fuente." + (f" No se pudo verificar: {', '.join(unverified)} (se dejó vacío)." if unverified else "")
    data["notes"] = f"{note} Fuente {src['id']}."
    rec = records.create(ctx.space_id, "campaign", title, {k: v for k, v in data.items() if v not in (None, "", [])}, project_id=ctx.params.get("project_id"))
    return {"mensaje": f"Campaña «{title}» registrada. {note}", "record_ids": [rec["id"]]}


def _days_since(iso: str | None) -> int | None:
    try:
        return (date.today() - date.fromisoformat(iso[:10])).days
    except (TypeError, ValueError):
        return None


def summary(space_id: str, min_cpm: float | None = None) -> dict:
    """Comparador y totales. Los cuatro estados se informan por separado y nunca se suman entre sí."""
    campaigns = records.list_records(space_id, "campaign")
    clips = records.list_records(space_id, "clip")
    rows, alerts = [], []
    totals = {"vistas_totales": 0.0, "vistas_elegibles": 0.0, "ingreso_estimado_usd": 0.0, "aprobado_usd": 0.0, "cobrado_usd": 0.0}
    for c in campaigns:
        d = c["data"]
        mine = [k for k in clips if k["data"].get("campaign_id") == c["id"]]
        views_total = sum(k["data"].get("views_total") or 0 for k in mine)
        eligible_known = [k for k in mine if k["data"].get("views_eligible") is not None]
        views_eligible = sum(k["data"].get("views_eligible") or 0 for k in eligible_known)
        cpm = d.get("cpm_usd")
        # El estimado parte solo de vistas elegibles informadas; nunca de vistas totales.
        estimated = round(views_eligible / 1000 * cpm, 2) if cpm and eligible_known else None
        if estimated is not None and d.get("budget_usd"):
            estimated = min(estimated, d["budget_usd"])
        approved = sum(k["data"].get("approved_usd") or 0 for k in mine)
        paid = sum(k["data"].get("paid_usd") or 0 for k in mine)
        missing = [lab for key, lab in (("cpm_usd", "CPM"), ("budget_usd", "presupuesto"), ("platforms", "plataformas"), ("valid_views_rules", "regla de vistas válidas"),
                                        ("approval_process", "proceso de aprobación"), ("min_payout_usd", "retiro mínimo"), ("end_date", "fecha de fin")) if d.get(key) in (None, "", [])]
        c_alerts = []
        if missing:
            c_alerts.append({"tipo": "datos_ausentes", "texto": "Faltan datos: " + ", ".join(missing)})
        age = _days_since(d.get("budget_updated"))
        if d.get("budget_usd") and (age is None or age > STALE_DAYS):
            c_alerts.append({"tipo": "presupuesto_desactualizado", "texto": f"Presupuesto sin actualizar desde hace {age if age is not None else 'fecha desconocida'} días; requiere actualización manual."})
        r_age = _days_since(d.get("rules_updated"))
        if c["status"] == "activa" and (r_age is None or r_age > STALE_DAYS):
            c_alerts.append({"tipo": "reglas_sin_revisar", "texto": "Reglas no revisadas recientemente; pueden haber cambiado."})
        rejected = [k for k in mine if k["data"].get("review_status") == "rechazado"]
        if rejected:
            c_alerts.append({"tipo": "rechazo", "texto": f"{len(rejected)} clip(s) rechazados: " + "; ".join(filter(None, (k["data"].get("rejection_reason") for k in rejected)))[:200]})
        if approved - paid > 0.005:
            c_alerts.append({"tipo": "saldo_pendiente", "texto": f"Saldo aprobado sin cobrar: {approved - paid:.2f} USD."})
        if d.get("end_date") and (_days_since(d["end_date"]) or -1) > 0 and c["status"] == "activa":
            c_alerts.append({"tipo": "datos_ausentes", "texto": "La fecha de fin ya pasó y la campaña sigue marcada como activa."})
        rows.append({"id": c["id"], "titulo": c["title"], "estado": c["status"], "organizador": d.get("organizer"), "cpm_usd": cpm, "presupuesto_usd": d.get("budget_usd"),
                     "plataformas": d.get("platforms") or [], "paises": d.get("countries") or [], "fin": d.get("end_date"), "retiro_minimo_usd": d.get("min_payout_usd"),
                     "fuente": d.get("source_url"), "fecha_fuente": d.get("source_date"), "cumple_cpm": (cpm >= min_cpm) if (cpm is not None and min_cpm) else None,
                     "clips": len(mine), "vistas_totales": views_total, "vistas_elegibles": views_eligible if eligible_known else None,
                     "ingreso_estimado_usd": estimated, "aprobado_usd": approved, "cobrado_usd": paid, "pendiente_cobro_usd": round(max(approved - paid, 0), 2),
                     "alertas": c_alerts})
        alerts += [dict(a, campana=c["title"], campana_id=c["id"]) for a in c_alerts]
        totals["vistas_totales"] += views_total
        totals["vistas_elegibles"] += views_eligible
        totals["ingreso_estimado_usd"] += estimated or 0
        totals["aprobado_usd"] += approved
        totals["cobrado_usd"] += paid
    rows.sort(key=lambda r: (r["cpm_usd"] is None, -(r["cpm_usd"] or 0)))
    return {"campanas": rows, "alertas": alerts, "totales": {k: round(v, 2) for k, v in totals.items()}, "min_cpm": min_cpm,
            "nota": "Vistas totales, vistas elegibles, ingreso estimado, aprobado y cobrado son estados distintos del mismo dinero; no se suman. "
                    "El estimado usa solo vistas elegibles informadas × CPM y no es un ingreso confirmado. Los datos se actualizan manualmente: no hay conector automático."}
