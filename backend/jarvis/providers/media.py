"""Generación de imágenes y video por API: OpenAI (imágenes y video), Gemini (imágenes) y fal.ai (cualquier modelo de su catálogo).

Ningún ID de modelo va fijado: el usuario indica en la conexión el modelo de imágenes o de video que su cuenta tenga disponible.
Las descargas de resultados pasan por la misma comprobación de destino público que el importador web.
"""
from __future__ import annotations
import base64
import json

from . import base
from .base import ProviderError
from .. import security

MAX_IMAGE = 40 * 1024 * 1024
MAX_VIDEO = 400 * 1024 * 1024
IMAGE_SIZES = {"openai": {"1:1": "1024x1024", "16:9": "1536x1024", "9:16": "1024x1536"}, "fal": {"1:1": "square_hd", "16:9": "landscape_16_9", "9:16": "portrait_16_9"}}
VIDEO_SIZES = {"16:9": "1280x720", "9:16": "720x1280"}
EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "video/mp4": ".mp4", "video/webm": ".webm"}


def _opt(conn: dict, key: str) -> str:
    return str((conn.get("options") or {}).get(key) or "").strip()


def _model(conn: dict, kind: str) -> str:
    m = _opt(conn, f"{kind}_model")
    if not m:
        raise ProviderError("config", f"Indica en la conexión «{conn.get('name')}» el modelo de {'imágenes' if kind == 'image' else 'video'} que quieres usar.")
    return m


def _extra(conn: dict) -> dict:
    raw = (conn.get("options") or {}).get("media_params")
    if not raw:
        return {}
    try:
        data = raw if isinstance(raw, dict) else json.loads(raw)
    except ValueError:
        raise ProviderError("config", "Los parámetros extra de la conexión no son JSON válido.")
    return data if isinstance(data, dict) else {}


def _auth(conn: dict, secret: str | None) -> dict:
    p = conn["provider"]
    if p == "fal":
        return {"Authorization": f"Key {secret or ''}"}
    if p == "gemini":
        return {"x-goog-api-key": secret or ""}
    return {"Authorization": f"Bearer {secret or ''}"}


def download(url: str, what: str, max_bytes: int) -> tuple[bytes, str]:
    """Descarga un resultado desde la dirección que devolvió el proveedor: solo https y hacia direcciones públicas."""
    if not url.lower().startswith("https://"):
        raise ProviderError("bad_response", f"{what}: el proveedor devolvió una dirección no segura.")
    try:
        security.check_public_url(url)
    except security.SecurityError as exc:
        raise ProviderError("bad_response", f"{what}: {exc}")
    with base.client(180) as cli:
        resp = base.send(cli, "GET", url, what)
    if len(resp.content) > max_bytes:
        raise ProviderError("bad_response", f"{what}: el archivo supera el tamaño máximo permitido.")
    return resp.content, (resp.headers.get("content-type") or "").split(";")[0].strip().lower()


def _fal(conn: dict, secret: str | None, model: str, payload: dict, wait, what: str, max_seconds: float) -> dict:
    """Cola de fal.ai: enviar, consultar el estado con la URL que devuelve y recoger el resultado."""
    root = conn["base_url"].rstrip("/")
    with base.client(conn.get("timeout_s") or 60) as cli:
        job = base.json_body(base.send(cli, "POST", f"{root}/{model.strip('/')}", what, json={**payload, **_extra(conn)}, headers=_auth(conn, secret)), what)
        status_url, response_url = str(job.get("status_url") or ""), str(job.get("response_url") or "")
        if not (status_url.startswith(root) and response_url.startswith(root)):
            raise ProviderError("bad_response", f"{what}: respuesta inesperada al enviar el trabajo.")
        waited = 0.0
        while True:
            st = base.json_body(base.send(cli, "GET", status_url, what, headers=_auth(conn, secret)), what)
            state = str(st.get("status") or "").upper()
            if state == "COMPLETED":
                break
            if state not in ("IN_QUEUE", "IN_PROGRESS"):
                raise ProviderError("bad_response", f"{what}: el proveedor informó el estado «{state or 'desconocido'}».")
            if waited >= max_seconds:
                raise ProviderError("timeout", f"{what}: el proveedor no terminó dentro del tiempo límite.")
            wait(4, None)
            waited += 4
        return base.json_body(base.send(cli, "GET", response_url, what, headers=_auth(conn, secret)), what)


def image(conn: dict, secret: str | None, prompt: str, *, aspect: str = "1:1", n: int = 1, wait=lambda s, p: None) -> list[tuple[bytes, str]]:
    p, what, model = conn["provider"], f"Imagen ({conn.get('name') or conn['provider']})", _model(conn, "image")
    out: list[tuple[bytes, str]] = []
    if p in ("openai", "openai_compat"):
        body = {"model": model, "prompt": prompt, "n": n, "size": IMAGE_SIZES["openai"].get(aspect, "1024x1024"), **_extra(conn)}
        with base.client(conn.get("timeout_s") or 180) as cli:
            data = base.json_body(base.send(cli, "POST", f"{conn['base_url'].rstrip('/')}/images/generations", what, json=body, headers=_auth(conn, secret)), what)
        for it in data.get("data") or []:
            if it.get("b64_json"):
                out.append((base64.b64decode(it["b64_json"]), "image/png"))
            elif it.get("url"):
                out.append(download(it["url"], what, MAX_IMAGE))
    elif p == "gemini":
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], **_extra(conn)}}
        with base.client(conn.get("timeout_s") or 180) as cli:
            for _ in range(n):
                data = base.json_body(base.send(cli, "POST", f"{conn['base_url'].rstrip('/')}/models/{model}:generateContent", what, json=body, headers=_auth(conn, secret)), what)
                for cand in data.get("candidates") or []:
                    for part in (cand.get("content") or {}).get("parts") or []:
                        blob = part.get("inlineData") or part.get("inline_data")
                        if blob and blob.get("data"):
                            out.append((base64.b64decode(blob["data"]), blob.get("mimeType") or blob.get("mime_type") or "image/png"))
    elif p == "fal":
        res = _fal(conn, secret, model, {"prompt": prompt, "image_size": IMAGE_SIZES["fal"].get(aspect, "square_hd"), "num_images": n}, wait, what, 300)
        for it in res.get("images") or ([res["image"]] if isinstance(res.get("image"), dict) else []):
            if isinstance(it, dict) and it.get("url"):
                out.append(download(it["url"], what, MAX_IMAGE))
    else:
        raise ProviderError("not_supported", f"El proveedor {p} no genera imágenes.")
    if not out:
        raise ProviderError("bad_response", f"{what}: el proveedor no devolvió ninguna imagen (puede haber rechazado la petición por sus normas de contenido).")
    return out[:n]


def video(conn: dict, secret: str | None, prompt: str, *, aspect: str = "16:9", seconds: int = 4, wait=lambda s, p: None, max_seconds: float = 1200) -> tuple[bytes, str]:
    p, what, model = conn["provider"], f"Video ({conn.get('name') or conn['provider']})", _model(conn, "video")
    if p in ("openai", "openai_compat"):
        if aspect not in VIDEO_SIZES:
            raise ProviderError("config", "Para video elige formato horizontal (16:9) o vertical (9:16).")
        root, h = conn["base_url"].rstrip("/"), _auth(conn, secret)
        with base.client(conn.get("timeout_s") or 60) as cli:
            job = base.json_body(base.send(cli, "POST", f"{root}/videos", what, json={"model": model, "prompt": prompt, "size": VIDEO_SIZES[aspect], "seconds": str(seconds), **_extra(conn)}, headers=h), what)
            vid = str(job.get("id") or "")
            if not vid.replace("_", "").replace("-", "").isalnum():
                raise ProviderError("bad_response", f"{what}: respuesta inesperada al crear el video.")
            waited = 0.0
            while True:
                state = str(job.get("status") or "")
                if state == "completed":
                    break
                if state in ("failed", "cancelled", "canceled"):
                    detail = (job.get("error") or {}).get("message") if isinstance(job.get("error"), dict) else ""
                    raise ProviderError("bad_response", f"{what}: el proveedor no pudo generar el video. {detail or ''}".strip())
                if waited >= max_seconds:
                    raise ProviderError("timeout", f"{what}: el video no terminó dentro del tiempo límite.")
                wait(6, (float(job.get("progress") or 0) / 100) if job.get("progress") is not None else None)
                waited += 6
                job = base.json_body(base.send(cli, "GET", f"{root}/videos/{vid}", what, headers=h), what)
        with base.client(300) as cli:
            resp = base.send(cli, "GET", f"{root}/videos/{vid}/content", what, headers=h)
        if len(resp.content) > MAX_VIDEO:
            raise ProviderError("bad_response", f"{what}: el archivo supera el tamaño máximo permitido.")
        return resp.content, "video/mp4"
    if p == "fal":
        res = _fal(conn, secret, model, {"prompt": prompt, "aspect_ratio": aspect}, wait, what, max_seconds)
        item = res.get("video") or (res.get("videos") or [None])[0]
        if not (isinstance(item, dict) and item.get("url")):
            raise ProviderError("bad_response", f"{what}: el proveedor no devolvió ningún video.")
        data, mime = download(item["url"], what, MAX_VIDEO)
        return data, mime if mime in EXT else "video/mp4"
    raise ProviderError("not_supported", f"El proveedor {p} no genera video.")
