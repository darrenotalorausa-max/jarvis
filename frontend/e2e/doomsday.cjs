// Recorrido en navegador de Doomsday contra una instancia LIMPIA en marcha (por defecto http://127.0.0.1:8766).
// Uso: node frontend/e2e/doomsday.cjs   ·   Variables: DOOMSDAY_URL, CAPTURAS=1 (guarda capturas en frontend/e2e/capturas)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.DOOMSDAY_URL || "http://127.0.0.1:8766";
const SHOTS = process.env.CAPTURAS ? path.join(__dirname, "capturas") : null;
let step = 0;
const ok = (msg) => console.log(`  ✓ ${String(++step).padStart(2, "0")} ${msg}`);

(async () => {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `doomsday-${name}.png`) }); };
  const post = (url, body) => page.evaluate(async ([u, b]) => { const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }); return r.json(); }, [url, body]);

  await page.goto(BASE);
  await page.getByRole("heading", { name: "Laboratorio de software" }).waitFor();
  const cat = await page.evaluate(() => fetch("/api/dd/catalog").then((r) => r.json()));
  if (cat.modulos.length !== 100) throw new Error("El catálogo no tiene 100 módulos");
  if ((await page.locator(".modrow__rank").count()) !== 20) throw new Error("El tablero no muestra los 20 mejores");
  ok("Tablero con 100 módulos, 20 mejores y cuatro capas");
  await shot("tablero");

  for (const k of Object.keys(cat.categorias)) {
    await page.goto(`${BASE}/#/c/${k}`);
    await page.getByRole("heading", { name: cat.categorias[k].nombre }).waitFor();
    if ((await page.locator("main .modrow").count()) !== 10) throw new Error(`La categoría ${k} no lista 10 módulos`);
  }
  ok("Las 10 categorías listan 10 módulos cada una");

  // Todos los paneles abren sin errores y muestran su orden libre.
  for (const m of cat.modulos) {
    await page.goto(`${BASE}/#/m/${m.id}`);
    await page.getByRole("heading", { name: m.nombre, exact: true, level: 1 }).waitFor();
    await page.getByRole("button", { name: "Enviar orden" }).waitFor();
  }
  ok("Los 100 paneles de módulo abren con su orden libre");

  // Datos reales → cálculo determinista (G02).
  const interna = cat.espacios.interna;
  const hoy = new Date().toISOString().slice(0, 10);
  const pedido = (ref, status, producto) => post("/api/records", { space: interna, kind: "dd_pedido", title: ref, status, data: { ref, fecha: hoy, producto, campana: "C1", ciudad: "Cali", precio: 100, costo_producto: 30, flete: 10, flete_devolucion: 8 } });
  for (let i = 0; i < 6; i++) await pedido(`E${i}`, "entregado", "Faja");
  for (let i = 0; i < 4; i++) await pedido(`D${i}`, "devuelto", "Faja");
  await post("/api/records", { space: interna, kind: "dd_gasto_pauta", title: "día", data: { fecha: hoy, plataforma: "meta", campana: "C1", producto: "Faja", gasto: 200, compras: 11 } });
  await page.goto(`${BASE}/#/m/G02`);
  await page.getByText("Utilidad neta COD por producto, campaña y ciudad").waitFor();
  await page.locator(".stat", { hasText: "Utilidad neta" }).getByText("88", { exact: true }).waitFor();
  ok("G02 calcula la utilidad neta con devoluciones, fletes y pauta (88)");
  await shot("g02-utilidad");
  await page.locator(".tab", { hasText: "Datos" }).click();
  await page.getByText("Pedidos").first().waitFor();
  await page.getByRole("cell", { name: "E0" }).first().waitFor();
  ok("La pestaña Datos muestra los registros del módulo");

  // Herramienta con entradas (X07).
  await page.goto(`${BASE}/#/m/X07`);
  const panel = page.locator(".panel", { hasText: "Revisión de cumplimiento de anuncios" });
  await panel.locator("textarea").fill("Esta crema cura el acné para siempre. Resultados garantizados. ¿Sufres de sobrepeso?");
  await panel.getByRole("button", { name: "Calcular" }).click();
  await panel.locator(".stat", { hasText: "Riesgo" }).getByText("alto").waitFor();
  ok("X07 detecta promesas prohibidas y marca riesgo alto");
  await shot("x07-cumplimiento");

  // Orden sin IA configurada: espera configuración, no inventa.
  await page.goto(`${BASE}/#/m/M06`);
  await page.locator(".panel", { hasText: "Orden libre" }).locator("textarea").first().fill("Dame variaciones del anuncio de la faja");
  await page.getByRole("button", { name: "Enviar orden" }).click();
  await page.locator(".jobrow").getByText("Esperando configuración").waitFor({ timeout: 20000 });
  ok("Sin IA conectada, la orden queda esperando configuración (no inventa resultados)");
  await shot("m06-orden");

  // Skill: editar, guardar como propia y restaurar.
  await page.goto(`${BASE}/#/m/G04/skill`);
  const area = page.getByLabel("Skill G04");
  await area.waitFor();
  if (!(await area.inputValue()).includes("Estratega de conversión")) throw new Error("La skill integrada de G04 no cargó");
  await area.fill((await area.inputValue()) + "\n**Mi regla.** Siempre con mis secciones de Dawn.");
  await page.getByRole("button", { name: "Guardar como mi versión" }).click();
  await page.getByText("tuya, versión 2").waitFor();
  ok("La skill se edita y queda como versión propia");
  await shot("g04-skill");
  await page.getByRole("button", { name: "Volver a la integrada" }).click();
  await page.getByRole("button", { name: "Confirmar" }).or(page.getByRole("button", { name: "Sí" })).or(page.getByRole("button", { name: "Continuar" })).first().click();
  await page.getByText("integrada, versión").waitFor();
  ok("Se restaura la skill integrada");
  await page.goto(`${BASE}/#/skills`);
  await page.getByRole("heading", { name: "Skills" }).waitFor();
  if ((await page.locator("main tbody tr").count()) !== 100) throw new Error("La tabla de skills no tiene 100 filas");
  ok("El repositorio lista las 100 skills");

  // Bóveda (P02): el secreto no aparece hasta revelarlo.
  await page.goto(`${BASE}/#/m/P02`);
  const vault = page.locator(".panel", { hasText: "Guardar en la bóveda" });
  await vault.locator("input").nth(0).fill("Shopify tienda 1");
  await vault.locator("input[type=password]").fill("S3creto-Largo-123");
  await vault.getByRole("button", { name: "Guardar en la bóveda" }).click();
  await vault.getByRole("cell", { name: "Shopify tienda 1" }).waitFor();
  if (await page.getByText("S3creto-Largo-123").count()) throw new Error("El secreto se muestra sin revelarlo");
  await vault.getByRole("button", { name: "Revelar" }).click();
  await vault.getByText("S3creto-Largo-123").waitFor();
  ok("La bóveda guarda el secreto fuera de la vista y lo revela a petición");

  // Operador logístico (G01): vista previa y guardado de su exportación CSV.
  await page.goto(`${BASE}/#/m/G01`);
  const logi = page.locator(".panel", { hasText: "Importar la exportación de tu operador logístico" });
  await logi.locator("input[type=file]").setInputFiles({ name: "dropi.csv", mimeType: "text/csv", buffer: Buffer.from("ID;ESTADO;CIUDAD;TOTAL;FLETE\nZ1;ENTREGADO;Cali;89.900;12.500\nZ2;DEVOLUCION;Pasto;89.900;12.500\n") });
  await logi.getByRole("button", { name: "Revisar sin guardar" }).click();
  await logi.getByText("Vista previa: aún no se ha guardado nada.").waitFor();
  await logi.getByRole("button", { name: "Guardar cambios" }).click();
  await logi.getByText("Guardado.").waitFor();
  for (const t of ["Traer pedidos de Shopify", "Traer gasto de pauta (Meta y TikTok)"]) await page.locator(".panel__title", { hasText: t }).waitFor();
  ok("G01 importa la exportación logística con vista previa y ofrece Shopify, Meta y TikTok");

  // Paneles de integración presentes en sus módulos.
  for (const [id, title] of [["M01", "Pausar en la plataforma"], ["V05", "Enviar por WhatsApp"], ["M06", "Producir creativos aprobados"], ["C04", "Recortar un clip"], ["P04", "Grabar una nota de voz"], ["G04", "Publicar la ficha aprobada como borrador en Shopify"]]) {
    await page.goto(`${BASE}/#/m/${id}`);
    await page.locator(".panel__title", { hasText: title }).waitFor();
  }
  ok("M01, V05, M06, C04, P04 y G04 muestran su integración");

  // Portal (V06): un espacio por cliente, dentro de la capa de clientes.
  await page.goto(`${BASE}/#/m/V06`);
  const portal = page.locator(".panel", { hasText: "Portal por cliente" });
  await portal.locator("input").first().fill("Acme");
  await portal.getByRole("button", { name: "Crear espacio del cliente" }).click();
  await portal.getByRole("cell", { name: "Acme", exact: true }).waitFor();
  await portal.locator("tr", { hasText: "Acme" }).getByRole("button", { name: "Trabajar en este espacio" }).click();
  await page.waitForFunction((base) => { const el = document.querySelector(".top select"); return !!el && el.value !== base && el.selectedOptions[0]?.textContent === "Acme"; }, cat.espacios.clientes);
  ok("V06 crea el espacio de un cliente y trabaja dentro de él");

  // Teleprompter (C06) y vistas del motor.
  await page.goto(`${BASE}/#/m/C06`);
  await page.locator(".panel", { hasText: "Teleprompter" }).locator("textarea").fill("Hola.\nEsto es una prueba.");
  await page.getByRole("button", { name: "Iniciar" }).click();
  await page.waitForFunction(() => /translateY\(-[1-9]/.test(document.querySelector(".prompter__text")?.style.transform || ""));
  ok("El teleprompter desplaza el guion");
  for (const [r, h] of [["revision", "Revisión"], ["conexiones", "Conexiones"], ["apps", "Apps"], ["sistema", "Trabajos"]]) {
    await page.goto(`${BASE}/#/${r}`);
    await page.locator("main h1", { hasText: h }).first().waitFor();
  }
  ok("Revisión, Conexiones, Apps conectadas y Sistema abren dentro de Doomsday");
  await page.goto(BASE);
  await page.locator(".stat", { hasText: "Módulos con actividad" }).getByText(/[1-9]\d* de 100/).waitFor();
  await shot("tablero-con-actividad");

  await browser.close();
  if (errors.length) { console.error("Errores de consola:\n" + errors.join("\n")); process.exit(1); }
  console.log(`Recorrido de Doomsday completado: ${step} pasos sin errores.`);
})().catch((e) => { console.error("FALLO:", e.message); process.exit(1); });
