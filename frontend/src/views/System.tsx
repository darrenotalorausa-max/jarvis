import { useRef, useState } from "react";
import { api, fmtBytes, fmtDate, fmtNum, url, type Job } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, Empty, FieldRow, Modal, Panel, Progress, Skeleton, Stat, Tabs, Text, useConfirm } from "../components/ui";

function JobDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { doneTick, jobs } = useApp();
  const live = jobs.find((j) => j.id === id);
  const { data } = useData<Job>(() => api(`/jobs/${id}`), [id, doneTick, live?.stage, live?.status]);
  return (
    <Modal title={`Trabajo ${id}`} onClose={onClose} wide>
      {!data ? <Skeleton /> : <div className="stack">
        <div className="row"><strong className="wrap">{data.title}</strong><Badge value={data.status} text={data.status_label} /></div>
        {data.status === "running" && <Progress value={data.progress} live />}
        {(data.error || data.message) && <p className={data.error ? "errorbox" : "note"}>{data.error || data.message}</p>}
        <dl className="kv">
          <dt>Creado</dt><dd>{fmtDate(data.created_at)}</dd><dt>Finalizado</dt><dd>{fmtDate(data.finished_at)}</dd>
          <dt>Uso</dt><dd>{data.usage?.llamadas !== undefined ? `${data.usage.llamadas} llamadas · ${data.usage.tokens} tokens · ${data.usage.costo_estimado_usd} USD estimados · ${data.usage.respuestas_en_cache} en caché · ${(data.usage.conexiones || []).join(", ") || "sin proveedores"}` : "—"}</dd>
        </dl>
        <p className="subhead">Etapas y registro</p>
        <div className="diff" style={{ maxHeight: 280, overflowY: "auto" }}>{(data.events || []).map((e: any) => <div key={e.id}>{e.ts.slice(11, 19)} [{e.kind}] {e.message}</div>)}</div>
        <p className="subhead">Parámetros</p>
        <div className="diff">{JSON.stringify(data.params, null, 2)}</div>
      </div>}
    </Modal>
  );
}

export function System() {
  const { jobs, run, route, nav, refreshJobs, boot } = useApp();
  const [tab, setTab] = useState<"trabajos" | "uso" | "diagnostico" | "respaldo">("trabajos");
  const [tick, setTick] = useState(0);
  const usage = useData<any>(() => api("/usage"), [tab === "uso", tick]);
  const diag = useData<any>(() => api("/diagnostics"), [tab === "diagnostico", tick]);
  const backups = useData<any>(() => api("/backups"), [tab === "respaldo", tick]);
  const [withFiles, setWithFiles] = useState(true);
  const [busy, setBusy] = useState(false);
  const [inspect, setInspect] = useState<{ file: File; info: any } | null>(null);
  const [word, setWord] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirm, confirmNode] = useConfirm();
  const act = async (id: string, what: "cancel" | "retry") => { await run(api(`/jobs/${id}/${what}`, { method: "POST" })); refreshJobs(); };
  const pick = async (file?: File) => {
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    const info = await run(api<any>("/backups/inspect", { form }));
    if (info) { setInspect({ file, info }); setWord(""); }
    if (fileInput.current) fileInput.current.value = "";
  };
  const restore = async () => {
    if (!inspect) return;
    setBusy(true);
    const form = new FormData();
    form.set("file", inspect.file);
    form.set("confirm", word);
    const r: any = await run(api("/backups/restore", { form }));
    setBusy(false);
    if (r) { alert(`Restauración completada. Copia de seguridad del estado anterior: ${r.copia_de_seguridad_previa}. La página se recargará.`); location.reload(); }
  };
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">Trabajos, uso y diagnóstico</h1><p className="page__sub">Todo lo que Jarvis ejecuta pasa por una cola persistente: sobrevive a reinicios, se puede cancelar y registra su progreso real por etapas.</p></div></div>
      <Tabs value={tab} onChange={setTab} tabs={[["trabajos", "Trabajos"], ["uso", "Uso y costos"], ["diagnostico", "Diagnóstico"], ["respaldo", "Respaldo y recuperación"]]} />
      {tab === "trabajos" && <Panel title="Trabajos de este espacio" actions={<Btn small onClick={refreshJobs}>Actualizar</Btn>}>
        {!boot.worker_alive && <p className="note note--amber">El worker no figuraba activo al cargar la página. Si los trabajos no avanzan, cierra y vuelve a abrir Jarvis con el lanzador.</p>}
        {!jobs.length ? <Empty title="Sin trabajos">Los trabajos aparecen al lanzar investigaciones, propuestas, lotes, paquetes o exportaciones.</Empty> : (
          <div className="tablewrap"><table><thead><tr><th>Trabajo</th><th>Estado</th><th>Etapa</th><th>Creado</th><th /></tr></thead>
            <tbody>{jobs.map((j) => (
              <tr key={j.id}>
                <td className="wrap"><button className="linkbtn" onClick={() => nav(`sistema/${j.id}`)}>{j.title}</button><div className="small mono">{j.id} · {boot.job_types[j.type] || j.type}</div></td>
                <td><Badge value={j.status} text={j.status_label} />{j.status === "running" && <div style={{ marginTop: 6, width: 120 }}><Progress value={j.progress} live /></div>}</td>
                <td className="small wrap">{j.error || j.message || j.stage || "—"}</td><td className="small">{fmtDate(j.created_at)}</td>
                <td><div className="row">
                  {(j.result?.deliverable_ids || []).map((d: string) => <Btn small key={d} onClick={() => nav(`revision/${d}`)}>Entregable</Btn>)}
                  {["pending", "running", "waiting_config", "waiting_quota", "waiting_approval"].includes(j.status) && <Btn small kind="danger" disabled={j.cancel_requested} onClick={() => act(j.id, "cancel")}>Cancelar</Btn>}
                  {["failed", "cancelled", "waiting_config", "waiting_quota", "waiting_approval"].includes(j.status) && <Btn small onClick={() => act(j.id, "retry")}>Reintentar</Btn>}
                </div></td>
              </tr>
            ))}</tbody></table></div>
        )}
      </Panel>}
      {tab === "uso" && <>
        <Panel title={`Uso del mes (desde ${usage.data ? fmtDate(usage.data.desde) : "…"})`} note={usage.data?.nota}>
          {!usage.data?.por_categoria.length ? <p className="muted">Sin uso de proveedores registrado este mes.</p> : <div className="stats">
            {usage.data.por_categoria.map((c: any) => <Stat key={c.category} label={c.category === "texto" ? "Texto" : c.category === "busqueda" ? "Búsqueda" : c.category === "voz" ? "Voz y transcripción" : c.category} value={`${fmtNum(c.costo_estimado_usd, 4)} USD`} hint={`${c.llamadas} llamadas · ${c.en_cache || 0} en caché · ${fmtNum((c.tokens_in || 0) + (c.tokens_out || 0), 0)} tokens`} />)}
            <Stat label="Ejecución local" value="sin costo de API" hint="FFmpeg y modelos locales usan tu equipo" />
          </div>}
        </Panel>
        <Panel title="Por conexión">
          {!usage.data?.por_conexion.length ? <p className="muted small">Sin datos.</p> : <div className="tablewrap"><table>
            <thead><tr><th>Conexión</th><th className="num">Llamadas</th><th className="num">En caché</th><th className="num">Errores</th><th className="num">Tokens</th><th className="num">Costo estimado</th><th className="num">Presupuesto</th><th>Cuota configurada</th><th>Cuota confirmada</th></tr></thead>
            <tbody>{usage.data.por_conexion.map((c: any) => (
              <tr key={c.connection_id}><td>{c.name || "(eliminada)"}</td><td className="num">{c.llamadas}</td><td className="num">{c.en_cache || 0}</td><td className="num">{c.errores}</td><td className="num">{fmtNum(c.tokens, 0)}</td>
                <td className="num">{fmtNum(c.costo_estimado_usd, 4)}</td><td className="num">{c.is_paid ? fmtNum(c.monthly_budget_usd) : "no es de pago"}</td>
                <td className="small">{[c.rpm_limit && `${c.rpm_limit}/min`, c.daily_limit && `${c.daily_limit}/día`].filter(Boolean).join(", ") || "—"}</td>
                <td className="small">{Object.keys(c.confirmed_quota || {}).length ? "observada en cabeceras" : "no confirmada"}</td></tr>
            ))}</tbody></table></div>}
        </Panel>
        <Panel title="Últimas llamadas">
          <div className="tablewrap" style={{ maxHeight: 320, overflowY: "auto" }}><table>
            <thead><tr><th>Fecha</th><th>Conexión</th><th>Capacidad</th><th className="num">Tokens</th><th className="num">Costo est.</th><th>Base</th><th>Estado</th></tr></thead>
            <tbody>{(usage.data?.recientes || []).map((u: any, i: number) => (
              <tr key={i}><td className="small">{fmtDate(u.ts)}</td><td className="small">{u.connection || u.provider}</td><td className="small">{u.capability}</td><td className="num">{u.tokens_in + u.tokens_out}</td><td className="num">{fmtNum(u.est_cost_usd, 5)}</td>
                <td className="small">{u.cost_basis}</td><td className="small wrap">{u.cached ? "caché" : u.state}{u.error ? `: ${u.error}` : ""}</td></tr>
            ))}</tbody></table></div>
        </Panel>
      </>}
      {tab === "diagnostico" && diag.data && <>
        <Panel title="Estado del sistema" actions={<Btn small onClick={() => setTick((n) => n + 1)}>Actualizar</Btn>}>
          <dl className="kv">
            <dt>Versión</dt><dd>{diag.data.version} (esquema {diag.data.esquema})</dd>
            <dt>Sistema</dt><dd>{diag.data.sistema} · Python {diag.data.python}</dd>
            <dt>Escucha en</dt><dd>{diag.data.escucha} {diag.data.solo_loopback ? <Badge value="ok" text="solo este equipo" /> : <Badge value="warn" text="expuesto a la red" />}</dd>
            <dt>Celular</dt><dd>{diag.data.acceso_red.activo ? <>Acceso en red activo con código: {diag.data.acceso_red.direcciones.join(", ") || "dirección no detectada"}</> : <>Desactivado. <a href={`#/biblioteca/conexiones/${encodeURIComponent("Usar Jarvis desde el celular.md")}`}>Cómo activarlo</a></>}</dd>
            <dt>Worker</dt><dd><Badge value={diag.data.worker_activo ? "ok" : "fail"} text={diag.data.worker_activo ? "Activo" : "Detenido"} /></dd>
            <dt>FFmpeg</dt><dd>{diag.data.ffmpeg.ffmpeg.disponible ? diag.data.ffmpeg.ffmpeg.version : <span className="amber">No instalado</span>}</dd>
            <dt>FFprobe</dt><dd>{diag.data.ffmpeg.ffprobe.disponible ? diag.data.ffmpeg.ffprobe.version : <span className="amber">No instalado</span>}</dd>
            <dt>Credenciales</dt><dd>{diag.data.secretos.label}</dd>
            <dt>Datos</dt><dd className="mono">{diag.data.directorios.datos}</dd><dt>Exportaciones</dt><dd className="mono">{diag.data.directorios.exportaciones}</dd><dt>Registros</dt><dd className="mono">{diag.data.directorios.logs}</dd>
            <dt>Contenido</dt><dd>{Object.entries(diag.data.conteos).map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd>
            <dt>Trabajos</dt><dd>{Object.entries(diag.data.trabajos_por_estado).map(([k, v]) => `${boot.job_statuses[k] || k}: ${v}`).join(" · ") || "ninguno"}</dd>
          </dl>
          <div className="row" style={{ marginTop: 12 }}><Btn small onClick={() => confirm("¿Vaciar la caché de respuestas de proveedores? Las próximas consultas volverán a llamar al proveedor.", async () => { const r: any = await run(api("/cache/clear", { body: {} })); if (r) setTick((n) => n + 1); })}>Vaciar caché</Btn></div>
        </Panel>
        <Panel title="Auditoría reciente">
          <div className="diff" style={{ maxHeight: 260, overflowY: "auto" }}>{diag.data.auditoria.length ? diag.data.auditoria.map((a: any, i: number) => <div key={i}>{a.ts.slice(0, 19).replace("T", " ")} · {a.actor} · {a.action} · {a.target}</div>) : "Sin eventos."}</div>
        </Panel>
      </>}
      {tab === "respaldo" && <>
        <Panel title="Crear respaldo" note="El respaldo incluye la base de datos y, si lo marcas, tus archivos con su manifiesto de huellas. Nunca incluye credenciales. Guárdalo fuera de este equipo.">
          <div className="row">
            <Check checked={withFiles} onChange={setWithFiles}>Incluir archivos (videos, documentos, exportaciones generadas)</Check>
            <Btn kind="primary" busy={busy} onClick={async () => { setBusy(true); await run(api("/backups", { body: { include_files: withFiles } }), "Respaldo creado"); setBusy(false); setTick((n) => n + 1); }}>Crear respaldo ahora</Btn>
          </div>
        </Panel>
        <Panel title="Respaldos en este equipo" note={backups.data ? `Carpeta: ${backups.data.carpeta}` : undefined}>
          {!backups.data?.items.length ? <p className="muted small">Aún no hay respaldos.</p> : <ul className="list">{backups.data.items.map((b: any) => <li key={b.archivo}><a href={url("/exports/file", { path: `backups/${b.archivo}` })}>{b.archivo}</a> <span className="muted small">· {fmtBytes(b.bytes)} · {fmtDate(new Date(b.modificado * 1000).toISOString())}</span></li>)}</ul>}
        </Panel>
        <Panel title="Restaurar desde un respaldo" note="Antes de restaurar se valida el archivo (formato, rutas y huellas) y se guarda automáticamente una copia del estado actual para poder volver atrás.">
          <input ref={fileInput} type="file" accept=".zip" className="sr" tabIndex={-1} onChange={(e) => pick(e.target.files?.[0])} />
          <Btn kind="amber" onClick={() => fileInput.current?.click()}>Elegir archivo de respaldo…</Btn>
        </Panel>
      </>}
      {route[1]?.startsWith("job_") && <JobDetail id={route[1]} onClose={() => nav("sistema")} />}
      {inspect && (
        <Modal title="Confirmar restauración" onClose={() => setInspect(null)}>
          <div className="stack">
            <p>Respaldo válido: <strong>{inspect.file.name}</strong>, creado {fmtDate(inspect.info.manifiesto.creado)} con la versión {inspect.info.manifiesto.version_app}.</p>
            <dl className="kv">
              <dt>Contiene</dt><dd>{Object.entries(inspect.info.manifiesto.conteos || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")} · {inspect.info.archivos} archivos</dd>
              <dt>Se reemplazará</dt><dd>{Object.entries(inspect.info.datos_actuales).map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd>
            </dl>
            <p className="note note--amber">{inspect.info.aviso}</p>
            <FieldRow label="Escribe RESTAURAR para confirmar"><Text value={word} onChange={setWord} /></FieldRow>
            <div className="row row--end"><Btn onClick={() => setInspect(null)}>Cancelar</Btn><Btn kind="danger" busy={busy} disabled={word !== "RESTAURAR"} onClick={restore}>Restaurar</Btn></div>
          </div>
        </Modal>
      )}
      {confirmNode}
    </div>
  );
}
