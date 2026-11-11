"""Router por capacidades con política FREE / LOCAL FIRST.

- Orden: local → nube sin costo declarado → pago (solo si el usuario activó el gasto y hay presupuesto).
- Nunca cambia a pago por su cuenta ni usa endpoints no configurados.
- Caché por espacio + proveedor + modelo + versión de instrucciones + contenido, con TTL.
- Reserva de presupuesto estimado antes de llamar y conciliación con los tokens reportados.
"""
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from datetime import timedelta

from . import connections, db, secrets_store
from .providers import llm as llm_api, search as search_api, voice as voice_api
from .providers import media as media_api
from .providers.base import ProviderError, SearchHit
from .util import canonical_json, dumps, iso_in, loads, now, now_iso, sha256_text

DEFAULT_LIMITS = {"max_calls": 40, "max_tokens": 200_000, "max_cost_usd": 1.0, "max_seconds": 1800}
RETRY_BACKOFF = (1.5, 4.0)
SLEEP = time.sleep  # sustituible en pruebas

_semaphores: dict[str, threading.BoundedSemaphore] = {}
_sem_lock = threading.Lock()


class RouterError(Exception):
    """kind: needs_config | quota | policy | limit"""

    def __init__(self, kind: str, message: str, resume_at: str | None = None, reasons: list[str] | None = None):
        super().__init__(message)
        self.kind, self.message, self.resume_at, self.reasons = kind, message, resume_at, reasons or []


@dataclass
class Ctx:
    space_id: str
    job_id: str | None = None
    limits: dict = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    calls: int = 0
    tokens: int = 0
    cost: float = 0.0
    cached_hits: int = 0
    used: list = field(default_factory=list)

    def check(self) -> None:
        lim = self.limits
        if self.calls >= lim.get("max_calls", DEFAULT_LIMITS["max_calls"]):
            raise RouterError("limit", f"Se alcanzó el límite de {lim.get('max_calls')} llamadas a proveedores para este trabajo.")
        if self.tokens >= lim.get("max_tokens", DEFAULT_LIMITS["max_tokens"]):
            raise RouterError("limit", "Se alcanzó el límite de tokens configurado para este trabajo.")
        if self.cost > lim.get("max_cost_usd", DEFAULT_LIMITS["max_cost_usd"]):
            raise RouterError("limit", "Se alcanzó el límite de costo estimado configurado para este trabajo.")

    def summary(self) -> dict:
        return {"llamadas": self.calls, "tokens": self.tokens, "costo_estimado_usd": round(self.cost, 6),
                "respuestas_en_cache": self.cached_hits, "conexiones": sorted(set(self.used))}


def _sem(conn: dict) -> threading.BoundedSemaphore:
    with _sem_lock:
        if conn["id"] not in _semaphores:
            _semaphores[conn["id"]] = threading.BoundedSemaphore(max(1, int(conn.get("concurrency") or 1)))
        return _semaphores[conn["id"]]


def _space(space_id: str) -> dict:
    sp = db.one("SELECT * FROM spaces WHERE id=?", (space_id,))
    if not sp:
        raise RouterError("policy", "El espacio indicado no existe.")
    return sp


def month_spend(conn_id: str) -> float:
    start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    row = db.one("SELECT COALESCE(SUM(est_cost_usd),0) s FROM usage WHERE connection_id=? AND ts>=? AND state IN ('ok','reservado')", (conn_id, start))
    return float(row["s"])


def _count_since(conn_id: str, since: str) -> int:
    row = db.one("SELECT COUNT(*) c FROM usage WHERE connection_id=? AND ts>=? AND cached=0 AND state IN ('ok','reservado')", (conn_id, since))
    return int(row["c"])


def candidates(space_id: str, capability: str) -> tuple[list[dict], list[str], str | None]:
    """Devuelve (conexiones utilizables en orden, motivos de exclusión, próxima reanudación por cuota)."""
    space = _space(space_id)
    if space["ai_policy"] == "sin_ia":
        raise RouterError("policy", f"El espacio «{space['name']}» tiene la IA desactivada por política de datos.")
    allow_paid = bool(db.get_setting("allow_paid", False))
    usable, reasons, resume = [], [], None
    for conn in connections.list_all():
        if capability not in conn["capabilities"]:
            continue
        name = conn["name"]
        status = connections.effective_status(conn)
        local = connections.is_local(conn)
        if status in ("no_configurada", "credencial_invalida", "sin_permiso", "no_compatible", "condiciones_pendientes", "deshabilitada"):
            reasons.append(f"{name}: {connections.STATUS_LABELS[status]}")
            continue
        if status == "cuota_agotada":
            reasons.append(f"{name}: Cuota agotada hasta {conn.get('blocked_until') or 'nuevo aviso'}")
            resume = min(filter(None, [resume, conn.get("blocked_until")]), default=None)
            continue
        if space["ai_policy"] == "solo_local" and not local:
            reasons.append(f"{name}: el espacio «{space['name']}» solo permite proveedores locales")
            continue
        if space["kind"] == "personal" and not local and conn["data_policy"] != "todo":
            reasons.append(f"{name}: no autorizada para datos personales")
            continue
        if conn["is_paid"]:
            if not allow_paid:
                reasons.append(f"{name}: es de pago y el gasto está desactivado")
                continue
            budget = conn.get("monthly_budget_usd")
            if not budget:
                reasons.append(f"{name}: es de pago y no tiene presupuesto mensual definido")
                continue
            if month_spend(conn["id"]) >= budget:
                reasons.append(f"{name}: presupuesto mensual estimado agotado")
                continue
        if conn.get("rpm_limit") and _count_since(conn["id"], (now() - timedelta(seconds=60)).isoformat(timespec="seconds")) >= conn["rpm_limit"]:
            reasons.append(f"{name}: límite por minuto configurado alcanzado")
            resume = min(filter(None, [resume, iso_in(60)]))
            continue
        if conn.get("daily_limit"):
            day = now().replace(hour=0, minute=0, second=0, microsecond=0)
            if _count_since(conn["id"], day.isoformat(timespec="seconds")) >= conn["daily_limit"]:
                reasons.append(f"{name}: límite diario configurado alcanzado")
                resume = min(filter(None, [resume, (day + timedelta(days=1)).isoformat(timespec="seconds")]))
                continue
        usable.append(conn)
    usable.sort(key=lambda c: (0 if connections.is_local(c) else 1 if not c["is_paid"] else 2, c["created_at"]))
    return usable, reasons, resume


def availability(space_id: str) -> dict:
    out = {}
    for cap in connections.CAPABILITIES:
        try:
            usable, reasons, _ = candidates(space_id, cap)
            out[cap] = {"disponible": bool(usable), "conexiones": [c["name"] for c in usable], "motivos": reasons}
        except RouterError as exc:
            out[cap] = {"disponible": False, "conexiones": [], "motivos": [exc.message]}
    return out


def _none_available(capability: str, reasons: list[str], resume: str | None) -> RouterError:
    label = connections.CAPABILITIES.get(capability, capability)
    if resume and reasons:
        return RouterError("quota", f"Sin capacidad disponible para «{label}» por cuota o límites. " + "; ".join(reasons), resume_at=resume, reasons=reasons)
    if reasons:
        return RouterError("needs_config", f"Ninguna conexión utilizable para «{label}»: " + "; ".join(reasons) + ". Revisa Conexiones.", reasons=reasons)
    return RouterError("needs_config", f"No hay ninguna conexión configurada con la capacidad «{label}». Añádela en Conexiones.")


def _cache_get(key: str):
    row = db.one("SELECT value, created_at, expires_at FROM cache WHERE key=?", (key,))
    if not row or (row["expires_at"] and row["expires_at"] <= now_iso()):
        return None
    return loads(row["value"]), row["created_at"]


def _cache_put(key: str, space_id: str, category: str, conn: dict, prompt_version: str, value, ttl_s: float) -> None:
    db.execute("INSERT OR REPLACE INTO cache(key,space_id,category,provider,model,prompt_version,value,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
               (key, space_id, category, conn["provider"], conn.get("model"), prompt_version, dumps(value), now_iso(), iso_in(ttl_s)))


def _dispatch(ctx: Ctx, capability: str, category: str, call, *, est_cost_fn, cost_fn, cache_parts=None, ttl_s=None,
              prompt_version="v1"):
    """call(conn, secret) -> (value_serializable, tokens_in, tokens_out, units, quota)"""
    ctx.check()
    usable, reasons, resume = candidates(ctx.space_id, capability)
    if not usable:
        raise _none_available(capability, reasons, resume)
    for conn in usable:
        key = None
        if ttl_s and cache_parts is not None:
            key = sha256_text(canonical_json([ctx.space_id, category, conn["provider"], conn.get("model"), prompt_version, cache_parts]))
            hit = _cache_get(key)
            if hit:
                value, created = hit
                db.execute("INSERT INTO usage(ts,space_id,job_id,connection_id,provider,model,capability,category,cached,state,cost_basis) VALUES(?,?,?,?,?,?,?,?,1,'ok','caché')",
                           (now_iso(), ctx.space_id, ctx.job_id, conn["id"], conn["provider"], conn.get("model"), capability, category))
                ctx.cached_hits += 1
                return value, {"connection": conn["name"], "provider": conn["provider"], "model": conn.get("model"), "cached": True, "obtained_at": created}
        secret = secrets_store.get_secret(connections.secret_name(conn["id"]))
        est = est_cost_fn(conn)
        if conn["is_paid"] and month_spend(conn["id"]) + est > (conn.get("monthly_budget_usd") or 0):
            reasons.append(f"{conn['name']}: la estimación de este trabajo supera el presupuesto mensual restante")
            continue
        usage_id = db.execute("INSERT INTO usage(ts,space_id,job_id,connection_id,provider,model,capability,category,est_cost_usd,cost_basis,state) VALUES(?,?,?,?,?,?,?,?,?,?, 'reservado')",
                              (now_iso(), ctx.space_id, ctx.job_id, conn["id"], conn["provider"], conn.get("model"), capability, category, est, "reserva estimada"))
        error: ProviderError | None = None
        started = time.monotonic()
        with _sem(conn):
            for attempt in range(len(RETRY_BACKOFF) + 1):
                try:
                    value, t_in, t_out, units, quota = call(conn, secret)
                    error = None
                    break
                except ProviderError as exc:
                    error = exc
                    if exc.kind in ("timeout", "network") and attempt < len(RETRY_BACKOFF):
                        SLEEP(RETRY_BACKOFF[attempt])
                        continue
                    break
        ms = int((time.monotonic() - started) * 1000)
        if error:
            db.execute("UPDATE usage SET state='error', est_cost_usd=0, error=?, duration_ms=? WHERE id=?", (error.message[:300], ms, usage_id))
            connections.record_error(conn, error)
            reasons.append(f"{conn['name']}: {error.message}")
            if error.kind == "quota":
                resume = min(filter(None, [resume, iso_in(error.retry_after or 300)]))
            continue
        cost = cost_fn(conn, t_in, t_out, units)
        basis = "estimado: uso reportado × precio configurado" if cost else ("sin precio configurado" if not connections.is_local(conn) else "ejecución local")
        db.execute("UPDATE usage SET state='ok', tokens_in=?, tokens_out=?, units=?, est_cost_usd=?, cost_basis=?, duration_ms=? WHERE id=?",
                   (t_in, t_out, units, cost, basis, ms, usage_id))
        connections.set_status(conn["id"], "operativa", None, quota=quota or None)
        ctx.calls += 1
        ctx.tokens += t_in + t_out
        ctx.cost += cost
        ctx.used.append(conn["name"])
        if key:
            _cache_put(key, ctx.space_id, category, conn, prompt_version, value, ttl_s)
        return value, {"connection": conn["name"], "provider": conn["provider"], "model": conn.get("model"), "cached": False, "obtained_at": now_iso()}
    raise _none_available(capability, reasons, resume)


def _token_cost(conn: dict, t_in: int, t_out: int, units: float) -> float:
    return (t_in * (conn.get("price_in") or 0) + t_out * (conn.get("price_out") or 0)) / 1_000_000


def _unit_cost(conn: dict, t_in: int, t_out: int, units: float) -> float:
    return units * (conn.get("price_unit") or 0)


def llm(ctx: Ctx, *, system: str, user: str, json_mode: bool = False, max_tokens: int | None = None,
        ttl_s: float | None = None, prompt_version: str = "v1", images=None) -> tuple[str, dict]:
    capability = "vision" if images else ("extraccion" if json_mode else "texto")
    est_in = int(len(system + user) / 3.5)

    def call(conn, secret):
        res = llm_api.chat(conn, secret, system, user, json_mode=json_mode, max_tokens=max_tokens, images=images)
        return res.text, res.tokens_in, res.tokens_out, 1, res.quota

    def est(conn):
        return _token_cost(conn, est_in, int(max_tokens or conn.get("max_tokens") or 2048), 1)

    parts = None if images else [system, user, json_mode, max_tokens]
    return _dispatch(ctx, capability, "texto", call, est_cost_fn=est, cost_fn=_token_cost, cache_parts=parts, ttl_s=ttl_s, prompt_version=prompt_version)


def search(ctx: Ctx, query: str, *, count: int = 8, country: str | None = None, lang: str | None = None,
           freshness: str | None = None, ttl_s: float | None = 6 * 3600) -> tuple[list[SearchHit], dict]:
    def call(conn, secret):
        hits = search_api.web_search(conn, secret, query, count=count, country=country, lang=lang, freshness=freshness)
        return [h.__dict__ for h in hits], 0, 0, 1, {}

    value, meta = _dispatch(ctx, "busqueda", "busqueda", call, est_cost_fn=lambda c: c.get("price_unit") or 0, cost_fn=_unit_cost,
                            cache_parts=[query, count, country, lang, freshness], ttl_s=ttl_s)
    return [SearchHit(**h) for h in value], meta


def transcribe(ctx: Ctx, audio_path, language: str | None = None, minutes: float = 0) -> tuple[dict, dict]:
    def call(conn, secret):
        return voice_api.transcribe(conn, secret, audio_path, language), 0, 0, minutes, {}

    return _dispatch(ctx, "transcripcion", "voz", call, est_cost_fn=lambda c: minutes * (c.get("price_unit") or 0), cost_fn=_unit_cost)


def tts(ctx: Ctx, text: str) -> tuple[bytes, dict]:
    holder = {}

    def call(conn, secret):
        holder["audio"] = voice_api.elevenlabs_tts(conn, secret, text)
        return None, 0, 0, len(text), {}

    _, meta = _dispatch(ctx, "voz", "voz", call, est_cost_fn=lambda c: len(text) * (c.get("price_unit") or 0), cost_fn=_unit_cost)
    return holder["audio"], meta


def image(ctx: Ctx, prompt: str, *, aspect: str = "1:1", n: int = 1, wait=lambda s, p: None) -> tuple[list, dict]:
    holder = {}

    def call(conn, secret):
        holder["items"] = media_api.image(conn, secret, prompt, aspect=aspect, n=n, wait=wait)
        return None, 0, 0, len(holder["items"]), {}

    _, meta = _dispatch(ctx, "imagen", "medios", call, est_cost_fn=lambda c: n * (c.get("price_unit") or 0), cost_fn=_unit_cost)
    return holder["items"], meta


def video(ctx: Ctx, prompt: str, *, aspect: str = "16:9", seconds: int = 4, wait=lambda s, p: None) -> tuple[tuple, dict]:
    """El precio por unidad de la conexión se interpreta como precio por segundo de video."""
    holder = {}

    def call(conn, secret):
        holder["item"] = media_api.video(conn, secret, prompt, aspect=aspect, seconds=seconds, wait=wait)
        return None, 0, 0, seconds, {}

    _, meta = _dispatch(ctx, "video", "medios", call, est_cost_fn=lambda c: seconds * (c.get("price_unit") or 0), cost_fn=_unit_cost)
    return holder["item"], meta


def usage_summary() -> dict:
    start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    by_cat = db.query("""SELECT category, COUNT(*) llamadas, SUM(cached) en_cache, SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out,
                         SUM(est_cost_usd) costo_estimado_usd FROM usage WHERE ts>=? AND state='ok' GROUP BY category""", (start,))
    by_conn = db.query("""SELECT u.connection_id, c.name, c.provider, c.is_paid, c.monthly_budget_usd, c.rpm_limit, c.daily_limit, c.confirmed_quota,
                          COUNT(*) llamadas, SUM(u.cached) en_cache, SUM(u.tokens_in+u.tokens_out) tokens, SUM(u.est_cost_usd) costo_estimado_usd,
                          SUM(CASE WHEN u.state='error' THEN 1 ELSE 0 END) errores
                          FROM usage u LEFT JOIN connections c ON c.id=u.connection_id WHERE u.ts>=? GROUP BY u.connection_id""", (start,))
    for r in by_conn:
        r["confirmed_quota"] = loads(r["confirmed_quota"], {})
    return {"desde": start, "por_categoria": by_cat, "por_conexion": by_conn, "gasto_pago_activado": bool(db.get_setting("allow_paid", False)),
            "nota": "Costos estimados a partir del uso reportado y de los precios que configuraste. La factura del proveedor es la referencia definitiva."}
