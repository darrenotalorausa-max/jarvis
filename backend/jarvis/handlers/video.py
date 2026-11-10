"""Editor audiovisual sobre FFmpeg. Los argumentos se construyen y validan aquí; nunca se ejecuta texto de un modelo."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .. import config, files, records, review, router
from ..jobs import JobError
from ..util import dumps, new_id, now_iso
from ..worker import handler
from .common import ask_json, available

PRESETS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
FRAMINGS = {"recorte": "Recorte centrado en el punto de interés", "relleno_desenfocado": "Imagen completa sobre fondo desenfocado", "barras": "Imagen completa con barras"}
MODES = ["clipping", "publicidad", "marca_personal", "formacion"]
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
          "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]
MANIFEST_VERSION = 1


def binary(name: str) -> str:
    path = os.environ.get(f"JARVIS_{name.upper()}") or shutil.which(name)
    if not path:
        raise JobError(f"{name} no está instalado o no está en el PATH. Consulta README_START_HERE.md para instalarlo.")
    return path


def ffmpeg_status() -> dict:
    out = {}
    for name in ("ffmpeg", "ffprobe"):
        try:
            path = binary(name)
            ver = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
            out[name] = {"disponible": True, "version": ver[:80]}
        except (JobError, OSError, subprocess.SubprocessError, IndexError):
            out[name] = {"disponible": False, "version": None}
    return out


def probe(path: Path) -> dict:
    res = subprocess.run([binary("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise JobError("El archivo no se pudo leer como medio audiovisual.")
    info = json.loads(res.stdout or "{}")
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    width, height = (v or {}).get("width"), (v or {}).get("height")
    rot = str(((v or {}).get("side_data_list") or [{}])[0].get("rotation", (v or {}).get("tags", {}).get("rotate", "0")))
    if v and rot.lstrip("-") in ("90", "270"):
        width, height = height, width
    return {"duration": round(float(info.get("format", {}).get("duration") or 0), 3), "width": width, "height": height,
            "has_video": bool(v), "has_audio": bool(a), "video_codec": (v or {}).get("codec_name"), "audio_codec": (a or {}).get("codec_name"),
            "tracks": [{"tipo": s.get("codec_type"), "codec": s.get("codec_name"), "idioma": s.get("tags", {}).get("language")} for s in streams]}


def default_project() -> dict:
    return {"mode": "clipping", "campaign_id": None, "sources": [], "segments": [], "presets": ["9:16"], "framing": "recorte", "focus_x": 0.5, "focus_y": 0.5,
            "normalize_audio": True, "burn_subtitles": False, "join": False, "subtitles": {}, "suggestions": [], "own_resources": [], "missing_resources": [], "outputs": []}


def _num(value, lo: float, hi: float, what: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise JobError(f"{what}: valor numérico no válido.")
    if not (lo <= v <= hi):
        raise JobError(f"{what}: fuera de rango.")
    return v


def validate_project(data: dict, space_id: str) -> dict:
    """Normaliza y valida la configuración editable del proyecto antes de guardarla o renderizarla."""
    out = {**default_project(), **{k: v for k, v in (data or {}).items() if k in default_project()}}
    if out["mode"] not in MODES:
        raise JobError("Modo no reconocido.")
    if out["framing"] not in FRAMINGS:
        raise JobError("Encuadre no reconocido.")
    out["presets"] = [p for p in dict.fromkeys(out["presets"] or []) if p in PRESETS] or ["9:16"]
    out["focus_x"], out["focus_y"] = _num(out["focus_x"], 0, 1, "Punto de interés"), _num(out["focus_y"], 0, 1, "Punto de interés")
    durations = {}
    for fid in out["sources"] + out["own_resources"]:
        f = files.get(fid, space_id)
        if not f:
            raise JobError("Un archivo del proyecto no existe en este espacio.")
        durations[fid] = f["meta"].get("duration") or 0
    segs = []
    for s in out["segments"]:
        if s.get("file_id") not in out["sources"]:
            raise JobError("Un segmento apunta a un archivo que no pertenece al proyecto.")
        dur = durations[s["file_id"]]
        start = _num(s.get("start", 0), 0, max(dur, 0), "Inicio del segmento")
        end = _num(s.get("end", 0), 0, dur + 0.05, "Fin del segmento")
        if end - start < 0.2:
            raise JobError("Cada segmento debe durar al menos 0,2 s y terminar después de empezar.")
        segs.append({"id": s.get("id") or new_id("seg"), "file_id": s["file_id"], "start": round(start, 3), "end": round(min(end, dur), 3),
                     "label": str(s.get("label") or "")[:80], "enabled": bool(s.get("enabled", True))})
    out["segments"] = segs
    subs = {}
    for fid, cues in (out["subtitles"] or {}).items():
        if fid in out["sources"]:
            subs[fid] = sorted(({"start": round(_num(c.get("start", 0), 0, 86400, "Subtítulo"), 3), "end": round(_num(c.get("end", 0), 0, 86400, "Subtítulo"), 3),
                                 "text": str(c.get("text") or "")[:400]} for c in cues if str(c.get("text") or "").strip()), key=lambda c: c["start"])
    out["subtitles"] = subs
    out["missing_resources"] = [str(m)[:200] for m in out["missing_resources"] if str(m).strip()]
    for flag in ("normalize_audio", "burn_subtitles", "join"):
        out[flag] = bool(out[flag])
    return out


# ---------- Subtítulos

def _ts(t: float, sep: str) -> str:
    ms = int(round(max(t, 0) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"


def to_srt(cues: list[dict]) -> str:
    return "\n".join(f"{i}\n{_ts(c['start'], ',')} --> {_ts(c['end'], ',')}\n{c['text'].strip()}\n" for i, c in enumerate(cues, start=1))


def to_vtt(cues: list[dict]) -> str:
    return "WEBVTT\n\n" + "\n".join(f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}\n{c['text'].strip()}\n" for c in cues)


_CUE = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[.,](\d{1,3})")


def parse_subtitles(text: str) -> list[dict]:
    """Admite SRT y VTT."""
    cues, cur = [], None
    for line in text.replace("\r", "").split("\n"):
        m = _CUE.search(line)
        if m:
            g = [int(x) for x in m.groups()]
            cur = {"start": g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, "end": g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, "text": ""}
            cues.append(cur)
        elif cur is not None and line.strip():
            cur["text"] = (cur["text"] + "\n" + line.strip()).strip()
        elif not line.strip():
            cur = None
    return [c for c in cues if c["text"]]


def _segment_cues(cues: list[dict], start: float, end: float) -> list[dict]:
    out = []
    for c in cues:
        if c["end"] > start and c["start"] < end:
            out.append({"start": max(c["start"], start) - start, "end": min(c["end"], end) - start, "text": c["text"]})
    return out


# ---------- Filtros

def filter_graph(framing: str, preset: str, fx: float, fy: float, srt_name: str | None = None, preview: bool = False) -> str:
    if preset not in PRESETS or framing not in FRAMINGS:
        raise JobError("Formato o encuadre no válido.")
    W, H = PRESETS[preset]
    fx, fy = _num(fx, 0, 1, "Punto de interés"), _num(fy, 0, 1, "Punto de interés")
    if framing == "recorte":
        g = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(iw-{W})*{fx:.3f}:(ih-{H})*{fy:.3f}"
    elif framing == "barras":
        g = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        g = (f"[0:v]split=2[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:2[bgb];"
             f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    g += ",setsar=1"
    if srt_name:
        if not re.fullmatch(r"[A-Za-z0-9_]+\.srt", srt_name):
            raise JobError("Nombre de subtítulos no válido.")
        g += f",subtitles={srt_name}:force_style='FontSize=14,Outline=2,Shadow=0,MarginV=48,Alignment=2'"
    if preview:
        g += f",scale={W // 3}:-2"
    return g + "[v]"


def preview_frame(file_row: dict, t: float, preset: str, framing: str, fx: float, fy: float) -> bytes:
    """Fotograma PNG con el encuadre aplicado, para previsualizar antes de renderizar."""
    dur = file_row["meta"].get("duration") or 0
    t = _num(t, 0, max(dur, 0), "Instante")
    res = subprocess.run([binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(files.path_of(file_row)),
                          "-frames:v", "1", "-filter_complex", filter_graph(framing, preset, fx, fy, preview=True), "-map", "[v]",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=60)
    if res.returncode != 0 or not res.stdout:
        raise JobError("No se pudo generar la previsualización del encuadre.")
    return res.stdout


def _workdir(ctx) -> Path:
    d = config.work_dir() / ctx.id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_project(ctx) -> tuple[dict, dict]:
    rec = records.get(ctx.params.get("project_id") or "", ctx.space_id)
    if not rec or rec["kind"] != "video_project":
        raise JobError("El proyecto de video no existe en este espacio.")
    return rec, validate_project(rec["data"], ctx.space_id)


def _save_project(ctx, rec: dict, data: dict, status: str | None = None) -> None:
    patch = {"data": data}
    if status:
        patch["status"] = status
    records.update(rec["id"], ctx.space_id, patch)


def _safe_cmd(args: list[str]) -> str:
    """Comando para el registro: sin rutas absolutas del equipo."""
    return " ".join(Path(a).name if os.sep in a or "/" in a else a for a in args)


# ---------- Trabajos

@handler("video_transcribe")
def video_transcribe(ctx) -> dict:
    rec, data = _load_project(ctx)
    f = files.get(ctx.params.get("file_id") or "", ctx.space_id)
    if not f or f["id"] not in data["sources"]:
        raise JobError("El archivo no pertenece al proyecto.")
    if not f["meta"].get("has_audio"):
        raise JobError("El archivo no tiene pista de audio que transcribir.")
    if not available(ctx, "transcripcion"):
        raise router.RouterError("needs_config", "No hay proveedor de transcripción disponible para este espacio. Configura uno en Conexiones "
                                 "(endpoint compatible con modelo de transcripción, o faster-whisper local) o importa un archivo SRT/VTT.")
    work = _workdir(ctx)
    try:
        ctx.stage("audio", 0.15, "Extrayendo audio")
        audio = work / "audio.mp3"
        args = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-i", str(files.path_of(f)), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio)]
        code, err = ctx.run_proc(args, timeout=1800)
        ctx.log("ffmpeg: " + _safe_cmd(args))
        if code != 0:
            raise JobError("No se pudo extraer el audio.")
        ctx.stage("transcripcion", 0.4, "Transcribiendo")
        result, meta = router.transcribe(ctx.router, audio, ctx.params.get("language"), minutes=(f["meta"].get("duration") or 0) / 60)
        cues = [c for c in result["segments"] if c["text"]]
        if not cues and result.get("text"):
            cues = [{"start": 0.0, "end": float(f["meta"].get("duration") or 0), "text": result["text"]}]
        data["subtitles"][f["id"]] = cues
        _save_project(ctx, rec, data)
        return {"mensaje": f"Transcripción lista: {len(cues)} segmentos ({meta['connection']}). El audio temporal se eliminó.", "segmentos": len(cues), "record_ids": [rec["id"]]}
    finally:
        shutil.rmtree(work, ignore_errors=True)


class Moment(BaseModel):
    start: float
    end: float
    reason: str


class Moments(BaseModel):
    moments: list[Moment] = Field(default_factory=list)


def _silence_blocks(ctx, path: Path, duration: float) -> list[tuple[float, float]]:
    args = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", "silencedetect=noise=-32dB:d=0.6", "-f", "null", "-"]
    code, err = ctx.run_proc(args, timeout=1800, tail=4_000_000)
    ctx.log("ffmpeg: " + _safe_cmd(args))
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", err)]
    blocks, pos = [], 0.0
    for i, s in enumerate(starts):
        if s - pos > 0.5:
            blocks.append((max(pos, 0.0), s))
        pos = ends[i] if i < len(ends) else duration
    if duration - pos > 0.5:
        blocks.append((pos, duration))
    return blocks


@handler("video_suggest")
def video_suggest(ctx) -> dict:
    rec, data = _load_project(ctx)
    f = files.get(ctx.params.get("file_id") or "", ctx.space_id)
    if not f or f["id"] not in data["sources"]:
        raise JobError("El archivo no pertenece al proyecto.")
    dur = float(f["meta"].get("duration") or 0)
    lo = _num(ctx.params.get("min_seconds") or 8, 1, 600, "Duración mínima")
    hi = _num(ctx.params.get("max_seconds") or 45, lo, 900, "Duración máxima")
    suggestions, origin = [], "cortes regulares"
    cues = data["subtitles"].get(f["id"]) or []
    if cues and available(ctx, "extraccion"):
        ctx.stage("seleccion", 0.4, "Seleccionando momentos a partir de la transcripción")
        transcript = "\n".join(f"[{c['start']:.1f}-{c['end']:.1f}] {c['text']}" for c in cues)[:14000]
        system = (f"Seleccionas momentos de un video para clips en modo «{data['mode']}». Usa solo los timecodes de la transcripción. "
                  f"Cada momento dura entre {lo:.0f} y {hi:.0f} segundos, empieza y termina en límites de frase y debe entenderse por sí solo. Explica el motivo en una frase.")
        res, _ = ask_json(ctx, Moments, system=system, user=f"Duración total: {dur:.1f} s\n<fuente id=\"transcripcion\">\n{transcript}\n</fuente>", max_tokens=1200, prompt_version="momentos-v1")
        for m in res.moments[:12]:
            if 0 <= m.start < m.end <= dur + 0.5 and lo * 0.7 <= m.end - m.start <= hi * 1.3:
                suggestions.append({"file_id": f["id"], "start": round(m.start, 2), "end": round(min(m.end, dur), 2), "reason": m.reason[:200], "origin": "modelo sobre transcripción"})
        origin = "modelo sobre transcripción"
    if not suggestions and f["meta"].get("has_audio"):
        ctx.stage("silencios", 0.4, "Detectando pausas en el audio")
        cur = None
        for s, e in _silence_blocks(ctx, files.path_of(f), dur):
            if cur and e - cur[0] <= hi:
                cur = (cur[0], e)
            else:
                if cur and cur[1] - cur[0] >= lo:
                    suggestions.append(cur)
                cur = (s, min(e, s + hi))
        if cur and cur[1] - cur[0] >= lo:
            suggestions.append(cur)
        suggestions = [{"file_id": f["id"], "start": round(s, 2), "end": round(e, 2), "reason": "Bloque de habla continuo entre pausas", "origin": "detección de silencios"} for s, e in suggestions[:20]]
        origin = "detección de silencios"
    if not suggestions:
        step, t = min(hi, max(lo, 30)), 0.0
        while t + lo <= dur and len(suggestions) < 20:
            suggestions.append({"file_id": f["id"], "start": round(t, 2), "end": round(min(t + step, dur), 2), "reason": "Corte regular (sin audio o sin pausas detectables)", "origin": "cortes regulares"})
            t += step
        origin = "cortes regulares"
    data["suggestions"] = [s for s in data["suggestions"] if s["file_id"] != f["id"]] + suggestions
    _save_project(ctx, rec, data)
    return {"mensaje": f"{len(suggestions)} momentos sugeridos ({origin}). Revísalos y añade los que quieras como segmentos.", "sugerencias": len(suggestions), "record_ids": [rec["id"]]}


@handler("video_render")
def video_render(ctx) -> dict:
    rec, data = _load_project(ctx)
    segs = [s for s in data["segments"] if s["enabled"]]
    if not segs:
        raise JobError("El proyecto no tiene segmentos activos que exportar.")
    work = _workdir(ctx)
    ffmpeg = binary("ffmpeg")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", rec["title"]).strip("_")[:40] or "video"
    outputs, failed, commands = [], [], []
    total = len(segs) * len(data["presets"])
    done = 0
    try:
        for preset in data["presets"]:
            tag = preset.replace(":", "x")
            rendered = []
            for i, seg in enumerate(segs, start=1):
                ctx.stage("render", 0.05 + 0.85 * done / total, f"Renderizando segmento {i} de {len(segs)} en {preset}")
                done += 1
                src = files.get(seg["file_id"], ctx.space_id)
                name = f"seg_{tag}_{i:02d}.mp4"
                try:
                    if not src or not src["meta"].get("has_video"):
                        raise JobError("el archivo de origen no existe o no tiene video")
                    srt_name = None
                    if data["burn_subtitles"]:
                        cues = _segment_cues(data["subtitles"].get(seg["file_id"]) or [], seg["start"], seg["end"])
                        if cues:
                            srt_name = f"subs_{tag}_{i:02d}.srt"
                            (work / srt_name).write_text(to_srt(cues), encoding="utf-8")
                    args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-ss", f"{seg['start']:.3f}", "-t", f"{seg['end'] - seg['start']:.3f}", "-i", str(files.path_of(src))]
                    if src["meta"].get("has_audio"):
                        amap = "0:a:0"
                    else:
                        args += ["-f", "lavfi", "-t", f"{seg['end'] - seg['start']:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
                        amap = "1:a:0"
                    args += ["-filter_complex", filter_graph(data["framing"], preset, data["focus_x"], data["focus_y"], srt_name), "-map", "[v]", "-map", amap]
                    if data["normalize_audio"] and src["meta"].get("has_audio"):
                        args += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
                    args += [*ENCODE, "-shortest", name]
                    code, err = ctx.run_proc(args, cwd=str(work), timeout=3600)
                    commands.append(_safe_cmd(args))
                    if code != 0 or not (work / name).exists():
                        raise JobError((err.strip().splitlines() or ["error de FFmpeg"])[-1][:200])
                    rendered.append((seg, name))
                except JobError as exc:
                    # Un clip fallido no detiene el lote ni toca los originales.
                    failed.append({"segmento": seg["label"] or seg["id"], "formato": preset, "error": exc.message})
                    ctx.log(f"Segmento {i} ({preset}) falló: {exc.message}")
            if data["join"] and len(rendered) > 1:
                ctx.stage("union", 0.92, f"Uniendo {len(rendered)} segmentos en {preset}")
                (work / f"list_{tag}.txt").write_text("".join(f"file '{n}'\n" for _, n in rendered), encoding="utf-8")
                joined = f"{slug}_{tag}.mp4"
                args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", f"list_{tag}.txt", "-c", "copy", "-movflags", "+faststart", joined]
                code, err = ctx.run_proc(args, cwd=str(work), timeout=1800)
                commands.append(_safe_cmd(args))
                if code == 0 and (work / joined).exists():
                    meta = probe(work / joined)
                    outputs.append(files.adopt(ctx.space_id, work / joined, joined, job_id=ctx.id, meta={**meta, "preset": preset, "segmentos": [s["id"] for s, _ in rendered]}))
                else:
                    failed.append({"segmento": "unión", "formato": preset, "error": (err.strip().splitlines() or ["error"])[-1][:200]})
            else:
                for j, (seg, name) in enumerate(rendered, start=1):
                    final = f"{slug}_{tag}_{j:02d}.mp4"
                    meta = probe(work / name)
                    outputs.append(files.adopt(ctx.space_id, work / name, final, job_id=ctx.id, meta={**meta, "preset": preset, "segmentos": [seg["id"]], "etiqueta": seg["label"]}))
        if not outputs:
            raise JobError("Ningún clip pudo exportarse: " + "; ".join(f"{f['segmento']}: {f['error']}" for f in failed)[:400])
        campaign = records.get(data.get("campaign_id") or "", ctx.space_id)
        manifest = build_manifest(rec, data, ctx.space_id, outputs)
        mf = files.save_bytes(ctx.space_id, f"{slug}_manifiesto.json", dumps(manifest).encode("utf-8"), job_id=ctx.id)
        data["outputs"] = [o["id"] for o in outputs]
        _save_project(ctx, rec, data, status="exportado")
        sections = [{"key": "archivos", "title": "Archivos exportados", "type": "files",
                     "items": [{"file_id": o["id"], "name": o["name"], "note": f"{o['meta'].get('width')}×{o['meta'].get('height')}, {o['meta'].get('duration')} s"} for o in outputs]
                     + [{"file_id": mf["id"], "name": mf["name"], "note": "Manifiesto del proyecto"}]},
                    {"key": "configuracion", "title": "Configuración aplicada", "type": "list",
                     "items": [f"Modo: {data['mode']}", f"Formatos: {', '.join(data['presets'])}", f"Encuadre: {FRAMINGS[data['framing']]}",
                               f"Audio normalizado: {'sí' if data['normalize_audio'] else 'no'}", f"Subtítulos incrustados: {'sí' if data['burn_subtitles'] else 'no'}",
                               f"Segmentos unidos: {'sí' if data['join'] else 'no'}"]},
                    {"key": "fallos", "title": "Clips con error", "type": "list", "items": [f"{f['segmento']} ({f['formato']}): {f['error']}" for f in failed] or ["Ninguno"]},
                    {"key": "recursos_faltantes", "title": "Recursos faltantes", "type": "list", "items": data["missing_resources"] or ["Ninguno anotado"]},
                    {"key": "comandos", "title": "Registro de comandos FFmpeg", "type": "list", "items": commands}]
        if campaign:
            c = campaign["data"]
            sections.insert(1, {"key": "reglas_campana", "title": f"Reglas de la campaña «{campaign['title']}»", "type": "list",
                                "items": [f"Plataformas: {', '.join(c.get('platforms') or []) or 'sin datos'}", f"Restricciones: {c.get('restrictions') or 'sin datos'}",
                                          f"Vistas válidas: {c.get('valid_views_rules') or 'sin datos'}", f"Aprobación: {c.get('approval_process') or 'sin datos'}"],
                                "note": "Comprueba el clip contra estas reglas antes de publicarlo; Jarvis no publica."})
        d = review.create(ctx.space_id, "video", f"Exportación: {rec['title']}", {"summary": f"{len(outputs)} archivo(s) exportado(s)" + (f"; {len(failed)} con error." if failed else "."),
                          "sections": sections, "meta": {"video_project_id": rec["id"]}}, author="jarvis", job_id=ctx.id, project_id=rec["project_id"], ref_id=rec["id"])
        return {"mensaje": f"{len(outputs)} archivo(s) exportado(s)" + (f", {len(failed)} con error" if failed else "") + ".", "deliverable_ids": [d["id"]],
                "file_ids": [o["id"] for o in outputs], "fallidos": failed}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_manifest(rec: dict, data: dict, space_id: str, outputs: list[dict] | None = None) -> dict:
    """Manifiesto documentado en docs/VIDEO_MANIFEST.md. Es un formato propio, no un proyecto de Premiere o Resolve."""
    def src(fid):
        f = files.get(fid, space_id)
        return {"id": fid, "nombre": f["name"], "sha256": f["sha256"], "duracion": f["meta"].get("duration"), "ancho": f["meta"].get("width"), "alto": f["meta"].get("height")} if f else {"id": fid}
    return {"formato": "jarvis-video-manifest", "version": MANIFEST_VERSION, "generado": now_iso(),
            "proyecto": {"id": rec["id"], "titulo": rec["title"], "modo": data["mode"], "campana_id": data.get("campaign_id")},
            "origenes": [src(f) for f in data["sources"]], "recursos_propios": [src(f) for f in data["own_resources"]],
            "segmentos": data["segments"], "subtitulos": data["subtitles"],
            "ajustes": {"formatos": {p: {"ancho": PRESETS[p][0], "alto": PRESETS[p][1]} for p in data["presets"]}, "encuadre": data["framing"],
                        "punto_interes": [data["focus_x"], data["focus_y"]], "normalizar_audio": data["normalize_audio"],
                        "subtitulos_incrustados": data["burn_subtitles"], "unir_segmentos": data["join"], "codificacion": " ".join(ENCODE)},
            "recursos_faltantes": data["missing_resources"],
            "salidas": [{"id": o["id"], "nombre": o["name"], "sha256": o["sha256"], **{k: o["meta"].get(k) for k in ("preset", "duration", "width", "height")}} for o in (outputs or [])]}
