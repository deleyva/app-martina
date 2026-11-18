// Fichas de audición (fase 111): el reproductor de los tests audiométricos.
//
// No hay audio guardado: cada par se sintetiza al tocarlo a partir de la
// frecuencia base, los cents y la dirección que vienen en el HTML
// (`data-pares`, `data-cents`). El timbre es el del generador de 2022
// (`generate_audiometric_tests.py`): seno con los armónicos 2, 3 y 4 a −10,
// −20 y −30 dB y fundidos de 10 ms, para que suene igual que los MP3 que el
// alumnado ya conoce.
//
// Tiempos de «Todo seguido», los del script: el número se ilumina, 2 s,
// primer sonido de 2 s, 0,5 s, segundo sonido de 2 s y 4 s para apuntar.
//
// Queda en `window.Audicion` (`montar`, más lo que usan las pruebas).

export const ARMONICOS = [0, 1, 10 ** (-10 / 20), 10 ** (-20 / 20), 10 ** (-30 / 20)];
export const TIEMPOS = { previo: 2, tono: 2, entre: 0.5, despues: 4, fundido: 0.01 };

// Lo que dura un par en «Todo seguido», de número a número.
export const PERIODO = TIEMPOS.previo + TIEMPOS.tono + TIEMPOS.entre + TIEMPOS.tono + TIEMPOS.despues;

// [primero, segundo] en Hz. Si baja, primero suena el agudo y luego la base.
export function frecuencias(par, cents) {
  const alto = par.f * 2 ** (cents / 1200);
  return par.sube ? [par.f, alto] : [alto, par.f];
}

// Cuándo suena cada cosa, en segundos desde `inicio`.
// `todos`: el test entero desde `desde`; si no, solo el par `desde`, sin espera.
export function plan(pares, cents, desde = 0, todos = false) {
  const indices = todos ? pares.map((_, i) => i).slice(desde) : [desde];
  return indices.map((i, k) => {
    const base = todos ? k * PERIODO : 0;
    const previo = todos ? TIEMPOS.previo : 0.05;
    const [f1, f2] = frecuencias(pares[i], cents);
    const t1 = base + previo;
    const t2 = t1 + TIEMPOS.tono + TIEMPOS.entre;
    return { indice: i, iluminar: base, t1, f1, t2, f2, fin: t2 + TIEMPOS.tono };
  });
}

let ctx = null;
let salida = null;
let onda = null;

function contexto() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();
    // Un nodo de ganancia común: es el volumen y el punto donde las pruebas
    // miden lo que sale (AnalyserNode).
    salida = ctx.createGain();
    salida.gain.value = 0.3;
    salida.connect(ctx.destination);
    onda = ctx.createPeriodicWave(
      new Float32Array(ARMONICOS.length),
      Float32Array.from(ARMONICOS),
    );
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

function tono(f, t0, dur) {
  const o = ctx.createOscillator();
  o.setPeriodicWave(onda);
  o.frequency.value = f;
  const g = ctx.createGain();
  const fd = TIEMPOS.fundido;
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(1, t0 + fd);
  g.gain.setValueAtTime(1, t0 + dur - fd);
  g.gain.linearRampToValueAtTime(0, t0 + dur);
  o.connect(g);
  g.connect(salida);
  o.start(t0);
  o.stop(t0 + dur + 0.02);
  return o;
}

// Solo suena una cosa a la vez en toda la página.
let actual = null;

function parar() {
  if (!actual) return;
  actual.osciladores.forEach((o) => {
    try { o.stop(); } catch (e) { /* ya parado */ }
  });
  actual.relojes.forEach(clearTimeout);
  actual.raiz.querySelectorAll(".fa-sonando").forEach((b) => b.classList.remove("fa-sonando"));
  const pararBtn = actual.raiz.querySelector("[data-parar]");
  if (pararBtn) pararBtn.hidden = true;
  actual = null;
}

function tocar(raiz, pares, cents, desde, todos) {
  parar();
  contexto();
  const inicio = ctx.currentTime + 0.05;
  const estado = { raiz, osciladores: [], relojes: [] };
  const botones = raiz.querySelectorAll("[data-par]");
  for (const p of plan(pares, cents, desde, todos)) {
    estado.osciladores.push(tono(p.f1, inicio + p.t1, TIEMPOS.tono));
    estado.osciladores.push(tono(p.f2, inicio + p.t2, TIEMPOS.tono));
    const boton = botones[p.indice];
    estado.relojes.push(setTimeout(() => {
      botones.forEach((b) => b.classList.remove("fa-sonando"));
      if (boton) boton.classList.add("fa-sonando");
    }, p.iluminar * 1000));
    estado.relojes.push(setTimeout(() => {
      if (boton) boton.classList.remove("fa-sonando");
    }, p.fin * 1000 + 100));
  }
  const ultimo = plan(pares, cents, desde, todos).pop();
  estado.relojes.push(setTimeout(() => { if (actual === estado) parar(); }, ultimo.fin * 1000 + 200));
  const pararBtn = raiz.querySelector("[data-parar]");
  if (pararBtn) pararBtn.hidden = false;
  actual = estado;
}

function montarAudiometrico(el) {
  if (el.dataset.montado) return;
  el.dataset.montado = "1";
  let pares;
  try {
    pares = JSON.parse(el.dataset.pares || "[]");
  } catch (e) {
    console.error("[audición] pares ilegibles", e);
    return;
  }
  const cents = parseFloat(el.dataset.cents);
  if (!pares.length || !(cents > 0)) return;
  el.querySelectorAll("[data-par]").forEach((b) => {
    b.addEventListener("click", () => tocar(el, pares, cents, parseInt(b.dataset.par, 10), false));
  });
  const todo = el.querySelector("[data-todo]");
  if (todo) todo.addEventListener("click", () => tocar(el, pares, cents, 0, true));
  const pararBtn = el.querySelector("[data-parar]");
  if (pararBtn) pararBtn.addEventListener("click", parar);
}

export function montar(raiz) {
  (raiz || document).querySelectorAll("[data-audiometrico]").forEach(montarAudiometrico);
}

if (typeof window !== "undefined") {
  window.Audicion = {
    montar,
    parar,
    frecuencias,
    plan,
    // Para medir en las pruebas: el contexto y el nodo de salida.
    contexto: () => contexto(),
    salida: () => salida,
  };
  // Se va de la página: que no siga sonando.
  window.addEventListener("pagehide", parar);
}
