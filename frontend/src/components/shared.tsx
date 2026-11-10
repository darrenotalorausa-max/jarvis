import { useRef, useState, type ReactNode } from "react";
import { api, fmtBytes, fmtDate, url, type Deliverable, type FileRow, type Job, type Rec } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Empty, ErrorBox, Modal, Progress } from "./ui";

export function useRecords(kind: string, deps: unknown[] = []) {
  const { space, doneTick } = useApp();
  return useData<Rec[]>(() => api("/records", { query: { space: space.id, kind } }), [space.id, kind, doneTick, ...deps]);
}

/** Lanza un trabajo y devuelve su ID. Informa de si se creó o si ya existía uno equivalente. */
export function useLaunch() {
  const { space, run, notify, refreshJobs } = useApp();
  return async (type: string, params: Record<string, unknown>, title?: string, limits?: Record<string, number>) => {
    const res = await run(api<{ job: Job; created: boolean }>("/jobs", { body: { space: space.id, type, params, title, limits } }));
    if (!res) return undefined;
    notify(res.created ? `Trabajo creado: ${res.job.id} · ${res.job.status_label}` : `Ya había un trabajo equivalente activo (${res.job.id}); no se duplicó.`, res.created ? "ok" : "info");
    refreshJobs();
    return res.job;
  };
}

/** Indica qué capacidades de IA faltan para una función y por qué. Nunca oculta la función: explica qué necesita. */
export function Needs({ caps, optional = [] }: { caps: string[]; optional?: string[] }) {
  const { space, boot, nav, doneTick } = useApp();
  const { data } = useData<Record<string, { disponible: boolean; conexiones: string[]; motivos: string[] }>>(() => api("/availability", { query: { space: space.id } }), [space.id, doneTick]);
  if (!data) return null;
  const rows = [...caps.map((c) => [c, true] as const), ...optional.map((c) => [c, false] as const)].filter(([c]) => !data[c]?.disponible);
  if (!rows.length) return null;
  return (
    <div className="banner">
      <div>
        {rows.map(([c, required]) => (
          <p key={c}>
            <strong>{boot.capabilities[c]}</strong>: {required ? "necesaria y no disponible" : "opcional, no disponible"} en «{space.name}».{" "}
            <span className="muted">{data[c].motivos.length ? data[c].motivos.join("; ") : "No hay ninguna conexión con esta capacidad."}</span>
          </p>
        ))}
      </div>
      <Btn small onClick={() => nav("conexiones")}>Ir a Conexiones</Btn>
    </div>
  );
}

export function JobList({ types, limit = 8, empty }: { types?: string[]; limit?: number; empty?: string }) {
  const { jobs, run, nav, refreshJobs } = useApp();
  const list = jobs.filter((j) => !types || types.includes(j.type)).slice(0, limit);
  if (!list.length) return <p className="muted small">{empty || "Sin trabajos todavía."}</p>;
  const act = async (id: string, what: "cancel" | "retry") => { await run(api(`/jobs/${id}/${what}`, { method: "POST" })); refreshJobs(); };
  return (
    <div>
      {list.map((j) => {
        const active = ["pending", "running"].includes(j.status);
        const waiting = j.status.startsWith("waiting");
        const dels: string[] = j.result?.deliverable_ids || [];
        return (
          <div className="jobrow" key={j.id}>
            <div className="jobrow__top">
              <span className="jobrow__title" title={j.title}>{j.title}</span>
              <Badge value={j.status} text={j.status_label} />
            </div>
            {j.status === "running" && <Progress value={j.progress} live />}
            <span className="small muted wrap">
              <span className="mono">{j.id}</span>
              {(j.error || j.message) && <> · {j.error || j.message}</>}
              {j.resume_at && j.status === "waiting_quota" && <> · reintento automático {fmtDate(j.resume_at)}</>}
            </span>
            <div className="row">
              {dels.map((d) => <Btn small key={d} onClick={() => nav(`revision/${d}`)}>Abrir entregable</Btn>)}
              {(active || waiting) && <Btn small kind="danger" onClick={() => act(j.id, "cancel")} disabled={j.cancel_requested}>{j.cancel_requested ? "Cancelando…" : "Cancelar"}</Btn>}
              {(waiting || ["failed", "cancelled"].includes(j.status)) && <Btn small onClick={() => act(j.id, "retry")}>Reintentar</Btn>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function DeliverableList({ kind, empty }: { kind?: string; empty: ReactNode }) {
  const { space, nav, doneTick } = useApp();
  const { data, error, reload } = useData<Deliverable[]>(() => api("/deliverables", { query: { space: space.id, kind } }), [space.id, kind, doneTick]);
  if (error) return <ErrorBox message={error} retry={reload} />;
  if (!data) return <p className="muted">Cargando…</p>;
  if (!data.length) return <Empty title="Aún no hay entregables aquí">{empty}</Empty>;
  return (
    <div className="tablewrap">
      <table>
        <thead><tr><th>Título</th><th>Estado</th><th>Versión</th><th>Actualizado</th></tr></thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.id}>
              <td><button className="linkbtn" onClick={() => nav(`revision/${d.id}`)}>{d.title}</button><div className="small muted">{d.kind_label} · <span className="mono">{d.id}</span></div></td>
              <td><Badge value={d.status} /></td>
              <td>v{d.current_version}</td>
              <td className="small">{fmtDate(d.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function UploadButton({ accept, onDone, children = "Subir archivo", multiple }: { accept?: string; onDone: (f: FileRow) => void; children?: ReactNode; multiple?: boolean }) {
  const { space, run } = useApp();
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const pick = async (list: FileList | null) => {
    if (!list?.length) return;
    setBusy(true);
    for (const file of Array.from(list)) {
      const form = new FormData();
      form.set("space", space.id);
      form.set("file", file);
      const row = await run(api<FileRow>("/files", { form }), `Archivo guardado: ${file.name}`);
      if (row) onDone(row);
    }
    setBusy(false);
    if (ref.current) ref.current.value = "";
  };
  return (
    <>
      <input ref={ref} type="file" accept={accept} multiple={multiple} className="sr" tabIndex={-1} onChange={(e) => pick(e.target.files)} />
      <Btn onClick={() => ref.current?.click()} busy={busy}>{children}</Btn>
    </>
  );
}

export function useFiles(deps: unknown[] = []) {
  const { space, doneTick } = useApp();
  return useData<FileRow[]>(() => api("/files", { query: { space: space.id } }), [space.id, doneTick, ...deps]);
}

export function FileTable({ files, onArchive }: { files: FileRow[]; onArchive?: (f: FileRow) => void }) {
  const { space, run } = useApp();
  const [desc, setDesc] = useState<{ name: string; text: string; via: string } | null>(null);
  const [busy, setBusy] = useState("");
  const describe = async (f: FileRow) => {
    setBusy(f.id);
    const r = await run(api<{ text: string; connection: string }>(`/files/${f.id}/describe`, { body: { space: space.id } }));
    setBusy("");
    if (r) setDesc({ name: f.name, text: r.text, via: r.connection });
  };
  if (!files.length) return <Empty title="Sin archivos">Sube documentos, imágenes o videos para usarlos en los módulos.</Empty>;
  return (
    <div className="tablewrap">
      <table>
        <thead><tr><th>Nombre</th><th>Origen</th><th>Tamaño</th><th>Detalle</th><th>Fecha</th><th /></tr></thead>
        <tbody>
          {files.map((f) => (
            <tr key={f.id}>
              <td className="wrap"><a href={url(`/files/${f.id}/download`, { space: space.id })}>{f.name}</a><div className="small mono">{f.id}</div></td>
              <td>{f.origin === "job" ? "Generado" : "Subido"}</td>
              <td className="num">{fmtBytes(f.size)}</td>
              <td className="small">{f.meta?.duration ? `${f.meta.width || "?"}×${f.meta.height || "?"} · ${f.meta.duration} s${f.meta.has_audio ? " · audio" : ""}` : f.meta?.probe_error || f.mime}</td>
              <td className="small">{fmtDate(f.created_at)}</td>
              <td><div className="row">
                {(f.mime || "").startsWith("image/") && <Btn small busy={busy === f.id} title="Requiere una conexión con capacidad de visión" onClick={() => describe(f)}>Describir con IA</Btn>}
                {onArchive && <Btn small kind="ghost" onClick={() => onArchive(f)}>Archivar</Btn>}
              </div></td>
            </tr>
          ))}
        </tbody>
      </table>
      {desc && <Modal title={`Descripción de ${desc.name}`} onClose={() => setDesc(null)}><p className="wrap">{desc.text}</p><p className="note">Generada por {desc.via}. Es una descripción automática: revísala antes de usarla.</p></Modal>}
    </div>
  );
}
