// Cliente de la API local. Ninguna credencial se guarda ni se lee en el navegador.
export class ApiError extends Error {
  status: number;
  kind?: string;
  constructor(message: string, status: number, kind?: string) {
    super(message);
    this.status = status;
    this.kind = kind;
  }
}

type Opts = { method?: string; body?: unknown; form?: FormData; query?: Record<string, unknown>; raw?: boolean };

export function url(path: string, query?: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(query || {})) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return `/api${path}${s ? `?${s}` : ""}`;
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const init: RequestInit = { method: opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET") };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers = { "Content-Type": "application/json" };
  }
  let res: Response;
  try {
    res = await fetch(url(path, opts.query), init);
  } catch {
    throw new ApiError("No se pudo conectar con Jarvis. Comprueba que la ventana del lanzador sigue abierta.", 0);
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    let kind: string | undefined;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      kind = j.kind;
    } catch { /* cuerpo no JSON */ }
    throw new ApiError(detail, res.status, kind);
  }
  if (opts.raw) return res as unknown as T;
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export type Field = { name: string; label: string; type: string; options?: string[]; required?: boolean; ref?: string };
export type KindSpec = { label: string; plural: string; module: string; statuses: string[]; fields: Field[]; private?: boolean; free_data?: boolean };
export type Rec = { id: string; space_id: string; kind: string; title: string; status: string; project_id: string | null; brand_id: string | null; data: Record<string, any>; archived: boolean; created_at: string; updated_at: string };
export type Space = { id: string; name: string; kind: string; ai_policy: string; archived: number };
export type Job = { id: string; space_id: string; type: string; title: string; status: string; status_label: string; stage: string | null; progress: number; message: string | null; error: string | null; result: any; params: any; usage: any; created_at: string; finished_at: string | null; resume_at: string | null; cancel_requested: boolean; events?: any[] };
export type Deliverable = { id: string; kind: string; kind_label: string; title: string; status: string; current_version: number; updated_at: string; project_id: string | null; brand_id: string | null; ref_id: string | null; job_id: string | null };
export type FileRow = { id: string; name: string; mime: string; size: number; origin: string; meta: Record<string, any>; created_at: string };
export type Section = { key: string; title: string; type: "text" | "list" | "table" | "facts" | "scores" | "files"; body: string; items: any[]; columns: string[]; rows: any[][]; note: string };

export const label = (s: string | null | undefined) => (s || "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
export const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" }) : "—");
export const fmtBytes = (n: number) => (n > 1e9 ? `${(n / 1e9).toFixed(2)} GB` : n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : n > 1e3 ? `${(n / 1e3).toFixed(0)} KB` : `${n} B`);
export const fmtNum = (n: number | null | undefined, d = 2) => (n === null || n === undefined ? "—" : n.toLocaleString("es", { maximumFractionDigits: d }));
export function ageDays(iso?: string | null): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : Math.floor((Date.now() - t) / 86400000);
}
export function freshness(iso?: string | null): string {
  const d = ageDays(iso);
  return d === null ? "fecha desconocida" : d <= 0 ? "hoy" : d === 1 ? "hace 1 día" : `hace ${d} días`;
}
