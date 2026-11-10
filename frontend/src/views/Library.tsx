import { useRef, useState } from "react";
import { api, url } from "../api";
import { useApp, useData } from "../store";
import { Md } from "../components/Md";
import { Btn, Empty, ErrorBox, Panel, Skeleton, Text } from "../components/ui";

type Col = { id: string; title: string; group: string; description: string; origin: string; docs: { path: string; title: string }[]; files: { path: string; name: string }[] };

export function Library() {
  const { route, nav, run } = useApp();
  const up = useRef<HTMLInputElement>(null);
  const upload = async (list: FileList | null) => {
    for (const f of Array.from(list || [])) { const form = new FormData(); form.set("file", f); const r: any = await run(api("/library/upload", { form }), `Añadido: ${f.name}`); if (r) { tree.reload(); open(r.path); } }
    if (up.current) up.current.value = "";
  };
  const tree = useData<Col[]>(() => api("/library"), []);
  const [q, setQ] = useState("");
  const hits = useData<any[]>(() => (q.trim().length > 1 ? api("/library/search", { query: { q } }) : Promise.resolve([])), [q]);
  const path = route.slice(1).map(decodeURIComponent).join("/");
  const doc = useData<{ title: string; markdown: string } | null>(() => (path ? api("/library/doc", { query: { path } }) : Promise.resolve(null)), [path]);
  const open = (p: string) => nav(`biblioteca/${p.split("/").map(encodeURIComponent).join("/")}`);
  const col = tree.data?.find((c) => path.startsWith(`${c.id}/`));
  const groups = Array.from(new Set((tree.data || []).map((c) => c.group)));
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">Biblioteca</h1>
        <p className="page__sub">Guías para conectar Jarvis, guías de mente, cuerpo, espíritu y economía, y tu propia biblioteca: habilidades, disparadores psicológicos, modelos de negocio y herramientas.</p></div>
        <div className="row"><input ref={up} type="file" accept=".md,.txt,.markdown" multiple className="sr" tabIndex={-1} onChange={(e) => upload(e.target.files)} />
          <Btn onClick={() => up.current?.click()} title="Markdown o texto. Podrás aplicarlo como skill al generar contenido.">Cargar skill o documento</Btn>
          <div style={{ width: 260 }}><Text value={q} onChange={setQ} placeholder="Buscar en la biblioteca…" /></div></div></div>
      {tree.error ? <ErrorBox message={tree.error} retry={tree.reload} /> : !tree.data ? <Skeleton /> : (
        <div className="grid libgrid">
          <Panel>
            {q.trim().length > 1 ? <>
              <p className="subhead" style={{ marginTop: 0 }}>{hits.data?.length || 0} resultado(s)</p>
              {(hits.data || []).map((h) => <button key={h.path} className="libitem" onClick={() => { open(h.path); setQ(""); }}><strong>{h.title}</strong><span>{h.collection} · {h.snippet}</span></button>)}
            </> : groups.map((g) => (
              <div key={g} className="libgroup">
                <p className="libgroup__title">{g}</p>
                {tree.data!.filter((c) => c.group === g).map((c) => (
                  <details key={c.id} open={col?.id === c.id || (!path && c.id === "conexiones")}>
                    <summary>{c.title} <span className="muted">{c.docs.length}</span></summary>
                    {c.docs.map((d) => <button key={d.path} className={`libitem${d.path === path ? " libitem--on" : ""}`} onClick={() => open(d.path)}>{d.title}</button>)}
                    {c.files.map((f) => <a key={f.path} className="libitem" href={url("/library/file", { path: f.path })}>Descargar: {f.name}</a>)}
                  </details>
                ))}
              </div>
            ))}
          </Panel>
          <Panel>
            {!path ? <Empty title="Elige una guía o un documento">Empieza por «Conectar Jarvis» si todavía no tienes IA configurada, o busca un tema arriba.</Empty>
              : doc.error ? <ErrorBox message={doc.error} retry={doc.reload} /> : !doc.data ? <Skeleton /> : <>
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                  <span className="small muted">{col?.title}{col?.origin ? ` · ${col.origin}` : ""}</span>
                  <span className="row">{path.startsWith("mis-skills/") && <Btn small kind="danger" onClick={async () => { await run(api("/library/doc", { method: "DELETE", query: { path } }), "Documento eliminado"); tree.reload(); nav("biblioteca"); }}>Eliminar</Btn>}
                    <Btn small kind="ghost" onClick={() => window.print()}>Imprimir</Btn></span>
                </div>
                <h1 className="page__title" style={{ marginBottom: 14 }}>{doc.data.title}</h1>
                <Md source={doc.data.markdown} />
              </>}
          </Panel>
        </div>
      )}
    </div>
  );
}
