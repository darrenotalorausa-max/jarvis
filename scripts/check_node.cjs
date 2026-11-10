// Comprueba la versión mínima de Node.js. Código de salida 0 si es válida.
const major = Number(process.versions.node.split(".")[0]);
if (major < 18) {
  console.log(`Node.js ${process.versions.node} es demasiado antiguo: se necesita 18 o superior.`);
  process.exit(1);
}
console.log(`Node.js ${process.versions.node}`);
