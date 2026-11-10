// Recorrido real en navegador contra una instancia en marcha de Jarvis (sin proveedores de IA).
// Uso: node frontend/e2e/smoke.cjs [URL] [carpeta_capturas]   · Requiere Playwright y FFmpeg instalados.
const { chromium } = require("playwright");
const { execFileSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const BASE = process.argv[2] || "http://127.0.0.1:8765";
const OUT = process.argv[3] || path.join(__dirname, "capturas");
fs.mkdirSync(OUT, { recursive: true });
const problems = [];
const step = (t) => console.log("·", t);

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "es-ES" });
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error") problems.push(`consola: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`excepción: ${e.message}`));
  page.on("response", (r) => { if (r.status() >= 500) problems.push(`HTTP ${r.status()} ${r.url()}`); });
  const shot = (name) => page.screenshot({ path: path.join(OUT, `${name}.png`) });
  const go = async (route) => { await page.goto(`${BASE}/#/${route}`); await page.waitForSelector(".page__title, .command", { timeout: 10000 }); };

  await page.goto(BASE);
  await page.waitForSelector(".wizard, .command");
  if (await page.locator(".wizard").count()) {
    step("primer inicio");
    await page.getByLabel(/Cómo te llamas/).fill("Ana");
    await page.getByLabel("Servicios B2B", { exact: true }).check();
    await shot("01-primer-inicio");
    await page.getByRole("button", { name: "Continuar" }).click();
    await page.getByLabel("Nombre", { exact: true }).fill("Nova");
    await page.getByRole("button", { name: "Guardar y continuar" }).click();
    await page.getByRole("button", { name: "Omitir por ahora" }).click();
    await page.getByRole("button", { name: "Continuar" }).click();
    await page.getByRole("button", { name: "Ejecutar recorrido" }).click();
    await page.getByText("Recorrido sin IA completado").waitFor();
    await shot("02-recorrido-sin-ia");
    await page.getByRole("button", { name: "Entrar en Jarvis" }).click();
  }
  await page.waitForSelector(".command");

  step("comando: órdenes por texto");
  const order = page.getByLabel("Orden para Jarvis");
  await order.fill("tarea: llamar al gestor");
  await order.press("Enter");
  await page.getByText(/Tarea creada: llamar al gestor/).waitFor();
  await order.fill("Busca oportunidades en rascadores para gatos");
  await order.press("Enter");
  await page.getByText(/Trabajo creado: Oportunidades/).waitFor();
  await page.locator(".badge", { hasText: "Esperando configuración" }).first().waitFor({ timeout: 20000 });
  if ((await page.locator(".core--approval, .core--idle, .core--processing").count()) !== 1) problems.push("el núcleo no muestra un estado válido");
  await order.fill("Resume lo pendiente");
  await order.press("Enter");
  await page.getByText(/Tareas abiertas: 2/).waitFor();
  await shot("03-comando");
  const mic = page.locator(".mic");
  if ((await mic.getAttribute("aria-pressed")) !== "false") problems.push("el micrófono aparece abierto sin pulsarlo");

  step("todas las pantallas cargan y muestran estados vacíos útiles");
  for (const r of ["oportunidades", "leads", "contenido", "video", "shopify", "clipping", "revision", "proyectos", "operaciones", "personal", "conexiones", "sistema"]) {
    await go(r);
    await page.waitForTimeout(350);
    if (await page.locator(".errorbox").count()) problems.push(`${r}: muestra un error`);
    await shot(`10-${r}`);
  }

  step("personal: crear, editar, archivar");
  await page.locator(".top select").selectOption({ label: "Personal · Personal" });
  await go("personal");
  await page.getByPlaceholder("Añadir tarea…").fill("Leer 20 páginas");
  await page.getByRole("button", { name: "Añadir", exact: true }).click();
  await page.getByRole("button", { name: "Leer 20 páginas" }).click();
  await page.getByLabel("Título *").fill("Leer 30 páginas");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("button", { name: "Leer 30 páginas" }).waitFor();
  await page.getByRole("tab", { name: "Hábitos" }).click();
  await page.getByRole("button", { name: "Nuevo" }).click();
  await page.getByLabel("Título *").fill("Caminar");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByLabel(/Caminar el /).last().click();
  await page.waitForFunction(() => { const b = [...document.querySelectorAll("input[aria-label^='Caminar el ']")].pop(); return b && b.checked; });
  await shot("20-personal-habitos");
  await page.locator(".top select").selectOption({ index: 1 });

  step("video: importar, segmentar, previsualizar y exportar con FFmpeg");
  const clip = path.join(OUT, "prueba.mp4");
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", clip]);
  await go("video");
  await page.getByPlaceholder("Nombre del proyecto").fill("Demo clip");
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await page.locator("input[type=file]").first().setInputFiles(clip);
  await page.locator("video.player").waitFor();
  await page.getByText(/Duración 6/).waitFor();
  await page.evaluate(() => { document.querySelector("video.player").currentTime = 1; });
  await page.getByRole("button", { name: /Marcar inicio/ }).click();
  await page.evaluate(() => { document.querySelector("video.player").currentTime = 3.5; });
  await page.getByRole("button", { name: /Marcar fin/ }).click();
  await page.getByRole("button", { name: "Añadir segmento" }).click();
  await page.getByLabel("1:1").check();
  await page.getByRole("button", { name: "Previsualizar encuadre aquí" }).click();
  await page.locator("img.framepreview").waitFor();
  await page.waitForFunction(() => { const i = document.querySelector("img.framepreview"); return i && i.complete && i.naturalWidth > 0; });
  await shot("30-video-editor");
  await page.getByRole("button", { name: "Exportar segmentos" }).click();
  await page.getByRole("button", { name: "Abrir entregable" }).first().waitFor({ timeout: 90000 });
  await page.getByRole("button", { name: "Abrir entregable" }).first().click();
  await page.getByText("Archivos exportados").waitFor();
  if ((await page.locator("video.player").count()) < 2) problems.push("la exportación no muestra los dos formatos");
  await shot("31-video-entregable");

  step("revisión: editar crea versión, aprobar, exportar");
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page.getByLabel("Resumen").fill("Resumen editado a mano");
  await page.getByRole("button", { name: /Guardar como v2/ }).click();
  await page.getByText("v2 ·").first().waitFor();
  await page.getByRole("button", { name: "Aprobar v2" }).click();
  await page.getByRole("button", { name: "Aprobar", exact: true }).click();
  await page.locator(".badge", { hasText: "Vigente" }).waitFor();
  await page.getByRole("button", { name: "Exportar Markdown" }).click();
  await page.getByText("Exportación creada").waitFor();
  await shot("32-revision-exportacion");
  await page.getByRole("button", { name: "Cerrar" }).click();

  step("shopify: producto → paquete → vista previa");
  await go("shopify");
  await page.getByRole("button", { name: "Nuevo" }).click();
  await page.getByLabel("Título *").fill("Rascador Roble");
  await page.getByLabel("Especificaciones (una por línea)").fill("Poste de sisal de 12 mm\nBase de roble de 40 cm");
  await page.getByLabel("Precio", { exact: true }).fill("59");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("button", { name: "Generar paquete" }).click();
  await page.getByRole("button", { name: "Generar", exact: true }).click();
  await page.getByRole("button", { name: "Abrir entregable" }).first().waitFor({ timeout: 30000 });
  await page.getByRole("tab", { name: "Paquetes generados" }).click();
  await page.getByRole("button", { name: /shopify-rascador-roble/ }).click();
  await page.frameLocator("iframe.iframe").getByText("Rascador Roble").first().waitFor();
  await shot("40-shopify-vista-previa");

  step("conexiones: error comprensible con un proveedor local apagado");
  await go("conexiones");
  await page.getByRole("button", { name: "Nueva conexión" }).click();
  await page.getByRole("textbox", { name: "Nombre", exact: true }).fill("Ollama local");
  await page.getByRole("textbox", { name: "Modelo", exact: true }).fill("modelo-inexistente");
  await page.getByRole("button", { name: "Guardar y probar conexión" }).click();
  await page.getByText("La prueba falló.").waitFor({ timeout: 20000 });
  await shot("50-conexion-error");
  await page.getByRole("button", { name: "Cerrar" }).first().click();
  await page.locator(".badge", { hasText: "Error" }).first().waitFor();

  step("sistema: trabajo en espera y diagnóstico");
  await go("sistema");
  await page.locator(".badge", { hasText: "Esperando configuración" }).first().waitFor();
  await shot("60-trabajos");
  await page.getByRole("tab", { name: "Diagnóstico" }).click();
  await page.getByText("solo este equipo").waitFor();
  await page.getByRole("tab", { name: "Respaldo y recuperación" }).click();
  await page.getByRole("button", { name: "Crear respaldo ahora" }).click();
  await page.getByText(/jarvis-backup-manual/).waitFor({ timeout: 30000 });
  await shot("61-respaldo");

  step("teclado y movimiento reducido");
  await go("comando");
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => document.activeElement && document.activeElement.tagName);
  if (!["A", "BUTTON", "SELECT", "TEXTAREA", "INPUT"].includes(focused)) problems.push(`el primer tabulador no llega a un control (${focused})`);
  await page.emulateMedia({ reducedMotion: "reduce" });
  const anim = await page.evaluate(() => getComputedStyle(document.querySelector(".core__ring--b")).animationName);
  if (anim !== "none") problems.push(`con movimiento reducido el núcleo sigue animado (${anim})`);
  await page.emulateMedia({ reducedMotion: "no-preference" });

  step("móvil");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const r of ["comando", "oportunidades", "revision", "clipping", "conexiones"]) {
    await go(r);
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 2) problems.push(`${r}: desbordamiento horizontal de ${overflow}px en móvil`);
    await shot(`70-movil-${r}`);
  }

  await browser.close();
  if (problems.length) { console.log("PROBLEMAS:\n" + problems.map((p) => " - " + p).join("\n")); process.exit(1); }
  console.log("Recorrido completado sin problemas. Capturas en", OUT);
})().catch((e) => { console.error("FALLO:", e.message.split("\n").slice(0, 6).join("\n")); if (problems.length) console.log(problems.join("\n")); process.exit(2); });
