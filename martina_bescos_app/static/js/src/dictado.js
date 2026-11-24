// Fichas de audición (fase 111): los dictados escritos en ABC.
//
// Dos trabajos:
//
// 1. **La respuesta**: abcjs pinta la partitura del ABC (vendorizado en
//    static/vendor/abcjs/).
// 2. **El audio, con la metodología de clase de Jesús** (2026-11-17): el
//    dictado entero; luego de dos en dos compases, cada pareja repetida con su
//    silencio para escribir; y entero al final. Con una claqueta fina que marca
//    el compás (hi-hat en la primera parte, un golpe plano en las demás) y, en
//    los rítmicos, notas mantenidas en do en vez de golpes.
//
// El audio no es un MP3: se construye un MIDI con todo el plan y lo toca
// SpessaSynth (`static/js/motor_midi.js`), el mismo motor de las pistas de
// práctica. Así el tempo, las repeticiones o el silencio se cambian sin
// regenerar nada, y «Lo toco yo» es silenciar el canal de la melodía.
//
// Las funciones puras (`analizar`, `planDictado`, `aMidi`) se prueban con
// bun:test; el resto es el reproductor de la página.

export const CANAL_MELODIA = 0;
export const CANAL_CLAQUETA = 9;

// La claqueta: hi-hat cerrado en la primera parte y aro de caja en las
// demás, flojitos.
export const CLAQUETA = { primera: 42, resto: 37, velPrimera: 48, velResto: 34, volumen: 70 };

// En los rítmicos todo suena en do (do5): lo que se oye es cuánto dura.
export const DO_RITMICO = 72;

// Lo que suena de cada nota: un poco menos que lo escrito, para que dos notas
// iguales seguidas se oigan como dos.
const ARTICULACION = 0.92;
const HUECO_MINIMO = 0.04;

// Timbres candidatos, por programa General MIDI. El banco decide cómo suenan.
export const TIMBRES = {
  piano: { programa: 0, etiqueta: "Piano" },
  epiano: { programa: 4, etiqueta: "Piano eléctrico" },
  flauta: { programa: 73, etiqueta: "Flauta" },
  sinte: { programa: 80, etiqueta: "Sintetizador suave" },
};
export const TIMBRE_POR_DEFECTO = { melodico: "piano", ritmico: "flauta" };

// Intensidad de las notas de la melodía. abcjs da 85-105 sin matices y hasta
// 120 con !ff!; se acota aquí porque el banco de las fichas
// (static/vendor/musescore/) solo lleva la capa mezzoforte del piano: la de
// fortissimo pesaba 5 MB más. scripts/recortar_banco.ts lee este mismo rango, y
// dictado.test.js comprueba que el banco suena en todo él.
export const VEL_MELODIA = { min: 60, max: 105 };

// Los pulsos del compás. En los compuestos (6/8, 9/8, 12/8) el pulso es la
// negra con puntillo.
export function pulsos(metrica) {
  const { num, den } = metrica;
  if (den === 8 && num % 3 === 0 && num > 3) {
    return { porCompas: num / 3, duracion: 3 / 8 };
  }
  return { porCompas: num, duracion: 1 / den };
}

// Lo que el plan necesita de un ABC. `abcjs` es el módulo (window.ABCJS).
export function analizar(abcjs, abc) {
  const tune = abcjs.parseOnly(abc)[0];
  if (!tune || !tune.lines || !tune.lines.length) throw new Error("El ABC no tiene notas.");
  const metrica = tune.getMeterFraction() || { num: 4, den: 4 };
  const compas = tune.getBarLength() || metrica.num / metrica.den;
  const anacrusa = tune.getPickupLength ? tune.getPickupLength() || 0 : 0;
  const audio = tune.setUpAudio({});
  const notas = audio.tracks
    .flat()
    .filter((e) => e.cmd === "note")
    .map((e) => ({ pitch: e.pitch, start: e.start, duration: e.duration, volume: e.volume }))
    .sort((a, b) => a.start - b.start);
  if (!notas.length) throw new Error("El ABC no tiene notas.");
  const final = Math.max(...notas.map((n) => n.start + n.duration));
  const compases = Math.max(1, Math.round((final - anacrusa) / compas + 0.49));
  return { metrica, compas, anacrusa, notas, compases };
}

// Las parejas de compases: [1,2], [3,4]… y, si sobra uno, él solo.
export function parejas(compases) {
  const salida = [];
  for (let d = 1; d <= compases; d += 2) salida.push([d, Math.min(d + 1, compases)]);
  return salida;
}

// El plan completo, en segundos.
// opciones: { tempo, tipo, repeticiones, silencio, cuenta_previa }
export function planDictado(analisis, opciones = {}) {
  const tempo = opciones.tempo || 60;
  const tipo = opciones.tipo === "ritmico" ? "ritmico" : "melodico";
  const repeticiones = Math.max(1, opciones.repeticiones || 2);
  const silencio = Math.max(0, opciones.silencio == null ? 10 : opciones.silencio);
  const cuenta = opciones.cuenta_previa !== false;

  const { compas, anacrusa, notas, compases, metrica } = analisis;
  const pulso = pulsos(metrica);
  const segPorEntera = 60 / tempo / pulso.duracion;
  const segPorCompas = compas * segPorEntera;

  const eventos = [];
  const tramos = [];
  let t = 0;

  function claqueta(inicio, nCompases) {
    for (let c = 0; c < nCompases; c++) {
      for (let p = 0; p < pulso.porCompas; p++) {
        const primera = p === 0;
        eventos.push({
          t: inicio + c * segPorCompas + p * pulso.duracion * segPorEntera,
          dur: 0.1,
          canal: CANAL_CLAQUETA,
          nota: primera ? CLAQUETA.primera : CLAQUETA.resto,
          vel: primera ? CLAQUETA.velPrimera : CLAQUETA.velResto,
        });
      }
    }
  }

  // Toca los compases `desde`..`hasta` (de 1 en adelante), con su compás de
  // cuenta previa delante (o un compás de silencio, si no hay cuenta).
  function tocar(desde, hasta, clase, vez, etiqueta) {
    const inicioTramo = t;
    if (cuenta) claqueta(t, 1);
    t += segPorCompas;
    // En unidades de redonda: la anacrusa va con el primer compás.
    const a = desde === 1 ? 0 : anacrusa + (desde - 1) * compas;
    const b = anacrusa + hasta * compas;
    const inicioMusica = t;
    for (const n of notas) {
      if (n.start < a - 1e-9 || n.start >= b - 1e-9) continue;
      const dur = n.duration * segPorEntera;
      eventos.push({
        t: inicioMusica + (n.start - a) * segPorEntera,
        dur: Math.max(0.05, Math.min(dur * ARTICULACION, dur - HUECO_MINIMO)),
        canal: CANAL_MELODIA,
        nota: tipo === "ritmico" ? DO_RITMICO : n.pitch,
        vel: Math.min(VEL_MELODIA.max, Math.max(VEL_MELODIA.min, n.volume || 90)),
      });
    }
    // La claqueta sigue debajo de la música, compás a compás. La anacrusa
    // no lleva claqueta propia: la cuenta previa ya marca dónde cae.
    const inicioCompases = inicioMusica + (desde === 1 ? anacrusa * segPorEntera : 0);
    claqueta(inicioCompases, hasta - desde + 1);
    t = inicioMusica + (b - a) * segPorEntera;
    tramos.push({ clase, desde, hasta, vez, inicio: inicioTramo, fin: t, etiqueta });
  }

  tocar(1, compases, "entero", 1, "Entero");
  for (const [d, h] of parejas(compases)) {
    const nombre = d === h ? `Compás ${d}` : `Compases ${d}–${h}`;
    for (let v = 1; v <= repeticiones; v++) {
      tocar(d, h, "pareja", v, `${nombre} · ${v}.ª vez`);
    }
    if (silencio > 0) {
      tramos.push({ clase: "silencio", desde: d, hasta: h, vez: 0, inicio: t, fin: t + silencio, etiqueta: `Escribe ${nombre.toLowerCase()}` });
      t += silencio;
    }
  }
  tocar(1, compases, "entero", 2, "Entero, para repasar");

  eventos.sort((x, y) => x.t - y.t);
  return { tramos, eventos, duracion: t + 0.5, compases, segPorCompas };
}

// --- MIDI -------------------------------------------------------------------

// Formato 0, 480 por negra y negra = 0,5 s: 960 ticks por segundo.
const PPQ = 480;
const TICKS_POR_SEGUNDO = 960;

function vlq(n) {
  const bytes = [n & 0x7f];
  while ((n >>= 7)) bytes.unshift((n & 0x7f) | 0x80);
  return bytes;
}

// `canales`: los que llevan el timbre. Los dictados usan uno; los patrones de
// piano (fase 114), dos, uno por mano, para poder apagar una.
export function aMidi(plan, { programa = 0, canales = [CANAL_MELODIA] } = {}) {
  const crudos = []; // [tick, orden, bytes]
  const tick = (s) => Math.max(0, Math.round(s * TICKS_POR_SEGUNDO));
  crudos.push([0, 0, [0xff, 0x51, 0x03, 0x07, 0xa1, 0x20]]); // 500.000 µs por negra
  for (const canal of canales) {
    crudos.push([0, 1, [0xc0 | canal, programa & 0x7f]]);
    crudos.push([0, 1, [0xb0 | canal, 7, 100]]);
  }
  crudos.push([0, 1, [0xb0 | CANAL_CLAQUETA, 7, CLAQUETA.volumen]]);
  for (const e of plan.eventos) {
    // Los apagados antes que los encendidos del mismo instante: si no, una
    // nota repetida se apaga justo al volver a sonar.
    crudos.push([tick(e.t), 3, [0x90 | e.canal, e.nota, e.vel]]);
    crudos.push([tick(e.t + e.dur), 2, [0x80 | e.canal, e.nota, 0]]);
  }
  crudos.push([tick(plan.duracion), 9, [0xff, 0x2f, 0x00]]);
  crudos.sort((x, y) => x[0] - y[0] || x[1] - y[1]);

  const pista = [];
  let antes = 0;
  for (const [t, , bytes] of crudos) {
    pista.push(...vlq(t - antes), ...bytes);
    antes = t;
  }
  const cabecera = [0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, (PPQ >> 8) & 0xff, PPQ & 0xff];
  const n = pista.length;
  const trk = [0x4d, 0x54, 0x72, 0x6b, (n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff];
  return new Uint8Array([...cabecera, ...trk, ...pista]);
}

// --- La página ----------------------------------------------------------------

function cargarScript(src, global) {
  if (window[global]) return Promise.resolve(window[global]);
  window.__cargas = window.__cargas || {};
  if (!window.__cargas[src]) {
    window.__cargas[src] = new Promise((ok, mal) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = () => ok(window[global]);
      s.onerror = () => mal(new Error("No se pudo cargar " + src));
      document.head.appendChild(s);
    });
  }
  return window.__cargas[src];
}

// Un solo motor para toda la página: el banco se descarga una vez.
let motor = null;
let ctx = null;
let sonando = null; // el reproductor que suena ahora

async function elMotor(urls) {
  if (motor) return motor;
  const AC = window.AudioContext || window.webkitAudioContext;
  ctx = ctx || new AC();
  await cargarScript(urls.motor, "MotorMidi");
  motor = await window.MotorMidi.crear(ctx, { procesador: urls.procesador, banco: urls.banco });
  return motor;
}

// El turno de sonar. En la página solo suena un reproductor a la vez, sea un
// dictado o un patrón de piano (patron_piano.js, fase 114): quien empieza para
// al que estuviera sonando.
export function tomarTurno(api) {
  if (sonando && sonando !== api) sonando.parar();
  sonando = api;
}

export function soltarTurno(api) {
  if (sonando === api) sonando = null;
}

function urlsDe(el) {
  const raiz = el.closest("[data-ficha]") || document.body;
  return {
    abcjs: raiz.dataset.abcjs,
    motor: raiz.dataset.motorMidi,
    procesador: raiz.dataset.procesadorMidi,
    banco: raiz.dataset.bancoMidi,
  };
}

function pintarPartitura(el, abc) {
  const destino = el.querySelector("[data-partitura]");
  if (!destino || !window.ABCJS) return;
  window.ABCJS.renderAbc(destino, abc, { responsive: "resize", add_classes: true, paddingtop: 0, paddingbottom: 0 });
}

function montarDictado(el) {
  if (el.dataset.montado) return;
  el.dataset.montado = "1";
  let datos;
  try {
    datos = JSON.parse(el.dataset.dictado || "{}");
  } catch (e) {
    console.error("[dictado] datos ilegibles", e);
    return;
  }
  const urls = urlsDe(el);
  const estado = el.querySelector("[data-estado]");
  const lista = el.querySelector("[data-tramos]");
  const btnTocar = el.querySelector("[data-tocar]");
  const btnPausa = el.querySelector("[data-pausa]");
  const btnParar = el.querySelector("[data-parar-dictado]");
  const yo = el.querySelector("[data-yo]");
  const solucion = el.querySelector("details");
  const decir = (texto) => { if (estado) estado.textContent = texto; };

  let plan = null;
  let bytes = null;
  let cargado = false;
  let enMarcha = false;

  // La partitura se pinta al abrir la solución: pintada dentro de un
  // <details> cerrado sale con ancho cero.
  if (solucion) {
    solucion.addEventListener("toggle", () => {
      if (!solucion.open) return;
      cargarScript(urls.abcjs, "ABCJS").then(() => pintarPartitura(el, datos.abc));
    });
  }

  async function preparar() {
    if (plan) return;
    const ABCJS = await cargarScript(urls.abcjs, "ABCJS");
    plan = planDictado(analizar(ABCJS, datos.abc), datos);
    const timbre = TIMBRES[datos.timbre] || TIMBRES[TIMBRE_POR_DEFECTO[datos.tipo] || "piano"];
    bytes = aMidi(plan, { programa: timbre.programa });
    if (lista) {
      lista.innerHTML = "";
      plan.tramos.forEach((tr, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "fa-tramo fa-tramo-" + tr.clase;
        b.textContent = tr.clase === "silencio" ? "✎ " + Math.round(tr.fin - tr.inicio) + " s" : tr.etiqueta;
        b.title = tr.etiqueta;
        b.dataset.indice = i;
        b.addEventListener("click", () => tocarDesde(tr.inicio));
        lista.appendChild(b);
      });
    }
  }

  function marcar(t) {
    if (!plan || !lista) return;
    const i = plan.tramos.findIndex((tr) => t >= tr.inicio && t < tr.fin);
    lista.querySelectorAll(".fa-tramo").forEach((b) => b.classList.toggle("fa-actual", Number(b.dataset.indice) === i));
    if (i >= 0) decir(plan.tramos[i].etiqueta);
    if (t >= plan.duracion - 0.3) parar("Terminado.");
  }

  function aplicarYo(m) {
    m.mezclar(new Map([[CANAL_MELODIA, { mudo: !!(yo && yo.checked), ganancia: 1 }]]));
  }

  async function tocarDesde(segundo) {
    try {
      decir("Preparando…");
      await preparar();
      const m = await elMotor(urls);
      if (sonando && sonando !== api) sonando.parar();
      if (ctx.state === "suspended") await ctx.resume();
      if (!cargado || m.__de !== el) {
        await m.cargar(bytes);
        m.__de = el;
        cargado = true;
      }
      aplicarYo(m);
      m.setUpdateInterval(0.1, marcar);
      m.schedule({ input: segundo, active: true });
      enMarcha = true;
      sonando = api;
      if (btnPausa) { btnPausa.hidden = false; btnPausa.textContent = "⏸ Pausa"; }
      if (btnParar) btnParar.hidden = false;
    } catch (e) {
      console.error("[dictado]", e);
      decir("No se pudo tocar: " + e.message);
    }
  }

  function pausar() {
    if (!motor || motor.__de !== el) return;
    enMarcha = !enMarcha;
    motor.schedule({ active: enMarcha });
    if (btnPausa) btnPausa.textContent = enMarcha ? "⏸ Pausa" : "▶ Seguir";
    if (!enMarcha) decir("En pausa.");
  }

  function parar(texto) {
    if (motor && motor.__de === el) {
      motor.schedule({ active: false });
      motor.setUpdateInterval(1, () => {});
    }
    enMarcha = false;
    if (sonando === api) sonando = null;
    if (btnPausa) btnPausa.hidden = true;
    if (btnParar) btnParar.hidden = true;
    if (lista) lista.querySelectorAll(".fa-actual").forEach((b) => b.classList.remove("fa-actual"));
    decir(texto || "");
  }

  const api = { parar, plan: () => plan, preparar };
  el.__dictado = api;
  if (btnTocar) btnTocar.addEventListener("click", () => tocarDesde(0));
  if (btnPausa) btnPausa.addEventListener("click", pausar);
  if (btnParar) btnParar.addEventListener("click", () => parar(""));
  if (yo) yo.addEventListener("change", () => { if (motor && motor.__de === el) aplicarYo(motor); });
  // La lista de tramos se ve desde el principio, sin esperar al ▶.
  preparar().catch((e) => decir("El ABC tiene un error: " + e.message));
}

// El editor: la partitura se pinta mientras se escribe, y avisa si el dictado
// no tiene los 8 compases de clase (avisa, no lo impide).
export function avisoDeCompases(compases) {
  if (compases === 8) return "";
  return `Este dictado tiene ${compases} ${compases === 1 ? "compás" : "compases"}; los de clase tienen 8.`;
}

function montarEditor(form) {
  if (form.dataset.montado) return;
  form.dataset.montado = "1";
  const texto = form.querySelector("[data-abc]");
  const vista = form.querySelector("[data-vista-previa]");
  const aviso = form.querySelector("[data-aviso]");
  if (!texto || !vista) return;
  const urls = urlsDe(form);
  let reloj = null;

  function pintar() {
    cargarScript(urls.abcjs, "ABCJS").then((ABCJS) => {
      ABCJS.renderAbc(vista, texto.value, { responsive: "resize", add_classes: true });
      try {
        aviso.textContent = avisoDeCompases(analizar(ABCJS, texto.value).compases);
      } catch (e) {
        aviso.textContent = "El ABC tiene un error: " + e.message;
      }
    });
  }

  texto.addEventListener("input", () => {
    clearTimeout(reloj);
    reloj = setTimeout(pintar, 250);
  });
  const plegable = form.closest("details");
  if (plegable) plegable.addEventListener("toggle", () => { if (plegable.open) pintar(); });
  if (!plegable || plegable.open) pintar();
}

export function montar(raiz) {
  (raiz || document).querySelectorAll("[data-dictado]").forEach(montarDictado);
  (raiz || document).querySelectorAll("[data-editor-abc]").forEach(montarEditor);
}

if (typeof window !== "undefined") {
  window.Dictado = {
    montar,
    analizar,
    planDictado,
    aMidi,
    pulsos,
    parejas,
    TIMBRES,
    // Para medir en las pruebas: el motor (y su nodo `salida`).
    motor: () => motor,
    // Lo que comparte con patron_piano.js (fase 114), que se carga después y
    // toca por el mismo motor: un banco descargado y un solo turno de sonar.
    CLAQUETA,
    CANAL_CLAQUETA,
    cargarScript,
    urlsDe,
    elMotor,
    contexto: () => ctx,
    tomarTurno,
    soltarTurno,
  };
  window.addEventListener("pagehide", () => { if (sonando) sonando.parar(); });
}
