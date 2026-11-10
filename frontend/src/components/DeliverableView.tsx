import { useEffect, useState } from "react";
import { api, fmtDate, freshness, url, type Section } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, ErrorBox, FieldRow, Modal, Panel, Rich, Select, Text } from "./ui";

type Detail = {
  id: string; kind: string; kind_label: string; title: string; status: string; current_version: number; job_id: string | null;
  version: { version: number; content: { summary: string; sections: Section[]; source_ids: string[]; meta: any }; checks: any; author: string; created_at: string; note: string; content_hash: string };
  versions: { version: number; author: string; note: string; created_at: string }[]; comments: any[]; approvals: any[]; sources: any[];
};
const FACT_LABEL: Record<string, string> = { hecho: "Hecho", hipotesis: "Hipótesis", desconocido: "Desconocido" };

function SectionView({ s, spaceId }: { s: Section; spaceId: string }) {
  return (
    <div className="stack">
      {s.body && <Rich text={s.body} />}
      {s.type === "list" && (s.items.length ? <ul className="list">{s.items.map((it, i) => <li key={i}>{String(it)}</li>)}</ul> : !s.body && <p className="muted small">Sin contenido.</p>)}
      {s.type === "facts" && (s.items.length ? s.items.map((f, i) => (
        <div key={i} className={`fact fact--${f.kind}`}>
          <div><Badge value={f.kind === "hecho" ? "ok" : f.kind === "hipotesis" ? "warn" : "mute"} text={FACT_LABEL[f.kind] || f.kind} /> {f.signal && <span className="small muted">señal: {f.signal}</span>}</div>
          <div className="wrap">{f.claim}</div>
          {f.evidence && <div className="small wrap">Evidencia: «{f.evidence}»</div>}
          {f.source_ids?.length > 0 && <div className="small mono">Fuentes: {f.source_ids.join(", ")}</div>}
          {f.limitations && <div className="small muted wrap">Limitaciones: {f.limitations}</div>}
        </div>
      )) : <p className="muted small">Sin elementos.</p>)}
      {s.type === "scores" && s.items.map((it, i) => (
        <div key={i} className="check-row" style={{ gridTemplateColumns: "210px 60px 1fr" }}><strong>{it.label}</strong><span className="mono">{it.value}/5</span><span className="small wrap">{it.rationale}</span></div>
      ))}
      {s.type === "table" && (s.rows.length ? (
        <div className="tablewrap"><table><thead><tr>{s.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{s.rows.map((r, i) => <tr key={i}>{s.columns.map((_, j) => <td key={j} className="wrap">{String(r[j] ?? "")}</td>)}</tr>)}</tbody></table></div>
      ) : <p className="muted small">Tabla vacía.</p>)}
      {s.type === "files" && <ul className="list">{s.items.map((f, i) => (
        <li key={i}><a href={url(`/files/${f.file_id}/download`, { space: spaceId })}>{f.name}</a>{f.note && <span className="muted small"> — {f.note}</span>}
          {String(f.name).endsWith(".mp4") && <div><video className="player" style={{ maxHeight: 240, marginTop: 6 }} controls preload="none" src={url(`/files/${f.file_id}/download`, { space: spaceId, inline: true })} /></div>}</li>
      ))}</ul>}
      {s.note && <p className="note">{s.note}</p>}
    </div>
  );
}

function SectionEdit({ s, onChange }: { s: Section; onChange: (s: Section) => void }) {
  const upd = (patch: Partial<Section>) => onChange({ ...s, ...patch });
  const item = (i: number, patch: any) => upd({ items: s.items.map((it, j) => (j === i ? { ...it, ...patch } : it)) });
  return (
    <div className="stack">
      {(s.type === "text" || s.body) && <Text area rows={Math.min(18, Math.max(3, s.body.split("\n").length + 1))} value={s.body} onChange={(v) => upd({ body: v })} />}
      {s.type === "list" && <FieldRow label="Un elemento por línea"><Text area rows={Math.max(3, s.items.length + 1)} value={s.items.join("\n")} onChange={(v) => upd({ items: v.split("\n").filter((x) => x.trim()) })} /></FieldRow>}
      {s.type === "facts" && <>
        {s.items.map((f, i) => (
          <div key={i} className={`fact fact--${f.kind}`}>
            <div className="row">
              <div style={{ width: 150 }}><Select value={f.kind} onChange={(v) => item(i, { kind: v })} options={Object.entries(FACT_LABEL)} /></div>
              <Btn small kind="ghost" onClick={() => upd({ items: s.items.filter((_, j) => j !== i) })}>Quitar</Btn>
            </div>
            <Text area rows={2} value={f.claim} onChange={(v) => item(i, { claim: v })} placeholder="Afirmación" />
            <Text value={f.evidence} onChange={(v) => item(i, { evidence: v })} placeholder="Cita de evidencia" />
            <Text value={(f.source_ids || []).join(", ")} onChange={(v) => item(i, { source_ids: v.split(",").map((x) => x.trim()).filter(Boolean) })} placeholder="IDs de fuente (src_…), separados por comas" />
            <Text value={f.limitations} onChange={(v) => item(i, { limitations: v })} placeholder="Limitaciones" />
          </div>
        ))}
        <Btn small onClick={() => upd({ items: [...s.items, { claim: "", kind: "hipotesis", source_ids: [], evidence: "", limitations: "" }] })}>Añadir afirmación</Btn>
      </>}
      {s.type === "scores" && s.items.map((it, i) => (
        <div key={i} className="row"><strong style={{ width: 210 }}>{it.label}</strong>
          <div style={{ width: 80 }}><Text type="number" value={it.value} onChange={(v) => item(i, { value: Math.max(0, Math.min(5, Number(v) || 0)) })} /></div>
          <div style={{ flex: 1, minWidth: 160 }}><Text value={it.rationale} onChange={(v) => item(i, { rationale: v })} /></div></div>
      ))}
      {s.type === "table" && <>
        <div className="tablewrap"><table><thead><tr>{s.columns.map((c) => <th key={c}>{c}</th>)}<th /></tr></thead>
          <tbody>{s.rows.map((r, i) => (
            <tr key={i}>{s.columns.map((_, j) => <td key={j}><textarea className="input" rows={1} value={String(r[j] ?? "")} aria-label={`${s.columns[j]}, fila ${i + 1}`}
              onChange={(e) => upd({ rows: s.rows.map((row, k) => (k === i ? row.map((c, m) => (m === j ? e.target.value : c)) : row)) })} /></td>)}
              <td><Btn small kind="ghost" onClick={() => upd({ rows: s.rows.filter((_, k) => k !== i) })}>Quitar</Btn></td></tr>
          ))}</tbody></table></div>
        <Btn small onClick={() => upd({ rows: [...s.rows, s.columns.map(() => "")] })}>Añadir fila</Btn>
      </>}
      {s.type === "files" && <p className="small muted">Los archivos adjuntos no se editan aquí; vuelve a generar el entregable para cambiarlos.</p>}
    </div>
  );
}

export function DeliverableView({ id, onChanged }: { id: string; onChanged?: () => void }) {
  const { space, run, nav, boot, doneTick, refreshJobs } = useApp();
  const { data: d, error, reload } = useData<Detail>(() => api(`/deliverables/${id}`, { query: { space: space.id } }), [id, space.id, doneTick]);
  const [draft, setDraft] = useState<{ title: string; summary: string; sections: Section[] } | null>(null);
  const [note, setNote] = useState("");
  const [comment, setComment] = useState("");
  const [dialog, setDialog] = useState<null | "approve" | "send" | "diff" | "exports">(null);
  const [exports, setExports] = useState<any>(null);
  const [diff, setDiff] = useState<{ a: number; b: number; lines?: string[] }>({ a: 1, b: 1 });
  const [send, setSend] = useState<{ conn: string; scope: string; hours: string }>({ conn: "", scope: "", hours: "24" });
  const conns = useData<any[]>(() => api("/connections"), [dialog === "send"]);
  useEffect(() => { setDraft(null); setExports(null); }, [id]);
  if (error) return <ErrorBox message={error} retry={reload} />;
  if (!d) return <p className="muted">Cargando entregable…</p>;
  const v = d.version, c = v.content;
  const post = async (path: string, body: Record<string, unknown>, ok?: string) => { const r = await run(api(`/deliverables/${id}/${path}`, { body: { space: space.id, ...body } }), ok); reload(); onChanged?.(); return r; };
  const save = async () => {
    if (!draft) return;
    const r = await post("versions", { title: draft.title, note: note || "Edición manual", content: { ...c, summary: draft.summary, sections: draft.sections } }, "Nueva versión guardada; las aprobaciones anteriores quedan invalidadas");
    if (r) { setDraft(null); setNote(""); }
  };
  const doExport = async (format: string) => { const r = await post("export", { format }); if (r) { setExports(r); setDialog("exports"); } };
  const loadDiff = async (a: number, b: number) => { const r = await run(api<any>(`/deliverables/${id}/diff`, { query: { space: space.id, a, b } })); setDiff({ a, b, lines: r?.diff }); };
  const hooks = (conns.data || []).filter((x) => x.provider === "webhook");
  const validApprovals = d.approvals.filter((a) => a.valid);
  const sendExternal = async () => {
    const hook = hooks.find((h) => h.id === send.conn);
    if (!hook) return;
    await post("approve", { version: d.current_version, action: "envio_externo", destination: hook.base_url, scope: send.scope, expires_hours: Number(send.hours) || 24 });
    const r: any = await post("send", { connection_id: hook.id });
    if (r?.job) { refreshJobs(); setDialog(null); }
  };

  return (
    <div className="grid grid--side">
      <div className="stack">
        <Panel title={<>{d.kind_label} · <span className="mono">{d.id}</span></>} actions={<>
          <Badge value={d.status} /> <span className="small muted">v{d.current_version} · {v.author} · {fmtDate(v.created_at)}</span>
        </>}>
          {draft ? <FieldRow label="Título"><Text value={draft.title} onChange={(t) => setDraft({ ...draft, title: t })} /></FieldRow> : <h1 className="page__title wrap">{d.title}</h1>}
          {draft ? <FieldRow label="Resumen"><Text area rows={2} value={draft.summary} onChange={(t) => setDraft({ ...draft, summary: t })} /></FieldRow> : c.summary && <p className="muted" style={{ marginTop: 6 }}>{c.summary}</p>}
          <div className="row" style={{ marginTop: 12 }}>
            {draft ? <>
              <div style={{ flex: 1, minWidth: 200 }}><Text value={note} onChange={setNote} placeholder="Nota de la versión (qué cambió)" /></div>
              <Btn onClick={() => setDraft(null)}>Descartar cambios</Btn>
              <Btn kind="primary" onClick={save}>Guardar como v{d.current_version + 1}</Btn>
            </> : <>
              <Btn onClick={() => setDraft({ title: d.title, summary: c.summary, sections: structuredClone(c.sections) })}>Editar</Btn>
              {["borrador", "cambios_solicitados", "rechazado"].includes(d.status) && <Btn onClick={() => post("status", { status: "en_revision" }, "Enviado a revisión")}>Enviar a revisión</Btn>}
              <Btn kind="primary" onClick={() => setDialog("approve")} disabled={d.status === "aprobado"}>Aprobar v{d.current_version}</Btn>
              <Btn onClick={() => doExport("md")}>Exportar Markdown</Btn>
              <Btn onClick={() => doExport("json")}>JSON</Btn>
              {c.sections.some((s) => s.type === "table") && <Btn onClick={() => doExport("csv")}>CSV</Btn>}
              {c.sections.some((s) => s.type === "files") && <Btn onClick={() => doExport("archivos")}>Copiar archivos a exports</Btn>}
              <Btn kind="amber" onClick={() => setDialog("send")}>Envío externo…</Btn>
              {d.versions.length > 1 && <Btn onClick={() => { setDialog("diff"); loadDiff(d.current_version - 1, d.current_version); }}>Comparar versiones</Btn>}
            </>}
          </div>
          {d.kind === "dossier" && !draft && (
            <div className="row" style={{ marginTop: 10 }}>
              <span className="small muted">Convertir en:</span>
              {[["producto", "Producto"], ["oferta_b2b", "Oferta B2B"], ["brief", "Brief de contenido"], ["proyecto", "Proyecto"]].map(([t, text]) => (
                <Btn small key={t} onClick={async () => { const r: any = await post("convert", { target: t }); if (r) run(Promise.resolve(), r.nota); }}>{text}</Btn>
              ))}
            </div>
          )}
        </Panel>
        {(draft ? draft.sections : c.sections).map((s, i) => (
          <Panel key={s.key} title={s.title}>
            {draft ? <SectionEdit s={s} onChange={(ns) => setDraft({ ...draft, sections: draft.sections.map((x, j) => (j === i ? ns : x)) })} /> : <SectionView s={s} spaceId={space.id} />}
          </Panel>
        ))}
      </div>

      <div className="stack">
        <Panel title="Comprobaciones automáticas" note={v.checks?.nota}>
          {(v.checks?.automaticas || []).map((k: any) => (
            <div className="check-row" key={k.id}><Badge value={k.result} text={k.result === "ok" ? "Correcto" : k.result === "warn" ? "Aviso" : "Falla"} /><div><div>{k.label}</div>{k.detail && <div className="small muted wrap">{k.detail}</div>}</div></div>
          ))}
          <p className="panel__title" style={{ margin: "14px 0 6px" }}>Requiere revisión de una persona</p>
          <ul className="list small">{(v.checks?.requiere_persona || []).map((t: string) => <li key={t}>{t}</li>)}</ul>
        </Panel>
        <Panel title="Aprobaciones">
          {!d.approvals.length ? <p className="muted small">Sin aprobaciones registradas.</p> : d.approvals.map((a) => (
            <div key={a.id} className="check-row" style={{ gridTemplateColumns: "88px 1fr" }}>
              <Badge value={a.valid ? "ok" : "mute"} text={a.valid ? "Vigente" : "No vigente"} />
              <div className="small wrap">
                <strong>{a.action === "version" ? "Versión aprobada" : "Envío externo"}</strong> · v{a.version} · {a.user} · {fmtDate(a.created_at)}
                {a.destination && <div>Destino: {a.destination}</div>}{a.scope && <div>Alcance: {a.scope}</div>}
                <div className="muted">{a.revoked_at ? `Invalidada: ${a.revoke_reason}` : a.used_at ? `Usada ${fmtDate(a.used_at)}` : `Caduca ${fmtDate(a.expires_at)}`}</div>
                {a.valid && <Btn small kind="ghost" onClick={async () => { await run(api(`/approvals/${a.id}/revoke`, { method: "POST" })); reload(); }}>Revocar</Btn>}
              </div>
            </div>
          ))}
          <div className="row" style={{ marginTop: 10 }}><Btn small kind="danger" onClick={() => post("reject", { reason: comment || "Rechazado" }, "Rechazado")}>Rechazar</Btn></div>
        </Panel>
        <Panel title="Comentarios">
          {d.comments.map((m) => <div key={m.id} className="msg msg--jarvis" style={{ marginBottom: 6 }}>{m.body}<span className="msg__meta">{m.kind === "cambio_solicitado" ? "Cambio solicitado" : m.kind === "rechazo" ? "Rechazo" : "Comentario"} · v{m.version} · {m.author} · {fmtDate(m.created_at)}</span></div>)}
          <Text area rows={2} value={comment} onChange={setComment} placeholder="Escribe un comentario o el cambio que pides" />
          <div className="row" style={{ marginTop: 8 }}>
            <Btn small disabled={!comment.trim()} onClick={async () => { await post("comments", { body: comment }); setComment(""); }}>Comentar</Btn>
            <Btn small kind="amber" disabled={!comment.trim()} onClick={async () => { await post("comments", { body: comment, kind: "cambio_solicitado" }); setComment(""); }}>Pedir cambios</Btn>
          </div>
        </Panel>
        {d.sources.length > 0 && (
          <Panel title={`Fuentes (${d.sources.length})`}>
            {d.sources.map((s) => (
              <div key={s.id} className="check-row" style={{ gridTemplateColumns: "1fr" }}>
                <div className="small wrap">
                  {String(s.url).startsWith("http") ? <a href={s.url} target="_blank" rel="noreferrer noopener">{s.title || s.url}</a> : <strong>{s.title}</strong>} <Badge value={s.status === "ok" ? "ok" : s.status === "solo_fragmento" ? "warn" : "fail"} text={s.status.replace("_", " ")} />
                  <div className="muted">Consultada {fmtDate(s.fetched_at)} ({freshness(s.fetched_at)}) · publicada: {s.published_at || "no disponible"} · vía {s.provider}</div>
                  <div className="mono">{s.id}</div>{s.note && <div className="muted">{s.note}</div>}
                </div>
              </div>
            ))}
          </Panel>
        )}
        <Panel title="Versiones">
          {d.versions.map((x) => <div key={x.version} className="small" style={{ padding: "4px 0" }}><strong>v{x.version}</strong> · {x.author} · {fmtDate(x.created_at)}<div className="muted wrap">{x.note}</div></div>)}
          {d.job_id && <p className="small muted" style={{ marginTop: 8 }}>Generado por <button className="linkbtn" onClick={() => nav(`sistema/${d.job_id}`)}>{d.job_id}</button></p>}
        </Panel>
      </div>

      {dialog === "approve" && (
        <Modal title={`Aprobar la versión ${d.current_version}`} onClose={() => setDialog(null)}>
          <p>La aprobación queda ligada a tu usuario y a esta versión exacta (<span className="mono">{v.content_hash.slice(0, 12)}…</span>). Si el contenido cambia, deja de ser válida.</p>
          <p className="note">Aprobar la versión no autoriza ningún envío o publicación externa: eso requiere una aprobación específica con destino.</p>
          <div className="row row--end"><Btn onClick={() => setDialog(null)}>Cancelar</Btn><Btn kind="primary" onClick={async () => { await post("approve", { version: d.current_version, action: "version" }, "Versión aprobada"); setDialog(null); }}>Aprobar</Btn></div>
        </Modal>
      )}
      {dialog === "send" && (
        <Modal title="Envío externo con aprobación específica" onClose={() => setDialog(null)}>
          {!hooks.length ? <>
            <p>No hay ningún destino externo configurado. Añade una conexión de tipo «Webhook de exportación» (por ejemplo, la entrada de tu CRM) en Conexiones.</p>
            <p className="note">Sin destino configurado puedes usar las exportaciones locales (Markdown, JSON, CSV) e importarlas a mano en tu CRM.</p>
            <div className="row row--end"><Btn onClick={() => nav("conexiones")}>Ir a Conexiones</Btn></div>
          </> : <div className="stack">
            <p>Vas a autorizar el envío de la <strong>versión {d.current_version}</strong> de «{d.title}» a un sistema externo. La autorización vale para un solo envío, este destino y esta versión.</p>
            <FieldRow label="Destino"><Select value={send.conn} onChange={(x) => setSend({ ...send, conn: x })} empty="Elige un destino" options={hooks.map((h) => [h.id, `${h.name} — ${h.base_url}`])} /></FieldRow>
            <FieldRow label="Alcance (para qué se autoriza)"><Text value={send.scope} onChange={(x) => setSend({ ...send, scope: x })} placeholder="Ej.: alta del lead en el CRM" /></FieldRow>
            <FieldRow label="Caducidad de la autorización (horas)"><Text type="number" value={send.hours} onChange={(x) => setSend({ ...send, hours: x })} /></FieldRow>
            <div className="row row--end"><Btn onClick={() => setDialog(null)}>Cancelar</Btn><Btn kind="amber" disabled={!send.conn} onClick={sendExternal}>Autorizar y enviar</Btn></div>
          </div>}
          {validApprovals.some((a) => a.action === "envio_externo") && <p className="small muted">Ya existe una autorización de envío vigente para esta versión.</p>}
        </Modal>
      )}
      {dialog === "exports" && exports && (
        <Modal title="Exportación creada" onClose={() => setDialog(null)}>
          <p>Versión {exports.version} exportada en formato {exports.formato}. Los archivos están en la carpeta <span className="mono wrap">{exports.carpeta}</span></p>
          <ul className="list">{exports.archivos.map((f: string) => <li key={f}><a href={url("/exports/file", { path: f })}>{f.split("/").pop()}</a></li>)}</ul>
        </Modal>
      )}
      {dialog === "diff" && (
        <Modal title="Comparar versiones" onClose={() => setDialog(null)} wide>
          <div className="row" style={{ marginBottom: 10 }}>
            <div style={{ width: 130 }}><Select value={String(diff.a)} onChange={(x) => loadDiff(Number(x), diff.b)} options={d.versions.map((x) => [String(x.version), `v${x.version}`])} /></div>
            <span>→</span>
            <div style={{ width: 130 }}><Select value={String(diff.b)} onChange={(x) => loadDiff(diff.a, Number(x))} options={d.versions.map((x) => [String(x.version), `v${x.version}`])} /></div>
          </div>
          <div className="diff">{!diff.lines ? "Cargando…" : !diff.lines.length ? "Las dos versiones son idénticas." : diff.lines.map((l, i) => <div key={i} className={l.startsWith("+") && !l.startsWith("+++") ? "add" : l.startsWith("-") && !l.startsWith("---") ? "del" : ""}>{l || " "}</div>)}</div>
        </Modal>
      )}
      <span className="sr">{boot.version}</span>
    </div>
  );
}
