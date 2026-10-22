// Patrones de batería con iconos (fase 75, 2026-10-09).
//
// Un patrón es texto dentro del ChordPro de la canción:
//
//   {start_of_ritmo: Rock básico · estrofa}
//   compás: 4/4
//   tempo: 90
//   SH: x x x x x x x x
//   CA: . . x . . . x .
//   BO: x . . . x x . .
//   {end_of_ritmo}
//
// `x` golpe, `X` acento, `.` o `-` silencio; los espacios y `|` no cuentan.
// Desde la fase 80 (2026-10-22) el mismo bloque lleva el acompañamiento,
// alineado con la batería: `GU` guitarra o ukelele (`v` abajo, `V` abajo con
// acento, `^` arriba, `x` rasgueo apagado), `BA` bajo, `MD` y `MI` las dos
// manos del piano (con `x`, `X` y `.` como la batería).
// La subdivisión sale de cuántos golpes caben en el compás. ChordSheetJS deja
// el bloque como `.paragraph.ritmo` con una fila de texto por línea; aquí se
// lee ese texto y se cambia por una rejilla SVG con iconos propios (no los de
// MusicWill), la cuenta encima y un ▶ que lo toca con sonidos sintetizados.
//
// `parsearRitmo` es puro (sin DOM): lo usan los tests y la skill PublishIES
// para validar un bloque antes de publicar.

// Una sola tabla de voces: icono de batería, icono del cuerpo y sonido.
// Equivalencia con el cuerpo decidida por Jesús el 2026-10-09.
export const VOCES = {
  SH: { bateria: "Charles", cuerpo: "Palmada en el muslo", color: "#0891b2" },
  CA: { bateria: "Caja", cuerpo: "Palmada", color: "#c2410c" },
  BO: { bateria: "Bombo", cuerpo: "Pisotón", color: "#4338ca" },
  // Acompañamiento (fase 80): no tiene equivalente en el cuerpo, así que el
  // texto es el mismo en los dos modos. Solo GU admite flechas de rasgueo.
  GU: { bateria: "Guitarra / ukelele", cuerpo: "Guitarra / ukelele", color: "#b45309", rasgueo: true },
  BA: { bateria: "Bajo", cuerpo: "Bajo", color: "#15803d" },
  MD: { bateria: "Piano mano derecha", cuerpo: "Piano mano derecha", color: "#7c3aed" },
  MI: { bateria: "Piano mano izquierda", cuerpo: "Piano mano izquierda", color: "#be185d" },
};
const ORDEN = ["SH", "CA", "BO", "GU", "BA", "MD", "MI"];
const BATERIA = new Set(["SH", "CA", "BO"]);

// Compases admitidos: cuántos pulsos y en cuántas partes se puede dividir
// cada pulso, con la cuenta en voz alta (decidida por Jesús el 2026-10-09).
const COMPASES = {
  "4/4": { pulsos: 4, partes: [1, 2, 4] },
  "3/4": { pulsos: 3, partes: [1, 2, 4] },
  "2/4": { pulsos: 2, partes: [1, 2, 4] },
  "12/8": { pulsos: 4, partes: [3] },
  "6/8": { pulsos: 2, partes: [3] },
};
const SILABAS = { 1: [""], 2: ["", "y"], 3: ["", "y", "a"], 4: ["", "e", "y", "a"] };

// Códigos de golpe: 0 silencio, 1 golpe, 2 acento; y solo en GU, 3 rasgueo
// hacia abajo, 4 abajo con acento, 5 hacia arriba. Los bloques de batería de
// antes de la fase 80 siguen siendo 0/1/2 exactamente igual.
const GOLPE = { x: 1, X: 2, ".": 0, "-": 0, v: 3, V: 4, "^": 5 };
const ACENTO = new Set([2, 4]);
const RASGUEO = new Set([3, 4, 5]);

// Texto del bloque (sin las directivas start/end) → patrón o errores.
// Nunca lanza: lo inválido vuelve como `errores` para enseñarlo en el bloque.
export function parsearRitmo(texto) {
  const errores = [];
  let compas = "4/4";
  let tempo = 80;
  const voces = [];
  for (const cruda of String(texto || "").split("\n")) {
    const linea = cruda.trim();
    if (!linea) continue;
    const m = /^([^:]+):\s*(.*)$/.exec(linea);
    if (!m) { errores.push(`No entiendo la línea «${linea}»`); continue; }
    const clave = m[1].trim();
    const valor = m[2].trim();
    const normal = clave.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    if (normal === "compas") {
      if (COMPASES[valor]) compas = valor;
      else errores.push(`Compás «${valor}» no admitido (vale ${Object.keys(COMPASES).join(", ")})`);
      continue;
    }
    if (normal === "tempo") {
      const n = parseInt(valor, 10);
      if (n >= 30 && n <= 240) tempo = n;
      else errores.push(`Tempo «${valor}» fuera de rango (30-240)`);
      continue;
    }
    const voz = clave.toUpperCase();
    if (!VOCES[voz]) { errores.push(`Voz «${clave}» desconocida (vale ${ORDEN.join(", ")})`); continue; }
    if (voces.some((v) => v.voz === voz)) { errores.push(`La voz ${voz} está dos veces`); continue; }
    const golpes = [];
    const rasgueo = !!VOCES[voz].rasgueo;
    for (const c of valor.replace(/[\s|]/g, "")) {
      if (!(c in GOLPE)) {
        errores.push(`Símbolo «${c}» en ${voz}: usa ${rasgueo ? "v, V, ^, x o ." : "x, X o ."}`);
        break;
      }
      if (RASGUEO.has(GOLPE[c]) && !rasgueo) {
        errores.push(`Las flechas v, V y ^ solo valen en GU (están en ${voz})`);
        break;
      }
      golpes.push(GOLPE[c]);
    }
    voces.push({ voz, golpes });
  }
  if (!voces.length) errores.push(`El ritmo no tiene ninguna voz (${ORDEN.join(", ")})`);
  const pasos = voces.length ? voces[0].golpes.length : 0;
  if (voces.some((v) => v.golpes.length !== pasos)) {
    errores.push(`Las voces no miden lo mismo: ${voces.map((v) => `${v.voz} ${v.golpes.length}`).join(", ")}`);
  }
  const { pulsos, partes } = COMPASES[compas];
  const porPulso = pasos / pulsos;
  if (pasos && !partes.includes(porPulso)) {
    const validos = partes.map((p) => p * pulsos).join(" o ");
    errores.push(`En ${compas} cada voz tiene que tener ${validos} golpes (tiene ${pasos})`);
  }
  voces.sort((a, b) => ORDEN.indexOf(a.voz) - ORDEN.indexOf(b.voz));
  return { compas, tempo, pulsos, porPulso, pasos, voces, errores };
}

// La cuenta de cada paso: «1 y 2 y …», «1 e y a …», «1 y a 2 y a …».
export function cuenta(patron) {
  const silabas = SILABAS[patron.porPulso] || [""];
  const fuera = [];
  for (let p = 0; p < patron.pulsos; p++) {
    silabas.forEach((s, i) => fuera.push(i === 0 ? String(p + 1) : s));
  }
  return fuera;
}

// --- Iconos (viewBox 0 0 40 40, currentColor) --------------------------------

const ICONOS = {
  bateria: {
    // Dos platos del charles sobre su soporte.
    SH: '<path d="M20 12 V36" stroke-width="2.5"/><ellipse cx="20" cy="12" rx="15" ry="3.6" fill="currentColor" stroke="none"/><ellipse cx="20" cy="17.5" rx="15" ry="3.6" fill="none" stroke-width="2.5"/><path d="M13 36 H27" stroke-width="2.5"/>',
    // Caja vista de lado, con su bordonera.
    CA: '<ellipse cx="20" cy="13" rx="15" ry="5" fill="none" stroke-width="2.5"/><path d="M5 13 V27 A15 5 0 0 0 35 27 V13" fill="none" stroke-width="2.5"/><path d="M9 17.5 L13 26 L17 18.5 L21 27 L25 18.5 L29 26 L32 18" fill="none" stroke-width="2"/>',
    // Bombo de frente.
    BO: '<circle cx="20" cy="20" r="16" fill="none" stroke-width="3"/><circle cx="20" cy="20" r="7" fill="currentColor" stroke="none"/>',
  },
  cuerpo: {
    // Mano abierta sobre el muslo.
    SH: '<path d="M4 30 Q20 24 36 30 L36 36 L4 36 Z" fill="currentColor" stroke="none" opacity=".35"/><path d="M12 25 V12 a2 2 0 0 1 4 0 V20 V8 a2 2 0 0 1 4 0 V20 V9 a2 2 0 0 1 4 0 V21 V13 a2 2 0 0 1 4 0 V24 Q28 28 22 28 H17 Q12 28 12 25 Z" fill="currentColor" stroke="none"/>',
    // Dos manos en «ʌ» que se tocan solo por la punta, pulgares hacia fuera
    // y el golpe arriba: a 30 px una mancha única no se leía como palmada.
    CA: '<g transform="rotate(24 11 37)"><rect x="7" y="14" width="8" height="23" rx="4" fill="currentColor" stroke="none"/><rect x="2.5" y="25" width="5" height="9" rx="2.5" fill="currentColor" stroke="none" transform="rotate(-30 5 34)"/></g><g transform="rotate(-24 29 37)"><rect x="25" y="14" width="8" height="23" rx="4" fill="currentColor" stroke="none"/><rect x="32.5" y="25" width="5" height="9" rx="2.5" fill="currentColor" stroke="none" transform="rotate(30 35 34)"/></g><path d="M20 1.5 V6 M12.5 4 L15 7.5 M27.5 4 L25 7.5" stroke-width="2.5"/>',
    // Zapato que pisa, con el golpe en el suelo.
    BO: '<path d="M6 30 V14 a4 4 0 0 1 8 0 V20 Q24 21 32 26 Q35 28 34 31 H6 Z" fill="currentColor" stroke="none"/><path d="M3 36 H37" stroke-width="2.5"/><path d="M8 38.5 L5 40 M20 38.5 V40 M32 38.5 L35 40" stroke-width="2"/>',
  },
};

// Acompañamiento (fase 80): el mismo icono en los dos modos.
// Mano con cuatro dedos y pulgar, sobre un teclado; la izquierda es la misma
// mano reflejada.
const MANO = '<path d="M13 24 V11 a2 2 0 0 1 4 0 V19 V7 a2 2 0 0 1 4 0 V19 V8 a2 2 0 0 1 4 0 V20 V12 a2 2 0 0 1 4 0 V23 Q29 27 23 27 H18 Q13 27 13 24 Z" fill="currentColor" stroke="none"/><path d="M13 18 Q6 17 7 23 L12 26" stroke-width="3"/>';
const TECLADO = '<path d="M3 31 H37 M3 39 H37 M3 31 V39 M11.5 31 V39 M20 31 V39 M28.5 31 V39 M37 31 V39" stroke-width="1.8"/>';
const ACOMPANAMIENTO = {
  // Guitarra: caja en ocho, boca, mástil y clavijero.
  GU: '<path d="M12.5 18 a7.5 7.5 0 1 1 15 0 a9 9 0 1 1 -15 0 Z" fill="none" stroke-width="2.5"/><path d="M20 10.5 V2" stroke-width="3"/><path d="M16.5 4 H23.5" stroke-width="2.5"/><circle cx="20" cy="22" r="3.2" fill="currentColor" stroke="none"/>',
  // Bajo: mástil largo y cuerpo pequeño.
  BA: '<ellipse cx="16" cy="30" rx="10" ry="8" fill="none" stroke-width="2.5"/><path d="M26 2 V27" stroke-width="3"/><path d="M22 4.5 H30 M22 9.5 H30" stroke-width="2"/><circle cx="16" cy="30" r="2.5" fill="currentColor" stroke="none"/>',
  MD: MANO + TECLADO,
  MI: `<g transform="translate(40 0) scale(-1 1)">${MANO}</g>` + TECLADO,
};
ICONOS.bateria = { ...ICONOS.bateria, ...ACOMPANAMIENTO };
ICONOS.cuerpo = { ...ICONOS.cuerpo, ...ACOMPANAMIENTO };

// Lo que va en cada paso de GU: flecha abajo, flecha arriba o rasgueo apagado.
const PASO = {
  abajo: '<path d="M20 4 V34" stroke-width="4.5"/><path d="M9 24 L20 35 L31 24" stroke-width="4.5"/>',
  arriba: '<path d="M20 36 V6" stroke-width="4.5"/><path d="M9 16 L20 5 L31 16" stroke-width="4.5"/>',
  apagado: '<path d="M11 11 L29 29 M29 11 L11 29" stroke-width="4.5"/>',
  // Bajo: una negra.
  nota: '<ellipse cx="16" cy="29" rx="8" ry="5.5" transform="rotate(-20 16 29)" fill="currentColor" stroke="none"/><path d="M23.3 26.5 V5" stroke-width="3"/>',
};

// El trazo de un golpe concreto: para la batería, el icono de la voz (según
// el modo); para GU, la flecha; para BA, la nota; para el piano, la mano.
function trazoDe(voz, g, modo) {
  if (g === 3 || g === 4) return PASO.abajo;
  if (g === 5) return PASO.arriba;
  if (voz === "GU") return PASO.apagado;
  if (voz === "BA") return PASO.nota;
  return ICONOS[modo][voz];
}

function icono(trazo, tam, x, y, extra = "") {
  return `<g transform="translate(${x} ${y}) scale(${tam / 40})" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"${extra}>${trazo}</g>`;
}

// --- Dibujo ------------------------------------------------------------------

const CELDA = 46;      // ancho de un paso
const FILA = 50;       // alto de una voz
const ETIQUETA = 185;  // columna de la izquierda: icono + nombre («Palmada en el muslo» cabe)
const CABECERA = 30;   // fila de la cuenta

export function svgRitmo(patron, modo = "bateria") {
  const ancho = ETIQUETA + patron.pasos * CELDA;
  const alto = CABECERA + patron.voces.length * FILA;
  const partes = [];
  // Pulsos alternos sombreados: se ve dónde empieza cada pulso.
  for (let p = 0; p < patron.pulsos; p++) {
    if (p % 2) continue;
    const x = ETIQUETA + p * patron.porPulso * CELDA;
    partes.push(`<rect x="${x}" y="0" width="${patron.porPulso * CELDA}" height="${alto}" fill="currentColor" opacity=".05"/>`);
  }
  cuenta(patron).forEach((s, i) => {
    const x = ETIQUETA + i * CELDA + CELDA / 2;
    const fuerte = i % patron.porPulso === 0;
    partes.push(`<text x="${x}" y="21" text-anchor="middle" font-size="${fuerte ? 18 : 15}" font-weight="${fuerte ? 800 : 500}" fill="currentColor" opacity="${fuerte ? 1 : 0.6}">${s}</text>`);
  });
  patron.voces.forEach((v, f) => {
    const y = CABECERA + f * FILA;
    const def = VOCES[v.voz];
    partes.push(`<line x1="0" y1="${y}" x2="${ancho}" y2="${y}" stroke="currentColor" opacity=".15"/>`);
    partes.push(`<g style="color:${def.color}">${icono(ICONOS[modo][v.voz], 34, 4, y + 8)}</g>`);
    partes.push(`<text x="46" y="${y + 23}" font-size="15" font-weight="700" fill="currentColor">${v.voz}</text>`);
    partes.push(`<text x="46" y="${y + 40}" font-size="12" fill="currentColor" opacity=".7">${modo === "cuerpo" ? def.cuerpo : def.bateria}</text>`);
    v.golpes.forEach((g, i) => {
      const cx = ETIQUETA + i * CELDA;
      if (!g) {
        partes.push(`<circle cx="${cx + CELDA / 2}" cy="${y + FILA / 2}" r="2.5" fill="currentColor" opacity=".25"/>`);
        return;
      }
      // El acento, más grande y con un «>» encima.
      const acento = ACENTO.has(g);
      const tam = acento ? 42 : 32;
      const off = (CELDA - tam) / 2;
      partes.push(`<g style="color:${def.color}">${icono(trazoDe(v.voz, g, modo), tam, cx + off, y + (FILA - tam) / 2)}</g>`);
      if (acento) partes.push(`<path d="M${cx + 6} ${y + 3} L${cx + 13} ${y + 6.5} L${cx + 6} ${y + 10}" stroke="currentColor" stroke-width="2" fill="none"/>`);
    });
  });
  // Rayas de pulso por encima de todo.
  for (let p = 0; p <= patron.pulsos; p++) {
    const x = ETIQUETA + p * patron.porPulso * CELDA;
    partes.push(`<line x1="${x}" y1="${CABECERA - 4}" x2="${x}" y2="${alto}" stroke="currentColor" stroke-width="${p === 0 || p === patron.pulsos ? 2.5 : 1.5}" opacity=".5"/>`);
  }
  partes.push(`<rect class="rt-cursor" x="${ETIQUETA}" y="${CABECERA - 2}" width="${CELDA}" height="${alto - CABECERA + 2}" fill="#facc15" opacity="0" rx="4"/>`);
  // En em: crece con la letra de la canción (A+/A− del visor) hasta el ancho disponible.
  return `<svg class="rt-svg" viewBox="0 0 ${ancho} ${alto}" style="width:${(ancho / 16).toFixed(2)}em" role="img" aria-label="Patrón rítmico en ${patron.compas}" font-family="system-ui, sans-serif">${partes.join("")}</svg>`;
}

// --- Sonido (Web Audio, sin ficheros) ----------------------------------------

let audio = null;
function contexto() {
  if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
  if (audio.state === "suspended") audio.resume();
  return audio;
}

let ruidoBuffer = null;
function ruido(ctx) {
  if (!ruidoBuffer) {
    ruidoBuffer = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const d = ruidoBuffer.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  const s = ctx.createBufferSource();
  s.buffer = ruidoBuffer;
  return s;
}

function envolvente(ctx, t, volumen, dur) {
  const g = ctx.createGain();
  g.gain.setValueAtTime(volumen, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + dur);
  g.connect(ctx.destination);
  return g;
}

const SONIDOS = {
  SH(ctx, t, v) {
    const s = ruido(ctx);
    const f = ctx.createBiquadFilter();
    f.type = "highpass";
    f.frequency.value = 7000;
    s.connect(f).connect(envolvente(ctx, t, 0.35 * v, 0.05));
    s.start(t);
    s.stop(t + 0.06);
  },
  CA(ctx, t, v) {
    const s = ruido(ctx);
    const f = ctx.createBiquadFilter();
    f.type = "bandpass";
    f.frequency.value = 1800;
    s.connect(f).connect(envolvente(ctx, t, 0.8 * v, 0.16));
    s.start(t);
    s.stop(t + 0.18);
    const o = ctx.createOscillator();
    o.frequency.setValueAtTime(190, t);
    o.connect(envolvente(ctx, t, 0.35 * v, 0.08));
    o.start(t);
    o.stop(t + 0.1);
  },
  BO(ctx, t, v) {
    const o = ctx.createOscillator();
    o.frequency.setValueAtTime(140, t);
    o.frequency.exponentialRampToValueAtTime(45, t + 0.25);
    o.connect(envolvente(ctx, t, 1.0 * v, 0.3));
    o.start(t);
    o.stop(t + 0.32);
  },
  // Acompañamiento (fase 80). Todo en Mi, que es el acorde abierto de la
  // guitarra: el patrón no sabe qué acorde lleva la letra, solo cuándo suena.
  GU(ctx, t, v, g) {
    if (!RASGUEO.has(g)) {
      // Rasgueo apagado: un chasquido sin altura.
      const s = ruido(ctx);
      const f = ctx.createBiquadFilter();
      f.type = "bandpass";
      f.frequency.value = 1500;
      s.connect(f).connect(envolvente(ctx, t, 0.5 * v, 0.06));
      s.start(t);
      s.stop(t + 0.08);
      return;
    }
    // Hacia abajo, las seis cuerdas de grave a aguda; hacia arriba, las cuatro
    // agudas de aguda a grave, más corto y más flojo.
    const cuerdas = g === 5 ? CUERDAS.slice(2).reverse() : CUERDAS;
    cuerdas.forEach((f, i) => nota(ctx, t + i * 0.012, f, (g === 5 ? 0.16 : 0.22) * v, g === 5 ? 0.3 : 0.45, "triangle"));
  },
  BA(ctx, t, v) {
    nota(ctx, t, CUERDAS[0], 0.9 * v, 0.35, "sine");
    nota(ctx, t, CUERDAS[0], 0.25 * v, 0.2, "triangle");
  },
  MD(ctx, t, v) {
    [329.63, 415.3, 493.88].forEach((f) => nota(ctx, t, f, 0.28 * v, 0.5, "sine"));
  },
  MI(ctx, t, v) {
    [82.41, 164.81].forEach((f) => nota(ctx, t, f, 0.5 * v, 0.5, "sine"));
  },
};

// Mi mayor abierto en la guitarra, de la sexta a la primera cuerda.
const CUERDAS = [82.41, 123.47, 164.81, 207.65, 246.94, 329.63];

function nota(ctx, t, frecuencia, volumen, dur, tipo) {
  const o = ctx.createOscillator();
  o.type = tipo;
  o.frequency.setValueAtTime(frecuencia, t);
  o.connect(envolvente(ctx, t, volumen, dur));
  o.start(t);
  o.stop(t + dur + 0.02);
}

// Un solo patrón sonando a la vez en toda la página.
let sonando = null;

function parar() {
  if (!sonando) return;
  clearInterval(sonando.reloj);
  sonando.cursor.setAttribute("opacity", "0");
  sonando.boton.textContent = "▶";
  sonando.boton.setAttribute("aria-pressed", "false");
  sonando = null;
}

// Programador con margen (el patrón clásico de Web Audio): cada 25 ms se
// encolan los golpes de los próximos 120 ms con la hora exacta del audio, así
// el pulso no depende de lo ocupado que esté el navegador.
function tocar(bloque, patron, boton) {
  const era = sonando && sonando.bloque === bloque;
  parar();
  if (era) return;
  const ctx = contexto();
  const cursor = bloque.querySelector(".rt-cursor");
  const estado = { bloque, boton, cursor, paso: 0, siguiente: ctx.currentTime + 0.08, cola: [] };
  const duracion = () => 60 / estado.tempo() / patron.porPulso;
  estado.tempo = () => parseInt(bloque.querySelector(".rt-tempo").value, 10) || patron.tempo;
  estado.reloj = setInterval(() => {
    if (!bloque.isConnected) { parar(); return; }
    while (estado.siguiente < ctx.currentTime + 0.12) {
      for (const v of patron.voces) {
        const g = v.golpes[estado.paso];
        if (g) SONIDOS[v.voz](ctx, estado.siguiente, ACENTO.has(g) ? 1 : 0.6, g);
      }
      estado.cola.push({ paso: estado.paso, t: estado.siguiente });
      estado.paso = (estado.paso + 1) % patron.pasos;
      estado.siguiente += duracion();
    }
    // El cursor va con el mismo reloj que el sonido, no con
    // requestAnimationFrame: en la prueba, el navegador frenó los cuadros
    // mientras el audio seguía sonando, y el cursor se quedó quieto.
    while (estado.cola.length > 1 && estado.cola[1].t <= ctx.currentTime) estado.cola.shift();
    const actual = estado.cola[0];
    if (actual && actual.t <= ctx.currentTime) {
      cursor.setAttribute("x", ETIQUETA + actual.paso * CELDA);
      cursor.setAttribute("opacity", "0.35");
    }
  }, 25);
  boton.textContent = "⏸";
  boton.setAttribute("aria-pressed", "true");
  sonando = estado;
}

// --- Montaje en la página ----------------------------------------------------

const CLAVE_MODO = "ritmo-modo";
function leerModo() {
  try { return localStorage.getItem(CLAVE_MODO) === "cuerpo" ? "cuerpo" : "bateria"; } catch (e) { return "bateria"; }
}

// Estilos una sola vez, desde aquí: así valen igual en el visor, en la página
// de la canción y en la vista previa del editor sin copiar CSS en tres sitios.
const CSS = `
.rt-bloque { margin: .4em 0 1.4em; font-family: system-ui, sans-serif; }
.rt-cabecera { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px; }
.rt-titulo { font-weight: 700; font-size: 1em; margin: 0 6px 0 0; }
.rt-cabecera button, .rt-cabecera input { font: 600 14px system-ui, sans-serif; border-radius: 8px; border: 1px solid rgba(127,127,127,.45); background: transparent; color: inherit; padding: 4px 10px; cursor: pointer; }
.rt-cabecera button[aria-pressed="true"] { background: #2563eb; border-color: #2563eb; color: #fff; }
.rt-cabecera input { width: 4.2em; cursor: text; }
.rt-cabecera .rt-dato { font-size: 13px; opacity: .7; }
.rt-rejilla { overflow-x: auto; }
.rt-svg { display: block; max-width: 100%; height: auto; }
.rt-error { border: 2px solid #dc2626; border-radius: 8px; padding: 8px 10px; color: #b91c1c; font: 14px system-ui, sans-serif; white-space: pre-line; }
@media print { .rt-cabecera button, .rt-cabecera input, .rt-cabecera .rt-dato { display: none !important; } .rt-svg { max-width: 100% !important; } }
`;
function ponerEstilos() {
  if (document.getElementById("rt-estilos")) return;
  const st = document.createElement("style");
  st.id = "rt-estilos";
  st.textContent = CSS;
  document.head.appendChild(st);
}

function textoDelBloque(parrafo) {
  return [...parrafo.querySelectorAll(":scope > .row")]
    .filter((r) => !r.querySelector(".label"))
    .map((r) => r.textContent)
    .join("\n");
}

function escapar(t) {
  return String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function montarBloque(parrafo) {
  const titulo = parrafo.querySelector(".label")?.textContent || "Ritmo";
  const patron = parsearRitmo(textoDelBloque(parrafo));
  const bloque = document.createElement("div");
  bloque.className = "rt-bloque";
  // Solo batería: 🥁. Con acompañamiento: 🎸.
  const emoji = patron.voces.some((v) => !BATERIA.has(v.voz)) ? "🎸" : "🥁";
  if (patron.errores.length) {
    bloque.innerHTML = `<div class="rt-cabecera"><span class="rt-titulo">${emoji} ${escapar(titulo)}</span></div>` +
      `<div class="rt-error">Este ritmo no se puede dibujar:\n${patron.errores.map(escapar).join("\n")}</div>`;
    parrafo.replaceWith(bloque);
    return;
  }
  let modo = leerModo();
  bloque.innerHTML = `
    <div class="rt-cabecera">
      <span class="rt-titulo">${emoji} ${escapar(titulo)}</span>
      <button type="button" class="rt-tocar" aria-pressed="false" title="Escuchar el patrón">▶</button>
      <input type="number" class="rt-tempo" min="30" max="240" value="${patron.tempo}" title="Tempo (pulsos por minuto)" aria-label="Tempo">
      <span class="rt-dato">ppm · ${patron.compas}</span>
      <button type="button" class="rt-modo" title="Ver los iconos de batería o los del cuerpo"></button>
    </div>
    <div class="rt-rejilla"></div>`;
  const rejilla = bloque.querySelector(".rt-rejilla");
  const botonModo = bloque.querySelector(".rt-modo");
  const pintar = () => {
    const tocando = sonando && sonando.bloque === bloque;
    if (tocando) parar();
    rejilla.innerHTML = svgRitmo(patron, modo);
    botonModo.textContent = modo === "cuerpo" ? "👏 Cuerpo" : "🥁 Batería";
  };
  pintar();
  bloque.querySelector(".rt-tocar").addEventListener("click", (e) => tocar(bloque, patron, e.currentTarget));
  // El modo es de toda la página y se recuerda: cambia todos los bloques.
  botonModo.addEventListener("click", () => {
    const nuevo = modo === "cuerpo" ? "bateria" : "cuerpo";
    try { localStorage.setItem(CLAVE_MODO, nuevo); } catch (e) { /* sin almacenamiento */ }
    document.dispatchEvent(new CustomEvent("ritmo-modo", { detail: nuevo }));
  });
  document.addEventListener("ritmo-modo", function cambiar(e) {
    if (!bloque.isConnected) { document.removeEventListener("ritmo-modo", cambiar); return; }
    modo = e.detail;
    pintar();
  });
  parrafo.replaceWith(bloque);
}

// Cambia cada `.paragraph.ritmo` del contenedor por su rejilla. Hay que
// llamarla después de meter el HTML de la canción en la página.
export function pintarRitmos(contenedor) {
  const parrafos = contenedor.querySelectorAll(".paragraph.ritmo");
  if (!parrafos.length) return;
  ponerEstilos();
  parrafos.forEach(montarBloque);
}
