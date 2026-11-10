// Núcleo visual de Jarvis. Su estado refleja siempre un estado real del sistema; nunca se anima "por decoración".
export type CoreState = "idle" | "listening" | "processing" | "speaking" | "error" | "approval";

const TEXT: Record<CoreState, [string, string]> = {
  idle: ["En espera", "Sin actividad en curso"],
  listening: ["Escuchando", "Micrófono abierto: suelta para terminar"],
  processing: ["Procesando", "Hay trabajo en ejecución"],
  speaking: ["Hablando", "Respuesta por voz en curso"],
  error: ["Atención", "Algo falló: revisa el detalle"],
  approval: ["Esperando tu decisión", "Hay entregables o envíos por aprobar"],
};

export function Core({ state, detail }: { state: CoreState; detail?: string }) {
  const [title, sub] = TEXT[state];
  const ticks = Array.from({ length: 60 }, (_, i) => i);
  return (
    <div className={`core core--${state}`} role="img" aria-label={`Estado de Jarvis: ${title}. ${detail || sub}`}>
      <svg viewBox="0 0 300 300" aria-hidden="true">
        <g className="core__ticks">
          {ticks.map((i) => (
            <line key={i} x1="150" y1="8" x2="150" y2={i % 5 === 0 ? 22 : 15} transform={`rotate(${i * 6} 150 150)`} />
          ))}
        </g>
        <circle className="core__ring core__ring--a" cx="150" cy="150" r="118" pathLength="100" />
        <circle className="core__ring core__ring--b" cx="150" cy="150" r="98" pathLength="100" />
        <circle className="core__ring core__ring--c" cx="150" cy="150" r="80" pathLength="100" />
        <circle className="core__halo" cx="150" cy="150" r="62" />
        <circle className="core__heart" cx="150" cy="150" r="34" />
        <g className="core__bars">
          {[-18, -9, 0, 9, 18].map((x, i) => <rect key={i} x={150 + x - 2} y="138" width="4" height="24" rx="2" style={{ animationDelay: `${i * 0.12}s` }} />)}
        </g>
      </svg>
      <div className="core__label">
        <strong>{title}</strong>
        <span>{detail || sub}</span>
      </div>
    </div>
  );
}
