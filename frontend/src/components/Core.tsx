import { useEffect, useRef, useState, type MutableRefObject } from "react";

// Núcleo de Jarvis: único elemento firma de la interfaz. Todo lo que muestra es un hecho del sistema:
// estado real, avance real de los trabajos (anillo de progreso) y nivel real del micrófono (onda).
export type CoreState = "idle" | "listening" | "processing" | "speaking" | "error" | "approval";

const TEXT: Record<CoreState, [string, string]> = {
  idle: ["En espera", "Sin actividad en curso"],
  listening: ["Escuchando", "Micrófono abierto: suelta para terminar"],
  processing: ["Procesando", "Hay trabajo en ejecución"],
  speaking: ["Hablando", "Respuesta por voz en curso"],
  error: ["Atención", "Algo falló: revisa el detalle"],
  approval: ["Esperando tu decisión", "Hay entregables o envíos por aprobar"],
};
const POINTS = 96;
const BASE = 56;
const circle = () => wavePath(0, 0);

function wavePath(amp: number, t: number): string {
  let d = "";
  for (let i = 0; i < POINTS; i++) {
    const a = (i / POINTS) * Math.PI * 2;
    const r = BASE + amp * 20 * (0.6 * Math.sin(a * 5 + t * 2.1) + 0.4 * Math.sin(a * 9 - t * 3.4));
    d += `${i ? "L" : "M"}${(200 + r * Math.cos(a)).toFixed(1)} ${(200 + r * Math.sin(a)).toFixed(1)}`;
  }
  return d + "Z";
}

function useClock(active: boolean): string {
  const fmt = () => new Date().toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
  const [now, setNow] = useState(fmt);
  useEffect(() => {
    if (!active) return;
    setNow(fmt());
    const t = setInterval(() => setNow((prev) => { const n = fmt(); return n === prev ? prev : n; }), 1000);
    return () => clearInterval(t);
  }, [active]);
  return now;
}

export type DialItem = { id: string; short: string; label: string };
type Props = { state: CoreState; detail?: string; progress?: number | null; count?: number; running?: number; levelRef?: MutableRefObject<number>; dial?: DialItem[] };

const polar = (r: number, deg: number) => { const a = ((deg - 90) * Math.PI) / 180; return [200 + r * Math.cos(a), 200 + r * Math.sin(a)]; };
/** Sector de corona entre dos radios: zona de pulsación de cada módulo. */
function sector(r1: number, r2: number, a0: number, a1: number): string {
  const [x0, y0] = polar(r2, a0), [x1, y1] = polar(r2, a1), [x2, y2] = polar(r1, a1), [x3, y3] = polar(r1, a0);
  return `M${x0.toFixed(1)} ${y0.toFixed(1)}A${r2} ${r2} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}A${r1} ${r1} 0 0 0 ${x3.toFixed(1)} ${y3.toFixed(1)}Z`;
}
/** Bisel: una marca cada 2°, como la escala de un instrumento. Un solo trazo para no crear 180 nodos. */
const BEZEL = Array.from({ length: 180 }, (_, i) => { const [x0, y0] = polar(196, i * 2), [x1, y1] = polar(i % 15 === 0 ? 189 : 193, i * 2); return `M${x0.toFixed(1)} ${y0.toFixed(1)}L${x1.toFixed(1)} ${y1.toFixed(1)}`; }).join("");

export function Core({ state, detail, progress = null, count = 0, running = 0, levelRef, dial = [] }: Props) {
  const [title, sub] = TEXT[state];
  const [boot, setBoot] = useState(true);
  const [aim, setAim] = useState<DialItem | null>(null);
  const wave = useRef<SVGPathElement>(null);
  const clock = useClock(state === "idle");
  useEffect(() => { const t = setTimeout(() => setBoot(false), 1300); return () => clearTimeout(t); }, []);

  // La onda solo se anima mientras hay algo real que mostrar; con movimiento reducido o pestaña oculta queda quieta.
  useEffect(() => {
    const el = wave.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !["listening", "speaking", "processing"].includes(state)) { el.setAttribute("d", circle()); return; }
    let raf = 0, amp = 0;
    const tick = (ms: number) => {
      if (!document.hidden) {
        const t = ms / 1000;
        const target = state === "listening" ? Math.max(0.1, Math.min(1, (levelRef?.current ?? 0) * 3.2))
          : state === "speaking" ? 0.42 + 0.22 * Math.sin(t * 6.3) : 0.14;
        amp += (target - amp) * 0.18;
        el.setAttribute("d", wavePath(amp, t));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [state, levelRef]);

  const pct = progress === null ? null : Math.round(progress * 100);
  const [readout, unit] =
    state === "idle" ? [clock, "En espera"]
    : state === "listening" ? ["···", "Te escucho"]
    : state === "speaking" ? ["···", "Respondiendo"]
    : state === "error" ? ["!", "Revisa el detalle"]
    : state === "approval" ? [String(count), count === 1 ? "decisión tuya" : "decisiones tuyas"]
    : pct !== null ? [`${pct}%`, running === 1 ? "1 trabajo" : `${running} trabajos`] : ["···", "Interpretando"];
  const step = dial.length ? 360 / dial.length : 0;

  return (
    <div className={`core core--${state}${boot ? " core--boot" : ""}`} style={{ ["--core-c" as string]: `var(--c)` }} role="img" aria-label={`Estado de Jarvis: ${title}. ${detail || sub}`}>
      <svg viewBox="0 0 400 400">
        <defs>
          <radialGradient id="core-glow"><stop offset="0" className="core__g0" /><stop offset="0.62" className="core__g1" /><stop offset="1" className="core__g2" /></radialGradient>
        </defs>
        <path className="core__bezel" d={BEZEL} />
        {dial.length > 0 && (
          <g className="core__dial">
            {dial.map((d, i) => {
              const mid = (i + 0.5) * step, [mx, my] = polar(181, mid);
              return (
                <a key={d.id} href={`#/${d.id}`} aria-label={d.label} onMouseEnter={() => setAim(d)} onMouseLeave={() => setAim(null)} onFocus={() => setAim(d)} onBlur={() => setAim(null)}>
                  <path className="core__hit" d={sector(170, 200, i * step, (i + 1) * step)} />
                  <path className="core__seg" d={sector(176, 186, i * step + 2.5, (i + 1) * step - 2.5)} />
                  <circle className="core__mark" cx={mx.toFixed(1)} cy={my.toFixed(1)} r="2.2" />
                </a>
              );
            })}
          </g>
        )}
        <circle className="core__hair" cx="200" cy="200" r="164" />
        <circle className="core__arc core__ring--a" cx="200" cy="200" r="164" pathLength="360" />
        <circle className="core__track" cx="200" cy="200" r="148" />
        <circle className="core__arc core__progress" cx="200" cy="200" r="148" pathLength="360" strokeDasharray={`${(progress ?? 0) * 360} 360`} />
        <circle className="core__arc core__ring--b" cx="200" cy="200" r="131" pathLength="360" />
        <circle className="core__arc core__scan" cx="200" cy="200" r="131" pathLength="360" />
        <circle className="core__arc core__ring--c" cx="200" cy="200" r="114" pathLength="360" />
        <circle className="core__disc" cx="200" cy="200" r="97" />
        <path ref={wave} className="core__wave" d={circle()} />
        <text className="core__readout" x="200" y="213">{readout}</text>
        <text className={`core__unit${aim ? " core__unit--aim" : ""}`} x="200" y="238">{aim ? aim.short : unit}</text>
      </svg>
      <div className="core__label">
        <span>{detail || sub}</span>
      </div>
    </div>
  );
}
