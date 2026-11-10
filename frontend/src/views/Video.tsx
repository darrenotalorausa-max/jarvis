import { useEffect, useRef, useState } from "react";
import { api, label, url, type FileRow, type Rec } from "../api";
import { useApp } from "../store";
import { JobList, Needs, UploadButton, useFiles, useLaunch, useRecords } from "../components/shared";
import { Badge, Btn, Check, Empty, FieldRow, Panel, Select, Text } from "../components/ui";

type Seg = { id?: string; file_id: string; start: number; end: number; label: string; enabled: boolean };
type Cue = { start: number; end: number; text: string };
const tc = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;

export function Video() {
  const { space, run, boot, route, nav } = useApp();
  const projects = useRecords("video_project");
  const [title, setTitle] = useState("");
  const current = (projects.data || []).find((p) => p.id === route[1]);
  const ff = boot.ffmpeg;
  const create = async () => {
    const rec = await run(api<Rec>("/records", { body: { space: space.id, kind: "video_project", title: title || "Proyecto de video", data: {} } }));
    if (rec) { setTitle(""); projects.reload(); nav(`video/${rec.id}`); }
  };
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">Editor audiovisual</h1>
        <p className="page__sub">Recorta, une, reencuadra, subtitula, normaliza y exporta con FFmpeg. Los originales nunca se modifican. El manifiesto es un formato propio documentado; no es un proyecto de Premiere ni de Resolve.</p></div></div>
      {(!ff.ffmpeg?.disponible || !ff.ffprobe?.disponible) && <div className="banner"><span><strong>FFmpeg no está disponible.</strong> Instálalo siguiendo README_START_HERE.md y reinicia Jarvis; sin él no se puede leer ni exportar video.</span></div>}
      {!current ? (
        <Panel title="Proyectos de video">
          <form className="row" style={{ marginBottom: 12 }} onSubmit={(e) => { e.preventDefault(); create(); }}>
            <div style={{ flex: 1, minWidth: 200 }}><Text value={title} onChange={setTitle} placeholder="Nombre del proyecto" /></div><Btn kind="primary" type="submit">Crear proyecto</Btn>
          </form>
          {!projects.data?.length ? <Empty title="Aún no hay proyectos de video">Crea uno, importa tus archivos autorizados y define los segmentos que quieres exportar.</Empty> : (
            <div className="tablewrap"><table><thead><tr><th>Proyecto</th><th>Modo</th><th>Segmentos</th><th>Estado</th><th /></tr></thead>
              <tbody>{projects.data.map((p) => (
                <tr key={p.id}><td><button className="linkbtn" onClick={() => nav(`video/${p.id}`)}>{p.title}</button></td><td>{label(p.data.mode)}</td><td>{(p.data.segments || []).length}</td><td><Badge value={p.status} /></td>
                  <td><Btn small kind="ghost" onClick={async () => { await run(api(`/records/${p.id}`, { method: "PATCH", body: { space: space.id, archived: true } }), "Proyecto archivado"); projects.reload(); }}>Archivar</Btn></td></tr>
              ))}</tbody></table></div>
          )}
        </Panel>
      ) : <Editor key={current.id} project={current} onSaved={projects.reload} />}
    </div>
  );
}

function Editor({ project, onSaved }: { project: Rec; onSaved: () => void }) {
  const { space, run, boot, nav, notify, doneTick } = useApp();
  const launch = useLaunch();
  const files = useFiles();
  const campaigns = useRecords("campaign");
  const [d, setD] = useState<Record<string, any>>(project.data);
  const [dirty, setDirty] = useState(false);
  const [active, setActive] = useState<string>(project.data.sources?.[0] || "");
  const [mark, setMark] = useState<{ start: number; end: number }>({ start: 0, end: 0 });
  const [previewAt, setPreviewAt] = useState<string | null>(null);
  const [missing, setMissing] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const subsInput = useRef<HTMLInputElement>(null);
  // Tras terminar un trabajo (transcripción, sugerencias, exportación) se recarga el proyecto desde el servidor si no hay cambios locales.
  useEffect(() => { if (!dirty) setD(project.data); }, [project.updated_at, doneTick]); // eslint-disable-line react-hooks/exhaustive-deps
  const upd = (patch: Record<string, any>) => { setD((x) => ({ ...x, ...patch })); setDirty(true); };
  const byId = Object.fromEntries((files.data || []).map((f) => [f.id, f]));
  const media = (files.data || []).filter((f) => f.meta?.has_video && f.origin === "upload");
  const sources: FileRow[] = (d.sources || []).map((id: string) => byId[id]).filter(Boolean);
  const cur = byId[active];
  const segs: Seg[] = d.segments || [];
  const cues: Cue[] = d.subtitles?.[active] || [];
  const save = async () => {
    const saved = await run(api<Rec>(`/records/${project.id}`, { method: "PATCH", body: { space: space.id, data: d } }), "Proyecto guardado");
    if (saved) { setD(saved.data); setDirty(false); onSaved(); }
    return saved;
  };
  const job = async (type: string, params: Record<string, unknown>, title: string) => { if (dirty && !(await save())) return; await launch(type, { project_id: project.id, ...params }, title); };
  const now = () => Number((video.current?.currentTime || 0).toFixed(2));
  const addSeg = (s: Partial<Seg>) => upd({ segments: [...segs, { file_id: active, start: 0, end: Math.min(cur?.meta?.duration || 5, 15), label: "", enabled: true, ...s }] });
  const setSeg = (i: number, patch: Partial<Seg>) => upd({ segments: segs.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  const setCues = (list: Cue[]) => upd({ subtitles: { ...(d.subtitles || {}), [active]: list } });
  const preset = (d.presets || ["9:16"])[0];
  const importSubs = async (file?: File) => {
    if (!file || !active) return;
    if (dirty && !(await save())) return;
    const saved = await run(api<Rec>(`/video/${project.id}/subtitles`, { body: { space: space.id, file: active, text: await file.text() } }), "Subtítulos importados");
    if (saved) { setD(saved.data); onSaved(); }
  };
  const camp = (campaigns.data || []).find((c) => c.id === d.campaign_id);

  return (
    <div className="grid grid--side">
      <div className="stack">
        <Panel title={project.title} actions={<>
          <Btn small kind="ghost" onClick={() => nav("video")}>Todos los proyectos</Btn>
          {dirty && <Badge value="warn" text="Cambios sin guardar" />}
          <Btn small kind="primary" onClick={save} disabled={!dirty}>Guardar</Btn>
        </>}>
          <div className="row" style={{ marginBottom: 10 }}>
            {sources.map((f) => <Btn small key={f.id} kind={active === f.id ? "primary" : "default"} onClick={() => setActive(f.id)}>{f.name}</Btn>)}
            <UploadButton accept="video/*,.mp4,.mov,.mkv,.webm,.m4v" onDone={(row) => { files.reload(); upd({ sources: [...(d.sources || []), row.id] }); setActive(row.id); }}>Importar video</UploadButton>
            {media.filter((f) => !(d.sources || []).includes(f.id)).length > 0 && (
              <div style={{ width: 220 }}><Select value="" onChange={(v) => { if (v) { upd({ sources: [...(d.sources || []), v] }); setActive(v); } }} empty="Añadir archivo ya subido…" options={media.filter((f) => !(d.sources || []).includes(f.id)).map((f) => [f.id, f.name])} /></div>
            )}
          </div>
          {!cur ? <Empty title="Importa un video para empezar">Usa solo material propio o con autorización. Formatos: MP4, MOV, MKV, WebM.</Empty> : <>
            <video ref={video} className="player" controls preload="metadata" src={url(`/files/${cur.id}/download`, { space: space.id, inline: true })} />
            <p className="small muted" style={{ marginTop: 6 }}>
              {cur.meta.probe_error ? <span className="amber">{cur.meta.probe_error}</span> : <>Duración {cur.meta.duration} s · {cur.meta.width}×{cur.meta.height} · video {cur.meta.video_codec || "—"} · audio {cur.meta.has_audio ? cur.meta.audio_codec : "sin pista"} · pistas: {(cur.meta.tracks || []).map((t: any) => t.tipo).join(", ")}</>}
            </p>
            <div className="row" style={{ marginTop: 8 }}>
              <Btn small onClick={() => setMark((m) => ({ ...m, start: now() }))}>Marcar inicio ({tc(mark.start)})</Btn>
              <Btn small onClick={() => setMark((m) => ({ ...m, end: now() }))}>Marcar fin ({tc(mark.end)})</Btn>
              <Btn small kind="primary" disabled={mark.end - mark.start < 0.2} onClick={() => addSeg({ start: mark.start, end: mark.end })}>Añadir segmento</Btn>
              <Btn small onClick={() => setPreviewAt(`${now()}-${Date.now()}`)}>Previsualizar encuadre aquí</Btn>
            </div>
            {previewAt && <div style={{ marginTop: 10 }}>
              <img className="framepreview" alt={`Previsualización del encuadre ${preset}`} src={url("/video/preview", { space: space.id, file: cur.id, t: previewAt.split("-")[0], preset, framing: d.framing, fx: d.focus_x, fy: d.focus_y, v: previewAt })}
                onError={() => { notify("No se pudo generar la previsualización del encuadre.", "error"); setPreviewAt(null); }} />
              <p className="small muted">Fotograma real con el encuadre «{boot.video.framings[d.framing]}» en {preset}.</p>
            </div>}
          </>}
        </Panel>

        <Panel title={`Segmentos (${segs.length})`} note="Edita la selección antes de renderizar. Un segmento con error no detiene el resto del lote.">
          {!segs.length ? <p className="muted small">Sin segmentos. Márcalos en el reproductor o añade un momento sugerido.</p> : (
            <div className="tablewrap"><table><thead><tr><th>Usar</th><th>Archivo</th><th>Inicio (s)</th><th>Fin (s)</th><th>Etiqueta</th><th /></tr></thead>
              <tbody>{segs.map((s, i) => (
                <tr key={i}>
                  <td><input type="checkbox" aria-label={`Usar segmento ${i + 1}`} checked={s.enabled} onChange={(e) => setSeg(i, { enabled: e.target.checked })} /></td>
                  <td className="small wrap">{byId[s.file_id]?.name || s.file_id}</td>
                  <td><input className="input" style={{ width: 90 }} type="number" step="0.1" aria-label="Inicio" value={s.start} onChange={(e) => setSeg(i, { start: Number(e.target.value) })} /></td>
                  <td><input className="input" style={{ width: 90 }} type="number" step="0.1" aria-label="Fin" value={s.end} onChange={(e) => setSeg(i, { end: Number(e.target.value) })} /></td>
                  <td><input className="input" aria-label="Etiqueta" value={s.label} onChange={(e) => setSeg(i, { label: e.target.value })} /></td>
                  <td><div className="row"><Btn small kind="ghost" onClick={() => { setActive(s.file_id); setTimeout(() => { if (video.current) video.current.currentTime = s.start; }, 150); }}>Ir</Btn>
                    <Btn small kind="ghost" onClick={() => upd({ segments: segs.filter((_, j) => j !== i) })}>Quitar</Btn></div></td>
                </tr>
              ))}</tbody></table></div>
          )}
          {(d.suggestions || []).filter((s: any) => s.file_id === active).length > 0 && <>
            <p className="subhead">Momentos sugeridos</p>
            {(d.suggestions as any[]).filter((s) => s.file_id === active).map((s, i) => (
              <div key={i} className="row small" style={{ padding: "4px 0" }}><span className="mono">{tc(s.start)}–{tc(s.end)}</span><span className="wrap" style={{ flex: 1 }}>{s.reason} <span className="muted">({s.origin})</span></span>
                <Btn small onClick={() => addSeg({ file_id: s.file_id, start: s.start, end: s.end, label: s.reason.slice(0, 40) })}>Añadir</Btn></div>
            ))}
          </>}
        </Panel>

        <Panel title={`Subtítulos de ${cur?.name || "—"}`} actions={cur && <>
          <input ref={subsInput} type="file" accept=".srt,.vtt" className="sr" tabIndex={-1} onChange={(e) => importSubs(e.target.files?.[0])} />
          <Btn small onClick={() => subsInput.current?.click()}>Importar SRT/VTT</Btn>
          {cues.length > 0 && <><a className="btn btn--sm" href={url(`/video/${project.id}/subtitles`, { space: space.id, file: active, fmt: "srt" })}>Exportar SRT</a>
            <a className="btn btn--sm" href={url(`/video/${project.id}/subtitles`, { space: space.id, file: active, fmt: "vtt" })}>Exportar VTT</a></>}
          <Btn small onClick={() => setCues([...cues, { start: now(), end: now() + 2, text: "" }])}>Añadir línea</Btn>
        </>} note={dirty && cues.length ? "Guarda el proyecto antes de exportar los subtítulos para incluir tus cambios." : undefined}>
          {!cues.length ? <p className="muted small">Sin subtítulos. Transcribe el audio (requiere proveedor de transcripción), importa un SRT/VTT o añade líneas a mano.</p> : (
            <div className="tablewrap" style={{ maxHeight: 300, overflowY: "auto" }}><table><thead><tr><th>Inicio</th><th>Fin</th><th>Texto</th><th /></tr></thead>
              <tbody>{cues.map((c, i) => (
                <tr key={i}>
                  <td><input className="input" style={{ width: 84 }} type="number" step="0.1" aria-label="Inicio" value={c.start} onChange={(e) => setCues(cues.map((x, j) => (j === i ? { ...x, start: Number(e.target.value) } : x)))} /></td>
                  <td><input className="input" style={{ width: 84 }} type="number" step="0.1" aria-label="Fin" value={c.end} onChange={(e) => setCues(cues.map((x, j) => (j === i ? { ...x, end: Number(e.target.value) } : x)))} /></td>
                  <td><input className="input" aria-label="Texto" value={c.text} onChange={(e) => setCues(cues.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} /></td>
                  <td><Btn small kind="ghost" onClick={() => setCues(cues.filter((_, j) => j !== i))}>Quitar</Btn></td>
                </tr>
              ))}</tbody></table></div>
          )}
        </Panel>
      </div>

      <div className="stack">
        <Panel title="Ajustes de exportación">
          <div className="stack">
            <FieldRow label="Modo"><Select value={d.mode} onChange={(v) => upd({ mode: v })} options={boot.video.modes.map((m) => [m, label(m)])} /></FieldRow>
            <FieldRow group label="Formatos (se exporta un archivo por formato)">
              <div className="row">{boot.video.presets.map((p) => <Check key={p} checked={(d.presets || []).includes(p)} onChange={(v) => upd({ presets: v ? [...(d.presets || []), p] : (d.presets || []).filter((x: string) => x !== p) })}>{p}</Check>)}</div>
            </FieldRow>
            <FieldRow label="Encuadre"><Select value={d.framing} onChange={(v) => upd({ framing: v })} options={Object.entries(boot.video.framings)} /></FieldRow>
            {d.framing === "recorte" && <>
              <FieldRow label={`Punto de interés horizontal: ${Math.round((d.focus_x ?? 0.5) * 100)} %`}><input type="range" min="0" max="1" step="0.05" value={d.focus_x ?? 0.5} onChange={(e) => upd({ focus_x: Number(e.target.value) })} /></FieldRow>
              <FieldRow label={`Punto de interés vertical: ${Math.round((d.focus_y ?? 0.5) * 100)} %`}><input type="range" min="0" max="1" step="0.05" value={d.focus_y ?? 0.5} onChange={(e) => upd({ focus_y: Number(e.target.value) })} /></FieldRow>
            </>}
            <Check checked={!!d.normalize_audio} onChange={(v) => upd({ normalize_audio: v })}>Normalizar audio (EBU R128, −14 LUFS)</Check>
            <Check checked={!!d.burn_subtitles} onChange={(v) => upd({ burn_subtitles: v })}>Incrustar subtítulos en la imagen</Check>
            <Check checked={!!d.join} onChange={(v) => upd({ join: v })}>Unir los segmentos en un solo archivo</Check>
            <FieldRow label="Campaña de clipping vinculada"><Select value={d.campaign_id || ""} onChange={(v) => upd({ campaign_id: v || null })} empty="Ninguna" options={(campaigns.data || []).map((c) => [c.id, c.title])} /></FieldRow>
            {camp && <p className="note note--amber wrap">Reglas de «{camp.title}»: {camp.data.restrictions || "sin restricciones registradas"}. Plataformas: {(camp.data.platforms || []).join(", ") || "sin datos"}.</p>}
          </div>
        </Panel>
        <Panel title="Acciones">
          <div className="stack">
            <Btn kind="primary" disabled={!segs.some((s) => s.enabled)} onClick={() => job("video_render", {}, `Exportar: ${project.title}`)}>Exportar segmentos</Btn>
            <Btn disabled={!cur} onClick={() => job("video_suggest", { file_id: active }, `Sugerir momentos: ${cur?.name}`)}>Sugerir momentos</Btn>
            <Btn disabled={!cur?.meta?.has_audio} onClick={() => job("video_transcribe", { file_id: active }, `Transcribir: ${cur?.name}`)}>Transcribir audio</Btn>
            <a className="btn" href={url(`/video/${project.id}/manifest`, { space: space.id })}>Descargar manifiesto del proyecto</a>
          </div>
          <Needs caps={[]} optional={["transcripcion"]} />
          <p className="note">Sin modelo, las sugerencias usan detección de pausas del audio (determinista). Con transcripción y modelo de texto se eligen por contenido.</p>
        </Panel>
        <Panel title="Trabajos de video"><JobList types={["video_render", "video_suggest", "video_transcribe"]} limit={6} empty="Sin trabajos de video." /></Panel>
        <Panel title="Recursos propios" note="Material autorizado que acompaña al proyecto (imágenes, tomas). Queda registrado en el manifiesto; Jarvis no lo inserta automáticamente en el montaje.">
          {(files.data || []).filter((f) => f.origin === "upload" && !(d.sources || []).includes(f.id) && /^(image|video)\//.test(f.mime || "")).map((f) => (
            <Check key={f.id} checked={(d.own_resources || []).includes(f.id)} onChange={(v) => upd({ own_resources: v ? [...(d.own_resources || []), f.id] : (d.own_resources || []).filter((x: string) => x !== f.id) })}>{f.name}</Check>
          ))}
          <div style={{ marginTop: 8 }}><UploadButton accept="image/*,video/*" onDone={(row) => { files.reload(); upd({ own_resources: [...(d.own_resources || []), row.id] }); }}>Subir recurso</UploadButton></div>
        </Panel>
        <Panel title="Recursos faltantes" note="No se genera B-roll inexistente: anota lo que falta por conseguir o grabar.">
          <ul className="list small">{(d.missing_resources || []).map((m: string, i: number) => <li key={i}>{m} <button className="linkbtn" onClick={() => upd({ missing_resources: d.missing_resources.filter((_: string, j: number) => j !== i) })}>quitar</button></li>)}</ul>
          <form className="row" style={{ marginTop: 8 }} onSubmit={(e) => { e.preventDefault(); if (missing.trim()) { upd({ missing_resources: [...(d.missing_resources || []), missing.trim()] }); setMissing(""); } }}>
            <div style={{ flex: 1 }}><Text value={missing} onChange={setMissing} placeholder="Ej.: plano del producto en uso" /></div><Btn small type="submit">Anotar</Btn>
          </form>
        </Panel>
      </div>
    </div>
  );
}
