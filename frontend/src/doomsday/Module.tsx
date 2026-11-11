import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, fmtDate, fmtNum, url, type Deliverable, type Rec } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, Empty, ErrorBox, FieldRow, Panel, Select, Skeleton, Stat, Tabs, Text, useConfirm } from "../components/ui";
import { Needs, UploadButton, useFiles, useRecords } from "../components/shared";
import { RecordsPanel } from "../components/RecordsPanel";
import { HealthImport, Scripture } from "../components/LifeTools";
import { lc, useCat, type Action, type FieldSpec, type Mod, type Tool } from "./App";

type ToolResult = { secciones?: { titulo: string; contenido: string }[]; archivo?: { id: string; name: string }; deliverable_id?: string; titulo: string; resumen: string; metricas: { label: string; valor: any; tono?: "ok" | "bad" | "amber" | null }[]; tablas: { titulo: string; columnas: string[]; filas: any[][] }[]; alertas: string[]; texto?: string; mapa?: Record<string, string> };
type Tab = "trabajar" | "datos" | "entregables" | "skill";

const CONN_LABEL: Record<string, string> = { shopify: "Shopify (Admin API)", meta: "Meta Ads", tiktok: "TikTok Ads", gmail: "Gmail", whatsapp: "WhatsApp Business (Cloud API)", dropi: "la exportación CSV de tu operador logístico (Dropi u otro)", video: "una conexión de IA que genere video (OpenAI, Gemini o fal.ai, en Conexiones de IA)" };

export function ModuleView({ mod }: { mod: Mod }) {
  const { cat } = useCat();
  const { space, setSpace, route, nav } = useApp();
  // Un módulo trabaja en cualquier espacio de su capa (por ejemplo, el de cada cliente); si estás en otra capa, cambia a la suya.
  const inLayer = space.kind === cat.capas[mod.capa].tipo;
  const target = cat.espacios[mod.capa];
  useEffect(() => { if (!inLayer) setSpace(target); }, [inLayer, target]);
  const tab = (["trabajar", "datos", "entregables", "skill"].includes(route[2]) ? route[2] : "trabajar") as Tab;
  if (!inLayer) return <Skeleton />;
  const tabs: [Tab, string][] = [["trabajar", "Trabajar"], ...(mod.kinds.length ? [["datos", "Datos"] as [Tab, string]] : []), ["entregables", "Entregables"], ["skill", "Skill"]];
  return (
    <div className="page">
      <header className="mhead" style={lc(mod.capa)}>
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
      {(tools.length > 0 || mod.widget || mod.kinds.includes("dd_habito")) && <h2 className="sechead">Herramientas propias <span>funcionan sin IA</span></h2>}
      {mod.conexiones.length > 0 && (
        <p className="note">Este módulo aprovecha: {mod.conexiones.map((c) => CONN_LABEL[c] || c).join(", ")}. Conéctalas en <button className="linkbtn" onClick={() => nav("apps")}>Apps conectadas</button>;
          sin ellas trabaja con los datos que registres o importes en «Datos». Leer no requiere aprobación; cualquier escritura sí.</p>
      )}
      {mod.widget && <Widget mod={mod} />}
      {["C05", "M02", "M08", "R08", "S01"].includes(mod.id) && <PlanQueue mod={mod} />}
      {mod.kinds.includes("dd_habito") && <Habits mod={mod} />}
      {tools.map((t) => <ToolPanel key={t.id} mod={mod} tool={t} />)}
      <h2 className="sechead">Órdenes con IA <span>la skill {mod.id} aplica su método completo</span></h2>
      <Needs caps={["extraccion"]} />
      <Panel title="Orden libre" note="Escribe poco: el resultado queda como borrador para tu revisión, con sus comprobaciones y supuestos.">
        <ActionForm mod={mod} act={orden} primary />
      </Panel>
      {acciones.length > 0 && (
        <div className="actions">
          {acciones.map((a) => <Panel key={a.id} title={a.label}><p className="act__task">{a.tarea}</p><ActionForm mod={mod} act={a} /></Panel>)}
        </div>
      )}
      <Activity mod={mod} />
    </>
  );
}

function Input({ f, value, onChange }: { f: FieldSpec; value: any; onChange: (v: any) => void }) {
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
  const { run, notify, refreshJobs, space } = useApp();
  const [values, setValues] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    const res = await run(api<{ job: { id: string; status_label: string }; created: boolean }>("/dd/run", { body: { module: mod.id, action: act.id, inputs: values, space: space.id } }));
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
  const { run, doneTick, space } = useApp();
  const [values, setValues] = useState<Record<string, any>>({});
  const [res, setRes] = useState<ToolResult | null>(null);
  const [busy, setBusy] = useState(false);
  const { nav, notify } = useApp();
  const calc = async (silent = false, extra: Record<string, any> = {}) => {
    setBusy(true);
    const { guardar, ...more } = extra;
    const p = api<ToolResult>(`/dd/tools/${tool.id}`, { body: { module: mod.id, inputs: { ...values, ...more }, space: space.id, guardar } });
    const r = silent ? await p.catch(() => undefined) : await run(p);
    setBusy(false);
    if (r) { setRes(r); if (r.deliverable_id) notify("Guardado como entregable. Ábrelo en Revisión para aprobarlo.", "ok"); }
  };
  // Las herramientas que solo leen registros se calculan al abrir y cuando termina un trabajo. Las que escriben o piden entradas, solo a petición.
  useEffect(() => { if (tool.auto && !tool.escribe) calc(true); }, [doneTick]);
  const guardable = !!res && !res.deliverable_id && (!!res.secciones?.length || res.tablas.some((t) => t.filas.length > 0));
  return (
    <Panel title={tool.label} note="Funciona sin IA: calcula con tus registros y con reglas fijas. Sin datos lo dice; no muestra cifras de ejemplo."
      actions={<>{tool.id === "tema" && <Btn small onClick={() => calc(false, { _descargar: true })}>Descargar .zip</Btn>}
        {guardable && <Btn small onClick={() => calc(false, { guardar: true })}>Guardar como entregable</Btn>}
        {res?.deliverable_id && <Btn small kind="ghost" onClick={() => nav(`revision/${res.deliverable_id}`)}>Abrir entregable</Btn>}
        <Btn small kind="primary" busy={busy} onClick={() => calc()}>{res ? "Recalcular" : "Ejecutar"}</Btn></>}>
      <Fields campos={tool.campos} values={values} set={(k, v) => setValues((s) => ({ ...s, [k]: v }))} />
      {res && <ToolView res={res} />}
    </Panel>
  );
}

const cellNum = (v: any) => (typeof v === "number" ? fmtNum(v) : v === null || v === undefined || v === "" ? "—" : String(v));

export function ToolView({ res }: { res: ToolResult }) {
  const { space } = useApp();
  return (
    <div className="tres">
      {res.resumen && <p className="small muted">{res.resumen}</p>}
      {res.metricas.length > 0 && <div className="stats">{res.metricas.map((m) => <Stat key={m.label} label={m.label} value={cellNum(m.valor)} tone={m.tono || undefined} />)}</div>}
      {res.archivo && <p><a className="btn btn--primary" href={url(`/files/${res.archivo.id}/download`, { space: space.id })}>Descargar {res.archivo.name}</a></p>}
      {res.texto && <pre>{res.texto}</pre>}
      {res.secciones && res.secciones.length > 0 && <div className="tres__doc">{res.secciones.map((s) => <div key={s.titulo}><h3>{s.titulo}</h3><p>{s.contenido}</p></div>)}</div>}
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
  const list = jobs.filter((j) => ["dd_run", "dd_clip", "dd_plan", "media_generate"].includes(j.type) && j.params?.module === mod.id).slice(0, 8);
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
  if (mod.widget === "sync") return <><ShopifySync /><AdsSync /><LogisticsImport /></>;
  if (mod.widget === "publicar") return <ShopifyDraft />;
  if (mod.widget === "pausa") return <><AdsSync /><AdsPause /></>;
  if (mod.widget === "whatsapp") return <><GmailSync module="V05" /><WhatsApp /></>;
  if (mod.widget === "gmail") return <GmailSync module="P03" />;
  if (mod.widget === "redes") return <SocialPublish />;
  if (mod.widget === "lanzar") return <AdsLaunch />;
  if (mod.widget === "capi") return <CapiSend />;
  if (mod.widget === "discord") return <Discord />;
  if (mod.widget === "tema") return <ThemeUpload />;
  if (mod.widget === "salud") return <><HealthImport />{mod.id === "H02" && <OuraSync />}</>;
  if (mod.widget === "escritura") return <Scripture />;
  if (mod.widget === "media") return <CreativeMedia />;
  if (mod.widget === "clip") return <ClipCutter />;
  if (mod.widget === "voz") return <VoiceCapture />;
  if (mod.widget === "portal") return <Portal />;
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

function Approve({ job }: { job: any }) {
  const { nav } = useApp();
  if (!job) return null;
  return <p className="note note--amber">Petición preparada y en espera. Nada sale hasta que la apruebes: <button className="linkbtn" onClick={() => nav("apps")}>revisa la petición exacta en Apps conectadas</button>.</p>;
}

function ShopifyDraft() {
  const { space, run, doneTick } = useApp();
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({});
  const [res, setRes] = useState<any>(null);
  const dels = useData<Deliverable[]>(() => api("/deliverables", { query: { space: space.id, kind: "dd", status: "aprobado" } }), [space.id, doneTick]);
  const fichas = (dels.data || []).filter((d) => d.ref_id === "G04");
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const go = async () => { const r = await run(api<any>("/dd/publish/shopify", { body: { ...v, connection_id: conn, space: space.id } })); if (r) setRes(r); };
  return (
    <Panel title="Publicar la ficha aprobada como borrador en Shopify" note="Crea el producto en estado borrador (no visible en la tienda) con todas las secciones de la ficha como descripción, precio, imagen y título y descripción para buscadores. Las secciones del tema se montan en el editor de Shopify.">
      {!fichas.length ? <p className="muted">Aún no hay ninguna ficha aprobada. Genera una ficha y apruébala en Revisión; entonces aparece aquí.</p> : (
        <ConnPicker value={conn} onChange={setConn}>
          <FieldRow label="Ficha aprobada"><Select value={v.deliverable_id ?? ""} onChange={set("deliverable_id")} options={fichas.map((d) => [d.id, `${d.title} (v${d.current_version})`])} empty="Elige una ficha" /></FieldRow>
          <FieldRow label="Precio de venta"><Text type="number" value={v.precio} onChange={set("precio")} /></FieldRow>
          <FieldRow label="Imagen principal (URL https, opcional)"><Text type="url" value={v.imagen} onChange={set("imagen")} placeholder="https://" /></FieldRow>
        </ConnPicker>
      )}
      <div className="row row--end"><Btn kind="primary" disabled={!conn || !v.deliverable_id || !v.precio} onClick={go}>Preparar borrador en Shopify</Btn></div>
      {res && <p className="note">{res.secciones} secciones y {res.caracteres} caracteres de descripción.</p>}
      <Approve job={res?.job} />
    </Panel>
  );
}

function AdsSync() {
  const { run, space } = useApp();
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({ plataforma: "meta", dias: 7 });
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const go = async () => { setBusy(true); const r = await run(api<any>("/dd/sync/ads", { body: { ...v, connection_id: conn, space: space.id } })); setBusy(false); if (r) setRes(r); };
  return (
    <Panel title="Traer gasto de pauta (Meta y TikTok)" note="Solo lectura. Trae el gasto diario por anuncio y actualiza lo ya cargado. Si el nombre de un producto aparece en el de la campaña, se asigna solo. La plantilla de TikTok no se ha probado todavía con una cuenta real.">
      <AppPicker value={conn} onChange={setConn} what="Meta Ads o TikTok Ads">
        <FieldRow label="Plataforma"><Select value={v.plataforma} onChange={set("plataforma")} options={[["meta", "Meta"], ["tiktok", "TikTok"]]} /></FieldRow>
        <FieldRow label={v.plataforma === "meta" ? "ID de la cuenta publicitaria" : "ID del anunciante"}><Text value={v.cuenta} onChange={set("cuenta")} placeholder={v.plataforma === "meta" ? "act_123456789" : "7001234567890"} /></FieldRow>
        <FieldRow label="Días hacia atrás (1 a 30)"><Text type="number" value={v.dias} onChange={set("dias")} /></FieldRow>
      </AppPicker>
      <div className="row row--end"><Btn kind="primary" busy={busy} disabled={!conn || !v.cuenta} onClick={go}>Traer gasto</Btn></div>
      {res && <p className="note">{res.filas} filas del {res.periodo}: {res.nuevos} nuevas, {res.actualizados} actualizadas. {res.nota}</p>}
    </Panel>
  );
}

function AdsPause() {
  const { run, space } = useApp();
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({ plataforma: "meta" });
  const [res, setRes] = useState<any>(null);
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const go = async (reanudar: boolean) => { const r = await run(api<any>("/dd/ads/pause", { body: { ...v, connection_id: conn, reanudar, space: space.id } })); if (r) setRes(r); };
  return (
    <Panel title="Pausar en la plataforma" note="Usa el «ID de campaña» que muestra la evaluación de reglas de abajo. Pausar es reversible, pero modifica tu cuenta: se ejecuta solo cuando apruebas la petición exacta. Subir presupuesto nunca se hace desde aquí.">
      <AppPicker value={conn} onChange={setConn} what="Meta Ads o TikTok Ads">
        <FieldRow label="Plataforma"><Select value={v.plataforma} onChange={set("plataforma")} options={[["meta", "Meta"], ["tiktok", "TikTok"]]} /></FieldRow>
        <FieldRow label={v.plataforma === "meta" ? "ID de campaña, conjunto o anuncio" : "ID del anuncio"}><Text value={v.objeto_id} onChange={set("objeto_id")} /></FieldRow>
        {v.plataforma === "tiktok" && <FieldRow label="ID del anunciante"><Text value={v.cuenta} onChange={set("cuenta")} /></FieldRow>}
        <FieldRow label="Nombre (para reconocerla al aprobar)"><Text value={v.nombre} onChange={set("nombre")} /></FieldRow>
      </AppPicker>
      <div className="row row--end">{v.plataforma === "meta" && <Btn disabled={!conn || !v.objeto_id} onClick={() => go(true)}>Preparar reanudación</Btn>}<Btn kind="primary" disabled={!conn || !v.objeto_id} onClick={() => go(false)}>Preparar pausa</Btn></div>
      <Approve job={res?.job} />
    </Panel>
  );
}

function AppPicker({ value, onChange, what, children }: { value: string; onChange: (v: string) => void; what: string; children?: ReactNode }) {
  const { nav } = useApp();
  const conns = useApiConns();
  if (conns.data && !conns.data.length) return <p className="muted">No hay ninguna app conectada. Añade {what} con su plantilla en <button className="linkbtn" onClick={() => nav("apps")}>Apps conectadas</button>.</p>;
  return <div className="form"><FieldRow label={`Conexión de ${what}`}><Select value={value} onChange={onChange} options={(conns.data || []).map((c) => [c.id, c.name])} empty="Elige una conexión" /></FieldRow>{children}</div>;
}

function LogisticsImport() {
  const { run, space, notify } = useApp();
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<any>(null);
  const send = async (commit: boolean) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("space", space.id);
    if (commit) form.append("commit", "1");
    const r = await run(api<any>("/dd/import/logistica", { form }));
    if (r) { setRes(r); if (commit) notify("Pedidos, fletes y liquidaciones actualizados.", "ok"); }
  };
  return (
    <Panel title="Importar la exportación de tu operador logístico (Dropi u otro)" note="Dropi no publica una API que se pueda usar aquí, así que sus datos entran con su exportación de pedidos en CSV. Reconoce las columnas por su nombre, actualiza el estado de entrega, los fletes y el costo de cada pedido, y crea las liquidaciones. Primero muestra qué haría; no guarda nada hasta que confirmes.">
      <div className="form"><FieldRow label="Archivo CSV de pedidos"><input className="input" type="file" accept=".csv,.txt" onChange={(e) => { setFile(e.target.files?.[0] || null); setRes(null); }} /></FieldRow></div>
      <div className="row row--end"><Btn disabled={!file} onClick={() => send(false)}>Revisar sin guardar</Btn><Btn kind="primary" disabled={!res || res.guardado} onClick={() => send(true)}>Guardar cambios</Btn></div>
      {res && (
        <div className="tres">
          <div className="stats"><Stat label="Filas" value={res.filas} /><Stat label="Pedidos actualizados" value={res.actualizados} /><Stat label="Pedidos nuevos" value={res.nuevos} />
            <Stat label="Liquidaciones" value={res.liquidaciones} /><Stat label="Estado no reconocido" value={res.sin_estado} tone={res.sin_estado ? "amber" : undefined} /></div>
          <p className="small muted">Columnas usadas: {Object.entries(res.columnas).map(([k, c]) => `${c} → ${k}`).join("; ")}.{res.ignoradas.length ? ` Ignoradas: ${res.ignoradas.join(", ")}.` : ""}</p>
          {res.guardado ? <p className="small">Guardado.</p> : <p className="tres__alert">Vista previa: aún no se ha guardado nada.</p>}
        </div>
      )}
    </Panel>
  );
}

function WhatsApp() {
  const { run, space } = useApp();
  const msgs = useRecords("dd_mensaje");
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({});
  const [res, setRes] = useState<any>(null);
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const listos = (msgs.data || []).filter((m) => m.status === "borrador_listo" && m.data.borrador);
  const go = async () => { const r = await run(api<any>("/dd/whatsapp/send", { body: { ...v, connection_id: conn, space: space.id } })); if (r) setRes(r); };
  return (
    <Panel title="Enviar por WhatsApp" note="Envía un mensaje por la API de WhatsApp Business cuando apruebas la petición exacta. Recibir mensajes de forma automática exige una dirección pública que WhatsApp pueda llamar, y Doomsday corre en tu equipo: los mensajes entrantes se pegan o importan en «Datos». Fuera de la ventana de 24 horas WhatsApp solo admite plantillas aprobadas.">
      <AppPicker value={conn} onChange={setConn} what="WhatsApp Business">
        <FieldRow label="ID del número de WhatsApp Business"><Text value={v.numero_id} onChange={set("numero_id")} /></FieldRow>
        <FieldRow label="Teléfono del destinatario (con código de país)"><Text value={v.telefono} onChange={set("telefono")} placeholder="57 300 123 4567" /></FieldRow>
        {listos.length > 0 && <FieldRow label="Usar un borrador listo"><Select value={v.record_id ?? ""} onChange={(id) => { const m = listos.find((x) => x.id === id); setV((s) => ({ ...s, record_id: id, mensaje: m?.data.borrador || s.mensaje })); }}
          options={listos.map((m) => [m.id, `${m.title} · ${String(m.data.borrador).slice(0, 40)}`])} empty="—" /></FieldRow>}
        <FieldRow label="Mensaje" wide><Text area rows={4} value={v.mensaje} onChange={set("mensaje")} /></FieldRow>
      </AppPicker>
      <div className="row row--end"><Btn kind="primary" disabled={!conn || !v.numero_id || !v.telefono || !v.mensaje} onClick={go}>Preparar envío</Btn></div>
      <Approve job={res?.job} />
    </Panel>
  );
}

function CreativeMedia() {
  const { run, refreshJobs, notify } = useApp();
  const list = useRecords("dd_creativo");
  const [secs, setSecs] = useState("8");
  const ok = (list.data || []).filter((c) => ["aprobado", "publicado", "ganador"].includes(c.status));
  const go = async (c: Rec, kind: "video" | "image") => {
    const r = await run(api<any>(`/dd/creativos/${c.id}/generar`, { body: { kind, seconds: Number(secs) || 8 } }));
    if (r) { notify(r.created ? "Producción en marcha. El archivo aparecerá en Actividad." : "Ya había una producción igual en curso.", r.created ? "ok" : "info"); refreshJobs(); }
  };
  return (
    <Panel title="Producir creativos aprobados" note="Genera el video o la imagen vertical del creativo con tu conexión de IA de video o imagen (OpenAI, Gemini o fal.ai). Gasta saldo de esa conexión: solo se hace cuando pulsas, dentro del presupuesto que le pusiste. Higgsfield no tiene conexión directa aquí.">
      {!ok.length ? <p className="muted">No hay creativos aprobados. Genera variaciones, revísalas en «Datos» y cambia a «aprobado» las que quieras producir.</p> : (
        <>
          <div className="form"><FieldRow label="Duración del video (2 a 20 s)"><Text type="number" value={secs} onChange={setSecs} /></FieldRow></div>
          <div className="tablewrap" style={{ marginTop: "var(--i3)" }}><table>
            <thead><tr><th>Creativo</th><th>Hook</th><th>Formato</th><th /></tr></thead>
            <tbody>{ok.slice(0, 40).map((c) => (
              <tr key={c.id}><td className="mono">{c.title}</td><td className="wrap">{c.data.hook || "—"}</td><td>{c.data.formato || "—"}</td>
                <td className="right"><div className="row" style={{ justifyContent: "flex-end" }}><Btn small onClick={() => go(c, "image")}>Imagen</Btn><Btn small kind="primary" onClick={() => go(c, "video")}>Video</Btn></div></td></tr>
            ))}</tbody>
          </table></div>
        </>
      )}
    </Panel>
  );
}

function ClipCutter() {
  const { run, space, refreshJobs, notify } = useApp();
  const vids = useFiles();
  const [v, setV] = useState<Record<string, any>>({ vertical: true });
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const list = (vids.data || []).filter((f) => /\.(mp4|mov|mkv|webm|m4v)$/i.test(f.name) && f.origin === "upload");
  const go = async () => {
    const r = await run(api<any>("/dd/clip", { body: { ...v, space: space.id } }));
    if (r) { notify(r.created ? "Recorte en marcha. El clip aparecerá en Actividad." : "Ya había un recorte igual en curso.", r.created ? "ok" : "info"); refreshJobs(); }
  };
  return (
    <Panel title="Recortar un clip" actions={<UploadButton accept="video/*" onDone={() => vids.reload()}>Subir video</UploadButton>}
      note="Recorta el tramo con FFmpeg en tu equipo, sin IA ni servicios externos. Con «vertical» lo deja en 9:16 centrado. Para subtítulos y reencuadre fino usa el Editor audiovisual de Jarvis.">
      <div className="form">
        <FieldRow label="Video"><Select value={v.file_id ?? ""} onChange={set("file_id")} options={list.map((f) => [f.id, f.name])} empty={list.length ? "Elige un video" : "Sube un video primero"} /></FieldRow>
        <FieldRow label="Inicio (segundos o mm:ss)"><Text value={v.inicio} onChange={set("inicio")} placeholder="1:05" /></FieldRow>
        <FieldRow label="Fin (segundos o mm:ss)"><Text value={v.fin} onChange={set("fin")} placeholder="1:42" /></FieldRow>
        <FieldRow label="Título del clip"><Text value={v.titulo} onChange={set("titulo")} /></FieldRow>
        <FieldRow label=""><Check checked={!!v.vertical} onChange={set("vertical")}>Vertical 9:16</Check></FieldRow>
      </div>
      <div className="row row--end"><Btn kind="primary" disabled={!v.file_id || !v.inicio || !v.fin} onClick={go}>Recortar</Btn></div>
    </Panel>
  );
}

function VoiceCapture() {
  const { run, space, notify } = useApp();
  const [state, setState] = useState<"idle" | "rec" | "busy">("idle");
  const [text, setText] = useState("");
  const rec = useRef<MediaRecorder | null>(null);
  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("busy");
        const form = new FormData();
        form.append("space", space.id);
        form.append("audio", new Blob(chunks, { type: mr.mimeType || "audio/webm" }), "nota.webm");
        const r = await run(api<{ text: string }>("/voice/transcribe", { form }));
        setState("idle");
        if (r?.text) setText((t) => (t ? `${t}\n${r.text}` : r.text));
      };
      rec.current = mr;
      mr.start();
      setState("rec");
    } catch { notify("No se pudo usar el micrófono. Concede el permiso en el navegador.", "error"); }
  };
  const save = async () => {
    const r = await run(api("/records", { body: { space: space.id, kind: "dd_nota", title: text.trim().slice(0, 80), data: { tipo: "nota", texto: text.trim(), fecha: new Date().toISOString().slice(0, 10) } } }), "Captura guardada. Usa «Clasificar y enrutar capturas» para ordenarlas.");
    if (r) setText("");
  };
  return (
    <Panel title="Grabar una nota de voz" note="El audio se transcribe con tu conexión de transcripción (o el modelo local si lo instalaste) y se borra al terminar; solo queda el texto. Sin conexión de transcripción, escribe o dicta con el teclado del sistema.">
      <div className="row">
        {state === "rec" ? <Btn kind="danger" onClick={() => rec.current?.stop()}>Detener y transcribir</Btn> : <Btn kind="primary" busy={state === "busy"} onClick={start}>Grabar</Btn>}
        {state === "rec" && <Badge value="running" text="Grabando" />}
      </div>
      <div className="form" style={{ marginTop: "var(--i3)" }}><FieldRow label="Texto capturado" wide><Text area rows={4} value={text} onChange={setText} /></FieldRow></div>
      <div className="row row--end"><Btn disabled={text.trim().length < 3} onClick={save}>Guardar captura</Btn></div>
    </Panel>
  );
}

function Portal() {
  const { run, reload, setSpace, nav } = useApp();
  const list = useData<any[]>(() => api("/dd/clients"), []);
  const [name, setName] = useState("");
  const add = async () => { const r = await run(api<any>("/dd/clients", { body: { nombre: name } }), "Espacio del cliente creado."); if (r) { setName(""); list.reload(); await reload(); } };
  return (
    <Panel title="Portal por cliente" note="Cada cliente tiene su propio espacio: sus entregas y reportes no se mezclan con los de otro. Para darle acceso, crea en «Trabajos, uso y respaldo» un usuario con rol «cliente» asignado a su espacio; al entrar verá solo la revisión de sus entregables y podrá comentar. El acceso desde fuera de tu equipo exige activar el acceso en red con código (ver README). No incluye cobros ni firma electrónica.">
      <div className="form"><FieldRow label="Nombre del cliente"><Text value={name} onChange={setName} /></FieldRow></div>
      <div className="row row--end"><Btn onClick={() => nav("sistema")}>Usuarios y acceso</Btn><Btn kind="primary" disabled={name.trim().length < 2} onClick={add}>Crear espacio del cliente</Btn></div>
      {list.data && (
        <div className="tablewrap" style={{ marginTop: "var(--i3)" }}><table>
          <thead><tr><th>Cliente</th><th>Entregables</th><th /></tr></thead>
          <tbody>{list.data.map((c) => <tr key={c.id}><td>{c.name}</td><td>{c.entregables}</td><td className="right"><Btn small onClick={async () => { await reload(); setSpace(c.id); }}>Trabajar en este espacio</Btn></td></tr>)}</tbody>
        </table></div>
      )}
    </Panel>
  );
}

// ---------- Planes de acciones externas: una sola aprobación, ligada al plan exacto

function PlanQueue({ mod }: { mod: Mod }) {
  const { run, refreshJobs, doneTick, jobs } = useApp();
  const plans = useData<any[]>(() => api("/dd/plans", { query: { module: mod.id } }), [mod.id, doneTick, jobs.length]);
  const [at, setAt] = useState<Record<string, string>>({});
  const [confirm, dialog] = useConfirm();
  if (!plans.data?.length) return null;
  const approve = async (id: string, when?: string) => { if (await run(api(`/dd/plans/${id}/approve`, { body: when ? { at: when } : {} }), when ? "Aprobado y programado." : "Aprobado. Se ejecuta ahora.")) { plans.reload(); refreshJobs(); } };
  const cancel = (id: string) => confirm("Se descartará este plan sin ejecutar nada.", async () => { await run(api(`/jobs/${id}/cancel`, { method: "POST" })); plans.reload(); refreshJobs(); }, true);
  return (
    <Panel title="Planes pendientes" note="Esto es exactamente lo que se enviará a la plataforma. Apruébalo para ejecutarlo ahora, o para una fecha y hora. La aprobación vale una sola vez y solo para estos pasos.">
      {plans.data.map((p) => (
        <div className="plan" key={p.id}>
          <div className="jobrow__top"><span className="jobrow__title">{p.titulo}</span><Badge value={p.estado === "pending" ? "running" : "waiting_approval"} text={p.estado === "pending" ? `Programado · ${fmtDate(p.programado)}` : "Espera tu aprobación"} /></div>
          <p className="small muted">Conexión: {p.conexion}. {p.pasos.length} {p.pasos.length === 1 ? "paso" : "pasos"}.</p>
          <details><summary className="small">Ver cada paso</summary>
            {p.pasos.map((s: any, i: number) => (
              <div className="plan__step" key={i}><span className="mono">{s.metodo}</span><div><strong>{s.paso}</strong><br /><code>{s.url}</code>{s.cuerpo && <pre>{JSON.stringify(s.cuerpo, null, 1)}</pre>}</div></div>
            ))}
          </details>
          {p.estado === "waiting_approval" && (
            <div className="row">
              <Btn small kind="primary" onClick={() => approve(p.id)}>Aprobar y ejecutar ahora</Btn>
              <input className="input" style={{ width: "auto" }} type="datetime-local" aria-label="Fecha y hora de ejecución" value={at[p.id] || ""} onChange={(e) => setAt((s) => ({ ...s, [p.id]: e.target.value }))} />
              <Btn small disabled={!at[p.id]} onClick={() => approve(p.id, at[p.id])}>Aprobar para esa hora</Btn>
              <Btn small kind="ghost" onClick={() => cancel(p.id)}>Descartar</Btn>
            </div>
          )}
        </div>
      ))}
      {dialog}
    </Panel>
  );
}

function usePlan(path: string) {
  const { run, space, notify, refreshJobs } = useApp();
  const [res, setRes] = useState<any>(null);
  const send = async (body: Record<string, any>) => {
    const r = await run(api<any>(path, { body: { ...body, space: space.id } }));
    if (r) { setRes(r); if (r.job) notify("Plan preparado. Revísalo y apruébalo en «Planes pendientes».", "ok"); refreshJobs(); }
  };
  return [send, res] as const;
}

function SocialPublish() {
  const piezas = useRecords("dd_pieza");
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({ red: "instagram" });
  const [send] = usePlan("/dd/social/publish");
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const cuenta = { instagram: "ID de la cuenta profesional de Instagram", facebook: "ID de la página", linkedin: "URN del autor (urn:li:person:…)", x: "" }[v.red as string];
  return (
    <Panel title="Publicar o programar en redes" note="Instagram, Facebook, LinkedIn y X se publican por su API oficial; el archivo debe estar en una URL pública. TikTok y YouTube exigen subir el archivo y no se publican desde aquí. Al publicar, la pieza pasa a «publicado».">
      <AppPicker value={conn} onChange={setConn} what="la red (plantillas «Instagram y página de Facebook», «LinkedIn» o «X»)">
        <FieldRow label="Red"><Select value={v.red} onChange={set("red")} options={[["instagram", "Instagram"], ["facebook", "Página de Facebook"], ["linkedin", "LinkedIn"], ["x", "X"]]} /></FieldRow>
        {cuenta && <FieldRow label={cuenta}><Text value={v.cuenta} onChange={set("cuenta")} /></FieldRow>}
        <FieldRow label="Pieza (opcional)"><Select value={v.record_id ?? ""} onChange={(id) => setV((s) => ({ ...s, record_id: id, texto: piezas.data?.find((p) => p.id === id)?.data.texto || s.texto }))}
          options={(piezas.data || []).filter((p) => p.status !== "publicado").map((p) => [p.id, p.title])} empty="Escribir el texto a mano" /></FieldRow>
        <FieldRow label="Imagen o video (URL https)"><Text type="url" value={v.media_url} onChange={set("media_url")} placeholder="https://" /></FieldRow>
        <FieldRow label="Texto" wide><Text area rows={4} value={v.texto} onChange={set("texto")} /></FieldRow>
      </AppPicker>
      <div className="row row--end"><Btn kind="primary" disabled={!conn || !v.texto} onClick={() => send({ ...v, connection_id: conn })}>Preparar publicación</Btn></div>
    </Panel>
  );
}

function AdsLaunch() {
  const crea = useRecords("dd_creativo");
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({ pais: "CO" });
  const [sel, setSel] = useState<string[]>([]);
  const [send] = usePlan("/dd/ads/launch");
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const ok = (crea.data || []).filter((c) => c.status === "aprobado");
  return (
    <Panel title="Lanzar en Meta (todo se crea en pausa)" note="Crea la campaña, el conjunto y un anuncio por creativo aprobado, todos en pausa: nada gasta hasta que los actives en el Administrador de anuncios. Revisa antes el cumplimiento de cada creativo. Solo anuncios de imagen por URL; los de video se suben en la plataforma. TikTok no se lanza desde aquí.">
      <AppPicker value={conn} onChange={setConn} what="Meta Ads">
        <FieldRow label="Cuenta publicitaria"><Text value={v.cuenta} onChange={set("cuenta")} placeholder="act_123456789" /></FieldRow>
        <FieldRow label="ID de la página"><Text value={v.pagina_id} onChange={set("pagina_id")} /></FieldRow>
        <FieldRow label="ID del píxel"><Text value={v.pixel_id} onChange={set("pixel_id")} /></FieldRow>
        <FieldRow label="URL de destino"><Text type="url" value={v.destino} onChange={set("destino")} placeholder="https://" /></FieldRow>
        <FieldRow label="Presupuesto diario"><Text type="number" value={v.presupuesto_diario} onChange={set("presupuesto_diario")} /></FieldRow>
        <FieldRow label="País (código de dos letras)"><Text value={v.pais} onChange={set("pais")} /></FieldRow>
        <FieldRow label=""><Check checked={!!v.moneda_sin_centavos} onChange={set("moneda_sin_centavos")}>La moneda de la cuenta no usa centavos (COP, CLP…)</Check></FieldRow>
      </AppPicker>
      {ok.length ? (
        <div className="stack" style={{ marginTop: "var(--i4)" }}>{ok.slice(0, 30).map((c) => (
          <Check key={c.id} checked={sel.includes(c.id)} onChange={(on) => setSel((s) => (on ? [...s, c.id] : s.filter((x) => x !== c.id)))}>
            <span className="mono">{c.title}</span> · {c.data.hook || "sin hook"} {!c.data.imagen_url && <span className="amber">(falta la URL de la imagen)</span>}</Check>
        ))}</div>
      ) : <p className="muted" style={{ marginTop: "var(--i3)" }}>No hay creativos en estado «aprobado». Apruébalos en «Datos».</p>}
      <div className="row row--end"><Btn kind="primary" disabled={!conn || !sel.length || !v.cuenta} onClick={() => send({ ...v, connection_id: conn, creativos: sel })}>Preparar lanzamiento</Btn></div>
    </Panel>
  );
}

function CapiSend() {
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({ moneda: "COP" });
  const [send, res] = usePlan("/dd/capi/send");
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  return (
    <Panel title="Enviar compras entregadas a Meta" note="Manda a la API de conversiones las compras contra entrega que de verdad se entregaron en los últimos 7 días, para que la plataforma optimice hacia pedidos entregados y no solo hacia formularios. El teléfono viaja solo como huella (hash), nunca el número. La huella se crea al importar la exportación logística con su columna de teléfono, en G01.">
      <AppPicker value={conn} onChange={setConn} what="Meta Ads">
        <FieldRow label="ID del píxel"><Text value={v.pixel_id} onChange={set("pixel_id")} /></FieldRow>
        <FieldRow label="Moneda"><Text value={v.moneda} onChange={set("moneda")} /></FieldRow>
      </AppPicker>
      <div className="row row--end"><Btn kind="primary" disabled={!conn || !v.pixel_id} onClick={() => send({ ...v, connection_id: conn })}>Preparar envío</Btn></div>
      {res?.eventos && <p className="note">{res.eventos} compras por un total de {fmtNum(res.valor)}.</p>}
    </Panel>
  );
}

function Discord() {
  const { run, space } = useApp();
  const [conn, setConn] = useState("");
  const [v, setV] = useState<Record<string, any>>({});
  const [apply] = usePlan("/dd/discord/apply");
  const [nota, setNota] = useState("");
  const set = (k: string) => (x: any) => setV((s) => ({ ...s, [k]: x }));
  const welcome = async () => {
    const r = await run(api<any>("/dd/discord/welcome", { body: { ...v, connection_id: conn, space: space.id } }));
    if (r) setNota(r.nota || `${r.nuevos} miembros nuevos: bienvenida preparada en «Planes pendientes».`);
  };
  return (
    <Panel title="Aplicar al servidor de Discord" note="Crea los canales y roles en borrador y publica reglas, recursos y bienvenida. «Revisar miembros nuevos» compara con la última lectura y prepara un mensaje de bienvenida para cada uno. Doomsday no mantiene un bot conectado en vivo: lo revisas cuando quieras y apruebas el lote.">
      <AppPicker value={conn} onChange={setConn} what="Discord">
        <FieldRow label="ID del servidor"><Text value={v.servidor} onChange={set("servidor")} /></FieldRow>
        <FieldRow label="ID del canal para mensajes y bienvenida"><Text value={v.canal_mensajes} onChange={set("canal_mensajes")} /></FieldRow>
      </AppPicker>
      <div className="row row--end"><Btn disabled={!conn || !v.servidor || !v.canal_mensajes} onClick={welcome}>Revisar miembros nuevos</Btn><Btn kind="primary" disabled={!conn || !v.servidor} onClick={() => apply({ ...v, connection_id: conn })}>Preparar la estructura</Btn></div>
      {nota && <p className="note">{nota}</p>}
    </Panel>
  );
}

function ThemeUpload() {
  const [conn, setConn] = useState("");
  const [tema, setTema] = useState("");
  const [send] = usePlan("/dd/theme/upload");
  return (
    <Panel title="Instalar las secciones en un tema" note="Sube las seis secciones a la carpeta «sections» del tema que indiques. Usa siempre un duplicado del tema, no el publicado: las secciones aún no se han probado en una tienda real. El ID del tema está en la URL del editor de temas.">
      <ConnPicker value={conn} onChange={setConn}><FieldRow label="ID del tema (duplicado)"><Text value={tema} onChange={setTema} /></FieldRow></ConnPicker>
      <div className="row row--end"><Btn kind="primary" disabled={!conn || !tema} onClick={() => send({ connection_id: conn, tema_id: tema })}>Preparar instalación</Btn></div>
    </Panel>
  );
}

function GmailSync({ module }: { module: string }) {
  const { run, space } = useApp();
  const [conn, setConn] = useState("");
  const [q, setQ] = useState("is:unread newer_than:3d -category:promotions");
  const [res, setRes] = useState<any>(null);
  const go = async () => { const r = await run(api<any>("/dd/sync/gmail", { body: { connection_id: conn, consulta: q, module, space: space.id } })); if (r) setRes(r); };
  return (
    <Panel title="Traer correos de Gmail" note="Solo lectura. Trae remitente, asunto y extracto de hasta 25 correos a la bandeja; después «Clasificar la bandeja» los ordena y prepara borradores. Los mensajes de WhatsApp e Instagram no llegan solos: exigen una dirección pública que Doomsday, al correr en tu equipo, no tiene.">
      <AppPicker value={conn} onChange={setConn} what="Gmail"><FieldRow label="Búsqueda de Gmail"><Text value={q} onChange={setQ} /></FieldRow></AppPicker>
      <div className="row row--end"><Btn kind="primary" disabled={!conn} onClick={go}>Traer correos</Btn></div>
      {res && <p className="note">{res.leidos} leídos, {res.nuevos} nuevos. {res.nota}</p>}
    </Panel>
  );
}

function OuraSync() {
  const { run, space } = useApp();
  const [conn, setConn] = useState("");
  const [res, setRes] = useState<any>(null);
  const go = async () => { const r = await run(api<any>("/dd/sync/oura", { body: { connection_id: conn, space: space.id } })); if (r) setRes(r); };
  return (
    <Panel title="Traer el sueño de Oura" note="Solo lectura: horas dormidas y eficiencia de los últimos 14 días. Otros relojes entran por la exportación de Apple Health de arriba.">
      <AppPicker value={conn} onChange={setConn} what="Oura" />
      <div className="row row--end"><Btn kind="primary" disabled={!conn} onClick={go}>Traer noches</Btn></div>
      {res && <p className="note">{res.dias} noches leídas, {res.nuevos} nuevas.</p>}
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
