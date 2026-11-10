import type { ReactNode } from "react";

// Lector de Markdown mínimo y seguro (sin HTML): títulos, listas, tablas, citas, código, negritas y enlaces.
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s)]+)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
    if (/^https?:\/\//.test(part)) return <a key={i} href={part} target="_blank" rel="noreferrer noopener">{part.replace(/^https?:\/\//, "")}</a>;
    return part;
  });
}
const cells = (line: string) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

export function Md({ source }: { source: string }) {
  const lines = source.replace(/\r/g, "").split("\n");
  const out: ReactNode[] = [];
  let i = 0, k = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    if (l.startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push(<pre key={k++} className="diff">{buf.join("\n")}</pre>);
    } else if (/^#{1,4} /.test(l)) {
      const level = l.match(/^#+/)![0].length;
      const text = l.replace(/^#+ /, "");
      out.push(level <= 2 ? <h2 key={k++}>{inline(text)}</h2> : level === 3 ? <h3 key={k++}>{inline(text)}</h3> : <h4 key={k++}>{inline(text)}</h4>);
      i++;
    } else if (/^-{3,}$/.test(l.trim())) { out.push(<hr key={k++} />); i++; }
    else if (l.trim().startsWith("|") && lines[i + 1]?.includes("---")) {
      const head = cells(l);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      out.push(<div key={k++} className="tablewrap"><table><thead><tr>{head.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr></thead>
        <tbody>{rows.map((r, j) => <tr key={j}>{head.map((_, c) => <td key={c} className="wrap">{inline(r[c] || "")}</td>)}</tr>)}</tbody></table></div>);
    } else if (/^\s*[-*] /.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*] /.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*] /, ""));
      out.push(<ul key={k++} className="list">{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>);
    } else if (/^\s*\d+\. /.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\. /.test(lines[i])) items.push(lines[i++].replace(/^\s*\d+\. /, ""));
      out.push(<ol key={k++} className="list">{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ol>);
    } else if (l.startsWith(">")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) buf.push(lines[i++].replace(/^>\s?/, ""));
      out.push(<blockquote key={k++}>{inline(buf.join(" "))}</blockquote>);
    } else {
      const buf: string[] = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,4} |```|>|\s*[-*] |\s*\d+\. |\|)/.test(lines[i]) && !/^-{3,}$/.test(lines[i].trim())) buf.push(lines[i++]);
      out.push(<p key={k++}>{buf.flatMap((t, j) => [...inline(t.replace(/\s+$/, "")), j < buf.length - 1 ? <br key={`b${j}`} /> : null])}</p>);
    }
  }
  return <article className="md">{out}</article>;
}
