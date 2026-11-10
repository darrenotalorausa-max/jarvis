import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { label } from "../api";

export function Panel({ title, actions, children, className = "", note }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; note?: ReactNode }) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="panel__head">
          {title && <h2 className="panel__title">{title}</h2>}
          {actions && <div className="row">{actions}</div>}
        </header>
      )}
      {children}
      {note && <p className="note">{note}</p>}
    </section>
  );
}

export function Btn({ children, onClick, kind = "default", disabled, type = "button", title, small, busy }: { children: ReactNode; onClick?: () => void; kind?: "default" | "primary" | "danger" | "ghost" | "amber"; disabled?: boolean; type?: "button" | "submit"; title?: string; small?: boolean; busy?: boolean }) {
  return (
    <button type={type} className={`btn btn--${kind}${small ? " btn--sm" : ""}`} onClick={onClick} disabled={disabled || busy} title={title} aria-busy={busy || undefined}>
      {busy ? "Procesando…" : children}
    </button>
  );
}

const TONES: Record<string, string> = {
  ok: "ok", operativa: "ok", completed: "ok", aprobado: "ok", hecha: "ok", hecho: "ok", cobrado: "ok", activa: "ok", activo: "ok", exportado: "ok", investigado: "ok",
  warn: "warn", sin_probar: "warn", waiting_config: "warn", waiting_quota: "warn", waiting_approval: "warn", en_revision: "warn", cambios_solicitados: "warn", condiciones_pendientes: "warn", cuota_agotada: "warn", pendiente: "warn", propuesta_lista: "warn",
  fail: "bad", failed: "bad", rechazado: "bad", error: "bad", credencial_invalida: "bad", sin_permiso: "bad", no_compatible: "bad",
  running: "live", pending: "info", borrador: "info", no_configurada: "mute", deshabilitada: "mute", cancelled: "mute",
};
export function Badge({ value, text }: { value: string; text?: string }) {
  return <span className={`badge badge--${TONES[value] || "info"}`}>{text || label(value)}</span>;
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty__title">{title}</p>
      {children && <p className="empty__text">{children}</p>}
      {action}
    </div>
  );
}

/** Estado de carga con la forma aproximada de lo que llega. */
export function Skeleton() {
  return <div className="skeleton" role="status" aria-label="Cargando"><i /><i /><i /></div>;
}

export function ErrorBox({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="errorbox" role="alert">
      <span>{message}</span>
      {retry && <Btn small onClick={retry}>Reintentar</Btn>}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: [T, string][]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(([id, text]) => (
        <button key={id} role="tab" aria-selected={value === id} className={`tab${value === id ? " tab--on" : ""}`} onClick={() => onChange(id)}>{text}</button>
      ))}
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("input,select,textarea,button")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="modal" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`modal__box${wide ? " modal__box--wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={id} ref={ref}>
        <header className="panel__head">
          <h2 className="panel__title" id={id}>{title}</h2>
          <Btn kind="ghost" small onClick={onClose}>Cerrar</Btn>
        </header>
        {children}
      </div>
    </div>
  );
}

export function FieldRow({ label: text, children, hint, wide, group }: { label: string; children: ReactNode; hint?: ReactNode; wide?: boolean; group?: boolean }) {
  // group: el campo contiene varios controles (casillas, botones); se expone como grupo en vez de anidar etiquetas.
  const cls = `field${wide ? " field--wide" : ""}`;
  const body = <><span className="field__label">{text}</span>{children}{hint && <span className="field__hint">{hint}</span>}</>;
  return group ? <div className={cls} role="group" aria-label={text}>{body}</div> : <label className={cls}>{body}</label>;
}

export function Text({ value, onChange, placeholder, type = "text", area, rows = 3 }: { value: any; onChange: (v: string) => void; placeholder?: string; type?: string; area?: boolean; rows?: number }) {
  return area
    ? <textarea className="input" rows={rows} value={value ?? ""} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    : <input className="input" type={type} value={value ?? ""} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} autoComplete="off" />;
}

export function Select({ value, onChange, options, empty }: { value: any; onChange: (v: string) => void; options: [string, string][]; empty?: string }) {
  return (
    <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
      {empty !== undefined && <option value="">{empty}</option>}
      {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
    </select>
  );
}

export function Check({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <label className="check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}

export function Stat({ label: text, value, tone, hint }: { label: string; value: ReactNode; tone?: "amber" | "ok" | "bad"; hint?: string }) {
  return (
    <div className={`stat${tone ? ` stat--${tone}` : ""}`}>
      <span className="stat__label">{text}</span>
      <span className="stat__value">{value}</span>
      {hint && <span className="stat__hint">{hint}</span>}
    </div>
  );
}

export function Progress({ value, live }: { value: number; live?: boolean }) {
  return (
    <div className={`progress${live ? " progress--live" : ""}`} role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ transform: `scaleX(${Math.max(0, Math.min(1, value)).toFixed(3)})` }} />
    </div>
  );
}

/** Texto con formato mínimo (negritas y saltos de línea) sin inyectar HTML. */
export function Rich({ text }: { text: string }) {
  return (
    <div className="rich">
      {text.split("\n").map((line, i) => (
        <p key={i}>{line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => (part.startsWith("**") && part.endsWith("**") ? <strong key={j}>{part.slice(2, -2)}</strong> : part))}</p>
      ))}
    </div>
  );
}

export function useConfirm(): [(text: string, onYes: () => void, danger?: boolean) => void, ReactNode] {
  const [state, setState] = useState<{ text: string; onYes: () => void; danger?: boolean } | null>(null);
  const node = state ? (
    <Modal title="Confirmar" onClose={() => setState(null)}>
      <p>{state.text}</p>
      <div className="row row--end">
        <Btn onClick={() => setState(null)}>Cancelar</Btn>
        <Btn kind={state.danger ? "danger" : "primary"} onClick={() => { const fn = state.onYes; setState(null); fn(); }}>Confirmar</Btn>
      </div>
    </Modal>
  ) : null;
  return [(text, onYes, danger) => setState({ text, onYes, danger }), node];
}
