"""Adaptadores de texto: API compatible con OpenAI (incluye Groq), Gemini Developer API y Ollama.

No se fija ningún ID de modelo: el usuario lo elige del listado real del proveedor.
"""
from __future__ import annotations

from . import base
from .base import LLMResult, ProviderError

OPENAI_STYLE = ("openai_compat", "groq")


def _auth(secret: str | None) -> dict:
    return {"Authorization": f"Bearer {secret}"} if secret else {}


def list_models(conn: dict, secret: str | None) -> list[str]:
    provider, url = conn["provider"], conn["base_url"]
    with base.client(min(conn.get("timeout_s") or 30, 30)) as cli:
        if provider in OPENAI_STYLE:
            data = base.json_body(base.send(cli, "GET", f"{url}/models", "Listar modelos", headers=_auth(secret)), "Listar modelos")
            return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))
        if provider == "gemini":
            data = base.json_body(base.send(cli, "GET", f"{url}/models", "Listar modelos", params={"pageSize": 200},
                                            headers={"x-goog-api-key": secret or ""}), "Listar modelos")
            return sorted(m["name"].removeprefix("models/") for m in data.get("models", [])
                          if "generateContent" in m.get("supportedGenerationMethods", []))
        if provider == "ollama":
            data = base.json_body(base.send(cli, "GET", f"{url}/api/tags", "Listar modelos"), "Listar modelos")
            return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))
    raise ProviderError("not_supported", f"El proveedor {provider} no ofrece modelos de texto.")


def chat(conn: dict, secret: str | None, system: str, user: str, *, json_mode: bool = False,
         max_tokens: int | None = None, temperature: float = 0.2, images: list[tuple[str, str]] | None = None) -> LLMResult:
    """images: lista de (mime, base64)."""
    provider, url, model = conn["provider"], conn["base_url"], conn.get("model")
    if not model:
        raise ProviderError("config", "La conexión no tiene un modelo seleccionado.")
    max_tokens = int(max_tokens or conn.get("max_tokens") or 2048)
    what = f"Texto ({conn.get('name') or provider})"
    with base.client(conn.get("timeout_s") or 60) as cli:
        if provider in OPENAI_STYLE:
            content = user if not images else [{"type": "text", "text": user}] + [
                {"type": "image_url", "image_url": {"url": f"data:{m};base64,{b}"}} for m, b in images]
            body = {"model": model, "temperature": temperature,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            token_param = (conn.get("options") or {}).get("max_tokens_param") or "max_tokens"
            body[token_param] = max_tokens
            try:
                resp = base.send(cli, "POST", f"{url}/chat/completions", what, json=body, headers=_auth(secret))
            except ProviderError as exc:
                # Algunos modelos solo aceptan max_completion_tokens: un único reintento con ese nombre.
                if exc.http_status == 400 and "max_tokens" in exc.message and token_param == "max_tokens":
                    body.pop("max_tokens")
                    body["max_completion_tokens"] = max_tokens
                    resp = base.send(cli, "POST", f"{url}/chat/completions", what, json=body, headers=_auth(secret))
                else:
                    raise
            data = base.json_body(resp, what)
            try:
                text = data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError):
                raise ProviderError("bad_response", f"{what}: la respuesta no contiene texto.")
            usage = data.get("usage") or {}
            return LLMResult(text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0),
                             data.get("model") or model, base.quota_from_headers(resp))
        if provider == "gemini":
            parts = [{"text": user}] + [{"inlineData": {"mimeType": m, "data": b}} for m, b in (images or [])]
            gen = {"maxOutputTokens": max_tokens, "temperature": temperature}
            if json_mode:
                gen["responseMimeType"] = "application/json"
            body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen,
                    "systemInstruction": {"parts": [{"text": system}]}}
            resp = base.send(cli, "POST", f"{url}/models/{model}:generateContent", what, json=body,
                             headers={"x-goog-api-key": secret or ""})
            data = base.json_body(resp, what)
            cands = data.get("candidates") or []
            if not cands:
                reason = (data.get("promptFeedback") or {}).get("blockReason") or "sin candidatos"
                raise ProviderError("bad_response", f"{what}: el proveedor no devolvió contenido ({reason}).")
            text = "".join(p.get("text", "") for p in (cands[0].get("content") or {}).get("parts", []))
            um = data.get("usageMetadata") or {}
            return LLMResult(text, int(um.get("promptTokenCount") or 0), int(um.get("candidatesTokenCount") or 0), model,
                             base.quota_from_headers(resp))
        if provider == "ollama":
            msg = {"role": "user", "content": user}
            if images:
                msg["images"] = [b for _, b in images]
            body = {"model": model, "stream": False, "messages": [{"role": "system", "content": system}, msg],
                    "options": {"num_predict": max_tokens, "temperature": temperature}}
            if json_mode:
                body["format"] = "json"
            data = base.json_body(base.send(cli, "POST", f"{url}/api/chat", what, json=body), what)
            text = (data.get("message") or {}).get("content") or ""
            return LLMResult(text, int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0), model)
    raise ProviderError("not_supported", f"El proveedor {provider} no genera texto.")
