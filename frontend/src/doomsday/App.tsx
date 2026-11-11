import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, fmtDate } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, ErrorBox, Modal, Panel, Skeleton, Stat } from "../components/ui";
import { Review } from "../views/manage";
import { Connections } from "../views/Connections";
import { Apps } from "../views/Apps";
import { System } from "../views/System";
import { ModuleView } from "./Module";

export type FieldSpec = { name: string; label: string; type: string; options?: string[] };
export type Action = { id: string; label: string; tarea: string; campos: FieldSpec[]; contexto: string[]; herramienta: string | null; emite: string | null };
export type Mod = {
  id: string; nombre: string; categoria: string; capa: string; problema: string; solucion: string; funciones: string[]; usuarios: string; decision_pdf: string;
  esfuerzo: string; puntos: number; nivel: string; kinds: string[]; tools: string[]; acciones: Action[]; conexiones: string[]; widget: string | null;
};
export type Tool = { id: string; label: string; campos: FieldSpec[]; auto: boolean };
export type Catalog = {
  version: string; categorias: Record<string, { nombre: string; capa: string }>; capas: Record<string, { nombre: string; descripcion: string }>; autonomia: Record<string, string>;
  top20: string[]; modulos: Mod[]; espacios: Record<string, string>; herramientas: Tool[]; skills: { id: string; nombre: string; origen: string; version: number; caracteres: number }[];
};
type Overview = { modulos: Record<string, { registros: number; entregables: number; por_revisar: number; ultimo: string | null }>; activos: number; por_revisar: number; skills_propias: number; trabajos: Record<string, number> };

const CatCtx = createContext<{ cat: Catalog; reload: () => void } | null>(null);
export const useCat = () => useContext(CatCtx)!;

const FIXED: [string, string, string][] = [
  ["revision", "Revisión y aprobación", "M5 4h10l4 4v12H5zM9 13l2 2l4-4"],
  ["skills", "Skills", "M4 6h16M4 12h16M4 18h10M18 16v5M15.5 18.5h5"],
  ["conexiones", "Conexiones de IA", "M9 7H7a5 5 0 0 0 0 10h2M15 7h2a5 5 0 0 1 0 10h-2M8 12h8"],
  ["apps", "Apps conectadas", "M5 5h6v6H5zM13 5h6v6h-6zM5 13h6v6H5zM16 13v6M13 16h6"],
  ["sistema", "Trabajos, uso y respaldo", "M4 6h16M4 12h10M4 18h13M19 12l2 2l-2 2"],
];

export function App() {
  const { boot, space, setSpace, route, nav, jobs, run, reload } = useApp();
  const cat = useData<Catalog>(() => api("/dd/catalog"), []);
  const [palette, setPalette] = useState(false);
  const current = route[0] || "inicio";
  const paused = !!boot.settings.agents_paused;
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); } };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  const mod = cat.data?.modulos.find((m) => m.id === route[1]);
  useEffect(() => {
    document.title = `${current === "m" && mod ? `${mod.id} ${mod.nombre}` : current === "c" && cat.data ? cat.data.categorias[route[1]]?.nombre : FIXED.find((f) => f[0] === current)?.[1] || "Tablero"} · Doomsday`;
  }, [current, mod, cat.data, route]);
  const ctx = useMemo(() => (cat.data ? { cat: cat.data, reload: cat.reload } : null), [cat.data]);
  if (cat.error) return <div className="splash"><ErrorBox message={cat.error} retry={cat.reload} /></div>;
  if (!ctx) return <div className="splash"><p className="muted">Cargando los 100 módulos…</p></div>;
  const layers = Object.entries(ctx.cat.espacios);
  const layer = layers.find(([, id]) => id === space.id)?.[0];
  const running = jobs.filter((j) => j.status === "running" || j.status === "pending").length;
  const waiting = jobs.filter((j) => j.status.startsWith("waiting")).length;
  const activeCat = current === "c" ? route[1] : current === "m" ? mod?.categoria : "";
  return (
    <CatCtx.Provider value={ctx}>
      <div className="shell">
        <header className="top">
          <a className="dbrand" href="#/">
            <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M9 7h7a9 9 0 0 1 0 18H9z" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" /><path d="M14 12v8" stroke="var(--accent-ink)" strokeWidth="2" strokeLinecap="round" /></svg>
            DOOMSDAY
          </a>
          <div className="seg" role="group" aria-label="Capa de datos">
            {layers.map(([key, id]) => <button key={key} aria-pressed={space.id === id} title={ctx.cat.capas[key].descripcion} onClick={() => setSpace(id)}>{ctx.cat.capas[key].nombre.split(" · ")[0]}</button>)}
          </div>
          <span className="top__spacer" />
          {running > 0 && <button className="pill pill--ok" onClick={() => nav("sistema")}><i />{running} en curso</button>}
          {waiting > 0 && <button className="pill pill--warn" onClick={() => nav("sistema")}><i />{waiting} en espera</button>}
          <button className="pill" onClick={() => setPalette(true)} title="Buscar un módulo (Ctrl K)">Buscar módulo <span className="mono">Ctrl K</span></button>
          <button className={`pill${paused ? " pill--warn" : ""}`} aria-pressed={paused} title={paused ? "Reanudar todos los agentes" : "Pausar todos los agentes"}
            onClick={async () => { await run(api("/settings", { method: "PATCH", body: { agents_paused: !paused } }), paused ? "Agentes reanudados" : "Agentes en pausa: no se inicia ningún trabajo nuevo"); reload(); }}>
            <i />{paused ? "Agentes en pausa" : "Agentes activos"}
          </button>
        </header>
        <nav className="nav" aria-label="Categorías y sistema">
          <a href="#/" aria-current={current === "inicio" ? "page" : undefined}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h7v6H4zM13 5h7v9h-7zM4 13h7v6H4zM13 16h7v3h-7z" /></svg><span>Tablero</span></a>
          <div className="nav__sep" />
          {Object.entries(ctx.cat.categorias).map(([k, c]) => (
            <a key={k} href={`#/c/${k}`} aria-current={activeCat === k ? "page" : undefined} title={c.nombre}><b className="nav__k">{k}</b><span>{c.nombre}</span></a>
          ))}
          <div className="nav__sep" />
          {FIXED.map(([id, text, d]) => (
            <a key={id} href={`#/${id}`} aria-current={current === id ? "page" : undefined} title={text}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg><span>{text}</span></a>
          ))}
        </nav>
        <main className="main" id="contenido" key={`${space.id}:${route.slice(0, 2).join("/")}`}>
          {current === "m" && mod ? <ModuleView mod={mod} />
            : current === "c" && ctx.cat.categorias[route[1]] ? <Category k={route[1]} />
              : current === "revision" ? <Review />
                : current === "skills" ? <Skills />
                  : current === "conexiones" ? <Connections />
                    : current === "apps" ? <Apps />
                      : current === "sistema" ? <System />
                        : <Home layer={layer} />}
        </main>
        {palette && <Palette onClose={() => setPalette(false)} />}
      </div>
    </CatCtx.Provider>
  );
}

function useOverview() {
  const { doneTick } = useApp();
  return useData<Overview>(() => api("/dd/overview"), [doneTick]);
}

export function ModRow({ m, rank, ov }: { m: Mod; rank?: number; ov?: Overview["modulos"][string] }) {
  return (
    <a className="modrow" href={`#/m/${m.id}`}>
      <span className={rank ? "modrow__rank" : "mid"}>{rank ? String(rank).padStart(2, "0") : m.id}</span>
      <span className="modrow__name">{rank ? <><span className="mid">{m.id}</span> {m.nombre}</> : m.nombre}<span className="modrow__sub">{m.solucion}</span></span>
      <span className="modrow__meta">
        {ov && ov.por_revisar > 0 && <span className="amber">{ov.por_revisar} por revisar</span>}
        {ov && ov.registros > 0 && <span>{ov.registros} registros</span>}
        <span>{m.puntos} pts</span>
        <i className={`dot${ov && ov.por_revisar ? " dot--warn" : ov && (ov.registros || ov.entregables) ? " dot--on" : ""}`} title={ov && (ov.registros || ov.entregables) ? "Con actividad" : "Sin actividad todavía"} />
      </span>
    </a>
  );
}

function Home({ layer }: { layer?: string }) {
  const { cat } = useCat();
  const { nav, run, notify, refreshJobs } = useApp();
  const ov = useOverview();
  const [target, setTarget] = useState("");
  const [order, setOrder] = useState("");
  const [busy, setBusy] = useState(false);
  const byId = useMemo(() => Object.fromEntries(cat.modulos.map((m) => [m.id, m])), [cat]);
  const picked = byId[target.trim().slice(0, 3).toUpperCase()];
  const send = async () => {
    if (!picked) return;
    setBusy(true);
    const res = await run(api<{ job: { id: string }; created: boolean }>("/dd/run", { body: { module: picked.id, action: "orden", inputs: { orden: order } } }));
    setBusy(false);
    if (!res) return;
    notify(res.created ? `Orden enviada a ${picked.id}. El entregable aparecerá en su panel.` : "Ya había una orden igual en curso; no se duplicó.", res.created ? "ok" : "info");
    setOrder("");
    refreshJobs();
    nav(`m/${picked.id}`);
  };
  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">Laboratorio de software</h1>
          <p className="page__sub">Cien módulos en diez categorías. Cada uno tiene sus datos, sus herramientas de cálculo y una skill profesional que convierte una orden corta en un entregable listo para revisar. Nada se publica, se envía ni gasta sin tu aprobación.</p>
        </div>
      </div>
      <div className="stats">
        <Stat label="Módulos con actividad" value={ov.data ? `${ov.data.activos} de 100` : "—"} />
        <Stat label="Entregables por revisar" value={ov.data?.por_revisar ?? "—"} tone={ov.data?.por_revisar ? "amber" : undefined} />
        <Stat label="Órdenes esperando" value={ov.data ? (ov.data.trabajos.waiting_config || 0) + (ov.data.trabajos.waiting_approval || 0) : "—"} hint="Configuración o aprobación"
          tone={ov.data && (ov.data.trabajos.waiting_config || ov.data.trabajos.waiting_approval) ? "amber" : undefined} />
        <Stat label="Skills propias" value={ov.data ? `${ov.data.skills_propias} de 100` : "—"} hint="El resto usa la skill integrada" />
        <Stat label="Capa activa" value={layer ? cat.capas[layer].nombre.split(" · ")[0] : "—"} hint="Cada capa guarda sus datos aparte" />
      </div>
      <Panel title="Dar una orden" note="Escribe poco: la skill del módulo aplica su método completo y deja el resultado como borrador en Revisión.">
        <div className="order">
          <div className="form">
            <label className="field"><span className="field__label">Módulo</span>
              <input className="input" list="dd-mods" placeholder="G04 Fábrica de fichas" value={target} onChange={(e) => setTarget(e.target.value)} />
              <datalist id="dd-mods">{cat.modulos.map((m) => <option key={m.id} value={`${m.id} ${m.nombre}`} />)}</datalist>
              {target && !picked && <span className="field__hint">Elige un módulo de la lista (empieza por su código, como G04).</span>}
            </label>
          </div>
          <textarea className="input" aria-label="Orden" placeholder={picked ? `Qué necesitas de «${picked.nombre}»` : "Elige un módulo y escribe qué necesitas"} value={order} onChange={(e) => setOrder(e.target.value)} />
          <div className="row"><Btn kind="primary" busy={busy} disabled={!picked || order.trim().length < 3} onClick={send}>Enviar orden</Btn>{picked && <Btn kind="ghost" onClick={() => nav(`m/${picked.id}`)}>Abrir el panel de {picked.id}</Btn>}</div>
        </div>
      </Panel>
      <div className="grid grid--side">
        <Panel title="Los 20 mejores proyectos" note="Orden de la clasificación general del Laboratorio Estratégico. Las puntuaciones son preliminares: ningún ahorro está medido todavía.">
          <div className="modlist">{cat.top20.map((id, i) => <ModRow key={id} m={byId[id]} rank={i + 1} ov={ov.data?.modulos[id]} />)}</div>
        </Panel>
        <div className="stack">
          <Panel title="Capas de datos">
            <div className="stack">{Object.entries(cat.capas).map(([k, c]) => <div key={k}><strong>{c.nombre}</strong><p className="small muted">{c.descripcion}</p></div>)}</div>
            <p className="note">Los datos de clientes, los de tus tiendas y los personales nunca comparten espacio ni caché.</p>
          </Panel>
          <Panel title="Categorías">
            <div className="modlist">{Object.entries(cat.categorias).map(([k, c]) => (
              <a key={k} className="modrow" href={`#/c/${k}`}><span className="mid">{k}</span><span className="modrow__name">{c.nombre}</span>
                <span className="modrow__meta">{ov.data ? cat.modulos.filter((m) => m.categoria === k && (ov.data!.modulos[m.id].registros || ov.data!.modulos[m.id].entregables)).length : 0} de 10 en uso</span></a>
            ))}</div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Category({ k }: { k: string }) {
  const { cat } = useCat();
  const ov = useOverview();
  const mods = cat.modulos.filter((m) => m.categoria === k).sort((a, b) => b.puntos - a.puntos);
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">{cat.categorias[k].nombre}</h1>
        <p className="page__sub">Capa «{cat.capas[cat.categorias[k].capa].nombre}». Diez módulos ordenados por puntuación.</p></div></div>
      <Panel><div className="modlist">{mods.map((m) => <ModRow key={m.id} m={m} ov={ov.data?.modulos[m.id]} />)}</div></Panel>
    </div>
  );
}

function Skills() {
  const { cat, reload } = useCat();
  const { run, notify } = useApp();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ importadas: string[]; ignoradas: string[] } | null>(null);
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    setBusy(true);
    const res = await run(api<{ importadas: string[]; ignoradas: string[] }>("/dd/skills/import", { form }));
    setBusy(false);
    if (res) { setResult(res); notify(`${res.importadas.length} skills importadas.`, res.importadas.length ? "ok" : "info"); reload(); }
  };
  return (
    <div className="page">
      <div className="page__head">
        <div><h1 className="page__title">Skills</h1>
          <p className="page__sub">Una skill por módulo: rol, método, estándar de calidad y prohibiciones. Las tuyas sustituyen a las integradas y cada cambio guarda la versión anterior.</p></div>
        <label className="btn btn--primary" aria-busy={busy}>Importar mis skills
          <input type="file" accept=".md,.txt,.zip" multiple hidden onChange={(e) => { upload(e.target.files); e.target.value = ""; }} /></label>
      </div>
      <p className="note">Formatos aceptados: un archivo por skill llamado con el código del módulo (<span className="mono">G04.md</span>, <span className="mono">M06-variaciones.md</span>), un solo archivo con secciones <span className="mono">## G04 · Nombre</span>, o un .zip con cualquiera de ellos.</p>
      <Panel>
        <div className="tablewrap"><table>
          <thead><tr><th>Módulo</th><th>Skill</th><th>Origen</th><th>Versión</th><th className="right">Caracteres</th></tr></thead>
          <tbody>{cat.skills.map((s) => (
            <tr key={s.id}><td className="mid">{s.id}</td><td><a href={`#/m/${s.id}/skill`}>{s.nombre}</a></td>
              <td><Badge value={s.origen === "propia" ? "activa" : "mute"} text={s.origen === "propia" ? "Tuya" : "Integrada"} /></td><td>v{s.version}</td><td className="right mono">{s.caracteres}</td></tr>
          ))}</tbody>
        </table></div>
      </Panel>
      {result && (
        <Modal title="Importación de skills" onClose={() => setResult(null)}>
          <p>{result.importadas.length ? `Importadas: ${result.importadas.join(", ")}.` : "No se importó ninguna skill."}</p>
          {result.ignoradas.length > 0 && <><p className="muted">No se importaron:</p><ul className="list">{result.ignoradas.map((x) => <li key={x}>{x}</li>)}</ul></>}
          <div className="row row--end"><Btn kind="primary" onClick={() => setResult(null)}>Entendido</Btn></div>
        </Modal>
      )}
    </div>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const { cat } = useCat();
  const { nav } = useApp();
  const [q, setQ] = useState("");
  const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const hits = cat.modulos.filter((m) => !q.trim() || norm(`${m.id} ${m.nombre} ${m.problema} ${m.solucion} ${m.funciones.join(" ")}`).includes(norm(q.trim()))).slice(0, 12);
  const go = (id: string) => { nav(`m/${id}`); onClose(); };
  return (
    <Modal title="Ir a un módulo" onClose={onClose}>
      <input className="input" autoFocus placeholder="Código, nombre o lo que quieres resolver" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) go(hits[0].id); }} />
      <div className="palette">
        {hits.map((m) => <button key={m.id} className="libitem" onClick={() => go(m.id)}><strong><span className="mid">{m.id}</span> {m.nombre}</strong><span>{m.solucion}</span></button>)}
        {!hits.length && <p className="muted small">Ningún módulo coincide con «{q}».</p>}
      </div>
    </Modal>
  );
}

export { fmtDate, Skeleton };
