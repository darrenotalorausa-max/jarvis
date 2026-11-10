import { useRef, useState } from "react";
import { api } from "../api";
import { useApp, useData } from "../store";
import { JobList, UploadButton, useFiles, useLaunch } from "./shared";
import { Badge, Btn, FieldRow, Panel, Select, Text } from "./ui";

/** Sube un archivo a un importador en dos pasos: vista previa (sin guardar) y confirmación. */
function ImportBox({ title, note, accept, path, extra, summary, onDone }: { title: string; note: string; accept: string; path: string; extra?: Record<string, string>; summary: (r: any) => string; onDone?: () => void }) {
  const { space, run } = useApp();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const send = async (f: File, commit: boolean) => {
    setBusy(true);
    const form = new FormData();
    form.append("space", space.id); form.append("file", f); form.append("commit", commit ? "si" : "");
    Object.entries(extra || {}).forEach(([k, v]) => form.append(k, v));
    const r = await run(api(path, { form }), commit ? "Importación guardada" : undefined);
    setBusy(false);
    if (!r) return;
    if (commit) { setFile(null); setPreview(null); onDone?.(); } else { setFile(f); setPreview(r); }
  };
  return (
    <Panel title={title} note={note} actions={<Btn small busy={busy && !preview} onClick={() => input.current?.click()}>Elegir archivo</Btn>}>
      <input ref={input} type="file" accept={accept} hidden onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) send(f, false); }} />
      {!preview ? <p className="muted small">Primero verás un resumen de lo que se importaría; nada se guarda hasta que confirmes.</p> : <>
        <p className="wrap"><strong>{file?.name}</strong> · {summary(preview)}</p>
        {preview.detalle?.length > 0 && <div className="tablewrap" style={{ maxHeight: 260, overflowY: "auto" }}><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Importe</th><th /></tr></thead>
          <tbody>{preview.detalle.slice(0, 60).map((d: any, i: number) => <tr key={i}><td className="small">{d.fecha}</td><td className="wrap">{d.concepto}</td><td className="mono">{d.importe}</td><td><Badge value={d.estado === "nuevo" ? "ok" : "mute"} text={d.estado} /></td></tr>)}</tbody></table></div>}
        <div className="row" style={{ marginTop: 10 }}><Btn kind="primary" busy={busy} onClick={() => send(file!, true)}>Guardar en mis registros</Btn><Btn kind="ghost" onClick={() => { setPreview(null); setFile(null); }}>Descartar</Btn></div>
      </>}
    </Panel>
  );
}

export function HealthImport({ onDone }: { onDone?: () => void }) {
  const [days, setDays] = useState("90");
  return <>
    <div className="row"><span className="small muted">Periodo a importar</span><div style={{ width: 200 }}><Select value={days} onChange={setDays} options={[["30", "Últimos 30 días"], ["90", "Últimos 90 días"], ["365", "Último año"], ["3650", "Todo"]]} /></div></div>
    <ImportBox title="Importar de Apple Health (iPhone y Apple Watch)" accept=".zip,.xml" path="/import/health" extra={{ days }} onDone={onDone}
      note="En el iPhone: app Salud → tu foto → «Exportar todos los datos de salud». Sube aquí el export.zip. Se leen sueño, entrenamientos y pasos; no se duplican al repetir la importación. Otros relojes (Garmin, Fitbit, Xiaomi): exporta a CSV e impórtalo en Sueño o Entrenamientos. No hay sincronización automática con el reloj."
      summary={(r) => `desde ${r.desde}: ${r.noches} noche(s), ${r.entrenamientos} entrenamiento(s), ${r.dias_de_pasos} día(s) de pasos · ${r.duplicados} ya estaban`} />
  </>;
}

export function OfxImport({ onDone }: { onDone?: () => void }) {
  return <ImportBox title="Importar extracto bancario (OFX / QFX)" accept=".ofx,.qfx,.txt" path="/import/ofx" onDone={onDone}
    note="Descarga el extracto desde la web de tu banco en formato OFX o QFX (suele estar junto a PDF y Excel) y súbelo. Cada movimiento lleva el identificador del banco, así que repetir el archivo no duplica nada. Jarvis no se conecta a tu banco ni guarda sus credenciales."
    summary={(r) => `${r.nuevos} movimiento(s) nuevo(s), ${r.duplicados} ya importado(s)${r.errores ? `, ${r.errores} ilegible(s)` : ""}${r.moneda ? ` · ${r.moneda}` : ""}`} />;
}

export function StudyRoute() {
  const launch = useLaunch();
  const files = useFiles();
  const [file, setFile] = useState("");
  const [deck, setDeck] = useState("");
  const docs = (files.data || []).filter((f) => /\.(pdf|docx|txt|md)$/i.test(f.name));
  return (
    <Panel title="Tutor: ruta de estudio desde un archivo" actions={<UploadButton accept=".pdf,.docx,.txt,.md" onDone={(f) => { files.reload(); setFile(f.id); }}>Subir material</UploadButton>}
      note="Convierte un PDF, DOCX o texto en módulos con objetivos, ejercicios, tarjetas de repaso y autoevaluación, usando solo el contenido del archivo. Necesita un modelo de texto permitido en este espacio (en el espacio personal: uno local o una conexión que autorices para datos personales). Los PDF escaneados sin texto no sirven.">
      <div className="form">
        <FieldRow label="Material"><Select value={file} onChange={setFile} empty="Elige un archivo…" options={docs.map((f) => [f.id, f.name])} /></FieldRow>
        <FieldRow label="Mazo para las tarjetas" hint="Vacío: el nombre del archivo."><Text value={deck} onChange={setDeck} /></FieldRow>
        <div className="row" style={{ alignSelf: "end" }}><Btn kind="primary" disabled={!file} onClick={() => launch("study_plan", { file_id: file, deck }, `Ruta de estudio: ${docs.find((f) => f.id === file)?.name || ""}`)}>Crear ruta de estudio</Btn></div>
      </div>
      <JobList types={["study_plan"]} limit={3} empty="Aún no has creado rutas de estudio." />
    </Panel>
  );
}

export function AskNotes() {
  const { space, run } = useApp();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<any>(null);
  const ask = async () => { if (q.trim().length < 3) return; setBusy(true); const r = await run(api("/life/ask", { body: { space: space.id, question: q } })); setBusy(false); if (r) setOut(r); };
  return (
    <Panel title="Pregunta a tus notas" note="Busca en tus notas, lecturas, diario y decisiones, y responde solo con lo que encuentre, citando de dónde sale. Tus notas únicamente se envían a un modelo permitido por la política de este espacio; sin uno, no se envía nada.">
      <form className="row" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <div style={{ flex: 1, minWidth: 0 }}><Text value={q} onChange={setQ} placeholder="¿Qué decidí sobre…? ¿Qué aprendí de…?" /></div>
        <Btn kind="primary" type="submit" busy={busy}>Preguntar</Btn>
      </form>
      {out && <div className="stack" style={{ marginTop: 12 }}>
        <p className="wrap">{out.answer}</p>
        {out.sources.length > 0 && <p className="small muted wrap">Notas usadas: {out.sources.map((s: any) => `«${s.title}» (${s.date})`).join(" · ")}{out.model ? ` · modelo: ${out.model}` : ""}</p>}
      </div>}
    </Panel>
  );
}

export function Scripture() {
  const { run, notify } = useApp();
  const [tick, setTick] = useState(0);
  const list = useData<any[]>(() => api("/scripture"), [tick]);
  const [tr, setTr] = useState("");
  const [ref, setRef] = useState("");
  const [res, setRes] = useState<any>(null);
  const [meta, setMeta] = useState({ name: "", title: "", license: "" });
  const input = useRef<HTMLInputElement>(null);
  const cur = tr || list.data?.[0]?.translation || "";
  const look = async () => {
    const t = ref.trim();
    if (!t || !cur) return;
    const isRef = /\d/.test(t);
    const r: any = await run(api(`/scripture/${cur}/${isRef ? "passage" : "search"}`, { query: isRef ? { ref: t } : { q: t } }));
    if (r) setRes({ ...r, isRef, q: t });
  };
  const upload = async (f: File) => {
    if (!meta.name.trim()) { notify("Escribe primero la sigla de la traducción (por ejemplo RV1909).", "error"); return; }
    const form = new FormData();
    form.append("name", meta.name); form.append("title", meta.title); form.append("license", meta.license); form.append("file", f);
    const r: any = await run(api("/scripture", { form }));
    if (r) { notify(`${r.translation}: ${r.verses} versículos en ${r.books} libros.`, "ok"); setTr(r.translation); setTick((n) => n + 1); }
  };
  return (
    <Panel title="Texto bíblico" note="Jarvis no trae ninguna traducción incluida: cargas la tuya, de dominio público o con licencia que te lo permita, y queda en tu equipo. Se muestra el texto tal cual, sin interpretación generada. Los comentarios tampoco vienen incluidos: guárdalos como notas de estudio citando su fuente.">
      {list.data && list.data.length > 0 && <>
        <form className="row" onSubmit={(e) => { e.preventDefault(); look(); }}>
          <div style={{ width: 180 }}><Select value={cur} onChange={setTr} options={list.data.map((t) => [t.translation, t.translation])} /></div>
          <div style={{ flex: 1, minWidth: 0 }}><Text value={ref} onChange={setRef} placeholder="Juan 3:16 · Salmos 23 · o una palabra para buscar" /></div>
          <Btn kind="primary" type="submit">Buscar</Btn>
        </form>
        {res && (res.isRef ? <div className="stack" style={{ marginTop: 12 }}>
          <p className="small muted">{res.reference} · {res.translation}</p>
          <p className="wrap scripture">{res.verses.map((v: any) => <span key={v.verse}><sup>{v.verse}</sup> {v.text} </span>)}</p>
        </div> : <div className="stack" style={{ marginTop: 12 }}>
          <p className="small muted">{res.total} versículo(s) contienen «{res.q}»{res.total > res.results.length ? ` · se muestran ${res.results.length}` : ""}</p>
          {res.results.map((v: any, i: number) => <p key={i} className="wrap"><span className="small muted">{v.book} {v.chapter}:{v.verse}</span> — {v.text}</p>)}
        </div>)}
        <p className="small muted" style={{ marginTop: 12 }}>Cargadas: {list.data.map((t) => `${t.translation} (${t.verses} versículos${t.license ? `, ${t.license}` : ""})`).join(" · ")}</p>
      </>}
      <details style={{ marginTop: 12 }} open={!list.data?.length}>
        <summary className="small">Cargar o sustituir una traducción</summary>
        <div className="form" style={{ marginTop: 10 }}>
          <FieldRow label="Sigla"><Text value={meta.name} onChange={(v) => setMeta({ ...meta, name: v })} placeholder="RV1909" /></FieldRow>
          <FieldRow label="Nombre completo"><Text value={meta.title} onChange={(v) => setMeta({ ...meta, title: v })} /></FieldRow>
          <FieldRow label="Licencia o procedencia"><Text value={meta.license} onChange={(v) => setMeta({ ...meta, license: v })} placeholder="Dominio público" /></FieldRow>
          <div className="row" style={{ alignSelf: "end" }}><Btn onClick={() => input.current?.click()}>Elegir archivo</Btn>
            {cur && <Btn kind="ghost" onClick={async () => { await run(api(`/scripture/${cur}`, { method: "DELETE" }), `${cur} eliminada`); setTr(""); setRes(null); setTick((n) => n + 1); }}>Quitar {cur}</Btn>}</div>
        </div>
        <input ref={input} type="file" accept=".json,.txt,.tsv" hidden onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
        <p className="small muted">Formatos: JSON (libro → capítulo → versículo → texto, o lista de objetos con book, chapter, verse, text) o texto con una línea por versículo: «Génesis 1:1 En el principio…».</p>
      </details>
    </Panel>
  );
}
