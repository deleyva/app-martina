// Diagramas de acordes para la letra con acordes: guitarra, ukelele y piano.
//
// De dónde sale cada digitación, por orden:
// 1. Una `{define}` escrita en el .cho de la canción. La leemos NOSOTROS del
//    texto, no ChordSheetJS: ChordSheetJS 16.2.2 trata `{define-ukulele: …}`
//    como si fuera de guitarra y descarta en silencio `{define-piano: C keys
//    0 4 7}` (comprobado el 2026-09-26). Formas admitidas:
//      {define: G base-fret 1 frets 3 2 0 0 3 3 fingers 2 1 0 0 3 4}
//        sin instrumento: 6 posiciones = guitarra, 4 = ukelele
//      {define-guitar: …}  {define-guitarra: …}
//      {define-ukulele: …} {define-ukelele: …}
//      {define-piano: C keys 0 4 7}   semitonos desde el Do más grave
//    Solo valen en el tono original: al transportar, el acorde es otro.
// 2. La base de datos @tombatossals/chords-db (MIT), servida en
//    static/vendor/chords-db/. Las de ChordSheetJS no valen: su Do es
//    x-3-2-0-3-3 y le faltan Dsus4, Si♭ o La♭m.
// 3. Piano: las notas salen de la fórmula del acorde.
//
// Los SVG usan currentColor: sirven igual en claro, en oscuro y en papel.

const NOTAS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

function claseDeAltura(nota) {
  const m = /^([A-G])([#b♯♭]?)/.exec(nota || "");
  if (!m) return null;
  const alt = { "#": 1, "♯": 1, b: -1, "♭": -1 }[m[2]] || 0;
  return (NOTAS[m[1]] + alt + 12) % 12;
}

// --- Nombre del acorde ------------------------------------------------------

// Sufijo tal como se escribe en una canción → sufijo de chords-db.
const ALIAS = {
  "": "major", M: "major", maj: "major",
  m: "minor", min: "minor", "-": "minor",
  "7": "7", maj7: "maj7", M7: "maj7", "Δ": "maj7", "Δ7": "maj7",
  m7: "m7", min7: "m7", "-7": "m7",
  sus: "sus4", sus4: "sus4", sus2: "sus2", "7sus4": "7sus4", "7sus": "7sus4",
  dim: "dim", "°": "dim", dim7: "dim7", "°7": "dim7",
  aug: "aug", "+": "aug",
  "6": "6", m6: "m6", "9": "9", m9: "m9", maj9: "maj9",
  add9: "add9", add2: "add9", madd9: "madd9",
  m7b5: "m7b5", "ø": "m7b5", "ø7": "m7b5",
  "11": "11", "13": "13", "69": "69", "6/9": "69", mmaj7: "mmaj7",
};

function analizar(nombre) {
  const m = /^([A-G][#b♯♭]?)([^/]*)(?:\/([A-G][#b♯♭]?))?$/.exec((nombre || "").trim());
  if (!m) return null;
  const sufijo = m[2];
  return {
    raiz: claseDeAltura(m[1]),
    sufijo: ALIAS[sufijo] !== undefined ? ALIAS[sufijo] : sufijo,
    bajo: m[3] ? claseDeAltura(m[3]) : null,
  };
}

// --- Definiciones propias de la canción --------------------------------------

const INSTRUMENTO_DE_SELECTOR = {
  guitar: "guitarra", guitarra: "guitarra",
  ukulele: "ukelele", ukelele: "ukelele", uke: "ukelele",
  piano: "piano", keyboard: "piano", teclado: "piano",
};

function leerDefiniciones(texto) {
  const defs = { guitarra: {}, ukelele: {}, piano: {} };
  const re = /\{\s*define(?:-([a-z]+))?\s*:\s*([^}]*)\}/gi;
  let m;
  while ((m = re.exec(texto || ""))) {
    const partes = m[2].trim().split(/\s+/);
    const nombre = partes.shift();
    if (!nombre) continue;
    const i = (k) => partes.indexOf(k);
    if (i("keys") >= 0) {
      const teclas = partes.slice(i("keys") + 1).map(Number).filter((n) => !Number.isNaN(n));
      if (teclas.length) defs.piano[nombre] = { teclas };
      continue;
    }
    if (i("frets") < 0) continue;
    const fin = i("fingers") >= 0 ? i("fingers") : partes.length;
    const trastes = partes.slice(i("frets") + 1, fin).map((v) => (/^[xXN-]$/.test(v) ? -1 : Number(v)));
    const dedos = i("fingers") >= 0 ? partes.slice(i("fingers") + 1).map((v) => Number(v) || 0) : [];
    const base = i("base-fret") >= 0 ? Number(partes[i("base-fret") + 1]) || 1 : 1;
    const inst = m[1]
      ? INSTRUMENTO_DE_SELECTOR[m[1].toLowerCase()]
      : trastes.length === 4 ? "ukelele" : trastes.length === 6 ? "guitarra" : null;
    if (inst && inst !== "piano") defs[inst][nombre] = { frets: trastes, fingers: dedos, baseFret: base, barres: [] };
  }
  return defs;
}

// --- Base de datos -------------------------------------------------------------

const cargas = {};
function cargarBase(url) {
  if (!cargas[url]) {
    cargas[url] = fetch(url)
      .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(indexar);
  }
  return cargas[url];
}

// {altura: {sufijo: [posiciones]}}. Las claves del JSON no son homogéneas
// (guitarra usa "Csharp", ukelele "Db"): se indexa por altura.
function indexar(db) {
  const indice = {};
  Object.values(db.chords).forEach((lista) => {
    lista.forEach((acorde) => {
      const h = claseDeAltura(acorde.key);
      (indice[h] = indice[h] || {})[acorde.suffix] = acorde.positions;
    });
  });
  return indice;
}

const NOMBRES_BAJO = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B"];
const NOMBRES_BAJO_B = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "A#", "B"];

function posicionDeBase(indice, a) {
  const porSufijo = indice[a.raiz];
  if (!porSufijo) return null;
  if (a.bajo !== null) {
    const prefijo = a.sufijo === "minor" ? "m/" : a.sufijo === "major" ? "/" : null;
    if (prefijo) {
      for (const n of [NOMBRES_BAJO[a.bajo], NOMBRES_BAJO_B[a.bajo]]) {
        const p = porSufijo[prefijo + n];
        if (p && p.length) return p[0];
      }
    }
  }
  const p = porSufijo[a.sufijo];
  return p && p.length ? p[0] : null;
}

// --- Piano ---------------------------------------------------------------------

const FORMULAS = {
  major: [0, 4, 7], minor: [0, 3, 7], "7": [0, 4, 7, 10], maj7: [0, 4, 7, 11],
  m7: [0, 3, 7, 10], sus2: [0, 2, 7], sus4: [0, 5, 7], "7sus4": [0, 5, 7, 10],
  dim: [0, 3, 6], dim7: [0, 3, 6, 9], aug: [0, 4, 8], "6": [0, 4, 7, 9],
  m6: [0, 3, 7, 9], "9": [0, 4, 7, 10, 14], m9: [0, 3, 7, 10, 14],
  maj9: [0, 4, 7, 11, 14], add9: [0, 4, 7, 14], madd9: [0, 3, 7, 14],
  m7b5: [0, 3, 6, 10], "69": [0, 4, 7, 9, 14], mmaj7: [0, 3, 7, 11],
  "11": [0, 4, 7, 10, 14, 17], "13": [0, 4, 7, 10, 14, 21],
};

// Teclas (semitonos desde el Do más grave del dibujo, 0–23) de un acorde.
function teclasPiano(a) {
  const formula = FORMULAS[a.sufijo];
  if (!formula) return null;
  let teclas = formula.map((i) => a.raiz + i);
  if (a.bajo !== null) {
    // Bajo abajo; el acorde encima, por encima del bajo.
    const bajo = a.bajo;
    teclas = teclas.map((t) => (t <= bajo ? t + 12 : t));
    teclas.unshift(bajo);
  }
  while (Math.max(...teclas) > 23) teclas = teclas.map((t) => t - 12);
  if (Math.min(...teclas) < 0) teclas = teclas.map((t) => t + 12);
  return teclas.filter((t) => t >= 0 && t <= 23);
}

// --- Dibujo --------------------------------------------------------------------

function svgTrastes(pos, cuerdas) {
  const ancho = 72, alto = 92, izq = 12, arriba = 18;
  const sep = (ancho - izq - 6) / (cuerdas - 1);
  const filas = Math.max(4, ...pos.frets.filter((f) => f > 0));
  const alturaTraste = (alto - arriba - 6) / filas;
  const x = (c) => izq + c * sep;
  const y = (t) => arriba + t * alturaTraste;
  const partes = [];
  for (let c = 0; c < cuerdas; c++) partes.push(`<line x1="${x(c)}" y1="${y(0)}" x2="${x(c)}" y2="${y(filas)}" stroke="currentColor" stroke-width="1"/>`);
  for (let t = 0; t <= filas; t++) {
    const grueso = t === 0 && pos.baseFret <= 1 ? 3 : 1;
    partes.push(`<line x1="${x(0)}" y1="${y(t)}" x2="${x(cuerdas - 1)}" y2="${y(t)}" stroke="currentColor" stroke-width="${grueso}"/>`);
  }
  if (pos.baseFret > 1) partes.push(`<text x="${izq - 3}" y="${y(0.5) + 3}" font-size="8" text-anchor="end" fill="currentColor">${pos.baseFret}</text>`);
  (pos.barres || []).forEach((b) => {
    const cs = pos.frets.map((f, i) => (f === b ? i : -1)).filter((i) => i >= 0);
    if (cs.length > 1) {
      const yc = y(b - 0.5);
      partes.push(`<line x1="${x(cs[0])}" y1="${yc}" x2="${x(cs[cs.length - 1])}" y2="${yc}" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>`);
    }
  });
  pos.frets.forEach((f, c) => {
    if (f < 0) partes.push(`<text x="${x(c)}" y="${arriba - 5}" font-size="9" text-anchor="middle" fill="currentColor">×</text>`);
    else if (f === 0) partes.push(`<circle cx="${x(c)}" cy="${arriba - 8}" r="3" fill="none" stroke="currentColor" stroke-width="1"/>`);
    else {
      partes.push(`<circle cx="${x(c)}" cy="${y(f - 0.5)}" r="4.6" fill="currentColor"/>`);
      const dedo = pos.fingers && pos.fingers[c];
      if (dedo) partes.push(`<text x="${x(c)}" y="${y(f - 0.5) + 2.8}" font-size="7" text-anchor="middle" class="cpd-dedo">${dedo}</text>`);
    }
  });
  return `<svg viewBox="0 0 ${ancho} ${alto}" width="${ancho}" height="${alto}" role="img">${partes.join("")}</svg>`;
}

// Teclado de dos octavas; las teclas del acorde en color de acento y el bajo
// de un acorde con barra (C/E) marcado con un punto.
function svgPiano(teclas, bajo) {
  const blancas = [0, 2, 4, 5, 7, 9, 11];
  const negras = { 1: 0, 3: 1, 6: 3, 8: 4, 10: 5 };  // semitono → blanca a su izquierda
  const bw = 8, bh = 44, nw = 5, nh = 27, n = 14;
  const acento = "var(--cpd-acento, #2563eb)";
  const partes = [];
  const pulsadas = new Set(teclas);
  for (let i = 0; i < n; i++) {
    const semitono = Math.floor(i / 7) * 12 + blancas[i % 7];
    const on = pulsadas.has(semitono);
    partes.push(`<rect x="${i * bw}" y="0" width="${bw}" height="${bh}" fill="${on ? acento : "none"}" stroke="currentColor" stroke-width="0.8"/>`);
    if (on && semitono === bajo) partes.push(`<circle cx="${i * bw + bw / 2}" cy="${bh - 6}" r="2" class="cpd-dedo"/>`);
  }
  for (let oct = 0; oct < 2; oct++) {
    Object.keys(negras).forEach((s) => {
      const semitono = oct * 12 + Number(s);
      const x = (oct * 7 + negras[s]) * bw + bw - nw / 2;
      partes.push(`<rect x="${x}" y="0" width="${nw}" height="${nh}" fill="${pulsadas.has(semitono) ? acento : "currentColor"}" stroke="currentColor" stroke-width="0.6"/>`);
    });
  }
  return `<svg viewBox="-1 -1 ${n * bw + 2} ${bh + 2}" width="${n * bw + 2}" height="${bh + 2}" role="img">${partes.join("")}</svg>`;
}

function escapar(t) {
  return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// HTML de un diagrama. `indice` es la base cargada del instrumento (null en
// piano); `defs` las de la canción, solo en el tono original.
function diagrama(nombre, instrumento, indice, defs) {
  const a = analizar(nombre);
  let svg = null;
  if (instrumento === "piano") {
    const propia = defs && defs.piano[nombre];
    const teclas = propia ? propia.teclas : a && teclasPiano(a);
    if (teclas) svg = svgPiano(teclas, propia || !a ? null : a.bajo);
  } else {
    const cuerdas = instrumento === "ukelele" ? 4 : 6;
    const propia = defs && defs[instrumento][nombre];
    const pos = propia || (a && indice ? posicionDeBase(indice, a) : null);
    if (pos && pos.frets.length === cuerdas) svg = svgTrastes(pos, cuerdas);
  }
  const titulo = `<figcaption>${escapar(nombre)}</figcaption>`;
  return svg
    ? `<figure class="cpd">${titulo}${svg}</figure>`
    : `<figure class="cpd cpd-sin">${titulo}<span>sin diagrama</span></figure>`;
}

export { leerDefiniciones, cargarBase, diagrama, analizar, teclasPiano };
