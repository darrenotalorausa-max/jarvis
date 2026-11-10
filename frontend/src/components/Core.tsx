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
const BASE = 58;
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

type Props = { state: CoreState; detail?: string; progress?: number | null; count?: number; running?: number; levelRef?: MutableRefObject<number> };

export function Core({ state, detail, progress = null, count = 0, running = 0, levelRef }: Props) {
  const [title, sub] = TEXT[state];
  const [boot, setBoot] = useState(true);
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
    state === "idle" ? [clock, "en espera"]
    : state === "listening" ? ["MIC", "abierto"]
    : state === "speaking" ? ["VOZ", "respuesta"]
    : state === "error" ? ["ERR", "revisar"]
    : state === "approval" ? [String(count), count === 1 ? "decisión" : "decisiones"]
    : pct !== null ? [`${pct}%`, running === 1 ? "1 trabajo" : `${running} trabajos`] : ["···", "interpretando"];

  return (
    <div className={`core core--${state}${boot ? " core--boot" : ""}`} style={{ ["--core-c" as string]: `var(--c)` }} role="img" aria-label={`Estado de Jarvis: ${title}. ${detail || sub}`}>
      <svg viewBox="0 0 400 400" aria-hidden="true">
        <g className="core__ticks">
          {Array.from({ length: 72 }, (_, i) => <line key={i} className={i % 6 === 0 ? "major" : undefined} x1="200" y1="6" x2="200" y2={i % 6 === 0 ? 18 : 12} transform={`rotate(${i * 5} 200 200)`} />)}
        </g>
        <circle className="core__arc core__ring--a" cx="200" cy="200" r="172" pathLength="360" />
        <circle className="core__track" cx="200" cy="200" r="154" />
        <circle className="core__arc core__progress" cx="200" cy="200" r="154" pathLength="360" strokeDasharray={`${(progress ?? 0) * 360} 360`} />
        <circle className="core__arc core__ring--b" cx="200" cy="200" r="138" pathLength="360" />
        <circle className="core__arc core__scan" cx="200" cy="200" r="138" pathLength="360" />
        <circle className="core__arc core__ring--c" cx="200" cy="200" r="120" pathLength="360" />
        <circle className="core__disc" cx="200" cy="200" r="94" />
        <path ref={wave} className="core__wave" d={circle()} />
        <text className="core__readout" x="200" y="208">{readout}</text>
        <text className="core__unit" x="200" y="230">{unit}</text>
      </svg>
      <div className="core__label">
        <strong>{title}</strong>
        <span>{detail || sub}</span>
      </div>
    </div>
  );
}
