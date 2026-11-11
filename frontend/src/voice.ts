// Manos libres: reconocer la palabra de activación en lo que se oye y separar la orden.
// Los reconocedores escriben «Jarvis» de muchas formas; se aceptan las más habituales en español.
const WAKE = /\b(?:oye\s+|hey\s+|ok\s+|hola\s+)?(jarvis|yarvis|jarbis|yarbis|harvis|jarvi|yarvi|charvis|llarvis|jervis|garvis)\b[\s,.:;!¡¿?]*/i;

export function extractCommand(transcript: string): { woke: boolean; command: string } {
  const text = (transcript || "").trim();
  const m = WAKE.exec(text);
  if (!m) return { woke: false, command: "" };
  return { woke: true, command: text.slice(m.index + m[0].length).trim().replace(/[.!?]+$/, "").trim() };
}
