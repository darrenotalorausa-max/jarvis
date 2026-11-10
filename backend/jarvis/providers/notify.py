"""Canales de aviso al propietario: Telegram (bot oficial), WhatsApp Cloud API (Meta) y ntfy (notificaciones push)."""
from __future__ import annotations

from . import base
from .base import ProviderError


def _opts(conn: dict) -> dict:
    return conn.get("options") or {}


def send(conn: dict, secret: str | None, text: str, title: str = "Jarvis OS") -> None:
    provider, url, o = conn["provider"], conn["base_url"], _opts(conn)
    what = f"Aviso ({conn.get('name') or provider})"
    text = text[:3500]
    with base.client(conn.get("timeout_s") or 20) as cli:
        if provider == "telegram":
            if not o.get("chat_id"):
                raise ProviderError("config", "Falta el chat ID de Telegram.")
            base.json_body(base.send(cli, "POST", f"{url}/bot{secret or ''}/sendMessage", what,
                                     json={"chat_id": str(o["chat_id"]), "text": f"{title}\n{text}", "disable_web_page_preview": True}), what)
        elif provider == "whatsapp":
            if not (o.get("phone_number_id") and o.get("to")):
                raise ProviderError("config", "Faltan el ID del número de WhatsApp Business y el número de destino.")
            if not str(o["phone_number_id"]).isdigit():
                raise ProviderError("config", "El ID del número de WhatsApp debe ser numérico.")
            body = {"messaging_product": "whatsapp", "to": str(o["to"]).lstrip("+"), "type": "text", "text": {"body": f"*{title}*\n{text}"}}
            base.json_body(base.send(cli, "POST", f"{url}/{o['phone_number_id']}/messages", what, json=body,
                                     headers={"Authorization": f"Bearer {secret or ''}"}), what)
        elif provider == "ntfy":
            topic = str(o.get("topic") or "")
            if not topic or not topic.replace("-", "").replace("_", "").isalnum():
                raise ProviderError("config", "Indica un tema de ntfy (solo letras, números, guiones).")
            headers = {"Title": title.encode("ascii", "ignore").decode() or "Jarvis OS", "Tags": "robot"}
            if secret:
                headers["Authorization"] = f"Bearer {secret}"
            base.send(cli, "POST", f"{url}/{topic}", what, content=text.encode("utf-8"), headers=headers)
        else:
            raise ProviderError("not_supported", f"El proveedor {provider} no envía avisos.")


def telegram_updates(conn: dict, secret: str | None, offset: int) -> list[dict]:
    """Mensajes nuevos del bot (sondeo corto). Devuelve [{update_id, chat_id, text}]."""
    with base.client(15) as cli:
        data = base.json_body(base.send(cli, "GET", f"{conn['base_url']}/bot{secret or ''}/getUpdates", "Telegram",
                                        params={"offset": offset, "timeout": 0, "allowed_updates": '["message"]'}), "Telegram")
    out = []
    for u in data.get("result") or []:
        msg = u.get("message") or {}
        out.append({"update_id": u.get("update_id", 0), "chat_id": str((msg.get("chat") or {}).get("id", "")), "text": msg.get("text") or ""})
    return out
