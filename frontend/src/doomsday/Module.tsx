import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, fmtDate, fmtNum, type Deliverable, type Rec } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, Empty, ErrorBox, FieldRow, Panel, Select, Skeleton, Stat, Tabs, Text, useConfirm } from "../components/ui";
import { Needs, useRecords } from "../components/shared";
import { RecordsPanel } from "../components/RecordsPanel";
import { useCat, type Action, type FieldSpec, type Mod, type Tool } from "./App";

type ToolResult = { titulo: string; resumen: string; metricas: { label: string; valor: any; tono?: "ok" | "bad" | "amber" | null }[]; tablas: { titulo: string; columnas: string[]; filas: any[][] }[]; alertas: string[]; texto?: string; mapa?: Record<string, string> };
type Tab = "trabajar" | "datos" | "entregables" | "skill";

const CONN_LABEL: Record<string, string> = { shopify: "Shopify (Admin API)", meta: "Meta Ads", gmail: "Gmail", whatsapp: "WhatsApp Business", higgsfield: "Higgsfield (imagen y video)" };

export function ModuleView({ mod }: { mod: Mod }) {
  const { cat } = useCat();
  const { space, setSpace, route, nav } = useApp();
  const target = cat.espacios[mod.capa];
  useEffect(() => { if (space.id !== target) setSpace(target); }, [space.id, target]);
  const tab = (["trabajar", "datos", "entregables", "skill"].includes(route[2]) ? route[2] : "trabajar") as Tab;
  if (space.id !== target) return <Skeleton />;
  const tabs: [Tab, string][] = [["trabajar", "Trabajar"], ...(mod.kinds.length ? [["datos", "Datos"] as [Tab, string]] : []), ["entregables", "Entregables"], ["skill", "Skill"]];
  return (
    <div className="page">
      <header className="mhead">
        <div className="mhead__title"><span className="mid">{mod.id}</span><h1 className="page__title">{mod.nombre}</h1></div>
        <p className="mhead__flow">{mod.problema} → <b>{mod.solucion}</b>.</p>
        <div className="chips">
          {mod.funciones.map((f) => <span key={f} className="chip">{f}</span>)}
          <span className="chip">Capa<b>{cat.capas[mod.capa].nombre.split(" · ")[0]}</b></span>
          <span className="chip" title={cat.autonomia[mod.nivel]}>Autonomía<b>{mod.nivel}</b></span>
          <span className="chip" title="Puntuación preliminar del Laboratorio Estratégico">Puntos<b>{mod.puntos}</b></span>
          <span className="chip" title="Decisión que recomendaba el análisis original">Análisis<b>{mod.decision_pdf.toLowerCase()}</b></span>
        </div>
      </header>
      <Tabs tabs={tabs} value={tab} onChange={(t) => nav(`m/${mod.id}${t === "trabajar" ? "" : `/${t}`}`)} />
      {tab === "trabajar" && <Work mod={mod} />}
      {tab === "datos" && <div className="stack">{mod.kinds.map((k) => <RecordsPanel key={k} kind={k} importable />)}</div>}
      {tab === "entregables" && <Deliverables mod={mod} />}
      {tab === "skill" && <SkillEditor mod={mod} />}
    </div>
  );
}

// ---------- Trabajar: órdenes, herramientas y actividad

function Work({ mod }: { mod: Mod }) {
  const { cat } = useCat();
  const { nav } = useApp();
  const tools = cat.herramientas.filter((t) => mod.tools.includes(t.id));
  const [orden, ...acciones] = mod.acciones;
  return (
    <>
      <Needs caps={["extraccion"]} />
      {mod.conexiones.length > 0 && (
        <p className="note">Este módulo aprovecha: {mod.conexiones.map((c) => CONN_LABEL[c] || c).join(", ")}. Conéctalas en <button className="linkbtn" onClick={() => nav("apps")}>Apps conectadas</button>;
          sin ellas trabaja con los datos que registres o importes en «Datos». Leer no requiere aprobación; cualquier escritura sí.</p>
      )}
      <Panel title="Orden libre" note={`La skill ${mod.id} aplica su método completo y usa los datos de este módulo. El resultado queda como borrador para tu revisión.`}>
        <ActionForm mod={mod} act={orden} primary />
      </Panel>
      {mod.widget && <Widget mod={mod} />}
      {mod.kinds.includes("dd_habito") && <Habits mod={mod} />}
      {acciones.length > 0 && (
        <div className="actions">
          {acciones.map((a) => <Panel key={a.id} title={a.label}><p className="act__task">{a.tarea}</p><ActionForm mod={mod} act={a} /></Panel>)}
        </div>
      )}
      {tools.map((t) => <ToolPanel key={t.id} mod={mod} tool={t} />)}
      <Activity mod={mod} />
    </>
  );
}

export function Input({ f, value, onChange }: { f: FieldSpec; value: any; onChange: (v: any) => void }) {
  if (f.type === "select") return <Select value={value ?? ""} onChange={onChange} options={(f.options || []).map((o) => [o, o.replace(/_/g, " ")])} empty="—" />;
  if (f.type === "bool") return <Check checked={!!value} onChange={onChange}>{f.label}</Check>;
  if (f.type === "textarea") return <Text area rows={4} value={value ?? ""} onChange={onChange} />;
  return <Text type={f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "url" ? "url" : "text"} value={value ?? ""} onChange={onChange} placeholder={f.type === "url" ? "https://" : undefined} />;
}

function Fields({ campos, values, set }: { campos: FieldSpec[]; values: Record<string, any>; set: (k: string, v: any) => void }) {
  if (!campos.length) return null;
  return (
    <div className="form">
      {campos.map((f) => (
        <FieldRow key={f.name} label={f.type === "bool" ? "" : f.label} wide={f.type === "textarea"}><Input f={f} value={values[f.name]} onChange={(v) => set(f.name, v)} /></FieldRow>
      ))}
    </div>
  );
}

function ActionForm({ mod, act, primary }: { mod: Mod; act: Action; primary?: boolean }) {
  const { run, notify, refreshJobs } = useApp();
  const [values, setValues] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    const res = await run(api<{ job: { id: string; status_label: string }; created: boolean }>("/dd/run", { body: { module: mod.id, action: act.id, inputs: values } }));
    setBusy(false);
    if (!res) return;
    notify(res.created ? `En marcha: ${act.label}. Verás el resultado abajo, en Actividad.` : "Ya había una orden igual en curso; no se duplicó.", res.created ? "ok" : "info");
    if (res.created && primary) setValues({});
    refreshJobs();
  };
  const empty = primary && !String(values.orden || "").trim();
  return (
    <div className="order">
      <Fields campos={act.campos} values={values} set={(k, v) => setValues((s) => ({ ...s, [k]: v }))} />
      <div className="row"><Btn kind={primary ? "primary" : "default"} busy={busy} disabled={empty} onClick={send}>{primary ? "Enviar orden" : "Ejecutar"}</Btn>
        {act.emite && <span className="small muted">Crea registros en «Datos» además del entregable.</span>}</div>
    </div>
  );
}

function ToolPanel({ mod, tool }: { mod: Mod; tool: Tool }) {
  const { run, doneTick } = useApp();
  const [values, setValues] = useState<Record<string, any>>({});
  const [res, setRes] = useState<ToolResult | null>(null);
  const [busy, setBusy] = useState(false);
  const calc = async (silent = false) => {
    setBusy(true);
    const p = api<ToolResult>(`/dd/tools/${tool.id}`, { body: { module: mod.id, inputs: values } });
    const r = silent ? await p.catch(() => undefined) : await run(p);
    setBusy(false);
    if (r) setRes(r);
  };
  // Las herramientas que solo leen registros se calculan al abrir y cuando termina un trabajo. Las que escriben (salud_tienda, utm) solo a petición.
  useEffect(() => { if (tool.auto && !["utm", "embudo", "churn"].includes(tool.id)) calc(true); }, [doneTick]);
  return (
    <Panel title={tool.label} actions={<Btn small busy={busy} onClick={() => calc()}>{res ? "Recalcular" : "Calcular"}</Btn>} note="Cálculo determinista con tus registros. Sin IA y sin cifras de ejemplo.">
      <Fields campos={tool.campos} values={values} set={(k, v) => setValues((s) => ({ ...s, [k]: v }))} />
      {res && <ToolView res={res} />}
    </Panel>
  );
}

const cellNum = (v: any) => (typeof v === "number" ? fmtNum(v) : v === null || v === undefined || v === "" ? "—" : String(v));

export function ToolView({ res }: { res: ToolResult }) {
  return (
    <div className="tres">
      {res.resumen && <p className="small muted">{res.resumen}</p>}
      {res.metricas.length > 0 && <div className="stats">{res.metricas.map((m) => <Stat key={m.label} label={m.label} value={cellNum(m.valor)} tone={m.tono || undefined} />)}</div>}
      {res.texto && <pre>{res.texto}</pre>}
      {res.mapa && Object.keys(res.mapa).length > 0 && (
        <details><summary className="small muted">Mapa para restaurar ({Object.keys(res.mapa).length}); no se guarda</summary><pre>{Object.entries(res.mapa).map(([k, v]) => `${k} = ${v}`).join("\n")}</pre></details>
      )}
      {res.alertas.map((a) => <p key={a} className="tres__alert">{a}</p>)}
      {res.tablas.filter((t) => t.filas.length).map((t) => (
        <div key={t.titulo}>
          <p className="subhead">{t.titulo}</p>
          <div className="tablewrap"><table>
            <thead><tr>{t.columnas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{t.filas.slice(0, 200).map((f, i) => <tr key={i}>{f.map((v, j) => <td key={j} className={typeof v === "number" ? `right mono${v < 0 ? " neg" : ""}` : "wrap"}>{cellNum(v)}</td>)}</tr>)}</tbody>
          </table></div>
        </div>
      ))}
    </div>
  );
}

function Activity({ mod }: { mod: Mod }) {
  const { jobs, nav, run, refreshJobs } = useApp();
  const list = jobs.filter((j) => j.type === "dd_run" && j.params?.module === mod.id).slice(0, 8);
  if (!list.length) return null;
  const act = async (id: string, what: "cancel" | "retry") => { await run(api(`/jobs/${id}/${what}`, { method: "POST" })); refreshJobs(); };
  return (
    <Panel title="Actividad">
      {list.map((j) => {
        const dels: string[] = j.result?.deliverable_ids || [];
        const active = ["pending", "running"].includes(j.status);
        return (
          <div className="jobrow" key={j.id}>
            <div className="jobrow__top"><span className="jobrow__title">{j.title}</span><Badge value={j.status} text={j.status_label} /></div>
            <p className="small muted">{j.error || j.message || "En cola"} · {fmtDate(j.created_at)}</p>
            <div className="row">
              {dels.map((d) => <Btn key={d} small kind="primary" onClick={() => nav(`revision/${d}`)}>Abrir entregable</Btn>)}
              {j.status === "waiting_config" && <Btn small onClick={() => nav("conexiones")}>Configurar IA</Btn>}
              {(active || j.status.startsWith("waiting")) && <Btn small kind="ghost" onClick={() => act(j.id, "cancel")}>Cancelar</Btn>}
              {["failed", "waiting_config", "cancelled"].includes(j.status) && <Btn small kind="ghost" onClick={() => act(j.id, "retry")}>Reintentar</Btn>}
            </div>
          </div>
        );
      })}
    </Panel>
  );
}

function Deliverables({ mod }: { mod: Mod }) {
  const { space, nav, doneTick } = useApp();
  const { data, error, reload } = useData<Deliverable[]>(() => api("/deliverables", { query: { space: space.id, kind: "dd" } }), [space.id, doneTick]);
  if (error) return <ErrorBox message={error} retry={reload} />;
  if (!data) return <Skeleton />;
  const list = data.filter((d) => d.ref_id === mod.id);
  if (!list.length) return <Empty title="Aún no hay entregables de este módulo">Envía una orden desde «Trabajar». Cada resultado llega aquí como borrador, con versiones, comprobaciones y aprobación.</Empty>;
  return (
    <Panel>
      <div className="tablewrap"><table>
        <thead><tr><th>Entregable</th><th>Estado</th><th>Versión</th><th>Actualizado</th></tr></thead>
        <tbody>{list.map((d) => (
          <tr key={d.id}><td><button className="linkbtn" onClick={() => nav(`revision/${d.id}`)}>{d.title}</button></td><td><Badge value={d.status} /></td><td>v{d.current_version}</td><td className="small">{fmtDate(d.updated_at)}</td></tr>
        ))}</tbody>
      </table></div>
    </Panel>
  );
}

// ---------- Skill del módulo (X06)

function SkillEditor({ mod }: { mod: Mod }) {
  const { run } = useApp();
  const { reload: reloadCat } = useCat();
  const s = useData<{ texto: string; origen: string; version: number; integrada: string }>(() => api(`/dd/skills/${mod.id}`), [mod.id]);
  const [text, setText] = useState<string | null>(null);
  const [confirm, dialog] = useConfirm();
  useEffect(() => { setText(null); }, [s.data?.version, s.data?.origen]);
  if (s.error) return <ErrorBox message={s.error} retry={s.reload} />;
  if (!s.data) return <Skeleton />;
  const value = text ?? s.data.texto;
  const dirty = text !== null && text.trim() !== s.data.texto.trim();
  const save = async () => { if (await run(api(`/dd/skills/${mod.id}`, { method: "PUT", body: { texto: value, nota: "editada en el panel" } }), "Skill guardada. Las próximas órdenes la usan.")) { s.reload(); reloadCat(); } };
  const restore = () => confirm("Se retirará tu versión y volverá la skill integrada. Tu texto queda en el historial.", async () => { if (await run(api(`/dd/skills/${mod.id}`, { method: "DELETE" }), "Skill integrada restaurada.")) { s.reload(); reloadCat(); } });
  return (
    <Panel title={<>Skill {mod.id} · <span className="muted">{s.data.origen === "propia" ? "tuya" : "integrada"}, versión {s.data.version}</span></>}
      actions={<>{s.data.origen === "propia" && <Btn small kind="ghost" onClick={restore}>Volver a la integrada</Btn>}<Btn small kind="primary" disabled={!dirty} onClick={save}>Guardar como mi versión</Btn></>}
      note="Es el método que sigue el módulo en cada orden: rol, pasos, estándar de calidad y lo que nunca hace. Edítala o pega la tuya; la anterior queda guardada en el historial.">
      <textarea className="input skilltext" aria-label={`Skill ${mod.id}`} value={value} onChange={(e) => setText(e.target.value)} spellCheck={false} />
      {dialog}
    </Panel>
  );
}

// ---------- Widgets propios de algunos módulos

function Widget({ mod }: { mod: Mod }) {
  if (mod.widget === "teleprompter") return <Teleprompter />;
  if (mod.widget === "boveda") return <Vault />;
  if (mod.widget === "repaso") return <Flashcards />;
  if (mod.widget === "sync") return <ShopifySync />;
  if (mod.widget === "publicar") return <ShopifyDraft />;
  if (mod.widget === "skills") return <Panel title="Repositorio de skills"><p className="muted">Las 100 skills, su origen y su versión están en <a href="#/skills">Skills</a>. Desde ahí importas las tuyas en bloque.</p></Panel>;
  return null;
}

function Teleprompter() {
  const [text, setText] = useState("");
  const [speed, setSpeed] = useState(40);
  const [mirror, setMirror] = useState(false);
  const [on, setOn] = useState(false);
  const el = useRef<HTMLDivElement>(null);
  const y = useRef(0);
  useEffect(() => {
    if (!on) return;
    let raf = 0, last = performance.now();
    const step = (t: number) => {
      y.current += (speed * (t - last)) / 1000;
      last = t;
      if (el.current) el.current.style.transform = `translateY(${-y.current}px)`;
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [on, speed]);
  const reset = () => { y.current = 0; if (el.current) el.current.style.transform = "translateY(0)"; setOn(false); };
  return (
    <Panel title="Teleprompter" actions={<><Btn small kind="primary" disabled={!text.trim()} onClick={() => setOn(!on)}>{on ? "Pausar" : "Iniciar"}</Btn><Btn small kind="ghost" onClick={reset}>Volver al inicio</Btn></>}>
      <div className="form">
        <FieldRow label="Guion" wide><Text area rows={4} value={text} onChange={setText} placeholder="Pega aquí el guion" /></FieldRow>
        <FieldRow label={`Velocidad: ${speed} px por segundo`}><input type="range" min={10} max={160} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} /></FieldRow>
        <FieldRow label=""><Check checked={mirror} onChange={setMirror}>Espejo (para cristal de teleprompter)</Check></FieldRow>
      </div>
      {text.trim() && <div className={`prompter${mirror ? " prompter--mirror" : ""}`} style={{ marginTop: "var(--i4)" }}><div className="prompter__text" ref={el}>{text}</div></div>}
    </Panel>
  );
}

function Vault() {
  const { run } = useApp();
  const list = useRecords("dd_acceso");
  const [v, setV] = useState<Record<string, any>>({});
  const [shown, setShown] = useState<Record<string, string>>({});
  const [confirm, dialog] = useConfirm();
  const add = async () => { if (await run(api("/dd/vault", { body: v }), "Acceso guardado. El secreto quedó en el almacén cifrado, fuera de la base de datos.")) { setV({}); list.reload(); } };
  const reveal = async (id: string) => {
    if (shown[id]) return setShown((s) => { const n = { ...s }; delete n[id]; return n; });
    const r = await run(api<{ secreto: string }>(`/dd/vault/${id}/reveal`, { method: "POST" }));
    if (r) { setShown((s) => ({ ...s, [id]: r.secreto })); setTimeout(() => setShown((s) => { const n = { ...s }; delete n[id]; return n; }), 20000); }
  };
  const revoke = (r: Rec) => confirm(`Se borrará el secreto de «${r.title}» y el acceso quedará marcado como revocado. Cambia también la contraseña en el servicio.`, async () => { await run(api(`/dd/vault/${r.id}`, { method: "DELETE" }), "Acceso revocado."); list.reload(); }, true);
  const set = (k: string) => (val: any) => setV((s) => ({ ...s, [k]: val }));
  return (
    <Panel title="Bóveda" note="Los secretos se guardan en el almacén de credenciales del sistema (o en un archivo protegido fuera de la carpeta de datos). No entran en la base de datos, los respaldos, los registros ni los prompts. Cada vez que se revela uno queda anotado en la auditoría.">
      <div className="form">
        <FieldRow label="Nombre del acceso"><Text value={v.titulo} onChange={set("titulo")} /></FieldRow>
        <FieldRow label="Empresa o colección"><Text value={v.coleccion} onChange={set("coleccion")} /></FieldRow>
        <FieldRow label="Usuario"><Text value={v.usuario} onChange={set("usuario")} /></FieldRow>
        <FieldRow label="URL"><Text type="url" value={v.url} onChange={set("url")} /></FieldRow>
        <FieldRow label="Contraseña o token"><Text type="password" value={v.secreto} onChange={set("secreto")} /></FieldRow>
        <FieldRow label=""><Check checked={!!v.tiene_2fa} onChange={set("tiene_2fa")}>Tiene verificación en dos pasos</Check></FieldRow>
      </div>
      <div className="row row--end"><Btn kind="primary" disabled={!v.titulo || !v.secreto} onClick={add}>Guardar en la bóveda</Btn></div>
      {list.data && list.data.length > 0 && (
        <div className="tablewrap" style={{ marginTop: "var(--i4)" }}><table>
          <thead><tr><th>Acceso</th><th>Colección</th><th>Usuario</th><th>2FA</th><th>Secreto</th><th /></tr></thead>
          <tbody>{list.data.map((r) => (
            <tr key={r.id}><td>{r.title}</td><td>{r.data.coleccion || "—"}</td><td>{r.data.usuario || "—"}</td><td>{r.data.tiene_2fa ? "Sí" : <span className="amber">No</span>}</td>
              <td className="mono">{r.status === "revocado" ? "revocado" : shown[r.id] ?? "••••••••"}</td>
              <td className="right">{r.status !== "revocado" && <div className="row" style={{ justifyContent: "flex-end" }}><Btn small onClick={() => reveal(r.id)}>{shown[r.id] ? "Ocultar" : "Revelar"}</Btn><Btn small kind="danger" onClick={() => revoke(r)}>Revocar</Btn></div>}</td></tr>
          ))}</tbody>
        </table></div>
      )}
      {dialog}
    </Panel>
  );
}

function Flashcards() {
  const { space, run, doneTick } = useApp();
  const cards = useData<Rec[]>(() => api("/life/cards", { query: { space: space.id } }), [space.id, doneTick]);
  const [flip, setFlip] = useState(false);
  const card = cards.data?.[0];
  const grade = async (g: number) => { if (!card) return; await run(api("/life/review", { body: { space: space.id, card_id: card.id, grade: g } })); setFlip(false); cards.reload(); };
  return (
    <Panel title={`Repaso de hoy${cards.data ? ` · ${cards.data.length} pendientes` : ""}`} note="Repetición espaciada: cada valoración decide cuándo vuelve la tarjeta. Crea tarjetas en «Datos» o con la acción «Crear tarjetas de un texto».">
      {!card ? <p className="muted">No hay tarjetas pendientes hoy.</p> : (
        <div className="stack">
          <div className="flashcard"><div><p className="small muted">{card.data.deck || "Sin mazo"}</p><p>{flip ? card.data.back : card.title}</p></div></div>
          <div className="row">{!flip ? <Btn kind="primary" onClick={() => setFlip(true)}>Ver respuesta</Btn> : (
            <>{[["Otra vez", 0], ["Difícil", 1], ["Bien", 2], ["Fácil", 3]].map(([t, g]) => <Btn key={g} kind={g === 2 ? "primary" : "default"} onClick={() => grade(g as number)}>{t}</Btn>)}</>
          )}</div>
        </div>
      )}
    </Panel>
  );
}

function useApiConns() {
  return useData<any[]>(() => api<any>("/connections").then((r) => (Array.isArray(r) ? r : r.items || []).filter((c: any) => c.provider === "api")), []);
}

function ConnPicker({ value, onChange, children }: { value: string; onChange: (v: string) => void; children?: ReactNode }) {
  const { nav } = useApp();
  const conns = useApiConns();
  if (conns.data && !conns.data.length) return <p className="muted">No hay ninguna app conectada. Añade tu tienda con la plantilla «Shopify (Admin API)» en <button className="linkbtn" onClick={() => nav("apps")}>Apps conectadas</button>.</p>;
  return <div className="form"><FieldRow label="Conexión de Shopify"><Select value={value} onChange={onChange} options={(conns.data || []).map((c) => [c.id, c.name])} empty="Elige una conexión" /></FieldRow>{children}</div>;
}

function ShopifySync() {
  const { run } = useApp();
  const [conn, setConn] = useState("");
  const [res, setRes] = useState<{ leidos: number; nuevos: number; nota: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); const r = await run(api<any>("/dd/sync/shopify", { body: { connection_id: conn } })); setBusy(false); if (r) setRes(r); };
  return (
    <Panel title="Traer pedidos de Shopify" note="Solo lectura: no modifica tu tienda y no requiere aprobación. El gasto de pauta y las liquidaciones se cargan en «Datos» con «Importar CSV» (exportación de Meta, TikTok o tu operador logístico).">
      <ConnPicker value={conn} onChange={setConn} />
      <div className="row row--end"><Btn kind="primary" busy={busy} disabled={!conn} onClick={go}>Traer los últimos 250 pedidos</Btn></div>
      {res && <p className="note">{res.leidos} pedidos leídos, {res.nuevos} nuevos. {res.nota}</p>}
    </Panel>
  );
}

function ShopifyDraft() {
  const { space, run, nav } = useApp();
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({});
  const [done, setDone] = useState(false);
  const go = async () => {
    const r = await run(api<any>(`/apps/${conn}/request`, { body: { space: space.id, action: "crear_producto_borrador", variables: { titulo: v.titulo, descripcion: v.descripcion } } }));
    if (r) setDone(true);
  };
  return (
    <Panel title="Publicar como borrador en Shopify" note="Crea el producto en estado borrador: no queda visible en la tienda. Como modifica un sistema externo, queda esperando tu aprobación con la petición exacta en Apps conectadas.">
      <ConnPicker value={conn} onChange={setConn}>
        <FieldRow label="Título del producto"><Text value={v.titulo} onChange={(x) => setV((s) => ({ ...s, titulo: x }))} /></FieldRow>
        <FieldRow label="Descripción (HTML de la ficha aprobada)" wide><Text area rows={5} value={v.descripcion} onChange={(x) => setV((s) => ({ ...s, descripcion: x }))} /></FieldRow>
      </ConnPicker>
      <div className="row row--end">{done && <Btn kind="amber" onClick={() => nav("apps")}>Revisar y aprobar en Apps conectadas</Btn>}<Btn kind="primary" disabled={!conn || !v.titulo} onClick={go}>Solicitar publicación en borrador</Btn></div>
    </Panel>
  );
}

function Habits({ mod }: { mod: Mod }) {
  const { run } = useApp();
  const habs = useRecords("dd_habito");
  const [res, setRes] = useState<any>(null);
  const check = async (h: string) => { const r = await run(api<any>("/dd/habits/check", { body: { module: mod.id, habito: h } }), `«${h}» marcado hoy.`); if (r) setRes(r); };
  const active = (habs.data || []).filter((h) => h.status === "activo");
  if (!active.length) return null;
  return (
    <Panel title="Marcar hoy">
      <div className="row">{active.map((h) => <Btn key={h.id} onClick={() => check(h.title)}>{h.title}</Btn>)}</div>
      {res && <ToolView res={res} />}
    </Panel>
  );
}
