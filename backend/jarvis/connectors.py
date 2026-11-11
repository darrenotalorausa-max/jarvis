"""Conector universal: cualquier API REST mediante acciones declaradas (método + ruta + parámetros).

- Las acciones de lectura se ejecutan directamente. Las de escritura solo como trabajo con aprobación específica del propietario.
- La URL final siempre queda dentro de la URL base de la conexión: una plantilla no puede desviar la petición a otro host.
- Las plantillas (PRESETS) describen APIs públicas según su documentación; ninguna se ha comprobado con credenciales reales.
"""
from __future__ import annotations
import base64
import json
import re
import secrets as pysecrets
import time
from urllib.parse import quote, urlencode, urlsplit

from . import connections, db, secrets_store
from .providers import base
from .providers.base import ProviderError
from .util import canonical_json, sha256_text

A = lambda id_, label, method, path, write=False, query=None, body=None: {"id": id_, "label": label, "method": method, "path": path, "write": write, "query": query or {}, "body": body}
GOOGLE = {"auth_url": "https://accounts.google.com/o/oauth2/v2/auth", "token_url": "https://oauth2.googleapis.com/token", "extra": {"access_type": "offline", "prompt": "consent"}}

PRESETS: dict[str, dict] = {
    "shopify": {"label": "Shopify (Admin API)", "base_url": "https://TU-TIENDA.myshopify.com/admin/api/2026-10", "auth": {"type": "header", "name": "X-Shopify-Access-Token"},
                "credential": "Token de acceso de una app personalizada de tu tienda (Configuración → Apps → Desarrollar apps).",
                "actions": [A("tienda", "Datos de la tienda", "GET", "/shop.json"), A("productos", "Listar productos", "GET", "/products.json", query={"limit": "{limite}"}),
                            A("pedidos", "Listar pedidos", "GET", "/orders.json", query={"status": "any", "limit": "{limite}"}),
                            A("crear_producto_borrador", "Crear producto en borrador", "POST", "/products.json", True, body={"product": {"title": "{titulo}", "body_html": "{descripcion}", "status": "draft"}})]},
    "stripe": {"label": "Stripe", "base_url": "https://api.stripe.com/v1", "auth": {"type": "bearer"}, "credential": "Clave secreta restringida de solo lectura (Desarrolladores → Claves de API).",
               "actions": [A("saldo", "Saldo", "GET", "/balance"), A("cobros", "Últimos cobros", "GET", "/charges", query={"limit": "{limite}"}),
                           A("clientes", "Clientes", "GET", "/customers", query={"limit": "{limite}"}), A("suscripciones", "Suscripciones", "GET", "/subscriptions", query={"limit": "{limite}"})]},
    "paypal": {"label": "PayPal (REST)", "base_url": "https://api-m.paypal.com", "auth": {"type": "bearer"}, "credential": "Token de acceso obtenido con tu client ID y secreto (caduca en horas).",
               "actions": [A("transacciones", "Transacciones", "GET", "/v1/reporting/transactions", query={"start_date": "{desde}", "end_date": "{hasta}"})]},
    "notion": {"label": "Notion", "base_url": "https://api.notion.com/v1", "auth": {"type": "bearer"}, "headers": {"Notion-Version": "2022-06-28"},
               "credential": "Secreto de una integración interna (notion.so/my-integrations), compartida con las páginas que quieras leer.",
               "actions": [A("yo", "Comprobar integración", "GET", "/users/me"), A("buscar", "Buscar páginas y bases de datos", "POST", "/search", body={"query": "{texto}", "page_size": 20}),
                           A("crear_pagina", "Crear página", "POST", "/pages", True, body={"parent": {"page_id": "{pagina_padre}"}, "properties": {"title": {"title": [{"text": {"content": "{titulo}"}}]}}})]},
    "cloudflare": {"label": "Cloudflare", "base_url": "https://api.cloudflare.com/client/v4", "auth": {"type": "bearer"}, "credential": "Token de API con permisos de lectura de zona.",
                   "actions": [A("verificar", "Verificar token", "GET", "/user/tokens/verify"), A("zonas", "Zonas (dominios)", "GET", "/zones"),
                               A("dns", "Registros DNS de una zona", "GET", "/zones/{zona_id}/dns_records")]},
    "github": {"label": "GitHub", "base_url": "https://api.github.com", "auth": {"type": "bearer"}, "headers": {"Accept": "application/vnd.github+json"}, "credential": "Token personal de acceso (fine-grained, solo lectura).",
               "actions": [A("yo", "Mi usuario", "GET", "/user"), A("repos", "Mis repositorios", "GET", "/user/repos", query={"per_page": "{limite}"}),
                           A("issues", "Issues de un repositorio", "GET", "/repos/{propietario}/{repo}/issues")]},
    "meta": {"label": "Meta (Ads e Instagram, Graph API)", "base_url": "https://graph.facebook.com/v26.0", "auth": {"type": "bearer"},
             "credential": "Token de acceso de usuario del sistema con ads_read e instagram_basic.",
             "actions": [A("cuentas_publicitarias", "Cuentas publicitarias", "GET", "/me/adaccounts", query={"fields": "name,account_status,currency"}),
                         A("rendimiento", "Rendimiento de anuncios (7 días)", "GET", "/{cuenta_publicitaria}/insights", query={"fields": "spend,impressions,clicks,ctr,cpc", "date_preset": "last_7d"}),
                         A("instagram_media", "Publicaciones de Instagram", "GET", "/{usuario_ig}/media", query={"fields": "caption,like_count,comments_count,permalink,timestamp"})]},
    "tiktok": {"label": "TikTok (API for Business / Display)", "base_url": "https://open.tiktokapis.com/v2", "auth": {"type": "bearer"}, "credential": "Token de acceso OAuth de tu app de TikTok for Developers.",
               "actions": [A("perfil", "Perfil y seguidores", "GET", "/user/info/", query={"fields": "display_name,follower_count,likes_count,video_count"})]},
    "youtube": {"label": "YouTube (Data API)", "base_url": "https://www.googleapis.com/youtube/v3", "auth": {"type": "query", "name": "key"}, "credential": "Clave de API de Google Cloud con YouTube Data API habilitada.",
                "actions": [A("canal", "Estadísticas de un canal", "GET", "/channels", query={"part": "snippet,statistics", "id": "{canal_id}"}),
                            A("videos_recientes", "Videos recientes del canal", "GET", "/search", query={"part": "snippet", "channelId": "{canal_id}", "order": "date", "maxResults": "{limite}"}),
                            A("video", "Estadísticas de un video", "GET", "/videos", query={"part": "statistics,snippet", "id": "{video_id}"})]},
    "google_drive": {"label": "Google Drive", "base_url": "https://www.googleapis.com/drive/v3", "auth": {"type": "oauth"},
                     "oauth": {**GOOGLE, "scopes": "https://www.googleapis.com/auth/drive.readonly"}, "credential": "Client ID y secreto OAuth (tipo «App de escritorio» o «Web») de tu proyecto de Google Cloud.",
                     "actions": [A("yo", "Cuenta conectada", "GET", "/about", query={"fields": "user"}), A("archivos", "Buscar archivos", "GET", "/files", query={"q": "{consulta}", "pageSize": "{limite}", "fields": "files(id,name,mimeType,modifiedTime)"})]},
    "google_sheets": {"label": "Google Sheets", "base_url": "https://sheets.googleapis.com/v4", "auth": {"type": "oauth"}, "oauth": {**GOOGLE, "scopes": "https://www.googleapis.com/auth/spreadsheets.readonly"},
                      "credential": "Client ID y secreto OAuth de tu proyecto de Google Cloud.", "actions": [A("valores", "Leer un rango", "GET", "/spreadsheets/{hoja_id}/values/{rango}")]},
    "gmail": {"label": "Gmail (solo lectura)", "base_url": "https://gmail.googleapis.com/gmail/v1", "auth": {"type": "oauth"}, "oauth": {**GOOGLE, "scopes": "https://www.googleapis.com/auth/gmail.readonly"},
              "credential": "Client ID y secreto OAuth de tu proyecto de Google Cloud.", "actions": [A("mensajes", "Buscar mensajes", "GET", "/users/me/messages", query={"q": "{consulta}", "maxResults": "{limite}"})]},
    "woocommerce": {"label": "WooCommerce", "base_url": "https://TU-SITIO.com/wp-json/wc/v3", "auth": {"type": "basic"}, "credential": "clave_consumidor:secreto_consumidor (WooCommerce → Ajustes → Avanzado → API REST).",
                    "actions": [A("pedidos", "Pedidos", "GET", "/orders", query={"per_page": "{limite}"}), A("productos", "Productos", "GET", "/products", query={"per_page": "{limite}"})]},
    "n8n": {"label": "n8n / Make / Zapier (webhook)", "base_url": "https://TU-INSTANCIA/webhook", "auth": {"type": "none"}, "credential": "Normalmente ninguna: la URL del webhook es el secreto.",
            "actions": [A("disparar", "Disparar flujo", "POST", "/{ruta}", True, body={"origen": "jarvis", "mensaje": "{mensaje}"})]},
    "personalizado": {"label": "API personalizada", "base_url": "", "auth": {"type": "bearer"}, "credential": "La clave o token de tu servicio.", "actions": []},
}
_VAR = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
MAX_RESPONSE = 400_000


def catalog() -> dict:
    return {k: {kk: vv for kk, vv in v.items() if kk != "oauth"} | {"usa_oauth": "oauth" in v} for k, v in PRESETS.items()}


def validate_options(options: dict) -> dict:
    """Normaliza la definición del conector que llega de la interfaz."""
    auth = options.get("auth") or {"type": "none"}
    if auth.get("type") not in ("none", "bearer", "header", "query", "basic", "oauth"):
        raise ValueError("Tipo de autenticación no reconocido.")
    actions = []
    for a in options.get("actions") or []:
        method = str(a.get("method") or "GET").upper()
        path = str(a.get("path") or "")
        if method not in _METHODS or not path.startswith("/") or "://" in path or ".." in path:
            raise ValueError(f"Acción «{a.get('label') or a.get('id')}»: método o ruta no válidos (la ruta empieza por / y es relativa a la URL base).")
        if not re.fullmatch(r"[a-z0-9_]{1,40}", str(a.get("id") or "")):
            raise ValueError("Cada acción necesita un identificador en minúsculas, números y guiones bajos.")
        # Todo lo que no sea GET modifica algo salvo que el usuario lo marque expresamente como lectura (p. ej. búsquedas por POST).
        write = bool(a.get("write")) or (method != "GET" and a.get("write") is not False)
        actions.append({"id": a["id"], "label": str(a.get("label") or a["id"])[:80], "method": method, "path": path, "write": write,
                        "query": a.get("query") or {}, "body": a.get("body")})
    out = {**options, "auth": auth, "actions": actions}
    out["headers"] = {str(k): str(v) for k, v in (options.get("headers") or {}).items() if k.lower() not in ("authorization", "cookie", "host")}
    return out


def _fill(value, variables: dict, in_path: bool = False):
    if isinstance(value, str):
        def sub(m):
            v = variables.get(m.group(1))
            if v in (None, ""):
                raise ProviderError("config", f"Falta el valor de «{m.group(1)}».")
            v = str(v)
            if in_path and ("/" in v and not re.fullmatch(r"[\w\-.:!$']+(/[\w\-.:!$']+)?", v) or ".." in v):
                raise ProviderError("config", f"El valor de «{m.group(1)}» no es válido para una ruta.")
            return quote(v, safe="/:!$'") if in_path else v
        return _VAR.sub(sub, value)
    if isinstance(value, dict):
        return {k: _fill(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, variables) for v in value]
    return value


def variables_of(action: dict) -> list[str]:
    return sorted(set(_VAR.findall(json.dumps([action["path"], action.get("query"), action.get("body")]))))


def _secret(conn: dict) -> dict:
    """El secreto puede ser un texto (clave) o un JSON con tokens OAuth."""
    raw = secrets_store.get_secret(connections.secret_name(conn["id"])) or ""
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"key": raw}
    except ValueError:
        return {"key": raw}


def _save_secret(conn: dict, data: dict) -> None:
    secrets_store.set_secret(connections.secret_name(conn["id"]), json.dumps(data))


def _oauth_cfg(conn: dict) -> dict:
    o = conn["options"]
    cfg = {**(PRESETS.get(o.get("preset") or "", {}).get("oauth") or {}), **(o.get("oauth") or {})}
    if not (cfg.get("auth_url") and cfg.get("token_url") and o.get("client_id")):
        raise ProviderError("config", "Faltan los datos de OAuth: URL de autorización, URL de token y client ID.")
    for k in ("auth_url", "token_url"):
        if urlsplit(cfg[k]).scheme != "https":
            raise ProviderError("config", "Las URL de OAuth deben ser https.")
    return cfg


def redirect_uri() -> str:
    from . import config
    return f"http://127.0.0.1:{config.port()}/api/oauth/callback"


def oauth_start(conn: dict) -> str:
    cfg = _oauth_cfg(conn)
    state = pysecrets.token_urlsafe(24)
    db.set_setting(f"oauth_state:{state}", {"conn": conn["id"], "ts": time.time()})
    q = {"client_id": conn["options"]["client_id"], "redirect_uri": redirect_uri(), "response_type": "code", "scope": cfg.get("scopes") or "", "state": state, **(cfg.get("extra") or {})}
    return f"{cfg['auth_url']}?{urlencode(q)}"


def _token_request(conn: dict, data: dict) -> dict:
    cfg, sec = _oauth_cfg(conn), _secret(conn)
    payload = {"client_id": conn["options"]["client_id"], "client_secret": sec.get("client_secret") or sec.get("key") or "", **data}
    with base.client(30) as cli:
        body = base.json_body(base.send(cli, "POST", cfg["token_url"], "OAuth", data=payload, headers={"Accept": "application/json"}), "OAuth")
    if not body.get("access_token"):
        raise ProviderError("auth", "OAuth: el proveedor no devolvió un token de acceso.")
    sec.update(client_secret=payload["client_secret"], access_token=body["access_token"], expires_at=time.time() + float(body.get("expires_in") or 3600) - 60)
    if body.get("refresh_token"):
        sec["refresh_token"] = body["refresh_token"]
    sec.pop("key", None)
    _save_secret(conn, sec)
    return sec


def oauth_finish(state: str, code: str) -> dict:
    saved = db.get_setting(f"oauth_state:{state}")
    db.execute("DELETE FROM settings WHERE key=?", (f"oauth_state:{state}",))
    if not saved or time.time() - saved["ts"] > 900:
        raise ProviderError("auth", "La autorización caducó o no es válida. Vuelve a pulsar «Autorizar».")
    conn = connections.get(saved["conn"])
    _token_request(conn, {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()})
    connections.set_status(conn["id"], "operativa", None)
    db.audit("oauth.autorizado", conn["id"], {})
    return conn


def _auth(conn: dict, headers: dict, params: dict) -> None:
    auth, sec = conn["options"].get("auth") or {}, _secret(conn)
    t = auth.get("type")
    if t == "oauth":
        if not sec.get("access_token"):
            raise ProviderError("config", "Conexión sin autorizar: pulsa «Autorizar» para completar el acceso.")
        if sec.get("expires_at", 0) < time.time():
            if not sec.get("refresh_token"):
                raise ProviderError("auth", "El acceso caducó y no hay token de renovación: vuelve a autorizar.")
            sec = _token_request(conn, {"grant_type": "refresh_token", "refresh_token": sec["refresh_token"]})
        headers["Authorization"] = f"Bearer {sec['access_token']}"
    elif t in ("bearer", "header", "query", "basic"):
        key = sec.get("key") or ""
        if not key:
            raise ProviderError("config", "Falta la credencial de esta conexión.")
        if t == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        elif t == "header":
            headers[auth.get("name") or "X-API-Key"] = key
        elif t == "query":
            params[auth.get("name") or "key"] = key
        else:
            headers["Authorization"] = "Basic " + base64.b64encode(key.encode()).decode()


def action_of(conn: dict, action_id: str) -> dict:
    a = next((x for x in conn["options"].get("actions") or [] if x["id"] == action_id), None)
    if not a:
        raise ProviderError("config", "La acción no existe en esta conexión.")
    return a


def build(conn: dict, action: dict, variables: dict) -> dict:
    """Petición final (sin credenciales) tal como se enviaría. Sirve para mostrarla antes de aprobar."""
    variables = {"limite": "20", **{k: v for k, v in (variables or {}).items() if v not in (None, "")}}
    root = conn["base_url"].rstrip("/")
    url = root + _fill(action["path"], variables, in_path=True)
    if urlsplit(url).netloc != urlsplit(root).netloc or not url.startswith(root):
        raise ProviderError("config", "La acción intenta salir de la URL base de la conexión.")
    return {"method": action["method"], "url": url, "query": _fill(action.get("query") or {}, variables), "body": _fill(action.get("body"), variables) if action.get("body") is not None else None}


def request_hash(conn: dict, action_id: str, variables: dict) -> str:
    return sha256_text(canonical_json([conn["id"], conn["base_url"], action_id, build(conn, action_of(conn, action_id), variables)]))


def execute(conn: dict, action_id: str, variables: dict, *, allow_write: bool = False) -> dict:
    action = action_of(conn, action_id)
    if action["write"] and not allow_write:
        raise ProviderError("permission", "Esta acción modifica un sistema externo: debe ejecutarse como trabajo con tu aprobación.")
    req = build(conn, action, variables)
    headers, params = {"Accept": "application/json", **(conn["options"].get("headers") or {})}, dict(req["query"])
    _auth(conn, headers, params)
    what = f"{conn['name']} · {action['label']}"
    with base.client(conn.get("timeout_s") or 30) as cli:
        resp = base.send(cli, req["method"], req["url"], what, params=params, headers=headers, **({"json": req["body"]} if req["body"] is not None else {}))
    raw = resp.content[:MAX_RESPONSE]
    try:
        data = json.loads(raw) if len(resp.content) <= MAX_RESPONSE else None
    except ValueError:
        data = None
    connections.set_status(conn["id"], "operativa", None)
    return {"status": resp.status_code, "json": data, "text": None if data is not None else raw.decode("utf-8", "replace"), "truncated": len(resp.content) > MAX_RESPONSE,
            "request": {"method": req["method"], "url": req["url"], "query": req["query"]}}


def test(conn: dict) -> str:
    conn = {**conn, "options": validate_options(conn["options"])}
    reads = [a for a in conn["options"]["actions"] if not a["write"] and not variables_of(a)]
    if not reads:
        return "Definición válida. No hay ninguna acción de lectura sin parámetros con la que probar; ejecuta una acción para comprobar la credencial."
    out = execute(conn, reads[0]["id"], {})
    return f"«{reads[0]['label']}» respondió HTTP {out['status']}."
