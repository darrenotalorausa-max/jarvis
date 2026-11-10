"""Centro de conexiones: catálogo de proveedores, CRUD, prueba real y estado comprensible."""
from __future__ import annotations

from . import db, secrets_store, security
from .providers import base, llm, search, voice
from .providers.base import ProviderError, STATUS_LABELS
from .util import dumps, loads, new_id, now, now_iso

NOTIFY_PROVIDERS = ("telegram", "whatsapp", "ntfy")
CAPABILITIES = {
    "texto": "Texto", "extraccion": "Extracción estructurada (JSON)", "vision": "Visión (imágenes)",
    "busqueda": "Búsqueda web", "transcripcion": "Transcripción", "voz": "Síntesis de voz",
}

PROVIDERS = {
    "ollama": {"label": "Ollama (local)", "base_url": "http://127.0.0.1:11434", "needs_secret": False, "local": True,
               "capabilities": ["texto", "extraccion"], "optional": ["vision"],
               "help": "Modelos ejecutados en tu equipo. Requiere Ollama instalado y un modelo descargado."},
    "gemini": {"label": "Gemini Developer API", "base_url": "https://generativelanguage.googleapis.com/v1beta", "needs_secret": True,
               "local": False, "capabilities": ["texto", "extraccion"], "optional": ["vision"],
               "help": "Clave de Google AI Studio. Los modelos, cuotas y condiciones dependen de tu cuenta."},
    "anthropic": {"label": "Claude (API de Anthropic)", "base_url": "https://api.anthropic.com", "needs_secret": True, "local": False,
                  "capabilities": ["texto", "extraccion"], "optional": ["vision"],
                  "help": "Clave de API de la consola de Anthropic (de pago por uso). Una suscripción de Claude.ai no incluye API."},
    "openai": {"label": "ChatGPT (API de OpenAI)", "base_url": "https://api.openai.com/v1", "needs_secret": True, "local": False,
               "capabilities": ["texto", "extraccion"], "optional": ["vision", "transcripcion"],
               "help": "Clave de API de platform.openai.com (de pago por uso). ChatGPT Plus no incluye API."},
    "api": {"label": "Conector universal (cualquier API REST)", "base_url": "", "needs_secret": False, "local": False,
            "capabilities": ["api"], "optional": [], "help": "Conecta cualquier servicio con API: elige una plantilla o define tus propias acciones. Las acciones de escritura requieren tu aprobación."},
    "groq": {"label": "Groq", "base_url": "https://api.groq.com/openai/v1", "needs_secret": True, "local": False,
             "capabilities": ["texto", "extraccion"], "optional": ["transcripcion", "vision"],
             "help": "API con formato OpenAI. La transcripción requiere indicar un modelo de transcripción disponible en tu cuenta."},
    "openai_compat": {"label": "API compatible con OpenAI", "base_url": "", "needs_secret": True, "local": False,
                      "capabilities": ["texto"], "optional": ["extraccion", "vision", "transcripcion"],
                      "help": "«Compatible» describe el formato, no las capacidades: marca solo las que tu proveedor soporte."},
    "brave": {"label": "Brave Search API", "base_url": "https://api.search.brave.com", "needs_secret": True, "local": False,
              "capabilities": ["busqueda"], "optional": [], "help": "La prueba de conexión consume una consulta."},
    "tavily": {"label": "Tavily", "base_url": "https://api.tavily.com", "needs_secret": True, "local": False,
               "capabilities": ["busqueda"], "optional": [], "help": "La prueba de conexión consume una consulta."},
    "elevenlabs": {"label": "ElevenLabs (voz)", "base_url": "https://api.elevenlabs.io", "needs_secret": True, "local": False,
                   "capabilities": ["voz"], "optional": [], "help": "Opcional. Usa solo voces que tengas derecho a utilizar."},
    "whisper_local": {"label": "Transcripción local (faster-whisper)", "base_url": "", "needs_secret": False, "local": True,
                      "capabilities": ["transcripcion"], "optional": [],
                      "help": "Requiere instalar el paquete opcional faster-whisper; el modelo se descarga la primera vez."},
    "telegram": {"label": "Telegram (avisos y órdenes desde el celular)", "base_url": "https://api.telegram.org", "needs_secret": True, "local": False,
                 "capabilities": ["notificacion"], "optional": [], "help": "Bot propio creado con @BotFather. La prueba envía un mensaje real a tu chat."},
    "whatsapp": {"label": "WhatsApp Business (Cloud API de Meta)", "base_url": "https://graph.facebook.com/v21.0", "needs_secret": True, "local": False,
                 "capabilities": ["notificacion"], "optional": [],
                 "help": "Solo avisos salientes. Meta solo entrega texto libre si escribiste al número en las últimas 24 h; fuera de esa ventana exige plantillas."},
    "ntfy": {"label": "ntfy (notificaciones push al celular)", "base_url": "https://ntfy.sh", "needs_secret": False, "local": False,
             "capabilities": ["notificacion"], "optional": [], "help": "Instala la app ntfy y suscríbete a tu tema. En ntfy.sh público, cualquiera que conozca el tema puede leerlo: usa un nombre largo y aleatorio."},
    "webhook": {"label": "Webhook de exportación (CRM u otro sistema)", "base_url": "", "needs_secret": False, "local": False,
                "capabilities": ["exportacion"], "optional": [],
                "help": "Destino externo para exportar entregables aprobados. Cada envío requiere aprobación específica."},
}

FIELDS = ("name", "provider", "base_url", "model", "capabilities", "enabled", "terms_accepted", "is_paid", "timeout_s",
          "max_tokens", "concurrency", "rpm_limit", "daily_limit", "monthly_budget_usd", "price_in", "price_out",
          "price_unit", "data_policy", "options")


def secret_name(conn_id: str) -> str:
    return f"conn:{conn_id}"


def _row(row: dict) -> dict:
    row = dict(row)
    row["capabilities"] = loads(row["capabilities"], [])
    row["options"] = loads(row["options"], {})
    row["confirmed_quota"] = loads(row.get("confirmed_quota"), {})
    for b in ("enabled", "terms_accepted", "is_paid"):
        row[b] = bool(row[b])
    return row


def is_local(conn: dict) -> bool:
    spec = PROVIDERS.get(conn["provider"], {})
    return bool(spec.get("local")) or (conn["provider"] == "openai_compat" and security.is_loopback_url(conn.get("base_url") or ""))


def effective_status(conn: dict, has_secret: bool | None = None) -> str:
    spec = PROVIDERS.get(conn["provider"], {})
    if has_secret is None:
        has_secret = bool(secrets_store.get_secret(secret_name(conn["id"])))
    if spec.get("needs_secret") and not has_secret and not is_local(conn):
        return "no_configurada"
    if conn["provider"] != "whisper_local" and not conn.get("base_url"):
        return "no_configurada"
    if not is_local(conn) and not conn["terms_accepted"]:
        return "condiciones_pendientes"
    if not conn["enabled"]:
        return "deshabilitada"
    if conn["status"] == "cuota_agotada" and conn.get("blocked_until") and conn["blocked_until"] <= now_iso():
        return "sin_probar"
    return conn["status"]


def public(conn: dict) -> dict:
    secret = secrets_store.get_secret(secret_name(conn["id"]))
    out = dict(conn)
    out["has_secret"] = bool(secret)
    out["secret_hint"] = secrets_store.mask(secret)
    out["is_local"] = is_local(conn)
    out["status"] = effective_status(conn, bool(secret))
    out["status_label"] = STATUS_LABELS.get(out["status"], out["status"])
    out["provider_label"] = PROVIDERS.get(conn["provider"], {}).get("label", conn["provider"])
    return out


def get(conn_id: str) -> dict | None:
    row = db.one("SELECT * FROM connections WHERE id=?", (conn_id,))
    return _row(row) if row else None


def list_all() -> list[dict]:
    return [_row(r) for r in db.query("SELECT * FROM connections ORDER BY created_at")]


def _validate(data: dict, existing: dict | None) -> dict:
    provider = data.get("provider") or (existing or {}).get("provider")
    if provider not in PROVIDERS:
        raise ValueError("Proveedor no reconocido.")
    spec = PROVIDERS[provider]
    out = {k: data[k] for k in FIELDS if k in data}
    out["provider"] = provider
    if "base_url" in out or not existing:
        url = (out.get("base_url") or spec["base_url"] or "").strip()
        out["base_url"] = security.check_provider_url(url) if url else ""
        if provider == "webhook" and not out["base_url"]:
            raise ValueError("Indica la URL del webhook.")
    if "capabilities" in out:
        allowed = set(spec["capabilities"]) | set(spec["optional"])
        caps = [c for c in (out["capabilities"] or []) if c in allowed]
        out["capabilities"] = caps or list(spec["capabilities"])
    elif not existing:
        out["capabilities"] = list(spec["capabilities"])
    for num, lo, hi in (("timeout_s", 3, 900), ("max_tokens", 16, 200000), ("concurrency", 1, 8)):
        if out.get(num) is not None:
            out[num] = max(lo, min(hi, float(out[num]) if num == "timeout_s" else int(out[num])))
    for opt in ("rpm_limit", "daily_limit", "monthly_budget_usd", "price_in", "price_out", "price_unit"):
        if opt in out:
            v = out[opt]
            out[opt] = None if v in (None, "") else max(0.0, float(v))
    if "data_policy" in out and out["data_policy"] not in ("negocio", "todo"):
        raise ValueError("Política de datos no válida.")
    if "options" in out and not isinstance(out["options"], dict):
        raise ValueError("Opciones no válidas.")
    if provider == "api" and "options" in out:
        from . import connectors
        out["options"] = connectors.validate_options(out["options"])
        if not (out.get("base_url") or (existing or {}).get("base_url")):
            raise ValueError("Indica la URL base de la API.")
    if not existing and not (out.get("name") or "").strip():
        out["name"] = spec["label"]
    return out


def create(data: dict) -> dict:
    vals = _validate(data, None)
    conn_id = new_id("con")
    cols = {**vals, "id": conn_id, "created_at": now_iso(), "updated_at": now_iso(), "status": "sin_probar"}
    cols["capabilities"] = dumps(cols.get("capabilities", []))
    cols["options"] = dumps(cols.get("options", {}))
    for b in ("enabled", "terms_accepted", "is_paid"):
        cols[b] = int(bool(cols.get(b, False)))
    keys = list(cols)
    db.execute(f"INSERT INTO connections({','.join(keys)}) VALUES({','.join('?' * len(keys))})", [cols[k] for k in keys])
    if data.get("secret"):
        secrets_store.set_secret(secret_name(conn_id), str(data["secret"]).strip())
    db.audit("conexion.crear", conn_id, {"provider": vals["provider"]})
    return public(get(conn_id))


def update(conn_id: str, data: dict) -> dict:
    existing = get(conn_id)
    if not existing:
        raise KeyError(conn_id)
    vals = _validate(data, existing)
    vals.pop("provider", None)
    if vals:
        if "capabilities" in vals:
            vals["capabilities"] = dumps(vals["capabilities"])
        if "options" in vals:
            vals["options"] = dumps(vals["options"])
        for b in ("enabled", "terms_accepted", "is_paid"):
            if b in vals:
                vals[b] = int(bool(vals[b]))
        reset = any(k in vals for k in ("base_url", "model"))
        sets = ",".join(f"{k}=?" for k in vals) + ",updated_at=?" + (",status='sin_probar',last_error=NULL" if reset else "")
        db.execute(f"UPDATE connections SET {sets} WHERE id=?", [*vals.values(), now_iso(), conn_id])
    if data.get("secret"):
        secrets_store.set_secret(secret_name(conn_id), str(data["secret"]).strip())
        db.execute("UPDATE connections SET status='sin_probar', last_error=NULL WHERE id=?", (conn_id,))
    if data.get("clear_secret"):
        secrets_store.delete_secret(secret_name(conn_id))
    db.audit("conexion.editar", conn_id, {"campos": sorted(k for k in data if k != "secret")})
    _wake_waiting_jobs()
    return public(get(conn_id))


def delete(conn_id: str) -> None:
    secrets_store.delete_secret(secret_name(conn_id))
    db.execute("DELETE FROM connections WHERE id=?", (conn_id,))
    db.audit("conexion.eliminar", conn_id)


def set_status(conn_id: str, status: str, error: str | None = None, quota: dict | None = None, blocked_until: str | None = None) -> None:
    sets, params = "status=?, last_error=?, last_checked_at=?, blocked_until=?", [status, error, now_iso(), blocked_until]
    if quota:
        sets += ", confirmed_quota=?"
        params.append(dumps({**quota, "_observado": now_iso()}))
    db.execute(f"UPDATE connections SET {sets} WHERE id=?", [*params, conn_id])


def record_error(conn: dict, exc: ProviderError) -> None:
    blocked = None
    if exc.kind == "quota":
        from .util import iso_in
        blocked = iso_in(exc.retry_after or 300)
    set_status(conn["id"], exc.status, exc.message, blocked_until=blocked)


def models(conn_id: str) -> list:
    conn = get(conn_id)
    if not conn:
        raise KeyError(conn_id)
    secret = secrets_store.get_secret(secret_name(conn_id))
    if conn["provider"] == "elevenlabs":
        return voice.elevenlabs_voices(conn, secret)
    return llm.list_models(conn, secret)


def test(conn_id: str) -> dict:
    """Comprobación real contra el proveedor. Nunca se da por buena sin respuesta válida."""
    conn = get(conn_id)
    if not conn:
        raise KeyError(conn_id)
    spec = PROVIDERS[conn["provider"]]
    secret = secrets_store.get_secret(secret_name(conn_id))
    detail = ""
    try:
        if spec["needs_secret"] and not secret and not is_local(conn):
            raise ProviderError("config", "Falta la credencial.")
        p = conn["provider"]
        if p == "api":
            from . import connectors
            detail = connectors.test(conn)
        elif p in ("ollama", "gemini", "groq", "openai_compat", "anthropic", "openai"):
            names = llm.list_models(conn, secret)
            if conn.get("model"):
                if names and conn["model"] not in names:
                    raise ProviderError("not_supported", f"El modelo «{conn['model']}» no aparece entre los {len(names)} modelos disponibles para esta credencial.")
                res = llm.chat(conn, secret, "Responde solo: ok", "ok", max_tokens=16)
                detail = f"Modelo «{conn['model']}» respondió ({res.tokens_in}+{res.tokens_out} tokens)."
                if res.quota:
                    set_status(conn_id, "operativa", None, quota=res.quota)
            else:
                raise ProviderError("config", f"Credencial aceptada; hay {len(names)} modelos disponibles. Selecciona uno para completar la prueba.")
        elif p in ("brave", "tavily"):
            hits = search.web_search(conn, secret, "prueba de conexión", count=1)
            detail = f"Búsqueda respondió con {len(hits)} resultado(s). Esta prueba consumió una consulta."
        elif p == "elevenlabs":
            voices = voice.elevenlabs_voices(conn, secret)
            detail = f"Credencial aceptada; {len(voices)} voces visibles. La síntesis no se probó para no consumir caracteres."
        elif p == "whisper_local":
            if not voice.local_whisper_available():
                raise ProviderError("not_supported", "El paquete faster-whisper no está instalado en este entorno.")
            detail = "faster-whisper instalado. El modelo se descargará al primer uso."
        elif p in NOTIFY_PROVIDERS:
            from .providers import notify as channels
            channels.send(conn, secret, "Prueba de conexión: este canal recibirá los avisos que elijas.")
            detail = "Mensaje de prueba enviado. Comprueba que llegó a tu celular."
        elif p == "webhook":
            security.check_provider_url(conn["base_url"])
            detail = "URL válida. No se envía ninguna petición de prueba: los envíos requieren aprobación."
        set_status(conn_id, "operativa", None)
        _wake_waiting_jobs()
        return {"ok": True, "status": "operativa", "detail": detail, "connection": public(get(conn_id))}
    except ProviderError as exc:
        record_error(conn, exc)
        return {"ok": False, "status": exc.status, "detail": exc.message, "connection": public(get(conn_id))}


def _wake_waiting_jobs() -> None:
    db.execute("UPDATE jobs SET status='pending', message='Reanudado tras cambio de conexiones', updated_at=? WHERE status='waiting_config'", (now_iso(),))
