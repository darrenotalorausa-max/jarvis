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
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("400 (Bad Request)")) problems.push(`consola: ${m.text()}`); }); // el 400 es la validación esperada de la misión
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
  for (const r of ["negocios", "biblioteca", "oportunidades", "leads", "contenido", "video", "shopify", "clipping", "revision", "proyectos", "operaciones", "personal", "conexiones", "sistema"]) {
    await go(r);
    await page.waitForTimeout(350);
    if (await page.locator(".errorbox").count()) problems.push(`${r}: muestra un error`);
    await shot(`10-${r}`);
  }

  step("centro de negocios: misión con evidencia obligatoria y pausa de agentes");
  await go("negocios");
  await page.getByRole("tab", { name: "Misiones" }).click();
  await page.getByRole("button", { name: "Nuevo" }).click();
  await page.getByLabel("Título *").fill("Publicar política de devoluciones");
  await page.getByLabel("Estado").selectOption("completada_verificada");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByText(/hacen falta su criterio de cierre y una evidencia/).waitFor();
  await page.getByLabel("Estado").selectOption("pendiente");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("button", { name: "Publicar política de devoluciones" }).waitFor();
  await page.getByRole("tab", { name: "Resumen" }).click();
  await page.getByText("0 de 1 misiones verificadas").waitFor();
  await page.getByRole("button", { name: "Pausar todos los agentes" }).click();
  await page.getByText("Agentes en pausa.", { exact: false }).first().waitFor();
  await shot("05-centro-negocios");
  await page.getByRole("button", { name: "Reanudar agentes" }).click();
  await page.getByRole("button", { name: "Pausar todos los agentes" }).waitFor();

  step("biblioteca, paleta Ctrl+K y dial del núcleo");
  await go("biblioteca");
  await page.getByRole("button", { name: "IA gratis en la nube con Gemini y Gemma" }).click();
  await page.getByText("aistudio.google.com").first().waitFor();
  await shot("06-biblioteca-guia");
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder("Escribe un módulo o un tema de la biblioteca").fill("anclaje");
  await page.getByRole("button", { name: /Anclaje/ }).first().click();
  await page.getByRole("heading", { name: /Anclaje/ }).first().waitFor();
  await go("comando");
  await page.locator(".core__dial a[aria-label='Clipping']").click();
  await page.getByRole("heading", { name: "Clipping" }).waitFor();

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
  await page.getByRole("tab", { name: "Mente" }).click();
  await page.getByRole("tab", { name: "Aprendizaje" }).click();
  await page.getByRole("button", { name: "Nuevo" }).click();
  await page.getByLabel("Título *").fill("¿Qué es el recuerdo activo?");
  await page.getByLabel("Respuesta *").fill("Recordar sin mirar el material");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("button", { name: "Mostrar respuesta" }).click();
  await page.getByRole("button", { name: "Bien", exact: true }).click();
  await page.getByText("Nada que repasar hoy").waitFor();
  await page.getByRole("tab", { name: "Tablero" }).click();
  await page.getByText("Patrimonio neto").waitFor();
  await shot("21-personal-tablero");
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

  step("apps: conectar una API, leer al momento y escritura solo con aprobación");
  await go("apps");
  await page.getByRole("tab", { name: "Catálogo" }).click();
  if ((await page.locator(".panel").count()) < 14) problems.push("el catálogo de apps muestra menos plantillas de las esperadas");
  await shot("62-apps-catalogo");
  await page.locator(".panel", { hasText: "API personalizada" }).getByRole("button", { name: "Conectar" }).click();
  await page.getByLabel("Nombre", { exact: true }).fill("Mi API");
  await page.getByLabel("URL base de la API").fill(`${BASE}/api`);
  await page.getByLabel("Autenticación").selectOption("none");
  await page.getByLabel(/He revisado las condiciones/).check();
  await page.getByRole("button", { name: /acciones \(avanzado\)/ }).click();
  await page.getByLabel("Acciones (JSON)").fill(JSON.stringify([
    { id: "guias", label: "Leer guías", method: "GET", path: "/library" },
    { id: "crear", label: "Crear algo", method: "POST", path: "/no-existe", body: { nombre: "{nombre}" } }]));
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("button", { name: "Ejecutar", exact: true }).click();
  await page.getByText(/HTTP 200 · GET/).waitFor();
  await page.locator(".panel .form select").first().selectOption("crear");
  await page.getByLabel("nombre", { exact: true }).fill("prueba");
  await page.getByRole("button", { name: /Solicitar/ }).click();
  await page.getByText(/Pendientes de aprobación \(1\)/).waitFor();
  await page.getByText(new RegExp("POST .*/api/no-existe")).waitFor();
  await shot("63-apps-aprobacion");
  await page.getByRole("button", { name: "Rechazar" }).click();
  await page.getByRole("heading", { name: /Pendientes de aprobación/ }).waitFor({ state: "detached" });
  await page.getByRole("tab", { name: /Conectar otros programas/ }).click();
  await page.getByRole("button", { name: "Generar token de API" }).click();
  await page.getByText("Cópialo ahora").waitFor();

  step("monitores: una regla real genera una alerta");
  await go("negocios");
  await page.getByRole("tab", { name: "Monitores y alertas" }).click();
  await page.getByRole("button", { name: "Nuevo" }).first().click();
  await page.getByLabel("Título *").fill("Vigilar trabajos");
  await page.getByLabel("Qué vigila *").selectOption("trabajos_fallidos");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("button", { name: "Ejecutar ahora" }).click();
  await page.getByText(/hallazgo\(s\), \d+ nuevo/).waitFor();
  await shot("64-monitores");

  step("usuarios con rol");
  await go("sistema");
  await page.getByRole("tab", { name: "Usuarios y roles" }).click();
  await page.getByRole("button", { name: "Nuevo usuario" }).click();
  await page.getByLabel("Usuario", { exact: true }).fill("marta");
  await page.locator(".modal input[type=checkbox]").first().check();
  await page.locator(".modal input[type=password]").fill("clave-larga-123");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await page.getByRole("cell", { name: "marta" }).waitFor();
  await shot("65-usuarios");

  step("personal: extracto bancario, texto bíblico y preguntas a las notas sin IA");
  await page.locator(".top select").selectOption({ label: "Personal · Personal" });
  await go("personal");
  await page.getByRole("tab", { name: "Patrimonio" }).click();
  await page.getByRole("tab", { name: "Presupuesto" }).click();
  const ofx = "OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR<BANKTRANLIST>" +
    "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261102<TRNAMT>-42.50<FITID>A1<NAME>Supermercado</STMTTRN>" +
    "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261103<TRNAMT>1200.00<FITID>A2<NAME>Nomina</STMTTRN></BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>";
  await page.locator("input[type=file][accept='.ofx,.qfx,.txt']").setInputFiles({ name: "extracto.ofx", mimeType: "text/plain", buffer: Buffer.from(ofx) });
  await page.getByText(/2 movimiento\(s\) nuevo\(s\), 0 ya importado/).waitFor();
  await page.getByRole("button", { name: "Guardar en mis registros" }).click();
  await page.getByRole("button", { name: "Supermercado" }).waitFor();
  await page.locator("input[type=file][accept='.ofx,.qfx,.txt']").setInputFiles({ name: "extracto.ofx", mimeType: "text/plain", buffer: Buffer.from(ofx) });
  await page.getByText(/0 movimiento\(s\) nuevo\(s\), 2 ya importado/).waitFor();
  await shot("66-extracto");
  await page.getByRole("tab", { name: "Espíritu" }).click();
  await page.getByRole("tab", { name: "Estudio bíblico" }).click();
  await page.getByLabel("Sigla").fill("PRUEBA");
  const verses = Array.from({ length: 12 }, (_, i) => `Juan 3:${i + 10} Texto de prueba número ${i + 10} con la palabra lámpara.`).join("\n");
  await page.locator("input[type=file][accept='.json,.txt,.tsv']").setInputFiles({ name: "t.txt", mimeType: "text/plain", buffer: Buffer.from(verses) });
  await page.getByPlaceholder(/Juan 3:16/).fill("Juan 3:16");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await page.getByText("Texto de prueba número 16").waitFor();
  await page.getByPlaceholder(/Juan 3:16/).fill("lámpara");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await page.getByText(/12 versículo\(s\) contienen/).waitFor();
  await shot("67-texto-biblico");
  await page.getByRole("tab", { name: "Mente" }).click();
  await page.getByRole("tab", { name: "Segundo cerebro" }).click();
  await page.getByPlaceholder(/Qué decidí sobre/).fill("recuerdo activo");
  await page.getByRole("button", { name: "Preguntar" }).click();
  await page.locator(".toast, .panel").filter({ hasText: /modelo|No encontré|conexi/i }).first().waitFor();
  await shot("68-notas");
  await page.locator(".top select").selectOption({ index: 1 });

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
