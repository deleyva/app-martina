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
import { leerDefiniciones, cargarBase, diagrama } from "./diagramas_acordes.js";

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

// Cómo se escribe cada clase de altura en una tonalidad de bemoles o de
// sostenidos. La grafía no se le deja a ChordSheetJS: forzándole "#" escribe
// Do como Si# y Fa como Mi# (Sol +5 salía «B# Am E# G»), y sin forzar mezcla
// (Sol −1 salía «Gb Ebm B Db» en vez de Fa# mayor). Con la tabla, las notas
// naturales son siempre naturales.
const GRAFIA = {
  b: ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"],
  "#": ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
};

function reescribir(nombre, alteracion) {
  const tabla = GRAFIA[alteracion];
  const nota = (raiz) => tabla[claseDeAltura(raiz)] ?? raiz;
  return nombre.replace(/^([A-G][#b]?)(.*?)(?:\/([A-G][#b]?))?$/, (_, raiz, resto, bajo) =>
    nota(raiz) + resto + (bajo ? "/" + nota(bajo) : ""));
}

// `normalizeChords: false` respeta la grafía del autor: sin ello «Dsus4» sale
// como «Dsus».
const FORMATO = { normalizeChords: false };

// HTML de la canción transpuesta `semitonos` (positivo sube, negativo baja).
function aHtml(cancion, semitonos) {
  const pasos = acotar(semitonos || 0);
  if (!pasos) return new HtmlDivFormatter(FORMATO).format(cancion);
  const html = new HtmlDivFormatter(FORMATO).format(cancion.transpose(pasos));
  const alteracion = alteracionPara(cancion, pasos);
  if (!alteracion) return html;
  // El texto del acorde ya viene escapado y sin etiquetas dentro del span.
  return html.replace(/(class="chord">)([^<]+)(<)/g, (_, a, nombre, c) => a + reescribir(nombre, alteracion) + c);
}

function etiquetaTono(semitonos) {
  if (!semitonos) return "Tono original";
  const signo = semitonos > 0 ? "+" : "";
  const unidad = Math.abs(semitonos) === 1 ? " semitono" : " semitonos";
  return signo + semitonos + unidad;
}

// Acordes distintos de la canción, en orden de aparición y con la misma
// grafía que la letra transpuesta.
function acordes(cancion, semitonos) {
  const pasos = acotar(semitonos || 0);
  if (!pasos) return cancion.getChords();
  const alteracion = alteracionPara(cancion, pasos);
  const vistos = [];
  cancion.transpose(pasos).getChords().forEach((c) => {
    const nombre = alteracion ? reescribir(c, alteracion) : c;
    if (!vistos.includes(nombre)) vistos.push(nombre);
  });
  return vistos;
}

// Tira de diagramas. Las {define} de la canción solo valen en el tono
// original: al transportar, el acorde es otro.
function diagramasHtml(nombres, instrumento, indice, defs, semitonos) {
  const propias = semitonos ? null : defs;
  return nombres.map((n) => diagrama(n, instrumento, indice, propias)).join("");
}

// Monta la tira de diagramas y su selector de instrumento. Lo usan el artículo
// y la pantalla completa; cada uno pone su HTML y llama a `refrescar()` al
// transportar.
//   tira       elemento donde van los diagramas
//   selector   <select> con valores "" (ocultos), guitarra, ukelele, piano
//   texto      el ChordPro original (para leer sus {define})
//   cancion    la canción ya parseada
//   urls       {guitarra, ukelele}: JSON de chords-db servidos por Django
//   semitonos  función que devuelve el transporte actual
const CLAVE_INSTRUMENTO = "cp-instrumento";

function montarDiagramas({ tira, selector, texto, cancion, urls, semitonos }) {
  const defs = leerDefiniciones(texto);
  let instrumento = "";
  try { instrumento = localStorage.getItem(CLAVE_INSTRUMENTO) || ""; } catch (e) { /* sin almacenamiento */ }
  if (![...selector.options].some((o) => o.value === instrumento)) instrumento = "";
  selector.value = instrumento;

  let turno = 0;  // descarta respuestas viejas si se cambia deprisa
  function refrescar() {
    const mio = ++turno;
    if (!instrumento) { tira.hidden = true; tira.innerHTML = ""; return; }
    const pasos = acotar(semitonos() || 0);
    const pintar = (indice) => {
      if (mio !== turno) return;
      tira.innerHTML = diagramasHtml(acordes(cancion, pasos), instrumento, indice, defs, pasos);
      tira.hidden = false;
    };
    if (instrumento === "piano") { pintar(null); return; }
    cargarBase(urls[instrumento]).then(pintar).catch((e) => {
      console.error("Diagramas:", e);
      if (mio === turno) { tira.textContent = "No se pudieron cargar los diagramas."; tira.hidden = false; }
    });
  }
  selector.addEventListener("change", () => {
    instrumento = selector.value;
    try { localStorage.setItem(CLAVE_INSTRUMENTO, instrumento); } catch (e) { /* sin almacenamiento */ }
    refrescar();
  });
  refrescar();
  return refrescar;
}

window.ChordPro = {
  LIMITE, acotar, parsear, aHtml, etiquetaTono,
  acordes, leerDefiniciones, cargarBase, diagramasHtml, montarDiagramas,
};
