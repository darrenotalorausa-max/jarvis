import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type Job, type KindSpec, type Space } from "./api";

export type Boot = {
  version: string; settings: Record<string, any>; spaces: Space[]; space_kinds: Record<string, string>; ai_policies: Record<string, string>;
  schema: Record<string, KindSpec>; providers: Record<string, any>; capabilities: Record<string, string>; deliverable_kinds: Record<string, string>;
  deliverable_statuses: string[]; job_types: Record<string, string>; job_statuses: Record<string, string>; secrets_backend: { kind: string; label: string; protected: boolean };
  ffmpeg: Record<string, { disponible: boolean; version: string | null }>; video: { presets: string[]; framings: Record<string, string>; modes: string[] };
  worker_alive: boolean; local_transcription: boolean;
};
type Toast = { id: number; kind: "ok" | "error" | "info"; text: string };
type Ctx = {
  boot: Boot; reload: () => Promise<void>; space: Space; setSpace: (id: string) => void; mode: "command" | "workspace"; setMode: (m: "command" | "workspace") => void;
  route: string[]; nav: (path: string) => void; jobs: Job[]; doneTick: number; refreshJobs: () => void; notify: (text: string, kind?: Toast["kind"]) => void;
  run: <T>(p: Promise<T>, okText?: string) => Promise<T | undefined>;
};
const C = createContext<Ctx | null>(null);
export const useApp = () => useContext(C)!;

const TERMINAL = ["completed", "failed", "cancelled"];
const pref = (k: string, d: string) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
const setPref = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
const parseRoute = () => (location.hash.replace(/^#\/?/, "") || "").split("/").filter(Boolean);

export function AppProvider({ children, fallback, onboarding }: { children: ReactNode; fallback: (error: string | null, retry: () => void) => ReactNode; onboarding: (boot: Boot, reload: () => Promise<void>) => ReactNode }) {
  const [boot, setBoot] = useState<Boot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [spaceId, setSpaceId] = useState(pref("jarvis.space", ""));
  const [mode, setModeState] = useState<"command" | "workspace">(pref("jarvis.mode", "command") as any);
  const [route, setRoute] = useState<string[]>(parseRoute());
  const [jobs, setJobs] = useState<Job[]>([]);
  const [doneTick, setDoneTick] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const reload = useCallback(async () => {
    try {
      setBoot(await api<Boot>("/bootstrap"));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  useEffect(() => {
    const on = () => setRoute(parseRoute());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  // Las animaciones se detienen cuando la pestaña no es visible.
  useEffect(() => {
    const on = () => document.documentElement.classList.toggle("paused", document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);

  const notify = useCallback((text: string, kind: Toast["kind"] = "info") => {
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 9000 : 4500);
  }, []);
  const run = useCallback(async <T,>(p: Promise<T>, okText?: string) => {
    try {
      const r = await p;
      if (okText) notify(okText, "ok");
      return r;
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Error inesperado en la interfaz.", "error");
      return undefined;
    }
  }, [notify]);

  const spaces = (boot?.spaces || []).filter((s) => !s.archived);
  const space = spaces.find((s) => s.id === spaceId) || spaces.find((s) => s.kind !== "personal") || spaces[0];
  const refreshJobs = useCallback(() => {
    if (space) api<Job[]>("/jobs", { query: { space: space.id, limit: 60 } }).then(setJobs).catch(() => undefined);
  }, [space?.id]);
  useEffect(() => { refreshJobs(); }, [refreshJobs]);
  // Progreso en vivo por SSE: el servidor empuja cambios de trabajos; no hay sondeo de modelos.
  useEffect(() => {
    if (!space) return;
    const es = new EventSource("/api/events");
    es.addEventListener("job", (ev) => {
      const job: Job = JSON.parse((ev as MessageEvent).data);
      if (job.space_id !== space.id) return;
      setJobs((list) => {
        const prev = list.find((j) => j.id === job.id);
        if (TERMINAL.includes(job.status) && (!prev || !TERMINAL.includes(prev.status))) setDoneTick((n) => n + 1);
        return prev ? list.map((j) => (j.id === job.id ? job : j)) : [job, ...list];
      });
    });
    return () => es.close();
  }, [space?.id]);

  const value = useMemo<Ctx | null>(() => boot && space ? {
    boot, reload, space, setSpace: (id) => { setSpaceId(id); setPref("jarvis.space", id); },
    mode, setMode: (m) => { setModeState(m); setPref("jarvis.mode", m); },
    route, nav: (p) => { location.hash = `#/${p}`; }, jobs, doneTick, refreshJobs, notify, run,
  } : null, [boot, space, mode, route, jobs, doneTick, reload, refreshJobs, notify, run]);

  if (!boot) return <>{fallback(error, reload)}</>;
  if (!boot.settings.onboarded || !space || !value) return <>{onboarding(boot, reload)}<Toasts items={toasts} /></>;
  return <C.Provider value={value}>{children}<Toasts items={toasts} /></C.Provider>;
}

function Toasts({ items }: { items: Toast[] }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {items.map((t) => <div key={t.id} className={`toast toast--${t.kind}`}>{t.text}</div>)}
    </div>
  );
}

/** Carga datos y los recarga cuando cambian las dependencias o termina un trabajo. */
export function useData<T>(loader: () => Promise<T>, deps: unknown[]): { data: T | undefined; error: string | null; loading: boolean; reload: () => void } {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    loader().then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((n) => n + 1) };
}
