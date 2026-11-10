import { useMemo, useState, type ReactNode } from "react";
import { api, fmtNum, label, url, type Field, type Rec } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, Empty, ErrorBox, FieldRow, Modal, Panel, Select, Text } from "./ui";

const WITH_PROJECT = ["milestone", "brief", "delivery", "capacity", "transaction", "time_entry", "campaign", "lead", "product", "experiment", "task"];
const WITH_BRAND = ["brand_asset", "brief", "product"];

type Props = {
  kind: string; title?: string; columns?: string[]; defaults?: Record<string, any>; rowActions?: (rec: Rec, reload: () => void) => ReactNode;
  importable?: boolean; note?: ReactNode; quickAdd?: string; brandId?: string; extraActions?: ReactNode; onChanged?: () => void; hideFields?: string[];
};

export function cell(f: Field | undefined, v: any, refs?: Record<string, string>): ReactNode {
  if (v === null || v === undefined || v === "") return <span className="muted">—</span>;
  if (!f) return String(v);
  if (f.type === "number") return fmtNum(v);
  if (f.type === "bool") return v ? "Sí" : "No";
  if (f.type === "tags") return (v as string[]).join(", ");
  if (f.type === "select") return label(v);
  if (f.type === "ref") return refs?.[v] || v;
  if (f.type === "url") return <a href={v} target="_blank" rel="noreferrer noopener">{String(v).replace(/^https?:\/\//, "").slice(0, 40)}</a>;
  const s = String(v);
  return s.length > 90 ? `${s.slice(0, 90)}…` : s;
}

export function RecordsPanel(p: Props) {
  const { boot, space, run, doneTick } = useApp();
  const spec = boot.schema[p.kind];
  const [archived, setArchived] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState<Partial<Rec> | null>(null);
  const [importing, setImporting] = useState(false);
  const [quick, setQuick] = useState("");
  const { data, error, reload } = useData<Rec[]>(() => api("/records", { query: { space: space.id, kind: p.kind, archived, q, status, brand_id: p.brandId } }), [space.id, p.kind, archived, q, status, p.brandId, doneTick]);
  const refKinds = useMemo(() => Array.from(new Set(spec.fields.filter((f) => f.type === "ref").map((f) => f.ref!))), [spec]);
  const needProject = WITH_PROJECT.includes(p.kind), needBrand = WITH_BRAND.includes(p.kind) && !p.brandId;
  const lookups = useData<Record<string, Rec[]>>(async () => {
    const kinds = [...refKinds, ...(needProject ? ["project"] : []), ...(needBrand ? ["brand"] : [])];
    const lists = await Promise.all(kinds.map((k) => api<Rec[]>("/records", { query: { space: space.id, kind: k } })));
    return Object.fromEntries(kinds.map((k, i) => [k, lists[i]]));
  }, [space.id, p.kind, doneTick]);
  const names = useMemo(() => Object.fromEntries(Object.values(lookups.data || {}).flat().map((r) => [r.id, r.title])), [lookups.data]);
  const cols = (p.columns || spec.fields.slice(0, 3).map((f) => f.name)).map((n) => spec.fields.find((f) => f.name === n)!).filter(Boolean);
  const changed = () => { reload(); p.onChanged?.(); };

  const patch = async (rec: Rec, body: Record<string, unknown>, ok?: string) => { await run(api(`/records/${rec.id}`, { method: "PATCH", body: { space: space.id, ...body } }), ok); changed(); };
  const addQuick = async () => {
    if (!quick.trim()) return;
    const data = { ...(p.defaults || {}) };
    if (p.kind === "capture") data.body = quick;
    await run(api("/records", { body: { space: space.id, kind: p.kind, title: quick.slice(0, 200), data, brand_id: p.brandId } }));
    setQuick("");
    changed();
  };

  return (
    <Panel title={p.title || spec.plural} note={p.note} actions={<>
      {p.extraActions}
      {p.importable && <Btn small onClick={() => setImporting(true)}>Importar CSV</Btn>}
      <a className="btn btn--sm" href={url("/records/export.csv", { space: space.id, kind: p.kind })}>Exportar CSV</a>
      <Btn small kind="primary" onClick={() => setEditing({ data: { ...(p.defaults || {}) }, status: spec.statuses[0], brand_id: p.brandId || null })}>Nuevo</Btn>
    </>}>
      {p.quickAdd && (
        <form className="row" style={{ marginBottom: 10 }} onSubmit={(e) => { e.preventDefault(); addQuick(); }}>
          <div style={{ flex: 1, minWidth: 180 }}><Text value={quick} onChange={setQuick} placeholder={p.quickAdd} /></div>
          <Btn type="submit" disabled={!quick.trim()}>Añadir</Btn>
        </form>
      )}
      <div className="row" style={{ marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 140, maxWidth: 280 }}><Text value={q} onChange={setQ} placeholder="Buscar…" /></div>
        {spec.statuses.length > 1 && <div style={{ width: 170 }}><Select value={status} onChange={setStatus} empty="Todos los estados" options={spec.statuses.map((s) => [s, label(s)])} /></div>}
        <Check checked={archived} onChange={setArchived}>Ver archivados</Check>
      </div>
      {error ? <ErrorBox message={error} retry={reload} /> : !data ? <p className="muted">Cargando…</p> : !data.length ? (
        <Empty title={archived ? "No hay elementos archivados" : q || status ? "Nada coincide con el filtro" : `Aún no hay ${spec.plural.toLowerCase()}`}>
          {!archived && !q && !status && "Crea el primero con «Nuevo»" + (p.importable ? " o impórtalos desde un CSV." : ".")}
        </Empty>
      ) : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>Título</th>{cols.map((f) => <th key={f.name} className={f.type === "number" ? "num" : ""}>{f.label.split(" (")[0]}</th>)}{needProject && <th>Proyecto</th>}{spec.statuses.length > 1 && <th>Estado</th>}<th /></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id}>
                  <td className="wrap"><button className="linkbtn" onClick={() => setEditing(r)}>{r.title}</button></td>
                  {cols.map((f) => <td key={f.name} className={f.type === "number" ? "num" : "wrap"}>{cell(f, r.data[f.name], names)}</td>)}
                  {needProject && <td className="small">{r.project_id ? names[r.project_id] || "—" : "—"}</td>}
                  {spec.statuses.length > 1 && (
                    <td><select className="input" aria-label={`Estado de ${r.title}`} value={r.status} onChange={(e) => patch(r, { status: e.target.value })} style={{ minWidth: 120 }}>
                      {spec.statuses.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                    </select></td>
                  )}
                  <td><div className="row">
                    {p.rowActions?.(r, changed)}
                    <Btn small kind="ghost" onClick={() => patch(r, { archived: !r.archived }, r.archived ? "Restaurado" : "Archivado")}>{r.archived ? "Restaurar" : "Archivar"}</Btn>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <RecordForm kind={p.kind} rec={editing} lookups={lookups.data || {}} hide={p.hideFields} showProject={needProject} showBrand={needBrand} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); changed(); }} />}
      {importing && <CsvImport kind={p.kind} defaults={p.defaults} projects={lookups.data?.project || []} onClose={() => { setImporting(false); changed(); }} />}
    </Panel>
  );
}

export function RecordForm({ kind, rec, lookups, onClose, onSaved, showProject, showBrand, hide = [] }: { kind: string; rec: Partial<Rec>; lookups: Record<string, Rec[]>; onClose: () => void; onSaved: (r: Rec) => void; showProject?: boolean; showBrand?: boolean; hide?: string[] }) {
  const { boot, space, run } = useApp();
  const spec = boot.schema[kind];
  const [title, setTitle] = useState(rec.title || "");
  const [status, setStatus] = useState(rec.status || spec.statuses[0]);
  const [project, setProject] = useState(rec.project_id || "");
  const [brand, setBrand] = useState(rec.brand_id || "");
  const [data, setData] = useState<Record<string, any>>({ ...(rec.data || {}) });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setData((d) => ({ ...d, [k]: v }));
  const save = async () => {
    setBusy(true);
    const body = { space: space.id, kind, title, status, project_id: project || null, brand_id: brand || null, data };
    const saved = await run(rec.id ? api<Rec>(`/records/${rec.id}`, { method: "PATCH", body }) : api<Rec>("/records", { body }), "Guardado");
    setBusy(false);
    if (saved) onSaved(saved);
  };
  const input = (f: Field) => {
    const v = data[f.name];
    if (f.type === "textarea") return <Text area value={v} onChange={(x) => set(f.name, x)} />;
    if (f.type === "select") return <Select value={v} onChange={(x) => set(f.name, x)} empty="—" options={(f.options || []).map((o) => [o, label(o)])} />;
    if (f.type === "ref") return <Select value={v} onChange={(x) => set(f.name, x)} empty="—" options={(lookups[f.ref!] || []).map((r) => [r.id, r.title])} />;
    if (f.type === "bool") return <Check checked={!!v} onChange={(x) => set(f.name, x)}>Sí</Check>;
    if (f.type === "tags") return <Text value={Array.isArray(v) ? v.join(", ") : v} onChange={(x) => set(f.name, x)} placeholder="Separados por comas" />;
    return <Text type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} value={v} onChange={(x) => set(f.name, x)} />;
  };
  return (
    <Modal title={`${rec.id ? "Editar" : "Nuevo"}: ${spec.label}`} onClose={onClose} wide>
      <form className="form" onSubmit={(e) => { e.preventDefault(); save(); }}>
        <FieldRow label="Título *" wide><Text value={title} onChange={setTitle} /></FieldRow>
        {spec.statuses.length > 1 && <FieldRow label="Estado"><Select value={status} onChange={setStatus} options={spec.statuses.map((s) => [s, label(s)])} /></FieldRow>}
        {showProject && <FieldRow label="Proyecto"><Select value={project} onChange={setProject} empty="Sin proyecto" options={(lookups.project || []).map((r) => [r.id, r.title])} /></FieldRow>}
        {showBrand && <FieldRow label="Marca"><Select value={brand} onChange={setBrand} empty="Sin marca" options={(lookups.brand || []).map((r) => [r.id, r.title])} /></FieldRow>}
        {spec.fields.filter((f) => !hide.includes(f.name)).map((f) => (
          <FieldRow key={f.name} label={f.label + (f.required ? " *" : "")} wide={f.type === "textarea"}>{input(f)}</FieldRow>
        ))}
        <div className="row row--end field--wide">
          {rec.id && <span className="small muted mono" style={{ marginRight: "auto" }}>{rec.id}</span>}
          <Btn onClick={onClose}>Cancelar</Btn>
          <Btn kind="primary" type="submit" busy={busy} disabled={!title.trim()}>Guardar</Btn>
        </div>
      </form>
    </Modal>
  );
}

function CsvImport({ kind, defaults, projects, onClose }: { kind: string; defaults?: Record<string, any>; projects: Rec[]; onClose: () => void }) {
  const { boot, space, run } = useApp();
  const spec = boot.schema[kind];
  const [text, setText] = useState("");
  const [cols, setCols] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [project, setProject] = useState("");
  const [result, setResult] = useState<any>(null);
  const targets: [string, string][] = [["title", "Título"], ["status", "Estado"], ...spec.fields.map((f) => [f.name, f.label.split(" (")[0]] as [string, string])];
  const load = async (file?: File) => {
    if (!file) return;
    const t = await file.text();
    const head = await run(api<{ columnas: string[] }>("/records/import", { body: { space: space.id, kind, text: t } }));
    if (!head) return;
    setText(t);
    setCols(head.columnas);
    setResult(null);
    const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[^a-z0-9]/g, "");
    setMapping(Object.fromEntries(head.columnas.map((c) => [c, targets.find(([id, lab]) => norm(lab) === norm(c) || norm(id) === norm(c))?.[0] || ""])));
  };
  const send = async (commit: boolean) => {
    const res = await run(api("/records/import", { body: { space: space.id, kind, text, mapping, commit, defaults, project_id: project || null } }), commit ? "Importación aplicada" : undefined);
    if (res) setResult(res);
  };
  return (
    <Modal title={`Importar CSV: ${spec.plural}`} onClose={onClose} wide>
      <div className="stack">
        <FieldRow label="Archivo CSV (separado por comas, punto y coma o tabulador)"><input className="input" type="file" accept=".csv,text/csv,text/plain" onChange={(e) => load(e.target.files?.[0])} /></FieldRow>
        {cols.length > 0 && <>
          <p className="small muted">Asigna cada columna del archivo a un campo. Las columnas sin asignar se ignoran.</p>
          <div className="form">
            {cols.map((c) => <FieldRow key={c} label={`Columna «${c}»`}><Select value={mapping[c]} onChange={(v) => setMapping((m) => ({ ...m, [c]: v }))} empty="Ignorar" options={targets} /></FieldRow>)}
            {projects.length > 0 && <FieldRow label="Asignar al proyecto"><Select value={project} onChange={setProject} empty="Sin proyecto" options={projects.map((r) => [r.id, r.title])} /></FieldRow>}
          </div>
          <div className="row">
            <Btn onClick={() => send(false)}>Previsualizar</Btn>
            <Btn kind="primary" disabled={!result || result.aplicado || !result.nuevos} onClick={() => send(true)}>Importar {result && !result.aplicado ? `${result.nuevos} nuevos` : ""}</Btn>
          </div>
        </>}
        {result && <>
          <p><Badge value="ok" text={`${result.nuevos} nuevos`} /> <Badge value="warn" text={`${result.duplicados} duplicados (se omiten)`} /> <Badge value="fail" text={`${result.errores} con error`} /> {result.aplicado && <strong>Importación aplicada.</strong>}</p>
          <div className="tablewrap" style={{ maxHeight: 260, overflowY: "auto" }}>
            <table>
              <thead><tr><th>Fila</th><th>Título</th><th>Resultado</th><th>Detalle</th></tr></thead>
              <tbody>{result.detalle.map((d: any) => <tr key={d.fila}><td>{d.fila}</td><td className="wrap">{d.title || "—"}</td><td><Badge value={d.estado === "nuevo" ? "ok" : d.estado === "duplicado" ? "warn" : "fail"} text={d.estado} /></td><td className="small wrap">{d.error || ""}</td></tr>)}</tbody>
            </table>
          </div>
        </>}
      </div>
    </Modal>
  );
}
