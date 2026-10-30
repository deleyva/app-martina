// ¿Es este MIDI el arreglo de esta ficha, y en qué tono suena? (fase 87)
//
//   bun scripts/bases/midi_contra_ficha.ts <ficha.cho> <entrada.mid|rmi> [salida.json]
//
// La ficha escribe un acorde por compás («[G] [Em]» son dos compases). En cada
// compás del MIDI se mira qué nota suena más abajo (sin batería) y qué notas
// suenan en conjunto, y se compara con el bajo y las notas del acorde de la
// ficha. Se prueban los 12 desfases, el compás del MIDI entero, a la mitad y
// doble, y empezar en otro tiempo (anacrusas). Un alineamiento de secuencias,
// como el de dos cadenas de ADN, deja que el MIDI tenga intro, solos o
// repeticiones que la ficha no escribe, y al revés.
//
// Da el desfase (cuántos semitonos suena el MIDI por encima de la ficha, lo
// que el 🎧 llama «Grabación»), los compases de la ficha cuyo bajo acierta y una
// marca por párrafo con acordes, en segundos del MIDI, que es el reloj del
// reproductor (fase 85). Por pantalla solo números: los MIDI karaoke llevan la
// letra dentro, y la ficha también. Las anclas de las marcas van al JSON.

import { BasicMIDI } from "spessasynth_core";
import { ChordProParser, HtmlDivFormatter } from "chordsheetjs";
import { acorde } from "./base_desde_chordpro.ts";
import { ancla } from "../../martina_bescos_app/static/js/src/practica.js";

type Compas = { p: number; raiz: number; bajo: number; tonos: number[] };
type Nota = { ini: number; fin: number; key: number; vel: number };

// Mismo camino que el visor (`chordpro.js`): escapar, parsear y pintar con
// HtmlDivFormatter, y contar los `.paragraph` en el mismo orden.
export function leerFicha(texto: string) {
  const escapado = texto.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html = new HtmlDivFormatter({ normalizeChords: false }).format(new ChordProParser().parse(escapado));
  const compases: Compas[] = [];
  const parrafos: { p: number; primero: number; ancla: string }[] = [];
  // `pintarRitmos` cambia cada `.paragraph.ritmo` por su rejilla, así que en el
  // visor no cuenta: sin quitarlo, todas las marcas caían un párrafo después.
  const trozos = html.split(/(<div class="paragraph[^"]*">)/).slice(1);
  const visibles = [];
  for (let k = 0; k < trozos.length; k += 2) if (!/\britmo\b/.test(trozos[k])) visibles.push(trozos[k + 1]);
  visibles.forEach((trozo, p) => {
    const nombres = [...trozo.matchAll(/<div class="chord">([^<]*)<\/div>/g)].map((m) => m[1].trim()).filter(Boolean);
    const texto = trozo
      .replace(/<div class="chord">[^<]*<\/div>/g, "")
      .replace(/<[^>]+>/g, "")
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
    const primero = compases.length;
    for (const n of nombres) {
      const a = acorde(n);
      if (a) compases.push({ p, raiz: a.raiz, bajo: a.bajo, tonos: a.intervalos.map((i) => (a.raiz + i) % 12) });
    }
    if (compases.length > primero) parrafos.push({ p, primero, ancla: ancla(texto) });
  });
  return { compases, parrafos };
}

export function leerMidi(buffer: ArrayBuffer) {
  const midi = BasicMIDI.fromArrayBuffer(buffer);
  const notas: Nota[] = [];
  const abiertas = new Map<number, { tick: number; vel: number }[]>();
  let compas = { tick: Infinity, num: 4, den: 4 };
  const eventos = midi.tracks.flatMap((t) => [...t.events]).sort((a, b) => a.ticks - b.ticks);
  for (const e of eventos) {
    const s = e.statusByte as number;
    if (s === 0x58 && e.ticks < compas.tick) compas = { tick: e.ticks, num: e.data[0], den: 2 ** e.data[1] };
    if (s < 0x80 || s >= 0xf0) continue;
    const tipo = s & 0xf0, canal = s & 0x0f;
    if (canal === 9 || (tipo !== 0x80 && tipo !== 0x90)) continue;
    const clave = canal * 128 + e.data[0];
    if (tipo === 0x90 && e.data[1] > 0) {
      if (!abiertas.has(clave)) abiertas.set(clave, []);
      abiertas.get(clave)!.push({ tick: e.ticks, vel: e.data[1] });
    } else {
      const a = abiertas.get(clave)?.shift();
      if (a && e.ticks > a.tick) notas.push({ ini: a.tick, fin: e.ticks, key: e.data[0], vel: a.vel });
    }
  }
  return { midi, notas, num: compas.num || 4, den: compas.den || 4 };
}

const MUESTRAS = 8;

// Por cada unidad de la rejilla: histograma del bajo (la nota más grave en 8
// puntos) y croma de todo lo que suena, pesado por duración y fuerza.
function rejilla(notas: Nota[], inicio: number, paso: number, fin: number) {
  const n = Math.max(1, Math.ceil((fin - inicio) / paso));
  const grave = new Int16Array(n * MUESTRAS).fill(999);
  const croma = Array.from({ length: n }, () => new Float64Array(12));
  const sub = paso / MUESTRAS;
  for (const nota of notas) {
    if (nota.fin <= inicio) continue;
    for (let k = Math.max(0, Math.ceil((nota.ini - inicio) / sub)); k * sub + inicio < nota.fin && k < grave.length; k++) {
      if (nota.key < grave[k]) grave[k] = nota.key;
    }
    for (let u = Math.max(0, Math.floor((nota.ini - inicio) / paso)); u < n && inicio + u * paso < nota.fin; u++) {
      const a = Math.max(nota.ini, inicio + u * paso), b = Math.min(nota.fin, inicio + (u + 1) * paso);
      if (b > a) croma[u][nota.key % 12] += ((b - a) / paso) * (nota.vel / 127);
    }
  }
  return Array.from({ length: n }, (_, u) => {
    const bajo = new Float64Array(12);
    let total = 0;
    for (let k = 0; k < MUESTRAS; k++) {
      const g = grave[u * MUESTRAS + k];
      if (g !== 999) { bajo[g % 12]++; total++; }
    }
    if (total) for (let c = 0; c < 12; c++) bajo[c] /= total;
    let max = 0, arg = -1;
    for (let c = 0; c < 12; c++) if (bajo[c] > max) { max = bajo[c]; arg = c; }
    const norma = Math.hypot(...croma[u]) || 1;
    return { bajo, arg, croma: croma[u].map((x) => x / norma) };
  });
}

type Unidad = ReturnType<typeof rejilla>[number];

function parecido(u: Unidad, c: Compas, d: number) {
  if (u.arg < 0) return { s: 0, acierto: false };
  const b = (c.bajo + d) % 12, r = (c.raiz + d) % 12;
  let coseno = 0, norma = 0;
  c.tonos.forEach((t, i) => { const w = i ? 0.8 : 1; coseno += u.croma[(t + d) % 12] * w; norma += w * w; });
  return { s: 0.6 * Math.max(u.bajo[b], u.bajo[r]) + 0.4 * (coseno / Math.sqrt(norma)), acierto: u.arg === b || u.arg === r };
}

const UMBRAL = 0.35, SOBRA_MIDI = 0.25, FALTA_MIDI = 0.5;

// Alineamiento semiglobal: la ficha entera, el MIDI con principio y final libres.
function alinear(us: Unidad[], cs: Compas[], d: number, conCamino: boolean) {
  const N = us.length, M = cs.length;
  let prev = new Float64Array(M + 1), cur = new Float64Array(M + 1);
  for (let j = 1; j <= M; j++) prev[j] = -FALTA_MIDI * j;
  const desde = conCamino ? new Uint8Array((N + 1) * (M + 1)) : null;
  let mejor = prev[M], fila = 0;
  for (let i = 1; i <= N; i++) {
    cur[0] = 0;
    for (let j = 1; j <= M; j++) {
      const diag = prev[j - 1] + parecido(us[i - 1], cs[j - 1], d).s - UMBRAL;
      const arriba = prev[j] - SOBRA_MIDI, izq = cur[j - 1] - FALTA_MIDI;
      let v = diag, o = 0;
      if (arriba > v) { v = arriba; o = 1; }
      if (izq > v) { v = izq; o = 2; }
      cur[j] = v;
      if (desde) desde[i * (M + 1) + j] = o;
    }
    if (cur[M] > mejor) { mejor = cur[M]; fila = i; }
    [prev, cur] = [cur, prev];
  }
  if (!desde) return { puntos: mejor, pares: [] as [number, number][] };
  const pares: [number, number][] = [];
  let i = fila, j = M;
  while (j > 0 && i > 0) {
    const o = desde[i * (M + 1) + j];
    if (o === 0) { pares.push([i - 1, j - 1]); i--; j--; } else if (o === 1) i--; else j--;
  }
  return { puntos: mejor, pares: pares.reverse() };
}

export function comparar(textoFicha: string, bufferMidi: ArrayBuffer) {
  const { compases, parrafos } = leerFicha(textoFicha);
  const { midi, notas, num, den } = leerMidi(bufferMidi);
  if (!compases.length || !notas.length) throw new Error("Ficha sin acordes o MIDI sin notas");
  const pulso = (midi.timeDivision * 4) / den;
  const fin = Math.max(...notas.map((n) => n.fin));
  const pruebas: { factor: number; corrimiento: number; inicio: number; paso: number; us: Unidad[] }[] = [];
  for (const factor of [0.5, 1, 2]) {
    const pulsosUnidad = num * factor;
    for (let k = 0; k < Math.max(1, Math.round(pulsosUnidad)); k++) {
      const inicio = k * pulso, paso = pulsosUnidad * pulso;
      pruebas.push({ factor, corrimiento: k, inicio, paso, us: rejilla(notas, inicio, paso, fin) });
    }
  }
  // El mejor de cada desfase, y su cuenta de aciertos.
  const porDesfase = [];
  for (let d = 0; d < 12; d++) {
    let mejor = null as null | { puntos: number; prueba: (typeof pruebas)[number] };
    for (const prueba of pruebas) {
      const { puntos } = alinear(prueba.us, compases, d, false);
      if (!mejor || puntos > mejor.puntos) mejor = { puntos, prueba };
    }
    const { pares } = alinear(mejor!.prueba.us, compases, d, true);
    const aciertos = pares.filter(([i, j]) => parecido(mejor!.prueba.us[i], compases[j], d).acierto).length;
    porDesfase.push({ desfase: ((d + 6) % 12) - 6, puntos: +mejor!.puntos.toFixed(2), aciertos, pares, prueba: mejor!.prueba });
  }
  porDesfase.sort((a, b) => b.puntos - a.puntos);
  const g = porDesfase[0];
  // Marca de cada párrafo: el primer compás suyo que casó, llevado hacia atrás
  // hasta su primer compás.
  const emparejado = new Map(g.pares.map(([i, j]) => [j, i]));
  const marcas = [];
  for (const [k, par] of parrafos.entries()) {
    const hasta = k + 1 < parrafos.length ? parrafos[k + 1].primero : compases.length;
    for (let j = par.primero; j < hasta; j++) {
      if (!emparejado.has(j)) continue;
      const u = Math.max(0, emparejado.get(j)! - (j - par.primero));
      const t = midi.midiTicksToSeconds(Math.round(g.prueba.inicio + u * g.prueba.paso));
      marcas.push({ p: par.p, t: Math.round(t * 100) / 100, ancla: par.ancla });
      break;
    }
  }
  return {
    desfase: g.desfase,
    aciertos: g.aciertos,
    compases: compases.length,
    emparejados: g.pares.length,
    factor: g.prueba.factor,
    corrimiento: g.prueba.corrimiento,
    compasMidi: `${num}/${den}`,
    duracion: Math.round(midi.duration * 10) / 10,
    otros: porDesfase.slice(1, 4).map((o) => ({ desfase: o.desfase, aciertos: o.aciertos, puntos: o.puntos })),
    puntos: g.puntos,
    marcas,
  };
}

if (import.meta.main) {
  const [ficha, entrada, salida] = process.argv.slice(2);
  if (!ficha || !entrada) {
    console.error("Uso: bun scripts/bases/midi_contra_ficha.ts <ficha.cho> <entrada.mid|rmi> [salida.json]");
    process.exit(2);
  }
  const r = comparar(await Bun.file(ficha).text(), await Bun.file(entrada).arrayBuffer());
  if (salida) await Bun.write(salida, JSON.stringify(r, null, 1));
  const pct = Math.round((100 * r.aciertos) / r.compases);
  console.log(`desfase ${r.desfase > 0 ? "+" : ""}${r.desfase} · ${r.aciertos}/${r.compases} compases (${pct} %) · emparejados ${r.emparejados} · compás MIDI ${r.compasMidi} ×${r.factor} desde el pulso ${r.corrimiento} · ${r.duracion} s`);
  console.log("otros desfases: " + r.otros.map((o) => `${o.desfase > 0 ? "+" : ""}${o.desfase} → ${o.aciertos}`).join(" · "));
  console.log("marcas: " + r.marcas.map((m) => `p${m.p}@${m.t}`).join(" "));
}
