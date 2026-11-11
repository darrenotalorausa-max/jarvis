import { createContext, useContext, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { api, type Deliverable } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, ErrorBox, FieldRow, Modal, Panel, Select, Stat, Text } from "../components/ui";
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
export type Tool = { id: string; label: string; campos: FieldSpec[]; auto: boolean; escribe: boolean };
export type Catalog = {
  version: string; categorias: Record<string, { nombre: string; capa: string }>; capas: Record<string, { nombre: string; tipo: string; descripcion: string }>; autonomia: Record<string, string>;
  top20: string[]; modulos: Mod[]; espacios: Record<string, string>; herramientas: Tool[]; skills: { id: string; nombre: string; origen: string; version: number; caracteres: number }[];
};
type ModStat = { registros: number; entregables: number; por_revisar: number; ultimo: string | null };
type Overview = { modulos: Record<string, ModStat>; activos: number; por_revisar: number; skills_propias: number; trabajos: Record<string, number>; actividad: Record<string, number> };

const CatCtx = createContext<{ cat: Catalog; reload: () => void } | null>(null);
export const useCat = () => useContext(CatCtx)!;
export const lc = (capa: string) => ({ "--lc": `var(--${capa})` }) as CSSProperties;
const short = (name: string) => name.split(" · ")[0];
const CAT_SHORT: Record<string, string> = { P: "Productividad", G: "Gestión interna", M: "Marketing y pauta", C: "Contenido y marca", V: "Clientes y ventas", S: "Productos y SaaS",
  A: "Agentes y automatización", H: "Salud y aprendizaje", R: "Relaciones y espíritu", X: "Infraestructura" };

const FIXED: [string, string, string][] = [
  ["revision", "Revisión y aprobación", "M5 4h10l4 4v12H5zM9 13l2 2l4-4"],
  ["skills", "Skills", "M4 6h16M4 12h16M4 18h10M18 16v5M15.5 18.5h5"],
  ["conexiones", "Conexiones de IA", "M9 7H7a5 5 0 0 0 0 10h2M15 7h2a5 5 0 0 1 0 10h-2M8 12h8"],
  ["apps", "Apps conectadas", "M5 5h6v6H5zM13 5h6v6h-6zM5 13h6v6H5zM16 13v6M13 16h6"],
  ["sistema", "Trabajos, uso y respaldo", "M4 6h16M4 12h10M4 18h13M19 12l2 2l-2 2"],
];

function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      {["personal", "interna", "clientes", "comercial"].map((k, i) => (
        <path key={k} d="M16 3.5a12.5 12.5 0 0 1 12.5 12.5" fill="none" stroke={`var(--${k})`} strokeWidth="3" strokeLinecap="round" transform={`rotate(${i * 90 + 8} 16 16)`} pathLength="100" strokeDasharray="78 22" />
      ))}
      <circle cx="16" cy="16" r="3" fill="var(--ink)" />
    </svg>
  );
}

export function App() {
  const { boot, space, setSpace, route, nav, jobs, run, reload } = useApp();
  const owner = (boot.user?.role || "propietario") === "propietario";
  const cat = useData<Catalog | null>(() => (owner ? api<Catalog>("/dd/catalog") : Promise.resolve(null)), [owner]);
  const ov = useOverview(owner);
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
    document.title = `${current === "m" && mod ? `${mod.id} ${mod.nombre}` : current === "c" && cat.data ? cat.data.categorias[route[1]]?.nombre : FIXED.find((f) => f[0] === current)?.[1] || "Centro de mando"} · Doomsday`;
  }, [current, mod, cat.data, route]);
  const ctx = useMemo(() => (cat.data ? { cat: cat.data, reload: cat.reload } : null), [cat.data]);
  if (!owner) return <Guest />;
  if (cat.error) return <div className="splash"><ErrorBox message={cat.error} retry={cat.reload} /></div>;
  if (!ctx) return <div className="splash"><p className="muted">Cargando los 100 módulos…</p></div>;
  const layers = Object.entries(ctx.cat.espacios);
  const layer = layers.find(([, id]) => id === space.id)?.[0] || Object.keys(ctx.cat.capas).find((k) => ctx.cat.capas[k].tipo === space.kind) || "interna";
  const siblings = boot.spaces.filter((s) => !s.archived && s.kind === space.kind);
  const running = jobs.filter((j) => j.status === "running" || j.status === "pending").length;
  const waiting = jobs.filter((j) => j.status.startsWith("waiting")).length;
  const activeCat = current === "c" ? route[1] : current === "m" ? mod?.categoria : "";
  const inUse = (k: string) => ctx.cat.modulos.filter((m) => m.capa === k && ov.data && (ov.data.modulos[m.id].registros || ov.data.modulos[m.id].entregables)).length;
  const today = new Date().toLocaleDateString("es", { day: "numeric", month: "long", year: "numeric" });
  return (
    <CatCtx.Provider value={ctx}>
      <div className="dshell" style={{ "--bc": `var(--${mod?.capa || layer})` } as CSSProperties}>
        <aside className="dside">
          <a className="dbrand" href="#/"><Mark /><strong>DOOMSDAY</strong><span>Centro de mando</span></a>
          <nav className="dnav" aria-label="Principal">
            <a href="#/" aria-current={current === "inicio" ? "page" : undefined}><i className="ldot" style={{ "--lc": "var(--accent)" } as CSSProperties} /><span>Centro de mando</span></a>
          </nav>
          <p className="dside__label">Capas de datos</p>
          <div className="dnav" role="group" aria-label="Capa de datos">
            {layers.map(([key, id]) => (
              <button key={key} aria-pressed={layer === key} title={ctx.cat.capas[key].descripcion} onClick={() => setSpace(id)}>
                <i className="ldot" style={lc(key)} /><span>{short(ctx.cat.capas[key].nombre)}</span><small>{inUse(key)}/{ctx.cat.modulos.filter((m) => m.capa === key).length}</small>
              </button>
            ))}
          </div>
          <p className="dside__label">Categorías</p>
          <nav className="dnav" aria-label="Categorías">
            {Object.entries(ctx.cat.categorias).map(([k, c]) => (
              <a key={k} href={`#/c/${k}`} aria-current={activeCat === k ? "page" : undefined} title={c.nombre}><b className="dnav__k" style={lc(c.capa)}>{k}</b><span>{CAT_SHORT[k] || c.nombre}</span></a>
            ))}
          </nav>
          <p className="dside__label">Sistema</p>
          <nav className="dnav" aria-label="Sistema">
            {FIXED.map(([id, text, d]) => (
              <a key={id} href={`#/${id}`} aria-current={current === id ? "page" : undefined}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg><span>{text}</span>
                {id === "revision" && ov.data && ov.data.por_revisar > 0 ? <small>{ov.data.por_revisar}</small> : null}</a>
            ))}
          </nav>
          <div className="dside__foot">
            <strong>Tú decides. Doomsday prepara.</strong>
            <span>Nada se envía, publica ni gasta solo: cada acción externa espera tu aprobación.</span>
            <span><kbd>Ctrl K</kbd> busca un módulo.</span>
          </div>
        </aside>
        <main className="dmain" id="contenido">
          <div className="dtop">
            <span className="dtop__date">{today}</span>
            {siblings.length > 1 && <Select value={space.id} onChange={setSpace} options={siblings.map((s) => [s.id, s.name])} />}
            {running > 0 && <button className="pill pill--ok" onClick={() => nav("sistema")}><i />{running} en curso</button>}
            {waiting > 0 && <button className="pill pill--warn" onClick={() => nav("sistema")}><i />{waiting} en espera</button>}
            <button className="pill" onClick={() => setPalette(true)}>Buscar módulo <kbd>Ctrl K</kbd></button>
            <button className={`pill${paused ? " pill--warn" : " pill--ok"}`} aria-pressed={paused} title={paused ? "Reanudar todos los agentes" : "Pausar todos los agentes"}
              onClick={async () => { await run(api("/settings", { method: "PATCH", body: { agents_paused: !paused } }), paused ? "Agentes reanudados" : "Agentes en pausa: no se inicia ningún trabajo nuevo"); reload(); }}>
              <i />{paused ? "Agentes en pausa" : "Agentes activos"}
            </button>
          </div>
          <div key={`${space.id}:${route.slice(0, 2).join("/")}`} style={{ display: "contents" }}>
            {current === "m" && mod ? <ModuleView mod={mod} />
              : current === "c" && ctx.cat.categorias[route[1]] ? <Category k={route[1]} ov={ov.data} />
                : current === "revision" ? <Review />
                  : current === "skills" ? <Skills />
                    : current === "conexiones" ? <Connections />
                      : current === "apps" ? <Apps />
                        : current === "sistema" ? <System />
                          : <Home ov={ov.data} />}
          </div>
        </main>
        {palette && <Palette onClose={() => setPalette(false)} />}
      </div>
    </CatCtx.Provider>
  );
}

function useOverview(enabled = true) {
  const { doneTick } = useApp();
  return useData<Overview | null>(() => (enabled ? api<Overview>("/dd/overview") : Promise.resolve(null)), [doneTick, enabled]);
}

export function ModRow({ m, rank, ov }: { m: Mod; rank?: number; ov?: ModStat }) {
  const used = !!ov && (ov.registros > 0 || ov.entregables > 0);
  return (
    <a className="modrow" href={`#/m/${m.id}`} style={lc(m.capa)}>
      <span className={rank ? "modrow__rank" : "mid"}>{rank ? String(rank).padStart(2, "0") : m.id}</span>
      <span className="modrow__name">{rank ? <><span className="mid">{m.id}</span> {m.nombre}</> : m.nombre}<span className="modrow__sub">{m.solucion}</span></span>
      <span className="modrow__meta">
        {ov && ov.por_revisar > 0 && <em>{ov.por_revisar} por revisar</em>}
        {ov && ov.registros > 0 && <span>{ov.registros} registros</span>}
        <i className={`dot${ov && ov.por_revisar ? " dot--next" : used ? " dot--on" : ""}`} title={ov && ov.por_revisar ? "Tiene entregables por revisar" : used ? "En uso" : "Sin usar todavía"} />
      </span>
    </a>
  );
}

// ---------- El dial: cien segmentos, uno por módulo, en cuatro anillos (una capa por anillo)

const RINGS: [string, number][] = [["interna", 184], ["personal", 154], ["clientes", 124], ["comercial", 94]];

function Dial({ ov }: { ov?: Overview | null }) {
  const { cat } = useCat();
  const { nav } = useApp();
  const [hover, setHover] = useState<Mod | null>(null);
  const [focus, setFocus] = useState(0);
  const refs = useRef<(Element | null)[]>([]);
  const segs = useMemo(() => {
    const out: { m: Mod; d: string }[] = [];
    for (const [capa, r] of RINGS) {
      const mods = cat.modulos.filter((m) => m.capa === capa);
      const gap = (5.5 / r) * (180 / Math.PI) * 0.5;  // separación constante en píxeles entre segmentos, en cualquier anillo
      mods.forEach((m, i) => {
        const a0 = (i / mods.length) * 360 + gap - 90, a1 = ((i + 1) / mods.length) * 360 - gap - 90;
        const p = (a: number) => `${(200 + r * Math.cos((a * Math.PI) / 180)).toFixed(2)} ${(200 + r * Math.sin((a * Math.PI) / 180)).toFixed(2)}`;
        out.push({ m, d: `M${p(a0)}A${r} ${r} 0 0 1 ${p(a1)}` });
      });
    }
    return out;
  }, [cat]);
  const move = (e: React.KeyboardEvent, i: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const n = (i + step + segs.length) % segs.length;
    setFocus(n);
    (refs.current[n] as HTMLElement | null)?.focus();
  };
  const shown = hover;
  const st = shown && ov?.modulos[shown.id];
  return (
    <div className="dial">
      <svg viewBox="0 0 400 400" role="group" aria-label="Los 100 módulos por capa. Usa las flechas para recorrerlos.">
        {segs.map(({ m, d }, i) => {
          const s = ov?.modulos[m.id];
          const cls = s?.por_revisar ? " dial__seg--next" : s && (s.registros || s.entregables) ? " dial__seg--on" : "";
          return (
            <a key={m.id} ref={(el) => { refs.current[i] = el; }} href={`#/m/${m.id}`} tabIndex={i === focus ? 0 : -1} aria-label={`${m.id} ${m.nombre}`} style={lc(m.capa)}
              onMouseEnter={() => setHover(m)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(m)} onBlur={() => setHover(null)} onKeyDown={(e) => move(e, i)}
              onClick={(e) => { e.preventDefault(); nav(`m/${m.id}`); }}>
              <path className={`dial__seg${cls}`} d={d} style={{ "--i": i } as CSSProperties} />
            </a>
          );
        })}
        {shown ? (
          <g style={lc(shown.capa)}>
            <text className="dial__k" x="200" y="192" textAnchor="middle">{shown.id}</text>
            <text className="dial__l" x="200" y="214" textAnchor="middle">{shown.nombre.length > 24 ? `${shown.nombre.slice(0, 23)}…` : shown.nombre}</text>
          </g>
        ) : (
          <g>
            <text className="dial__n" x="200" y="210" textAnchor="middle">{ov ? ov.activos : "–"}</text>
            <text className="dial__l" x="200" y="234" textAnchor="middle">de 100 en uso</text>
          </g>
        )}
      </svg>
      <p className="dial__cap">{shown ? `${shown.solucion}.${st && st.por_revisar ? ` ${st.por_revisar} por revisar.` : st && st.registros ? ` ${st.registros} registros.` : ""}` : "Cada segmento es un módulo. Pasa el cursor, o usa las flechas, para ver cuál es."}</p>
    </div>
  );
}

function Heat({ data }: { data: Record<string, number> }) {
  const days = useMemo(() => {
    const out: { d: string; c: number }[] = [];
    const end = new Date();
    end.setDate(end.getDate() + (6 - ((end.getDay() + 6) % 7)));  // la última columna termina en domingo
    for (let i = 83; i >= 0; i--) {
      const x = new Date(end);
      x.setDate(end.getDate() - i);
      const k = `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
      out.push({ d: k, c: data[k] || 0 });
    }
    return out;
  }, [data]);
  const max = Math.max(1, ...days.map((x) => x.c));
  return <div className="heat" role="img" aria-label="Órdenes y entregables por día en las últimas doce semanas">{days.map((x) => <i key={x.d} data-l={x.c ? Math.min(3, Math.ceil((x.c / max) * 3)) : 0} title={`${x.d}: ${x.c}`} />)}</div>;
}

function Home({ ov }: { ov?: Overview | null }) {
  const { cat } = useCat();
  const { nav, run, notify, refreshJobs } = useApp();
  const plans = useData<any[]>(() => api("/dd/plans"), [ov]);
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
  const next: { m: Mod; text: string; to: string }[] = [];
  for (const p of plans.data || []) if (p.estado === "waiting_approval" && byId[p.modulo]) next.push({ m: byId[p.modulo], text: `Aprobar: ${p.titulo}`, to: `m/${p.modulo}` });
  for (const m of cat.modulos) { const s = ov?.modulos[m.id]; if (s?.por_revisar) next.push({ m, text: `Revisar ${s.por_revisar} ${s.por_revisar === 1 ? "entregable" : "entregables"}`, to: `m/${m.id}/entregables` }); }
  if (next.length < 5) for (const id of cat.top20) { if (next.length >= 5) break; const s = ov?.modulos[id]; if (s && !s.registros && !s.entregables) next.push({ m: byId[id], text: `Empezar: ${byId[id].solucion}`, to: `m/${id}` }); }
  const inUse = (k: string) => cat.modulos.filter((m) => m.capa === k && ov && (ov.modulos[m.id].registros || ov.modulos[m.id].entregables)).length;
  return (
    <div className="page">
      <section className="hero">
        <div>
          <h1 className="hero__word">DOOMSDAY</h1>
          <p className="hero__lead">Cien módulos en un solo tablero. Da la orden, revisa el resultado y aprueba lo que sale.</p>
          <div className="stats">
            <Stat label="Módulos en uso" value={<>{ov ? ov.activos : "–"} <small className="muted small">de 100</small></>} />
            <Stat label="Por revisar" value={ov?.por_revisar ?? "–"} />
            <Stat label="Esperan tu decisión" value={ov ? (ov.trabajos.waiting_config || 0) + (ov.trabajos.waiting_approval || 0) : "–"} />
            <Stat label="Skills tuyas" value={<>{ov ? ov.skills_propias : "–"} <small className="muted small">de 100</small></>} />
          </div>
          <div className="legend">
            {Object.entries(cat.capas).map(([k, c]) => <span key={k}><i style={lc(k)} />{short(c.nombre)} <b>{inUse(k)}/{cat.modulos.filter((m) => m.capa === k).length}</b></span>)}
            <span><i style={{ "--lc": "var(--accent)" } as CSSProperties} />Por revisar</span>
            <span><i className="ring" />Sin usar</span>
          </div>
        </div>
        <Panel><Dial ov={ov} /></Panel>
      </section>
      <div className="grid grid--2">
        <Panel title="Qué sigue">
          {next.length ? (
            <div className="modlist">{next.slice(0, 6).map((n, i) => (
              <a key={`${n.m.id}${i}`} className="modrow" href={`#/${n.to}`} style={lc(n.m.capa)}>
                <i className={`dot ${n.text.startsWith("Empezar") ? "dot--on" : "dot--next"}`} style={{ justifySelf: "center" }} />
                <span className="modrow__name">{n.text}<span className="modrow__sub">{n.m.id} · {n.m.nombre}</span></span><span className="modrow__meta"><em>Abrir</em></span>
              </a>
            ))}</div>
          ) : <p className="muted">Nada pendiente. Da una orden a cualquier módulo.</p>}
        </Panel>
        <Panel title="Actividad" note="Órdenes y entregables por día, últimas doce semanas.">{ov ? <Heat data={ov.actividad || {}} /> : null}</Panel>
      </div>
      <Panel title="Dar una orden" note="Escribe poco: la skill del módulo aplica su método completo y deja el resultado como borrador en Revisión. Sin IA conectada, usa las herramientas de cada módulo: calculan con tus datos.">
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
          <div className="modlist">{cat.top20.map((id, i) => <ModRow key={id} m={byId[id]} rank={i + 1} ov={ov?.modulos[id]} />)}</div>
        </Panel>
        <Panel title="Categorías">
          <div className="modlist">{Object.entries(cat.categorias).map(([k, c]) => (
            <a key={k} className="modrow" href={`#/c/${k}`} style={lc(c.capa)}><span className="mid">{k}</span><span className="modrow__name">{c.nombre}</span>
              <span className="modrow__meta">{ov ? cat.modulos.filter((m) => m.categoria === k && (ov.modulos[m.id].registros || ov.modulos[m.id].entregables)).length : 0}/10</span></a>
          ))}</div>
        </Panel>
      </div>
    </div>
  );
}

function Category({ k, ov }: { k: string; ov?: Overview | null }) {
  const { cat } = useCat();
  const mods = cat.modulos.filter((m) => m.categoria === k).sort((a, b) => b.puntos - a.puntos);
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">{cat.categorias[k].nombre}</h1>
        <p className="page__sub">Capa «{cat.capas[cat.categorias[k].capa].nombre}». Diez módulos, cada uno con sus datos, sus herramientas y su skill.</p></div></div>
      <Panel><div className="modlist">{mods.map((m) => <ModRow key={m.id} m={m} ov={ov?.modulos[m.id]} />)}</div></Panel>
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
            <tr key={s.id}><td className="mid" style={lc(cat.categorias[s.id[0]].capa)}>{s.id}</td><td><a href={`#/m/${s.id}/skill`}>{s.nombre}</a></td>
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
        {hits.map((m) => <button key={m.id} className="libitem" onClick={() => go(m.id)}><strong><span className="mid" style={lc(m.capa)}>{m.id}</span> {m.nombre}</strong><span>{m.solucion}</span></button>)}
        {!hits.length && <p className="muted small">Ningún módulo coincide con «{q}».</p>}
      </div>
    </Modal>
  );
}

/** Clientes y equipo: entran con su usuario y ven solo la revisión de sus espacios. El cliente puede aceptar los documentos que se le envían. */
function Guest() {
  const { boot, space, setSpace, run, doneTick } = useApp();
  const [v, setV] = useState<Record<string, any>>({});
  const [done, setDone] = useState("");
  const docs = useData<Deliverable[]>(() => api("/deliverables", { query: { space: space.id, kind: "dd", status: "aprobado" } }), [space.id, doneTick, done]);
  const contratos = (docs.data || []).filter((d) => d.title.startsWith("V08 · "));
  const sign = async () => {
    const r = await run(api<{ huella: string }>("/dd/sign", { body: { space: space.id, deliverable_id: v.id, nombre: v.nombre, acepto: !!v.acepto } }), "Documento aceptado. Queda constancia con fecha y huella del texto.");
    if (r) { setDone(r.huella); setV({}); }
  };
  return (
    <div className="dshell" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
      <main className="dmain">
        <div className="dtop">
          <a className="dbrand" href="#/" style={{ padding: 0, marginRight: "auto" }}><Mark /><strong>DOOMSDAY</strong><span>Portal de {space.name}</span></a>
          {boot.spaces.length > 1 && <Select value={space.id} onChange={setSpace} options={boot.spaces.map((s) => [s.id, s.name])} />}
          <button className="pill" onClick={async () => { await api("/logout", { method: "POST" }); location.reload(); }}>{boot.user.username} · salir</button>
        </div>
        <div className="page" key={space.id}>
          {boot.user.role === "cliente" && contratos.length > 0 && (
            <Panel title="Documentos por aceptar" note="Al aceptar queda registrado tu nombre, la fecha, tu usuario y la huella exacta del texto que leíste. Es una aceptación electrónica simple.">
              <div className="form">
                <FieldRow label="Documento"><Select value={v.id ?? ""} onChange={(id) => setV((s) => ({ ...s, id }))} options={contratos.map((d) => [d.id, d.title.replace("V08 · ", "")])} empty="Elige el documento" /></FieldRow>
                <FieldRow label="Tu nombre completo"><Text value={v.nombre} onChange={(nombre) => setV((s) => ({ ...s, nombre }))} /></FieldRow>
                <FieldRow label=""><Check checked={!!v.acepto} onChange={(acepto) => setV((s) => ({ ...s, acepto }))}>He leído el documento completo y lo acepto</Check></FieldRow>
              </div>
              <div className="row row--end"><Btn kind="primary" disabled={!v.id || !v.acepto || (v.nombre || "").trim().length < 5} onClick={sign}>Aceptar documento</Btn></div>
              {done && <p className="note">Aceptado. Huella: <span className="mono">{done.slice(0, 24)}…</span></p>}
            </Panel>
          )}
          <Review />
        </div>
      </main>
    </div>
  );
}
