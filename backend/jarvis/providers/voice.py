"""Voz: síntesis con ElevenLabs y transcripción (endpoint compatible con OpenAI o faster-whisper local)."""
from __future__ import annotations
from pathlib import Path

from . import base
from .base import ProviderError


def elevenlabs_voices(conn: dict, secret: str | None) -> list[dict]:
    with base.client(min(conn.get("timeout_s") or 30, 30)) as cli:
        data = base.json_body(base.send(cli, "GET", f"{conn['base_url']}/v2/voices", "Listar voces", params={"page_size": 100},
                                        headers={"xi-api-key": secret or ""}), "Listar voces")
    return [{"id": v.get("voice_id"), "name": v.get("name"), "category": v.get("category")} for v in data.get("voices", []) if v.get("voice_id")]


def elevenlabs_tts(conn: dict, secret: str | None, text: str) -> bytes:
    opts = conn.get("options") or {}
    voice_id = opts.get("voice_id")
    if not voice_id:
        raise ProviderError("config", "Selecciona un voice ID autorizado en la conexión de ElevenLabs.")
    if not voice_id.isalnum():
        raise ProviderError("config", "El voice ID no es válido.")
    body = {"text": text[:2500]}
    if conn.get("model"):
        body["model_id"] = conn["model"]
    with base.client(conn.get("timeout_s") or 60) as cli:
        resp = base.send(cli, "POST", f"{conn['base_url']}/v1/text-to-speech/{voice_id}", "Síntesis de voz",
                         params={"output_format": "mp3_44100_128"}, json=body, headers={"xi-api-key": secret or ""})
    if not resp.content:
        raise ProviderError("bad_response", "Síntesis de voz: respuesta vacía.")
    return resp.content


def local_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def transcribe(conn: dict, secret: str | None, audio_path: Path, language: str | None = None) -> dict:
    """Devuelve {"text": str, "segments": [{"start","end","text"}], "duration": float|None}."""
    provider = conn["provider"]
    what = f"Transcripción ({conn.get('name') or provider})"
    if provider in ("openai_compat", "groq", "openai"):
        model = (conn.get("options") or {}).get("transcription_model")
        if not model:
            raise ProviderError("config", "Indica el modelo de transcripción en la conexión (campo «Modelo de transcripción»).")
        data = {"model": model, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        with base.client(max(conn.get("timeout_s") or 120, 120)) as cli, open(audio_path, "rb") as fh:
            resp = base.send(cli, "POST", f"{conn['base_url']}/audio/transcriptions", what, data=data,
                             files={"file": (audio_path.name, fh, "application/octet-stream")},
                             headers={"Authorization": f"Bearer {secret or ''}"})
        body = base.json_body(resp, what)
        segs = [{"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": (s.get("text") or "").strip()}
                for s in body.get("segments") or []]
        text = body.get("text") or " ".join(s["text"] for s in segs)
        return {"text": text, "segments": segs, "duration": body.get("duration")}
    if provider == "whisper_local":
        if not local_whisper_available():
            raise ProviderError("not_supported", "Transcripción local: falta instalar el paquete opcional faster-whisper (ver README).")
        from faster_whisper import WhisperModel
        model = WhisperModel(conn.get("model") or "base", device="auto", compute_type="auto")
        it, info = model.transcribe(str(audio_path), language=language)
        segs = [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()} for s in it]
        return {"text": " ".join(s["text"] for s in segs), "segments": segs, "duration": getattr(info, "duration", None)}
    raise ProviderError("not_supported", f"El proveedor {provider} no transcribe audio.")
