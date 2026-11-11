"""Generación de imágenes y video por API. Guarda los archivos en el espacio y crea un entregable para revisarlos."""
from __future__ import annotations
import re

from .. import files, review, router
from ..jobs import JobError
from ..worker import handler
from ..providers import media as media_api
from .common import available

KINDS = {"image": ("imagen", "Imagen"), "video": ("video", "Video")}


@handler("media_generate")
def media_generate(ctx) -> dict:
    p = ctx.params
    kind = p.get("kind") if p.get("kind") in KINDS else "image"
    cap, label = KINDS[kind]
    prompt = str(p.get("prompt") or "").strip()
    if len(prompt) < 5:
        raise JobError("Describe lo que quieres generar.")
    aspect = p.get("aspect") if p.get("aspect") in ("1:1", "16:9", "9:16") else ("16:9" if kind == "video" else "1:1")
    if not available(ctx, cap):
        raise router.RouterError("needs_config", f"No hay ninguna conexión habilitada que genere {'imágenes' if kind == 'image' else 'video'} en este espacio. "
                                 "Conecta OpenAI, Gemini o fal.ai en Conexiones, indica el modelo y marca la capacidad. Si es de pago, actívala y ponle presupuesto.")

    def wait(seconds: float, progress: float | None) -> None:
        ctx.check_cancel()
        if progress is not None:
            ctx.stage("generacion", 0.1 + 0.8 * max(0.0, min(1.0, progress)), "El proveedor está generando el video")
        router.SLEEP(seconds)

    ctx.stage("generacion", 0.1, f"Generando {label.lower()}")
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:40].strip("-") or kind
    saved = []
    if kind == "image":
        n = max(1, min(4, int(p.get("count") or 1)))
        items, meta = router.image(ctx.router, prompt, aspect=aspect, n=n, wait=wait)
        for i, (data, mime) in enumerate(items, start=1):
            saved.append(files.save_bytes(ctx.space_id, f"{slug}-{i}{media_api.EXT.get(mime, '.png')}", data, origin="job", job_id=ctx.id,
                                          meta={"media": "image", "prompt": prompt[:1000], "connection": meta["connection"], "aspect": aspect}))
    else:
        seconds = max(2, min(20, int(p.get("seconds") or 4)))
        (data, mime), meta = router.video(ctx.router, prompt, aspect=aspect, seconds=seconds, wait=wait)
        saved.append(files.save_bytes(ctx.space_id, f"{slug}{media_api.EXT.get(mime, '.mp4')}", data, origin="job", job_id=ctx.id,
                                      meta={"media": "video", "prompt": prompt[:1000], "connection": meta["connection"], "aspect": aspect, "seconds": seconds}))
    ctx.stage("entrega", 0.95, "Guardando el resultado")
    d = review.create(ctx.space_id, "documento", f"{label}: {prompt[:70]}", {
        "summary": f"{len(saved)} archivo(s) generado(s) con {meta['connection']}.",
        "sections": [
            {"key": "indicacion", "title": "Indicación usada", "type": "text", "body": prompt},
            {"key": "archivos", "title": "Archivos", "type": "files", "items": [{"file_id": f["id"], "name": f["name"], "note": f"{label} · {aspect}"} for f in saved]},
            {"key": "uso", "title": "Antes de publicar", "type": "list", "items": [
                "Es material generado por IA: revísalo entero (manos, textos, logotipos, rostros) antes de usarlo.",
                "Comprueba en las condiciones del proveedor si puedes usarlo comercialmente y si debes etiquetarlo como generado por IA.",
                "No uses la imagen o la voz de personas reales ni marcas de terceros sin permiso."]},
        ]}, author="jarvis", job_id=ctx.id, project_id=p.get("project_id") or None)
    return {"mensaje": f"{label} lista: {len(saved)} archivo(s).", "deliverable_ids": [d["id"]], "file_ids": [f["id"] for f in saved]}
