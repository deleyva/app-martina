// Base de acompañamiento a partir de la ficha de una canción (fase 83, prueba).
//
//   bun scripts/bases/base_desde_chordpro.ts <ficha.cho> <carpeta_salida>
//
// Lee el ChordPro tal como lo guarda la app y escribe en la carpeta:
//   base.mid        batería, bajo, guitarra y piano
//   secciones.json  el segundo en que empieza cada sección (las marcas del 🎧)
//   compases.json   el acorde de cada compás, para comprobar el audio
//
// Tres convenciones de las fichas, que son las que lo hacen posible:
//   - Cada acorde entre corchetes es UN compás («[G] [G] [Em] [Em]» son cuatro).
//   - El bloque {start_of_ritmo} es la rejilla que se toca en cada compás, con
//     el mismo parser que pinta la app (`ritmos.js`).
//   - El tempo sale del bloque de ritmo o de {tempo: …}.
//
// No hay melodía ni riffs del disco: solo la armonía de la ficha tocada con la
// rejilla de clase. Es un arreglo propio, sin la grabación de nadie.

import { parsearRitmo } from "../../martina_bescos_app/static/js/src/ritmos.js";

const PPQ = 480;
const NOTAS: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

// Intervalos por calidad, de la más larga a la más corta para que «m7» no se
// lea como «m».
const CALIDADES: [string, number[]][] = [
  ["maj7", [0, 4, 7, 11]], ["m7b5", [0, 3, 6, 10]], ["m7", [0, 3, 7, 10]], ["m6", [0, 3, 7, 9]],
  ["dim", [0, 3, 6]], ["aug", [0, 4, 8]], ["sus4", [0, 5, 7]], ["sus2", [0, 2, 7]],
  ["add9", [0, 4, 7, 14]], ["m", [0, 3, 7]], ["7", [0, 4, 7, 10]], ["6", [0, 4, 7, 9]],
  ["9", [0, 4, 7, 10, 14]], ["+", [0, 4, 8]], ["", [0, 4, 7]],
];

type Acorde = { nombre: string; raiz: number; bajo: number; intervalos: number[] } | null;

function clase(nota: string): number {
  return (NOTAS[nota[0]] + (nota[1] === "#" ? 1 : nota[1] === "b" ? -1 : 0) + 12) % 12;
}

export function acorde(nombre: string): Acorde {
  const m = /^([A-G][#b]?)(.*?)(?:\/([A-G][#b]?))?$/.exec(nombre.trim());
  if (!m) return null;  // N.C., silencios
  const raiz = clase(m[1]);
  const resto = m[2];
  const intervalos = (CALIDADES.find(([q]) => resto.startsWith(q)) || CALIDADES.at(-1)!)[1];
  return { nombre, raiz, bajo: m[3] ? clase(m[3]) : raiz, intervalos };
}

// La nota de la clase `pc` más cercana por encima de `desde`.
const encima = (pc: number, desde: number) => desde + ((pc - desde) % 12 + 12) % 12;

export type Seccion = { etiqueta: string; compases: string[] };

export function leerFicha(texto: string) {
  const secciones: Seccion[] = [];
  let ritmo = "";
  let tempo = 0;
  let dentroRitmo = false;
  let actual: Seccion | null = null;
  const cerrar = () => { if (actual && actual.compases.length) secciones.push(actual); actual = null; };
  for (const cruda of texto.split("\n")) {
    const linea = cruda.trim();
    if (dentroRitmo) {
      if (/^\{end_of_ritmo/.test(linea)) dentroRitmo = false;
      else ritmo += linea + "\n";
      continue;
    }
    if (/^\{start_of_ritmo/.test(linea)) { if (!ritmo) dentroRitmo = true; continue; }
    const t = /^\{tempo:\s*(\d+)/.exec(linea);
    if (t) { tempo = Number(t[1]); continue; }
    if (!linea) { cerrar(); continue; }
    const etiqueta = /^\{(?:start_of_\w+|comment|c):\s*(.+?)\}$/.exec(linea);
    if (etiqueta) { cerrar(); actual = { etiqueta: etiqueta[1], compases: [] }; continue; }
    if (/^\{/.test(linea)) continue;
    const acordes = [...linea.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1]);
    if (!acordes.length) continue;
    if (!actual) actual = { etiqueta: "", compases: [] };
    actual.compases.push(...acordes);
  }
  cerrar();
  const patron = parsearRitmo(ritmo);
  if (patron.errores.length) throw new Error("Ritmo: " + patron.errores.join("; "));
  return { secciones, patron, tempo: tempo || patron.tempo };
}

// ── MIDI ──
type Evento = { tick: number; datos: number[] };

function vlq(n: number): number[] {
  const bytes = [n & 0x7f];
  while ((n >>= 7)) bytes.unshift((n & 0x7f) | 0x80);
  return bytes;
}

function smf(eventos: Evento[], tempo: number, pulsos: number): Uint8Array {
  // Las notas que acaban antes que las que empiezan en el mismo tick.
  eventos.sort((a, b) => a.tick - b.tick || (a.datos[0] & 0xf0) - (b.datos[0] & 0xf0));
  const pista: number[] = [];
  const mpq = Math.round(60_000_000 / tempo);
  pista.push(0, 0xff, 0x51, 3, (mpq >> 16) & 0xff, (mpq >> 8) & 0xff, mpq & 0xff);
  pista.push(0, 0xff, 0x58, 4, pulsos, 2, 24, 8);
  let anterior = 0;
  for (const e of eventos) {
    pista.push(...vlq(e.tick - anterior), ...e.datos);
    anterior = e.tick;
  }
  pista.push(0, 0xff, 0x2f, 0);
  const cab = [0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, PPQ >> 8, PPQ & 0xff];
  const len = pista.length;
  return new Uint8Array([...cab, 0x4d, 0x54, 0x72, 0x6b, (len >>> 24) & 0xff, (len >> 16) & 0xff, (len >> 8) & 0xff, len & 0xff, ...pista]);
}

const CANAL = { bajo: 0, guitarra: 1, piano: 2, bateria: 9 };
const BATERIA: Record<string, number> = { SH: 42, CA: 38, BO: 36 };

export function generar(texto: string) {
  const { secciones, patron, tempo } = leerFicha(texto);
  const { pulsos, pasos } = patron;
  const tickCompas = PPQ * pulsos;
  const tickPaso = tickCompas / pasos;
  const segCompas = (60 / tempo) * pulsos;
  const ev: Evento[] = [];
  const nota = (canal: number, n: number, vel: number, ini: number, dur: number) => {
    ev.push({ tick: Math.round(ini), datos: [0x90 | canal, n, vel] });
    ev.push({ tick: Math.round(ini + Math.max(dur, 10)), datos: [0x80 | canal, n, 0] });
  };
  // Instrumentos (General MIDI, desde 0) y volumen de cada uno en la mezcla.
  ev.push({ tick: 0, datos: [0xc0 | CANAL.bajo, 33] }, { tick: 0, datos: [0xb0 | CANAL.bajo, 7, 105] });
  ev.push({ tick: 0, datos: [0xc0 | CANAL.guitarra, 25] }, { tick: 0, datos: [0xb0 | CANAL.guitarra, 7, 92] });
  ev.push({ tick: 0, datos: [0xc0 | CANAL.piano, 0] }, { tick: 0, datos: [0xb0 | CANAL.piano, 7, 72] });
  ev.push({ tick: 0, datos: [0xb0 | CANAL.bateria, 7, 100] });

  // Un compás de cuenta: cuatro golpes de baqueta.
  for (let p = 0; p < pulsos; p++) nota(CANAL.bateria, 37, p ? 85 : 105, p * PPQ, PPQ / 2);

  const voz = (v: string) => patron.voces.find((x: { voz: string }) => x.voz === v)?.golpes as number[] | undefined;
  // Siguiente golpe a partir del paso i (o el final del compás), para que cada
  // nota dure hasta la siguiente.
  const hasta = (golpes: number[], i: number) => {
    for (let j = i + 1; j < golpes.length; j++) if (golpes[j]) return j;
    return golpes.length;
  };

  const plano: { compas: number; acorde: string; raiz: number | null; bajo: number | null }[] = [];
  const marcas: { etiqueta: string; t: number; compases: number }[] = [];
  let compas = 1;
  for (const s of secciones) {
    marcas.push({ etiqueta: s.etiqueta, t: +(compas * segCompas).toFixed(3), compases: s.compases.length });
    for (const nombre of s.compases) {
      const a = acorde(nombre);
      plano.push({ compas, acorde: nombre, raiz: a?.raiz ?? null, bajo: a?.bajo ?? null });
      const base = compas * tickCompas;
      for (const [v, n] of Object.entries(BATERIA)) {
        const g = voz(v);
        g?.forEach((golpe, i) => { if (golpe) nota(CANAL.bateria, n, golpe === 2 ? 118 : v === "SH" ? (i % (pasos / pulsos) ? 62 : 80) : 96, base + i * tickPaso, tickPaso / 2); });
      }
      if (a) {
        const bajo = encima(a.bajo, 28);
        const g = voz("BA");
        g?.forEach((golpe, i) => { if (golpe) nota(CANAL.bajo, bajo, golpe === 2 ? 115 : 98, base + i * tickPaso, (hasta(g, i) - i) * tickPaso * 0.92); });
        const mi = voz("MI");
        mi?.forEach((golpe, i) => { if (golpe) nota(CANAL.piano, encima(a.raiz, 40), 78, base + i * tickPaso, (hasta(mi, i) - i) * tickPaso * 0.95); });
        const md = voz("MD");
        const triada = a.intervalos.map((iv) => encima((a.raiz + iv) % 12, 59)).sort((x, y) => x - y);
        md?.forEach((golpe, i) => { if (golpe) for (const n of triada) nota(CANAL.piano, n, 66, base + i * tickPaso, (hasta(md, i) - i) * tickPaso * 0.85); });
        // Guitarra: seis cuerdas aproximadas; abajo sube con 11 ticks entre
        // cuerdas (unos 12 ms a 120), arriba baja por las cuatro agudas.
        const r = encima(a.raiz, 40);
        const quinta = a.intervalos.includes(7) ? 7 : a.intervalos[2];
        const cuerdas = [r, r + quinta, r + 12, r + 12 + a.intervalos[1], r + 12 + quinta, r + 24]
          .map((n, k) => (k === 5 && a.intervalos.length > 3 ? r + 12 + a.intervalos[3] : n));
        const gu = voz("GU");
        gu?.forEach((golpe, i) => {
          if (!golpe) return;
          const dur = (hasta(gu, i) - i) * tickPaso * 0.95;
          const arriba = golpe === 5;
          const orden = arriba ? cuerdas.slice(2).reverse() : cuerdas;
          const vel = golpe === 4 ? 100 : arriba ? 58 : 80;
          orden.forEach((n, k) => nota(CANAL.guitarra, n, vel, base + i * tickPaso + k * 11, dur - k * 11));
        });
      }
      compas++;
    }
  }
  // Final: el último acorde entero y un platillo.
  const ultimo = acorde(secciones.at(-1)!.compases.at(-1)!);
  const base = compas * tickCompas;
  nota(CANAL.bateria, 49, 105, base, tickCompas);
  nota(CANAL.bateria, 36, 100, base, PPQ);
  if (ultimo) {
    nota(CANAL.bajo, encima(ultimo.bajo, 28), 100, base, tickCompas);
    for (const iv of ultimo.intervalos) nota(CANAL.piano, encima((ultimo.raiz + iv) % 12, 59), 70, base, tickCompas);
    nota(CANAL.piano, encima(ultimo.raiz, 40), 75, base, tickCompas);
  }
  return {
    midi: smf(ev, tempo, pulsos),
    secciones: marcas,
    compases: plano,
    tempo,
    duracion: +((compas + 1) * segCompas).toFixed(3),
  };
}

if (import.meta.main) {
  const [ficha, salida] = process.argv.slice(2);
  if (!ficha || !salida) {
    console.error("Uso: bun scripts/bases/base_desde_chordpro.ts <ficha.cho> <carpeta_salida>");
    process.exit(2);
  }
  const r = generar(await Bun.file(ficha).text());
  await Bun.write(`${salida}/base.mid`, r.midi);
  await Bun.write(`${salida}/secciones.json`, JSON.stringify(r.secciones, null, 1));
  await Bun.write(`${salida}/compases.json`, JSON.stringify(r.compases));
  console.log(`tempo ${r.tempo} · ${r.compases.length} compases · ${r.duracion} s`);
  for (const s of r.secciones) console.log(`  ${String(s.t).padStart(7)} s  ${s.etiqueta || "(sin nombre)"}  (${s.compases} c.)`);
}
