// Cuentas del mezclador de las pistas MIDI (fase 85), sin DOM ni audio para
// que se puedan probar con `bun test`.
//
// Un MIDI de karaoke trae cada parte del arreglo en su canal: el bajo en uno,
// la melodía en otro, la batería en el 10. Cada canal es una fila del
// mezclador, con su nombre sacado del instrumento General MIDI que pide.

// Nombre de cada programa General MIDI (0-127), por familias de ocho.
const GM = [
  "Piano", "Piano", "Piano", "Piano", "Piano eléctrico", "Piano eléctrico", "Clave", "Clavinet",
  "Celesta", "Glockenspiel", "Caja de música", "Vibráfono", "Marimba", "Xilófono", "Campanas", "Dulcémele",
  "Órgano", "Órgano", "Órgano", "Órgano de iglesia", "Armonio", "Acordeón", "Armónica", "Bandoneón",
  "Guitarra española", "Guitarra acústica", "Guitarra eléctrica", "Guitarra eléctrica", "Guitarra eléctrica",
  "Guitarra saturada", "Guitarra distorsionada", "Armónicos de guitarra",
  "Bajo acústico", "Bajo eléctrico", "Bajo eléctrico", "Bajo sin trastes", "Bajo slap", "Bajo slap",
  "Bajo sintetizado", "Bajo sintetizado",
  "Violín", "Viola", "Violonchelo", "Contrabajo", "Cuerdas en trémolo", "Cuerdas en pizzicato", "Arpa", "Timbales",
  "Cuerdas", "Cuerdas", "Cuerdas sintetizadas", "Cuerdas sintetizadas", "Coro", "Voz", "Voz sintetizada",
  "Golpe de orquesta",
  "Trompeta", "Trombón", "Tuba", "Trompeta con sordina", "Trompa", "Metales", "Metales sintetizados",
  "Metales sintetizados",
  "Saxo soprano", "Saxo alto", "Saxo tenor", "Saxo barítono", "Oboe", "Corno inglés", "Fagot", "Clarinete",
  "Flautín", "Flauta", "Flauta de pico", "Flauta de pan", "Botella", "Shakuhachi", "Silbido", "Ocarina",
  ...Array(8).fill("Sintetizador solista"),
  ...Array(8).fill("Colchón de sintetizador"),
  ...Array(8).fill("Efecto de sintetizador"),
  "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Gaita", "Violín folk", "Shanai",
  "Campanillas", "Agogó", "Steel drum", "Caja china", "Taiko", "Tom melódico", "Tom sintetizado", "Platillo al revés",
  ...Array(8).fill("Efecto de sonido"),
];

export const CANAL_BATERIA = 9;   // el 10 de los músicos: en General MIDI, siempre batería
export const VOLUMEN_MAX = 1.5;

export function nombreGM(programa, bateria) {
  if (bateria) return "Batería";
  return GM[programa] || "Instrumento";
}

// Los canales que suenan, en orden, con el instrumento que tienen cuando dan
// su primera nota (un cambio de programa más tarde no cambia el nombre).
// `eventos` va en orden de tiempo: { canal, tipo: "programa", programa } o
// { canal, tipo: "nota" }. Dos canales con el mismo instrumento se numeran.
export function resumirCanales(eventos) {
  const programa = new Map();
  const canales = new Map();
  for (const e of eventos) {
    if (e.tipo === "programa") { programa.set(e.canal, e.programa); continue; }
    if (e.tipo !== "nota") continue;
    let c = canales.get(e.canal);
    if (!c) {
      const bateria = e.canal === CANAL_BATERIA;
      const p = programa.get(e.canal) || 0;
      c = { canal: e.canal, programa: p, bateria, notas: 0, nombre: nombreGM(p, bateria) };
      canales.set(e.canal, c);
    }
    c.notas++;
  }
  const lista = [...canales.values()].sort((a, b) => a.canal - b.canal);
  const veces = new Map();
  for (const c of lista) veces.set(c.nombre, (veces.get(c.nombre) || 0) + 1);
  const vistos = new Map();
  for (const c of lista) {
    if (veces.get(c.nombre) < 2) continue;
    const n = (vistos.get(c.nombre) || 0) + 1;
    vistos.set(c.nombre, n);
    c.nombre += " " + n;
  }
  return lista;
}

// Lo que de verdad suena en cada canal: { mudo, ganancia }. Apagado manda
// siempre; si algún canal tiene solo, suenan solo los que lo tienen (y no
// están apagados), como en una mesa de mezclas.
export function sonido(canales, mezcla) {
  const m = mezcla || {};
  const haySolo = canales.some((c) => m[c.canal] && m[c.canal].solo);
  const fuera = new Map();
  for (const c of canales) {
    const f = m[c.canal] || {};
    const volumen = typeof f.volumen === "number" ? Math.max(0, Math.min(VOLUMEN_MAX, f.volumen)) : 1;
    fuera.set(c.canal, { mudo: !!f.apagado || (haySolo && !f.solo), ganancia: volumen });
  }
  return fuera;
}
