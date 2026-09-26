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
//   texto      el ChordPro original (para leer sus {define}), o una función
//              que lo devuelva: tras editar la letra, el texto cambia
//   cancion    la canción ya parseada, o una función que la devuelva
//   urls       {guitarra, ukelele}: JSON de chords-db servidos por Django
//   semitonos  función que devuelve el transporte actual
const CLAVE_INSTRUMENTO = "cp-instrumento";

function montarDiagramas({ tira, selector, texto, cancion, urls, semitonos }) {
  const leer = (v) => (typeof v === "function" ? v() : v);
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
      tira.innerHTML = diagramasHtml(acordes(leer(cancion), pasos), instrumento, indice,
                                     leerDefiniciones(leer(texto)), pasos);
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

// Editor de la letra: ventana con el texto a la izquierda y la vista previa a
// la derecha. No guarda si el ChordPro no se puede leer. Estilos en línea
// porque se abre igual en el artículo (Tailwind) y en los visores (sin él).
//   texto      ChordPro actual
//   url        POST que guarda (musica:guardar_chordpro)
//   csrf       token CSRF de la página
//   alGuardar  recibe el texto guardado y la respuesta del servidor
function abrirEditor({ texto, url, csrf, alGuardar }) {
  const fondo = document.createElement("div");
  fondo.setAttribute("data-editor-chordpro", "");
  fondo.style.cssText = "position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:16px;";
  fondo.innerHTML = `
    <div style="background:#fff;color:#111;border-radius:12px;width:min(1200px,100%);height:min(90vh,900px);display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.4);font:14px system-ui,sans-serif;overflow:hidden;">
      <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #e5e7eb;">
        <strong style="margin-right:auto;">✎ Editar la letra con acordes</strong>
        <span data-estado style="font-size:12px;color:#6b7280;"></span>
        <button type="button" data-cancelar style="padding:6px 12px;border-radius:6px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">Cancelar</button>
        <button type="button" data-guardar style="padding:6px 14px;border-radius:6px;border:0;background:#2563eb;color:#fff;font-weight:600;cursor:pointer;">Guardar</button>
      </div>
      <div data-cuerpo style="display:flex;flex:1 1 0;min-height:0;">
        <textarea data-texto spellcheck="false" style="flex:1 1 0;min-width:0;min-height:0;border:0;border-right:1px solid #e5e7eb;padding:12px;font:13px/1.5 ui-monospace,Menlo,monospace;resize:none;outline:none;color:#111;background:#fafafa;"></textarea>
        <div style="flex:1 1 0;min-width:0;min-height:0;overflow:auto;padding:12px;">
          <p data-error style="display:none;color:#b91c1c;margin:0 0 8px;"></p>
          <div data-previa class="chordpro-sheet cpv-salida" style="font-size:14px;"></div>
        </div>
      </div>
      <div style="padding:6px 14px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;">
        Acordes entre corchetes antes de la sílaba: <code>[G]I found a [Em]love</code>. Secciones: <code>{start_of_verse: Estrofa}</code> … <code>{end_of_verse}</code>, igual con <code>chorus</code>. Comentarios: <code>{comment: …}</code>. Digitaciones: <code>{define-ukelele: G base-fret 1 frets 0 2 3 2}</code>.
        Guardar: Ctrl/⌘+S · Cancelar: Esc.
      </div>
    </div>`;
  const area = fondo.querySelector("[data-texto]");
  const previa = fondo.querySelector("[data-previa]");
  const error = fondo.querySelector("[data-error]");
  const estado = fondo.querySelector("[data-estado]");
  const botonGuardar = fondo.querySelector("[data-guardar]");
  area.value = texto || "";
  // Estrecho (móvil, tablet en vertical): texto arriba y vista previa abajo.
  // Sin límite de alto en cada mitad, la previa empujaba la barra de Guardar
  // fuera del cuadro.
  if (window.innerWidth < 760) fondo.querySelector("[data-cuerpo]").style.flexDirection = "column";
  let valido = true;
  const original = area.value;

  function refrescar() {
    try {
      previa.innerHTML = aHtml(parsear(area.value), 0);
      error.style.display = "none";
      valido = true;
    } catch (e) {
      error.textContent = e.message;
      error.style.display = "block";
      valido = false;
    }
    botonGuardar.disabled = !valido;
    botonGuardar.style.opacity = valido ? "1" : ".5";
  }
  function cerrar() {
    if (area.value !== original && !window.confirm("¿Descartar los cambios?")) return;
    document.removeEventListener("keydown", teclas, true);
    fondo.remove();
  }
  function guardar() {
    if (!valido) return;
    botonGuardar.disabled = true;
    estado.textContent = "Guardando…";
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ chordpro: area.value }),
    })
      .then((r) => (r.ok ? r.json() : r.text().then((t) => { throw new Error(t || "HTTP " + r.status); })))
      .then((d) => {
        document.removeEventListener("keydown", teclas, true);
        fondo.remove();
        if (alGuardar) alGuardar(d.chordpro, d);
      })
      .catch((e) => {
        estado.textContent = "No se pudo guardar: " + e.message;
        botonGuardar.disabled = false;
      });
  }
  // En fase de captura y parando la propagación: los visores tienen teclas
  // propias (+, -, espacio, flechas) que no deben dispararse al escribir.
  function teclas(e) {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cerrar(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); e.stopPropagation(); guardar(); return; }
    if (fondo.contains(e.target)) e.stopPropagation();
  }
  document.addEventListener("keydown", teclas, true);
  area.addEventListener("input", refrescar);
  fondo.querySelector("[data-cancelar]").addEventListener("click", cerrar);
  botonGuardar.addEventListener("click", guardar);
  document.body.appendChild(fondo);
  refrescar();
  area.focus({ preventScroll: true });
}

window.ChordPro = {
  LIMITE, acotar, parsear, aHtml, etiquetaTono,
  acordes, leerDefiniciones, cargarBase, diagramasHtml, montarDiagramas, abrirEditor,
};
