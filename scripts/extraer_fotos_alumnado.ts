// Saca las fotos de los listados de alumnado con foto (PDF de SIGAD) y las
// empareja con el nombre que va debajo de cada una.
// Uso: bun scripts/extraer_fotos_alumnado.ts <salida> <pdf>...
// Necesita poppler (pdfimages, pdftotext) y mutool. Luego:
//   python manage.py importar_fotos_alumnado <salida> [--aplicar]
// La carpeta de salida lleva fotos de menores: nunca dentro del repo.
// Deja <salida>/<n>.jpg y <salida>/manifest.json [{fichero, nombre, grupo, pdf, pagina}]
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, renameSync, writeFileSync, mkdtempSync } from "node:fs";
import { join, basename } from "node:path";

const [salida, ...pdfs] = process.argv.slice(2);
mkdirSync(salida, { recursive: true });

type Palabra = { x0: number; y0: number; x1: number; y1: number; t: string };
const manifest: any[] = [];
let n = 0;

for (const pdf of pdfs) {
  const tmp = mkdtempSync(join(salida, ".tmp-"));
  execFileSync("pdfimages", ["-j", pdf, join(tmp, "img")]);
  const ficheros = readdirSync(tmp).filter((f) => f.startsWith("img-")).sort();
  const lista = execFileSync("pdfimages", ["-list", pdf]).toString().split("\n").slice(2).filter(Boolean)
    .map((l) => l.trim().split(/\s+/)).map((c) => ({ pagina: +c[0], ancho: +c[3], alto: +c[4], enc: c[8] }));
  if (lista.length !== ficheros.length) throw new Error(`${pdf}: ${lista.length} en la lista, ${ficheros.length} extraídas`);

  // Dónde se pinta cada imagen, en el mismo orden que pdfimages.
  const traza = execFileSync("mutool", ["trace", pdf], { maxBuffer: 1 << 28 }).toString();
  const colocadas: { pagina: number; x: number; y: number; w: number; h: number }[] = [];
  let pagina = 0;
  for (const linea of traza.split("\n")) {
    const p = linea.match(/<page number="(\d+)"/);
    if (p) pagina = +p[1];
    const m = linea.match(/<fill_image .*transform="([-\d. ]+)"/);
    if (m) {
      const [a, , , d, e, f] = m[1].trim().split(/\s+/).map(Number);
      colocadas.push({ pagina, x: e, y: f, w: a, h: d });
    }
  }
  if (colocadas.length !== lista.length) throw new Error(`${pdf}: ${colocadas.length} colocadas, ${lista.length} imágenes`);

  // Palabras con caja, por página.
  const xml = execFileSync("pdftotext", ["-bbox", pdf, "-"], { maxBuffer: 1 << 28 }).toString();
  const porPagina: Palabra[][] = [];
  for (const [, cuerpo] of xml.matchAll(/<page[^>]*>([\s\S]*?)<\/page>/g)) {
    porPagina.push([...cuerpo.matchAll(/<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<\/word>/g)]
      .map((w) => ({ x0: +w[1], y0: +w[2], x1: +w[3], y1: +w[4], t: w[5].replace(/&amp;/g, "&") })));
  }

  colocadas.forEach((c, i) => {
    if (lista[i].enc !== "jpeg") throw new Error(`${pdf}: imagen ${i} no es JPEG`);
    const palabras = porPagina[c.pagina - 1];
    const grupo = (() => {
      const g = palabras.find((w) => w.t === "Grupo:");
      if (!g) return "";
      return palabras.filter((w) => Math.abs(w.y0 - g.y0) < 16 && w.x0 > g.x1 && w.x0 < g.x1 + 45)
        .sort((a, b) => (Math.abs(a.y0 - b.y0) > 2 ? a.y0 - b.y0 : a.x0 - b.x0)).map((w) => w.t).join(" ");
    })();
    const cx = c.x + c.w / 2, fondo = c.y + c.h;
    const debajo = palabras
      .filter((w) => w.y0 > fondo && w.y0 < fondo + 25 && Math.abs((w.x0 + w.x1) / 2 - cx) < 52)
      .sort((a, b) => (Math.abs(a.y0 - b.y0) > 2 ? a.y0 - b.y0 : a.x0 - b.x0));
    const nombre = debajo.map((w) => w.t).join(" ").replace(/\s+/g, " ").trim();
    const fichero = `${String(++n).padStart(3, "0")}.jpg`;
    renameSync(join(tmp, ficheros[i]), join(salida, fichero));
    manifest.push({ fichero, nombre, grupo, pdf: basename(pdf), pagina: c.pagina });
  });
}
writeFileSync(join(salida, "manifest.json"), JSON.stringify(manifest, null, 1));
console.log(`${manifest.length} fotos; sin nombre: ${manifest.filter((m) => !m.nombre).length}`);
