// Letra con acordes (ChordPro): el único sitio que sabe pintarla.
//
// Lo usan el artículo de la canción (`musica/recurso.html`) y el visor de
// sesiones de clase y de estudio (`my_library/viewers/chordpro_viewer.html`).
// Antes vivía en línea dentro del artículo; si los dos visores llevaran su
// propia copia, el escape de abajo acabaría estando en una sí y en otra no.
//
// El texto se guarda SIN transponer. Transponer es una vista, no otro dato que
// mantener, así que se hace aquí, en el navegador, cada vez que se pinta.

import { ChordProParser, HtmlDivFormatter } from "chordsheetjs";

// Más de una octava arriba o abajo vuelve al mismo sitio: no aporta nada.
const LIMITE = 11;

// HtmlDivFormatter NO escapa la letra, y el resultado entra por innerHTML. Sin
// esto, un `<img src=x onerror=...>` escrito en el campo se ejecutaría para
// todo el que abra la página. Escapando antes de parsear, el formatter emite
// entidades e innerHTML las devuelve como texto literal.
function escaparHtml(texto) {
  return texto
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function acotar(semitonos) {
  return Math.max(-LIMITE, Math.min(LIMITE, semitonos));
}

// Devuelve la canción parseada o lanza con un mensaje legible.
function parsear(texto) {
  try {
    return new ChordProParser().parse(escaparHtml(texto || ""));
  } catch (e) {
    throw new Error("La letra tiene un error de formato ChordPro: " + e.message);
  }
}

// Clase de altura (0 = Do) de la nota con la que empieza un nombre de acorde
// o de tonalidad: «G», «Ab», «F#m» → 7, 8, 6.
const NOTAS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
function claseDeAltura(nombre) {
  const m = /^([A-G])([#b♯♭]?)/.exec(nombre || "");
  if (!m) return null;
  const alteracion = { "#": 1, "♯": 1, b: -1, "♭": -1 }[m[2]] || 0;
  return (NOTAS[m[1]] + alteracion + 12) % 12;
}

// Tónica de la canción: la directiva {key: …} si la hay; si no, el primer
// acorde, que en casi todo el repertorio de clase es la tónica.
function tonica(cancion) {
  const clave = cancion.key;
  if (clave) return { altura: claseDeAltura(clave), menor: /m(?!aj)/.test(clave.slice(1)) };
  for (const linea of cancion.lines) {
    for (const item of linea.items) {
      if (item.chords) {
        return { altura: claseDeAltura(item.chords), menor: /^[A-G][#b]?m(?!aj)/.test(item.chords) };
      }
    }
  }
  return null;
}

// Las tonalidades mayores que se escriben con bemoles: Fa, Si♭, Mi♭, La♭, Re♭.
// Sin esto, subir medio tono desde Sol da «G# Fm C# D#» cuando el disco de
// Perfect está en La♭ y en el aula se lee «A♭ Fm D♭ E♭».
const MAYORES_CON_BEMOLES = new Set([5, 10, 3, 8, 1]);

function alteracionPara(cancion, pasos) {
  const t = tonica(cancion);
  if (!t || t.altura === null) return null;
  // Una tonalidad menor se escribe como su relativo mayor.
  const mayor = (t.altura + pasos + (t.menor ? 3 : 0) + 120) % 12;
  return MAYORES_CON_BEMOLES.has(mayor) ? "b" : "#";
}

// `normalizeChords: false` respeta la grafía del autor: sin ello «Dsus4» sale
// como «Dsus».
const FORMATO = { normalizeChords: false };

// HTML de la canción transpuesta `semitonos` (positivo sube, negativo baja).
function aHtml(cancion, semitonos) {
  const pasos = acotar(semitonos || 0);
  const vista = pasos
    ? cancion.transpose(pasos, { accidental: alteracionPara(cancion, pasos) })
    : cancion;
  return new HtmlDivFormatter(FORMATO).format(vista);
}

function etiquetaTono(semitonos) {
  if (!semitonos) return "Tono original";
  const signo = semitonos > 0 ? "+" : "";
  const unidad = Math.abs(semitonos) === 1 ? " semitono" : " semitonos";
  return signo + semitonos + unidad;
}

window.ChordPro = { LIMITE, acotar, parsear, aHtml, etiquetaTono };
