import { useEffect, useState } from "react";
import { useApp } from "./store";
import { Select } from "./components/ui";
import { Command } from "./views/Command";
import { Clipping, Content, Leads, Opportunities, Shopify } from "./views/business";
import { Video } from "./views/Video";
import { Operations, Personal, Projects, Review } from "./views/manage";
import { Connections } from "./views/Connections";
import { System } from "./views/System";
import { Business } from "./views/CommandCenter";
import { Library } from "./views/Library";
import { Apps } from "./views/Apps";
import { api } from "./api";
import { useData } from "./store";
import { Modal } from "./components/ui";
import { setSound, soundOn } from "./sound";

const NAV: [string, string, string][] = [
  ["comando", "Comando Jarvis", "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7"],
  ["negocios", "Centro de negocios", "M3 20h18M5 20V9l7-5l7 5v11M9 20v-6h6v6"],
  ["oportunidades", "Mesa de oportunidades", "M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14M21 21l-5-5"],
  ["leads", "Leads y ofertas B2B", "M4 20V6l8-3l8 3v14M9 20v-5h6v5M9 10h.01M15 10h.01"],
  ["contenido", "Fábrica de contenido", "M4 5h16v11H4zM8 20h8M12 16v4M9 9l5 2l-5 2z"],
  ["video", "Editor audiovisual", "M3 6h13v12H3zM16 10l5-3v10l-5-3M3 10h13"],
  ["shopify", "Constructor Shopify", "M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2"],
  ["clipping", "Clipping", "M6 4v16M6 8h9l-2 3l2 3H6M18 4v16"],
  ["revision", "Revisión y aprobación", "M5 4h10l4 4v12H5zM9 13l2 2l4-4"],
  ["proyectos", "Proyectos, marcas y biblioteca", "M3 7h7l2 2h9v10H3zM3 7V5h6"],
  ["operaciones", "Operaciones y economía", "M4 20V10M10 20V4M16 20v-7M21 20H3"],
  ["personal", "Espacio personal", "M12 4a4 4 0 1 0 0 8a4 4 0 0 0 0-8M4 20a8 8 0 0 1 16 0"],
  ["biblioteca", "Biblioteca", "M5 4h5v16H5zM10 4h5v16h-5zM16 6l3-1l3 14l-3 1z"],
  ["conexiones", "Conexiones", "M9 7H7a5 5 0 0 0 0 10h2M15 7h2a5 5 0 0 1 0 10h-2M8 12h8"],
  ["apps", "Apps conectadas", "M5 5h6v6H5zM13 5h6v6h-6zM5 13h6v6H5zM16 13v6M13 16h6"],
  ["sistema", "Trabajos, uso y diagnóstico", "M4 6h16M4 12h10M4 18h13M19 12l2 2l-2 2"],
];
const VIEWS: Record<string, () => JSX.Element> = {
  comando: Command, oportunidades: Opportunities, leads: Leads, contenido: Content, video: Video, shopify: Shopify, clipping: Clipping,
  negocios: Business, biblioteca: Library, apps: Apps, revision: Review, proyectos: Projects, operaciones: Operations, personal: Personal, conexiones: Connections, sistema: System,
};
const last = { get: () => { try { return localStorage.getItem("jarvis.last") || "oportunidades"; } catch { return "oportunidades"; } }, set: (v: string) => { try { localStorage.setItem("jarvis.last", v); } catch { /* sin almacenamiento */ } } };

export function App() {
  const { boot, space, setSpace, route, nav, jobs, run, reload } = useApp();
  const [palette, setPalette] = useState(false);
  const [sound, setSoundState] = useState(soundOn());
  const paused = !!boot.settings.agents_paused;
  const role = boot.user?.role || "propietario";
  const visible = NAV.filter(([id]) => role === "propietario" || (role === "cliente" ? id === "revision" : !["conexiones", "apps", "sistema", "personal", "comando"].includes(id)));
  const home = role === "propietario" ? "comando" : visible[0][0];
  const current = VIEWS[route[0]] && visible.some(([id]) => id === route[0]) ? route[0] : home;
  const View = VIEWS[current];
  const command = current === "comando";
  useEffect(() => { if (!command) last.set(route.join("/")); }, [route, command]);
  useEffect(() => { document.title = `${NAV.find((n) => n[0] === current)?.[1] || "Jarvis"} · Jarvis OS`; }, [current]);
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); } };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  const running = jobs.filter((j) => j.status === "running").length;
  const waiting = jobs.filter((j) => j.status.startsWith("waiting")).length;
  return (
    <div className={`shell${command ? " shell--command" : ""}`}>
      <header className="top">
        <a className="brand" href="#/comando" style={{ textDecoration: "none" }}>
          <svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="11" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="46 23" strokeLinecap="round" /><circle cx="16" cy="16" r="3" fill="var(--accent-ink)" /></svg>
          Jarvis OS
        </a>
        <div className="seg" role="group" aria-label="Modo de la interfaz">
          <button aria-pressed={command} onClick={() => nav("comando")}>Command</button>
          <button aria-pressed={!command} onClick={() => nav(last.get())}>Workspace</button>
        </div>
        <span className="top__spacer" />
        {running > 0 && <button className="pill pill--ok" onClick={() => nav("sistema")}><i />{running} en ejecución</button>}
        {waiting > 0 && <button className="pill pill--warn" onClick={() => nav("sistema")}><i />{waiting} en espera</button>}
        {role !== "propietario" && <button className="pill" onClick={async () => { await api("/logout", { method: "POST" }); location.reload(); }}>{boot.user.username} · salir</button>}
        <button className="pill" onClick={() => setPalette(true)} title="Buscar módulos y guías (Ctrl K)">Buscar <span className="mono">Ctrl K</span></button>
        {role === "propietario" && <button className={`pill${paused ? " pill--warn" : ""}`} aria-pressed={paused} title={paused ? "Reanudar todos los agentes" : "Pausar todos los agentes"}
          onClick={async () => { await run(api("/settings", { method: "PATCH", body: { agents_paused: !paused } }), paused ? "Agentes reanudados" : "Agentes en pausa: no se inicia ningún trabajo nuevo"); reload(); }}><i />{paused ? "Agentes en pausa" : "Agentes activos"}</button>}
        <button className="pill" aria-pressed={sound} title="Sonidos de la interfaz" onClick={() => { setSound(!sound); setSoundState(!sound); }}>{sound ? "Sonido sí" : "Sonido no"}</button>
        <label className="sr" htmlFor="espacio">Espacio de trabajo</label>
        <div><Select value={space.id} onChange={setSpace} options={boot.spaces.filter((s) => !s.archived).map((s) => [s.id, `${s.name} · ${boot.space_kinds[s.kind]}`])} /></div>
      </header>
      <nav className="nav" aria-label="Módulos">
        {visible.map(([id, text, d]) => (
          <a key={id} href={`#/${id}`} aria-current={current === id ? "page" : undefined} title={text} aria-label={text}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg><span>{text}</span>
          </a>
        ))}
      </nav>
      <main className="main" id="contenido" key={`${space.id}:${current}`}><View /></main>
      {palette && <Palette onClose={() => setPalette(false)} />}
    </div>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const { nav } = useApp();
  const [q, setQ] = useState("");
  const hits = useData<any[]>(() => (q.trim().length > 1 ? api("/library/search", { query: { q } }) : Promise.resolve([])), [q]);
  const { boot } = useApp();
  const role = boot.user?.role || "propietario";
  const mods = NAV.filter(([id]) => role === "propietario" || (role === "cliente" ? id === "revision" : !["conexiones", "apps", "sistema", "personal", "comando"].includes(id))).filter(([, text]) => !q.trim() || text.toLowerCase().includes(q.trim().toLowerCase()));
  const go = (route: string) => { nav(route); onClose(); };
  return (
    <Modal title="Ir a…" onClose={onClose}>
      <input className="input" autoFocus placeholder="Escribe un módulo o un tema de la biblioteca" value={q} onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { if (mods[0]) go(mods[0][0]); else if (hits.data?.[0]) go(`biblioteca/${hits.data[0].path.split("/").map(encodeURIComponent).join("/")}`); } }} />
      <div className="palette">
        {mods.map(([id, text]) => <button key={id} className="libitem" onClick={() => go(id)}><strong>{text}</strong><span>Módulo</span></button>)}
        {(hits.data || []).slice(0, 8).map((h) => <button key={h.path} className="libitem" onClick={() => go(`biblioteca/${h.path.split("/").map(encodeURIComponent).join("/")}`)}><strong>{h.title}</strong><span>{h.collection}</span></button>)}
        {q.trim().length > 1 && !mods.length && !hits.data?.length && <p className="muted small">Nada coincide con «{q}».</p>}
      </div>
    </Modal>
  );
}
