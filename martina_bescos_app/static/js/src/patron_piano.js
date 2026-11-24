// Fichas (fase 114): un patrón de acompañamiento de piano sobre una progresión.
//
// Lo que se guarda son cuatro datos: la progresión en GRADOS ([1, 5, 5, 1]), el
// patrón (un identificador del catálogo), la tonalidad y el tempo. De ahí sale
// todo lo demás, aquí:
//
// 1. **Las notas.** La primera tríada va en estado fundamental, con la
//    fundamental entre do4 y si4; cada acorde siguiente, en la inversión que
//    menos mueve la mano. Los registros se eligen para leerse dentro del
//    pentagrama: la derecha en el de sol, la izquierda en el de fa.
// 2. **La partitura.** Un ABC a dos pentagramas, con el cifrado encima y los
//    grados debajo, que pinta abcjs (static/vendor/abcjs/).
// 3. **El sonido.** Un plan de notas por mano que `Dictado.aMidi` convierte en
//    MIDI y toca el motor de las fichas (static/js/motor_midi.js), cada mano en
//    su canal para poder apagar una.
//
// Nada de lo que hay hasta «La página» sabe de abcjs ni del navegador: el día
// que la partitura la pinte otro, cambia `abc()` y lo guardado sigue valiendo.
// Transportar es cambiar un dato, no una función del pintor.
//
// El catálogo (patrones y tonalidades) es musica/patrones_piano.json, el mismo
// fichero que lee el servidor. Las funciones puras se prueban con bun:test.

import CATALOGO from "../../../../musica/patrones_piano.json";

export const TONALIDADES = CATALOGO.tonalidades;
export const PATRONES = CATALOGO.patrones;

// En corcheas: corchea, negra, negra con puntillo, blanca, blanca con puntillo
// y redonda. Son las que se escriben con una sola figura.
export const DURACIONES = [1, 2, 3, 4, 6, 8];
export const CORCHEAS_POR_COMPAS = 8;

const LETRAS = ["C", "D", "E", "F", "G", "A", "B"];
const SEMITONOS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const MAYOR = [0, 2, 4, 5, 7, 9, 11];
export const ROMANOS = ["I", "ii", "iii", "IV", "V", "vi", "vii°"];
const SUFIJO = ["", "m", "m", "", "", "m", "dim"];

// La derecha: la primera tríada, con la fundamental entre do4 y si4, que es
// donde cabe en el pentagrama de sol; las demás, entre la3 y do6.
const PRIMERA = { min: 60, max: 71 };
const DERECHA = { min: 57, max: 84 };
// La izquierda: el bajo y su quinta, entre fa2 y mi3 (sin líneas adicionales por
// debajo del pentagrama de fa), y su tríada sin bajar de fa2.
const BAJO = { min: 41, max: 52 };
// Todo lo que puede sonar en un patrón: de fa2 a do6. Lo lee
// scripts/recortar_banco.ts para que el banco de las fichas lleve el piano con
// muestra propia en ese registro entero; si se ensancha aquí, hay que rehacer
// el banco, y patron_piano.test.js lo dice.
export const REGISTRO = { min: BAJO.min, max: DERECHA.max };

export const CANAL_DERECHA = 0;
export const CANAL_IZQUIERDA = 1;
// Dentro de VEL_MELODIA de dictado.js (60-105): el banco de las fichas solo
// lleva esa capa del piano. La izquierda, un poco más presente que el acorde.
export const INTENSIDAD = { derecha: 74, izquierda: 86 };

// Como en los dictados: cada nota suena un poco menos de lo escrito, para que
// dos iguales seguidas se oigan como dos.
const ARTICULACION = 0.92;
const HUECO_MINIMO = 0.04;

// El bucle no lo hace el reproductor saltando atrás (el salto se oye): el MIDI
// lleva las vueltas escritas una detrás de otra, hasta unos cinco minutos.
export const MINUTOS_DE_BUCLE = 5;
export const MAX_VUELTAS = 64;

export function tonalidad(id) {
  const t = TONALIDADES.find((x) => x.id === id);
  if (!t) throw new Error("Tonalidad desconocida: " + id);
  const semitono = (SEMITONOS[t.letra] + t.alt + 12) % 12;
  // La tónica de referencia, entre do4 y si4.
  const octava = 4;
  return { ...t, semitono, octava, midi: 12 * (octava + 1) + semitono, indice: LETRAS.indexOf(t.letra) };
}

export function patron(id) {
  const p = PATRONES.find((x) => x.id === id);
  if (!p) throw new Error("Patrón desconocido: " + id);
  return p;
}

// `paso` es la distancia diatónica a la tónica de referencia: 0 la tónica, 7 su
// octava, -1 la sensible de debajo.
export function nota(t, paso) {
  const grado = ((paso % 7) + 7) % 7;
  const octavas = Math.floor(paso / 7);
  const L = t.indice + grado;
  const letra = LETRAS[L % 7];
  let alter = ((t.semitono + MAYOR[grado]) % 12) - SEMITONOS[letra];
  if (alter > 6) alter -= 12;
  if (alter < -6) alter += 12;
  return {
    paso,
    letra,
    alter,
    octava: t.octava + octavas + Math.floor(L / 7),
    midi: t.midi + MAYOR[grado] + 12 * octavas,
  };
}

// «C4», «Bb3», «F#4»: para los tests y para leer un fallo.
export function nombreDeNota(n) {
  return n.letra + (n.alter === 1 ? "#" : n.alter === -1 ? "b" : "") + n.octava;
}

// Las tres posiciones de la tríada de un grado, en cinco octavas.
function posiciones(grado) {
  const r = grado - 1;
  const salida = [];
  for (let k = -2; k <= 2; k++) {
    const b = r + 7 * k;
    salida.push([b, b + 2, b + 4], [b + 2, b + 4, b + 7], [b + 4, b + 7, b + 9]);
  }
  return salida;
}

// La mano derecha: una tríada por grado, cada una lo más cerca posible de la
// anterior (a igual distancia, la de la nota aguda más baja).
export function voces(t, grados) {
  let anterior = null;
  return grados.map((g) => {
    if (!Number.isInteger(g) || g < 1 || g > 7) throw new Error("Grado desconocido: " + g);
    const candidatas = posiciones(g)
      .map((pasos) => pasos.map((p) => nota(t, p)))
      .filter((ns) => ns[0].midi >= DERECHA.min && ns[2].midi <= DERECHA.max);
    let mejor;
    if (!anterior) {
      mejor = candidatas.find(
        (ns) => (((ns[0].paso - (g - 1)) % 7) + 7) % 7 === 0 && ns[0].midi >= PRIMERA.min && ns[0].midi <= PRIMERA.max,
      );
    } else {
      const previa = anterior;
      const distancia = (ns) => ns.reduce((suma, n, i) => suma + Math.abs(n.midi - previa[i].midi), 0);
      mejor = candidatas.sort((a, b) => distancia(a) - distancia(b) || a[2].midi - b[2].midi)[0];
    }
    anterior = mejor;
    return mejor;
  });
}

export function bajo(t, grado) {
  for (let k = -4; k <= 1; k++) {
    const n = nota(t, grado - 1 + 7 * k);
    if (n.midi >= BAJO.min && n.midi <= BAJO.max) return n;
  }
  throw new Error("Sin bajo para el grado " + grado);
}

// La quinta del acorde: por debajo del bajo si no baja de fa2; si no, encima.
export function quinta(t, b) {
  const debajo = nota(t, b.paso - 3);
  return debajo.midi >= BAJO.min ? debajo : nota(t, b.paso + 4);
}

// Cuántas octavas por debajo de la derecha va la tríada de la izquierda: dos si
// así no baja de fa2; si no, una. Es la misma para toda la progresión: si cada
// acorde eligiera la suya, la mano saltaría de octava entre dos acordes vecinos.
export function octavasDeLaIzquierda(derechas) {
  const masGrave = Math.min(...derechas.map((ns) => ns[0].midi));
  return masGrave - 24 >= BAJO.min ? 2 : 1;
}

export function cifrado(t, grado) {
  const raiz = nota(t, grado - 1);
  const alteracion = raiz.alter === 1 ? "#" : raiz.alter === -1 ? "b" : "";
  return { raiz, romano: ROMANOS[grado - 1], texto: raiz.letra + alteracion + SUFIJO[grado - 1] };
}

// Por qué un patrón no se puede escribir, o "" si está bien.
export function defectoDelPatron(p) {
  const propios = { derecha: [], izquierda: ["bajo", "quinta"] };
  for (const mano of ["derecha", "izquierda"]) {
    const sucesos = p[mano];
    if (!Array.isArray(sucesos) || !sucesos.length) return `A «${p.id}» le falta la mano ${mano}.`;
    const valen = ["acorde", "grave", "medio", "agudo", "silencio", ...propios[mano]];
    let suma = 0;
    for (const [que, dur] of sucesos) {
      if (!valen.includes(que)) return `En «${p.id}», la mano ${mano} no sabe tocar «${que}».`;
      if (!DURACIONES.includes(dur)) return `En «${p.id}», ${dur} corcheas no se escriben con una sola figura.`;
      suma += dur;
    }
    if (suma !== CORCHEAS_POR_COMPAS) return `En «${p.id}», la mano ${mano} suma ${suma} corcheas y el compás tiene ${CORCHEAS_POR_COMPAS}.`;
  }
  return "";
}

// Un compás por grado: lo que toca cada mano, ya con sus notas.
export function compases(t, grados, p) {
  const defecto = defectoDelPatron(p);
  if (defecto) throw new Error(defecto);
  const derechas = voces(t, grados);
  const octavas = octavasDeLaIzquierda(derechas);
  return grados.map((g, i) => {
    const derecha = derechas[i];
    // La tríada de la izquierda: la misma, una o dos octavas más abajo.
    const izquierda = derecha.map((n) => nota(t, n.paso - 7 * octavas));
    const b = bajo(t, g);
    const mano = (sucesos, triada, propios) =>
      sucesos.map(([que, dur]) => {
        const toca = { acorde: triada, grave: [triada[0]], medio: [triada[1]], agudo: [triada[2]], silencio: [], ...propios };
        return { notas: toca[que], dur };
      });
    return {
      grado: g,
      cifrado: cifrado(t, g),
      derecha: mano(p.derecha, derecha, {}),
      izquierda: mano(p.izquierda, izquierda, { bajo: [b], quinta: [quinta(t, b)] }),
    };
  });
}

// --- ABC ----------------------------------------------------------------------

// Sin alteraciones escritas: son notas de la escala y las pone la armadura.
function notaAbc(n) {
  return n.octava >= 5 ? n.letra.toLowerCase() + "'".repeat(n.octava - 5) : n.letra + ",".repeat(4 - n.octava);
}

// Las corcheas seguidas de una misma mitad del compás van pegadas: abcjs las
// une con una barra.
function manoAbc(sucesos, antes) {
  let o = 0;
  let previo = null;
  let texto = antes;
  for (const e of sucesos) {
    const pegada =
      previo && previo.dur === 1 && e.dur === 1 && previo.notas.length && e.notas.length && Math.floor(previo.o / 4) === Math.floor(o / 4);
    const figura = e.dur === 1 ? "" : String(e.dur);
    const que = !e.notas.length ? "z" : e.notas.length > 1 ? "[" + e.notas.map(notaAbc).join("") + "]" : notaAbc(e.notas[0]);
    texto += (previo && !pegada ? " " : "") + que + figura;
    previo = { ...e, o };
    o += e.dur;
  }
  return texto;
}

// `porLinea`: compases por sistema. En el móvil, dos; con sitio, cuatro.
// El tempo no va escrito en la partitura: lo dice (y lo cambia) el mando de
// «Negra =», y dos cifras distintas a la vista serían una de más.
export function abc(t, grados, p, { porLinea = 4 } = {}) {
  const cs = compases(t, grados, p);
  const lineas = [];
  for (let i = 0; i < cs.length; i += porLinea) {
    const tramo = cs.slice(i, i + porLinea);
    const final = i + porLinea >= cs.length ? " |]" : " |";
    lineas.push("[V:1] " + tramo.map((c) => manoAbc(c.derecha, `"${c.cifrado.texto}"`)).join(" | ") + final);
    lineas.push("[V:2] " + tramo.map((c) => manoAbc(c.izquierda, `"_${c.cifrado.romano}"`)).join(" | ") + final);
  }
  // `%%stretchlast`: sin él, abcjs deja sin estirar el último sistema, y un
  // patrón de redondas ocupa medio ancho al lado de uno de corcheas.
  return ["X:1", "M:4/4", "L:1/8", "%%stretchlast 1", "%%score {1 2}", "V:1 clef=treble", "V:2 clef=bass", `K:${t.id}`, ...lineas].join("\n") + "\n";
}

// --- El sonido ------------------------------------------------------------------

// El plan, en segundos: un compás de cuenta (solo claqueta) y la progresión
// tantas vueltas como quepan en MINUTOS_DE_BUCLE, sin hueco entre una y otra.
// `claqueta` es la CLAQUETA de dictado.js y `canalClaqueta` su canal.
export function planPatron(cs, { tempo = 80, vueltas = 0, claqueta, canalClaqueta = 9 } = {}) {
  const segPorCorchea = 60 / tempo / 2;
  const segPorCompas = segPorCorchea * CORCHEAS_POR_COMPAS;
  const vuelta = cs.length * segPorCompas;
  const n = vueltas || Math.max(1, Math.min(MAX_VUELTAS, Math.ceil((MINUTOS_DE_BUCLE * 60) / vuelta)));
  const eventos = [];

  function golpes(inicio) {
    if (!claqueta) return;
    for (let pulso = 0; pulso < 4; pulso++) {
      eventos.push({
        t: inicio + pulso * 2 * segPorCorchea,
        dur: 0.1,
        canal: canalClaqueta,
        nota: pulso === 0 ? claqueta.primera : claqueta.resto,
        vel: pulso === 0 ? claqueta.velPrimera : claqueta.velResto,
      });
    }
  }

  golpes(0);
  const inicio = segPorCompas;
  for (let v = 0; v < n; v++) {
    cs.forEach((c, i) => {
      const t0 = inicio + v * vuelta + i * segPorCompas;
      golpes(t0);
      for (const [mano, canal] of [["derecha", CANAL_DERECHA], ["izquierda", CANAL_IZQUIERDA]]) {
        let o = 0;
        for (const e of c[mano]) {
          const dur = e.dur * segPorCorchea;
          for (const nt of e.notas) {
            eventos.push({
              t: t0 + o * segPorCorchea,
              dur: Math.max(0.05, Math.min(dur * ARTICULACION, dur - HUECO_MINIMO)),
              canal,
              nota: nt.midi,
              vel: INTENSIDAD[mano],
            });
          }
          o += e.dur;
        }
      }
    });
  }
  eventos.sort((a, b) => a.t - b.t);
  return { eventos, inicio, vuelta, vueltas: n, segPorCompas, compases: cs.length, duracion: inicio + n * vuelta + 0.5 };
}

// En qué compás de la progresión cae el segundo `t` del plan: -1 en la cuenta.
export function compasQueSuena(plan, t) {
  if (t < plan.inicio) return -1;
  return Math.floor((t - plan.inicio) / plan.segPorCompas + 1e-6) % plan.compases;
}

// --- La página ------------------------------------------------------------------

// Por debajo de este ancho, dos compases por línea.
const ANCHO_DE_CUATRO = 560;
const ANCHO_MAXIMO = 740;

export function disposicion(ancho) {
  return {
    porLinea: ancho < ANCHO_DE_CUATRO ? 2 : 4,
    // De 20 en 20: que arrastrar el borde de la ventana no repinte a cada píxel.
    staffwidth: Math.max(280, Math.min(ANCHO_MAXIMO, Math.floor((ancho - 24) / 20) * 20)),
  };
}

function montarPatron(el) {
  if (el.dataset.montado) return;
  el.dataset.montado = "1";
  const D = window.Dictado;
  let datos;
  try {
    datos = JSON.parse(el.dataset.patronPiano || "{}");
  } catch (e) {
    console.error("[patrón de piano] datos ilegibles", e);
    return;
  }
  const destino = el.querySelector("[data-pp-partitura]");
  const estado = el.querySelector("[data-pp-estado]");
  const selTonalidad = el.querySelector("[data-pp-tonalidad]");
  const btnTocar = el.querySelector("[data-pp-tocar]");
  const btnParar = el.querySelector("[data-pp-parar]");
  const chkBucle = el.querySelector("[data-pp-bucle]");
  const chkClaqueta = el.querySelector("[data-pp-claqueta]");
  const selManos = el.querySelector("[data-pp-manos]");
  const inpTempo = el.querySelector("[data-pp-tempo]");
  const urls = D.urlsDe(el);
  const decir = (texto) => { if (estado) estado.textContent = texto; };

  let idTonalidad = datos.tonalidad;
  let plan = null;
  let cargado = false;
  let enMarcha = false;
  let pintado = "";
  let marcado = -2;

  function losCompases() {
    return compases(tonalidad(idTonalidad), datos.grados, patron(datos.patron));
  }

  // En el proyector el patrón entero tiene que caber en la pantalla. Aquí solo
  // se dice la proporción de lo pintado; el tope de ancho lo pone la hoja de
  // estilos de la ficha con ella y con el alto de la ventana, así que no hay
  // que volver a medir cuando cambia la pantalla. abcjs guarda la proporción.
  function encajar() {
    const svg = destino && destino.querySelector("svg");
    const caja = svg && svg.viewBox ? svg.viewBox.baseVal : null;
    if (caja && caja.width && caja.height) el.style.setProperty("--pp-proporcion", (caja.width / caja.height).toFixed(4));
  }

  function pintar() {
    if (!destino) return;
    if (!destino.clientWidth) return; // escondido (otra diapositiva): se pinta al aparecer
    // El ancho del ejercicio, no el de la partitura: en clase esta puede ir
    // estrechada para caber, y decidir con ella haría repintar en bucle.
    const d = disposicion(el.clientWidth);
    const clave = [idTonalidad, d.porLinea, d.staffwidth].join("|");
    if (clave === pintado) return;
    D.cargarScript(urls.abcjs, "ABCJS").then((ABCJS) => {
      try {
        const texto = abc(tonalidad(idTonalidad), datos.grados, patron(datos.patron), { porLinea: d.porLinea });
        ABCJS.renderAbc(destino, texto, { responsive: "resize", add_classes: true, staffwidth: d.staffwidth, paddingtop: 0, paddingbottom: 0 });
        pintado = clave;
        marcado = -2;
        encajar();
      } catch (e) {
        console.error("[patrón de piano]", e);
        decir("No se puede escribir este patrón: " + e.message);
      }
    }, () => decir("No se pudo cargar la partitura."));
  }

  function marcar(compas) {
    if (compas === marcado || !destino) return;
    marcado = compas;
    destino.querySelectorAll(".pp-suena").forEach((x) => x.classList.remove("pp-suena"));
    // Solo lo que se toca y su cifrado: la clave, el compás y el tempo llevan
    // también la clase del primer compás, y no son de él.
    if (compas >= 0) {
      const mm = ".abcjs-mm" + compas;
      const que = [".abcjs-note", ".abcjs-rest", ".abcjs-chord", ".abcjs-annotation"].map((c) => c + mm).join(", ");
      destino.querySelectorAll(que).forEach((x) => x.classList.add("pp-suena"));
    }
  }

  function mezcla(m) {
    const manos = selManos ? selManos.value : "";
    m.mezclar(new Map([
      [CANAL_DERECHA, { mudo: manos === "izquierda", ganancia: 1 }],
      [CANAL_IZQUIERDA, { mudo: manos === "derecha", ganancia: 1 }],
      [D.CANAL_CLAQUETA, { mudo: !!(chkClaqueta && !chkClaqueta.checked), ganancia: 1 }],
    ]));
  }

  // El tempo no rehace el MIDI: es la velocidad a la que lo lee el motor.
  function velocidad() {
    const pedido = inpTempo ? Number(inpTempo.value) : 0;
    if (!pedido || pedido < 30 || pedido > 240) return 1;
    return pedido / datos.tempo;
  }

  function alAvanzar(t) {
    if (!plan) return;
    const finDeLaPrimera = plan.inicio + plan.vuelta;
    if (chkBucle && !chkBucle.checked && t >= finDeLaPrimera) return parar("");
    if (t >= plan.duracion - 0.3) return parar("Terminado.");
    const compas = compasQueSuena(plan, t);
    marcar(compas);
    decir(compas < 0 ? "Cuenta…" : "Compás " + (compas + 1) + " de " + plan.compases);
  }

  async function tocar() {
    try {
      decir("Preparando…");
      if (!plan) plan = planPatron(losCompases(), { tempo: datos.tempo, claqueta: D.CLAQUETA, canalClaqueta: D.CANAL_CLAQUETA });
      const m = await D.elMotor(urls);
      D.tomarTurno(api);
      const ctx = D.contexto();
      if (ctx.state === "suspended") await ctx.resume();
      if (!cargado || m.__de !== el) {
        await m.cargar(D.aMidi(plan, { programa: 0, canales: [CANAL_DERECHA, CANAL_IZQUIERDA] }));
        m.__de = el;
        cargado = true;
      }
      mezcla(m);
      m.setUpdateInterval(0.1, alAvanzar);
      m.schedule({ rate: velocidad(), input: 0, active: true });
      enMarcha = true;
      if (btnParar) btnParar.hidden = false;
    } catch (e) {
      console.error("[patrón de piano]", e);
      decir("No se pudo tocar: " + e.message);
    }
  }

  // Al parar se devuelve el motor como estaba: es el mismo de los dictados, y
  // se quedaría con esta velocidad y con la claqueta o una mano apagadas.
  function parar(texto) {
    const m = D.motor();
    if (m && m.__de === el) {
      m.schedule({ active: false, rate: 1 });
      m.setUpdateInterval(1, () => {});
      m.mezclar(new Map([CANAL_DERECHA, CANAL_IZQUIERDA, D.CANAL_CLAQUETA].map((c) => [c, { mudo: false, ganancia: 1 }])));
    }
    enMarcha = false;
    D.soltarTurno(api);
    if (btnParar) btnParar.hidden = true;
    marcar(-1);
    decir(texto || "");
  }

  function conElMotorEnMarcha(hacer) {
    const m = D.motor();
    if (enMarcha && m && m.__de === el) hacer(m);
  }

  const api = { parar, plan: () => plan, tonalidad: () => idTonalidad };
  el.__patronPiano = api;

  if (selTonalidad) {
    selTonalidad.value = idTonalidad;
    selTonalidad.addEventListener("change", () => {
      if (enMarcha) parar("");
      idTonalidad = selTonalidad.value;
      plan = null;
      cargado = false;
      pintar();
    });
  }
  if (btnTocar) btnTocar.addEventListener("click", tocar);
  if (btnParar) btnParar.addEventListener("click", () => parar(""));
  if (selManos) selManos.addEventListener("change", () => conElMotorEnMarcha(mezcla));
  if (chkClaqueta) chkClaqueta.addEventListener("change", () => conElMotorEnMarcha(mezcla));
  if (inpTempo) inpTempo.addEventListener("change", () => conElMotorEnMarcha((m) => m.schedule({ rate: velocidad() })));

  if (destino && typeof ResizeObserver !== "undefined") {
    let reloj = null;
    new ResizeObserver(() => {
      clearTimeout(reloj);
      reloj = setTimeout(pintar, 150);
    }).observe(destino);
  }
  pintar();
}

export function montar(raiz) {
  (raiz || document).querySelectorAll("[data-patron-piano]").forEach(montarPatron);
}

if (typeof window !== "undefined") {
  window.PatronPiano = { montar, tonalidad, patron, compases, abc, planPatron, compasQueSuena, disposicion, nombreDeNota, TONALIDADES, PATRONES };
}
