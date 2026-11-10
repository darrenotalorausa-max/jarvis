import { useEffect } from "react";
import { useApp } from "./store";
import { Select } from "./components/ui";
import { Command } from "./views/Command";
import { Clipping, Content, Leads, Opportunities, Shopify } from "./views/business";
import { Video } from "./views/Video";
import { Operations, Personal, Projects, Review } from "./views/manage";
import { Connections } from "./views/Connections";
import { System } from "./views/System";

const NAV: [string, string, string][] = [
  ["comando", "Comando Jarvis", "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7"],
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
  ["conexiones", "Conexiones", "M9 7H7a5 5 0 0 0 0 10h2M15 7h2a5 5 0 0 1 0 10h-2M8 12h8"],
  ["sistema", "Trabajos, uso y diagnóstico", "M4 6h16M4 12h10M4 18h13M19 12l2 2l-2 2"],
];
const VIEWS: Record<string, () => JSX.Element> = {
  comando: Command, oportunidades: Opportunities, leads: Leads, contenido: Content, video: Video, shopify: Shopify, clipping: Clipping,
  revision: Review, proyectos: Projects, operaciones: Operations, personal: Personal, conexiones: Connections, sistema: System,
};
const last = { get: () => { try { return localStorage.getItem("jarvis.last") || "oportunidades"; } catch { return "oportunidades"; } }, set: (v: string) => { try { localStorage.setItem("jarvis.last", v); } catch { /* sin almacenamiento */ } } };

export function App() {
  const { boot, space, setSpace, route, nav, jobs } = useApp();
  const current = VIEWS[route[0]] ? route[0] : "comando";
  const View = VIEWS[current];
  const command = current === "comando";
  useEffect(() => { if (!command) last.set(route.join("/")); }, [route, command]);
  useEffect(() => { document.title = `${NAV.find((n) => n[0] === current)?.[1] || "Jarvis"} · Jarvis OS`; }, [current]);
  const running = jobs.filter((j) => j.status === "running").length;
  const waiting = jobs.filter((j) => j.status.startsWith("waiting")).length;
  return (
    <div className={`shell${command ? " shell--command" : ""}`}>
      <header className="top">
        <a className="brand" href="#/comando" style={{ textDecoration: "none" }}>
          <svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="11" fill="none" stroke="#5fd7ff" strokeWidth="1.6" /><circle cx="16" cy="16" r="6.5" fill="none" stroke="#5fd7ff" strokeWidth="1" strokeDasharray="3 2.4" /><circle cx="16" cy="16" r="2.6" fill="#c4ecff" /></svg>
          JARVIS OS
        </a>
        <div className="seg" role="group" aria-label="Modo de la interfaz">
          <button aria-pressed={command} onClick={() => nav("comando")}>COMMAND</button>
          <button aria-pressed={!command} onClick={() => nav(last.get())}>WORKSPACE</button>
        </div>
        <span className="top__spacer" />
        {running > 0 && <button className={`pill pill--ok`} style={{ cursor: "pointer", background: "none" }} onClick={() => nav("sistema")}><i />{running} en ejecución</button>}
        {waiting > 0 && <button className="pill pill--warn" style={{ cursor: "pointer", background: "none" }} onClick={() => nav("sistema")}><i />{waiting} en espera</button>}
        <label className="sr" htmlFor="espacio">Espacio de trabajo</label>
        <div><Select value={space.id} onChange={setSpace} options={boot.spaces.filter((s) => !s.archived).map((s) => [s.id, `${s.name} · ${boot.space_kinds[s.kind]}`])} /></div>
      </header>
      <nav className="nav" aria-label="Módulos">
        {NAV.map(([id, text, d]) => (
          <a key={id} href={`#/${id}`} aria-current={current === id ? "page" : undefined} title={text} aria-label={text}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg><span>{text}</span>
          </a>
        ))}
      </nav>
      <main className="main" id="contenido" key={`${space.id}:${current}`}><View /></main>
    </div>
  );
}
