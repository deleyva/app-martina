// Reproductor de práctica del visor ChordPro (fase 82).
//
// Una grabación subida a la canción (el original o un backing track) suena en
// el tono que tiene la letra en pantalla, más lenta si se quiere y en bucle, y
// salta a cada párrafo por sus marcas de tiempo. Es lo que hacen Songsterr
// (vídeo sincronizado por compás) y Transpose (tono, velocidad y bucles) pero
// con un audio propio, que es el único que una página puede transportar: el de
// YouTube vive en otro dominio y su sonido no está al alcance de la página.
//
// El motor es Signalsmith Stretch (MIT), servido aparte y sin pasar por esbuild
// (ver static/vendor/signalsmith-stretch/LEEME.txt). Trabaja sobre el audio ya
// decodificado: en modo «entrada en vivo» no cambia la velocidad ni hace
// bucles. Por eso se descarga la pista entera antes de sonar.
//
// Lo carga el visor (`my_library/viewers/chordpro_viewer.html`) al pulsar 🎧,
// y queda en `window.ReproductorPractica.montar(opciones)`.

import * as P from "./practica.js";

const VELOCIDAD_MIN = 0.25;
const VELOCIDAD_MAX = 1.5;
// Se pulsa la marca un poco tarde: lo que tarda el dedo en reaccionar al oír
// que empieza el párrafo.
const REACCION = 0.12;

// Teclas libres en las tres páginas que incluyen el visor: el modo clase ya usa
// m, v, p, d, c, t, s, n, l y e, y la sesión de estudio la m.
const TECLAS = { k: "play", x: "marca", r: "seccion", a: "a", b: "b", ",": "atras", ".": "adelante" };

const ESTILOS = `
.cpr { position: fixed; left: 0; right: 0; z-index: 9999; background: rgba(20,20,24,.96); color: #fff;
       font: 14px system-ui, sans-serif; padding: 8px 12px; box-sizing: border-box; border-top: 1px solid #333; }
.cpr-fila { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; justify-content: center; margin: 3px 0; }
.cpr [hidden] { display: none !important; }
.cpr button, .cpr select, .cpr input:not([type=range]) { background: #333; color: #fff; border: 1px solid #555;
       border-radius: 6px; padding: 5px 10px; font: inherit; }
.cpr button { cursor: pointer; min-width: 36px; }
.cpr button:hover { background: #444; }
.cpr button:disabled { opacity: .45; cursor: default; }
.cpr button[aria-pressed="true"] { background: #1d4ed8; border-color: #1d4ed8; }
.cpr .cpr-play { font-size: 18px; min-width: 52px; }
.cpr .cpr-grupo { display: inline-flex; gap: 4px; align-items: center; }
.cpr .cpr-tiempo { font-variant-numeric: tabular-nums; min-width: 7.5em; text-align: center; }
.cpr .cpr-pista { position: relative; flex: 1 1 260px; max-width: 900px; height: 28px; }
.cpr .cpr-pista input { position: absolute; inset: 0; width: 100%; margin: 0; z-index: 2; background: transparent; }
.cpr .cpr-tick { position: absolute; top: 2px; bottom: 2px; width: 2px; background: #f59e0b; z-index: 1; pointer-events: none; }
.cpr .cpr-tramo { position: absolute; top: 4px; bottom: 4px; background: rgba(59,130,246,.35); border-radius: 3px; z-index: 0; pointer-events: none; }
.cpr .cpr-aviso { color: #fde68a; }
.cpr .cpr-marcado { background: #3b2f0b; border-radius: 8px; padding: 6px; }
.cpr .cpr-marca { background: #b45309; border-color: #b45309; font-weight: 700; }
.cpr form { background: #1f2937; border-radius: 8px; padding: 8px; }
.cpv-salida .paragraph.cpr-marcado { position: relative; }
.cpv-salida .paragraph.cpr-marcado::before { content: attr(data-cpr-t); position: absolute; left: -64px; top: .1em;
       font: 600 12px system-ui, sans-serif; color: #b45309; background: #fef3c7; border-radius: 6px; padding: 1px 6px; cursor: pointer; }
.cpv-salida .paragraph.cpr-sonando { background: #fef9c3; box-shadow: 0 0 0 8px #fef9c3; border-radius: 4px; }
.cpv-salida.cpr-modo-marcar .paragraph { cursor: crosshair; outline: 1px dashed #d1d5db; outline-offset: 4px; }
.cpv-salida.cpr-modo-marcar .paragraph.cpr-siguiente { outline: 2px solid #b45309; }
@media (max-width: 760px) { .cpv-salida .paragraph.cpr-marcado::before { position: static; display: inline-block; margin-bottom: 2px; } }
@media print { .cpr { display: none !important; }
  .cpv-salida .paragraph.cpr-marcado::before { display: none !important; }
  .cpv-salida .paragraph.cpr-sonando { background: none !important; box-shadow: none !important; } }
`;

function estilos() {
  if (document.getElementById("cpr-estilos")) return;
  const s = document.createElement("style");
  s.id = "cpr-estilos";
  s.textContent = ESTILOS;
  document.head.appendChild(s);
}

function cargarScript(src) {
  return new Promise((ok, mal) => {
    if (window.SignalsmithStretch) return ok();
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => ok();
    s.onerror = () => mal(new Error("No se pudo cargar el motor de audio."));
    document.head.appendChild(s);
  });
}

function escribiendo(el) {
  return el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

function leerLocal(clave) {
  try { return localStorage.getItem(clave); } catch (e) { return null; }
}
function guardarLocal(clave, valor) {
  try { localStorage.setItem(clave, valor); } catch (e) { /* modo privado: da igual */ }
}

// El texto de un párrafo SIN los acordes: con ellos, el ancla de «Intro [G]»
// cambiaba al transportar (G → Ab) y la marca se perdía. Un párrafo que solo
// tiene acordes se queda sin ancla, y entonces la marca va por su número.
function textoDe(parrafo) {
  const copia = parrafo.cloneNode(true);
  copia.querySelectorAll(".chord").forEach((e) => e.remove());
  return copia.textContent;
}

function plantilla(puedeEditar) {
  const opciones = [];
  for (let s = -11; s <= 11; s++) {
    opciones.push(`<option value="${s}"${s === 0 ? " selected" : ""}>${s > 0 ? "+" : ""}${s}</option>`);
  }
  return `
  <div class="cpr-fila">
    <button type="button" class="cpr-play" data-c="play" title="Reproducir o pausar (K)">▶</button>
    <span class="cpr-tiempo" data-v="tiempo">0:00 / 0:00</span>
    <div class="cpr-pista">
      <div data-v="tramo"></div>
      <div data-v="ticks"></div>
      <input type="range" data-c="pos" min="0" max="0" step="0.05" value="0" aria-label="Posición">
    </div>
    <button type="button" data-c="cerrar" title="Cerrar el reproductor">✕</button>
  </div>
  <div class="cpr-fila">
    <select data-c="pista" title="Grabación"></select>
    <span class="cpr-grupo" title="Velocidad, sin cambiar el tono">
      <button type="button" data-c="vel-">−</button><span data-v="vel">100 %</span><button type="button" data-c="vel+">+</button>
    </span>
    <button type="button" data-c="tono" aria-pressed="true"
            title="Que el audio suene en el tono de la letra en pantalla, o en el de la grabación">🎵 Tono de la letra</button>
    <span class="cpr-grupo">
      <button type="button" data-c="a" title="Empieza el bucle aquí (A)">A</button>
      <button type="button" data-c="b" title="Acaba el bucle aquí (B)">B</button>
      <button type="button" data-c="seccion" aria-pressed="false" title="Repetir el párrafo que suena (R)">🔁 Párrafo</button>
      <button type="button" data-c="sinbucle" title="Quitar el bucle">Sin bucle</button>
    </span>
    <button type="button" data-c="seguir" aria-pressed="true" title="La letra va al párrafo que suena">Seguir</button>
    ${puedeEditar ? `
    <span class="cpr-grupo">
      <button type="button" data-c="marcar" aria-pressed="false" title="Marcar dónde empieza cada párrafo">✎ Marcar</button>
      <span class="cpr-grupo" title="Cuántos semitonos suena la grabación por encima de la letra tal como está escrita">
        Grabación <button type="button" data-c="des-">−</button><span data-v="des">0</span><button type="button" data-c="des+">+</button>
      </span>
      <button type="button" data-c="nueva" title="Subir otra grabación">＋ Audio</button>
      <button type="button" data-c="borrar" title="Borrar esta grabación">🗑</button>
    </span>` : ""}
  </div>
  <div class="cpr-fila cpr-aviso" data-v="estado" hidden></div>
  ${puedeEditar ? `
  <div class="cpr-fila cpr-marcado" data-v="marcado" hidden>
    <span>Pulsa <b>X</b> o ⏺ cuando empiece cada párrafo, o toca un párrafo para ponerle el segundo actual. Siguiente: <b data-v="siguiente">—</b></span>
    <button type="button" class="cpr-marca" data-c="marca">⏺ Marca (X)</button>
    <button type="button" data-c="deshacer" title="Quitar la última marca">↶</button>
    <button type="button" data-c="limpiar">Borrar todas</button>
    <span data-v="guardado"></span>
  </div>
  <form class="cpr-fila" data-v="form" hidden>
    <input type="file" name="archivo" accept="audio/*,.mp3,.m4a,.ogg,.wav,.flac,.opus" required>
    <input type="text" name="nombre" value="Original" maxlength="80" placeholder="Nombre" required style="width: 12em">
    <label>Suena <select name="semitonos">${opciones.join("")}</select> semitonos por encima de la letra escrita</label>
    <button type="submit">Subir</button>
    <button type="button" data-c="cancelar">Cancelar</button>
  </form>` : ""}`;
}

function montar(op) {
  const { visor, salida, barra, csrf } = op;
  const datos = op.datos || {};
  const pistas = (datos.pistas || []).slice();
  const puedeEditar = !!datos.puedeEditar;
  estilos();

  const panel = document.createElement("div");
  panel.className = "cpr";
  panel.setAttribute("data-cpr", "");
  panel.hidden = true;
  panel.innerHTML = plantilla(puedeEditar);
  barra.after(panel);
  const v = (n) => panel.querySelector(`[data-v="${n}"]`);
  const c = (n) => panel.querySelector(`[data-c="${n}"]`);

  let actual = pistas[0] || null;
  // El visor lo crea dentro del toque en 🎧, antes de cargar este fichero.
  let ctx = op.contexto || null;
  let nodo = null;
  let cargada = null;
  let cargando = null;
  let duracion = 0;
  let posicion = 0;
  let sonando = false;
  let velocidad = 1;
  let tonoDeLetra = true;
  let bucle = null;           // { inicio, fin, tipo: "ab" | "seccion" }
  let puntoA = null;
  let seguir = true;
  let marcando = false;
  let marcas = [];            // las de `actual`, reancladas a la letra de ahora
  let seccion = -1;
  let parrafos = [];
  let abierto = false;
  let destruido = false;
  const paddingOriginal = visor.style.paddingBottom;

  // ── Estado en pantalla ──
  function avisar(texto) {
    const e = v("estado");
    e.textContent = texto || "";
    e.hidden = !texto;
    colocar();
  }

  function semitonosAudio() {
    if (!actual || !tonoDeLetra) return 0;
    return P.semitonosDelAudio(op.semitonosLetra(), actual.semitonos);
  }

  function pintarSelector() {
    const sel = c("pista");
    sel.innerHTML = "";
    for (const p of pistas) {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.nombre;
      sel.appendChild(o);
    }
    sel.hidden = pistas.length < 2;
    if (actual) sel.value = actual.id;
  }

  function pintarControles() {
    const hay = !!actual;
    for (const n of ["play", "pos", "vel-", "vel+", "tono", "a", "b", "seccion", "sinbucle", "seguir", "marcar", "des-", "des+", "borrar"]) {
      const b = c(n);
      if (b) b.disabled = !hay;
    }
    c("play").textContent = sonando ? "⏸" : "▶";
    v("vel").textContent = Math.round(velocidad * 100) + " %";
    const s = semitonosAudio();
    const tono = c("tono");
    tono.setAttribute("aria-pressed", tonoDeLetra ? "true" : "false");
    tono.textContent = tonoDeLetra
      ? "🎵 Tono de la letra" + (s ? ` (${s > 0 ? "+" : ""}${s})` : "")
      : "🎵 Tono de la grabación";
    c("seccion").setAttribute("aria-pressed", bucle && bucle.tipo === "seccion" ? "true" : "false");
    c("seguir").setAttribute("aria-pressed", seguir ? "true" : "false");
    c("a").setAttribute("aria-pressed", puntoA !== null || (bucle && bucle.tipo === "ab") ? "true" : "false");
    if (puedeEditar) {
      v("des").textContent = actual ? (actual.semitonos > 0 ? "+" : "") + actual.semitonos : "0";
      c("marcar").setAttribute("aria-pressed", marcando ? "true" : "false");
      v("marcado").hidden = !marcando;
    }
    pintarPosicion();
    pintarTicks();
  }

  function pintarPosicion() {
    const pos = c("pos");
    pos.max = String(duracion || 0);
    if (document.activeElement !== pos) pos.value = String(posicion);
    v("tiempo").textContent = P.formatoTiempo(posicion) + " / " + P.formatoTiempo(duracion);
    const tramo = v("tramo");
    if (bucle && duracion) {
      tramo.className = "cpr-tramo";
      tramo.style.left = (bucle.inicio / duracion) * 100 + "%";
      tramo.style.width = ((bucle.fin - bucle.inicio) / duracion) * 100 + "%";
    } else {
      tramo.className = "";
    }
  }

  function pintarTicks() {
    const ticks = v("ticks");
    ticks.innerHTML = "";
    if (!duracion) return;
    for (const m of marcas) {
      const t = document.createElement("div");
      t.className = "cpr-tick";
      t.style.left = Math.min(100, (m.t / duracion) * 100) + "%";
      ticks.appendChild(t);
    }
  }

  // ── La letra: marcas, párrafo que suena, siguiente por marcar ──
  function decorar() {
    parrafos = Array.from(salida.querySelectorAll(".paragraph"));
    const anclas = parrafos.map((p) => P.ancla(textoDe(p)));
    const r = P.reanclar(actual ? actual.marcas || [] : [], anclas);
    marcas = r.marcas;
    const porParrafo = new Map(marcas.map((m) => [m.p, m]));
    parrafos.forEach((el, i) => {
      const m = abierto ? porParrafo.get(i) : null;
      el.classList.toggle("cpr-marcado", !!m);
      if (m) el.setAttribute("data-cpr-t", P.formatoTiempo(m.t));
      else el.removeAttribute("data-cpr-t");
      el.classList.remove("cpr-sonando", "cpr-siguiente");
    });
    salida.classList.toggle("cpr-modo-marcar", abierto && marcando);
    seccion = -1;
    pintarSeccion();
    pintarTicks();
  }

  function pintarSeccion(saltar) {
    if (!abierto) return;
    const ahora = P.seccionEn(marcas, posicion);
    if (ahora !== seccion || saltar) {
      const antes = seccion;
      seccion = ahora;
      parrafos.forEach((el) => el.classList.remove("cpr-sonando"));
      const m = marcas[seccion];
      const el = m ? parrafos[m.p] : null;
      // Resaltado también en pausa: dice dónde se va a seguir.
      if (el && cargada !== null) el.classList.add("cpr-sonando");
      if (el && seguir && (saltar || (sonando && antes !== seccion))) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }
    if (marcando) {
      const sig = P.siguientePorMarcar(marcas, parrafos.length, posicion);
      parrafos.forEach((el, i) => el.classList.toggle("cpr-siguiente", i === sig));
      v("siguiente").textContent = sig < 0 ? "ya no quedan párrafos" : "«" + textoDe(parrafos[sig]).trim().slice(0, 40) + "…»";
    }
  }

  // ── Motor ──
  // El AudioContext se crea dentro del toque del usuario: fuera de él, Safari
  // y Chrome lo dejan mudo.
  function contexto() {
    if (!ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) throw new Error("Este navegador no reproduce audio con Web Audio.");
      // iPhone: sin esto, el interruptor de silencio apaga el audio de la web.
      try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) { /* no pasa nada */ }
      ctx = new Ctx();
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  async function motor() {
    if (nodo) return nodo;
    const audio = contexto();
    if (!audio.audioWorklet) throw new Error("Este navegador no puede cambiar el tono ni la velocidad (le falta AudioWorklet).");
    await cargarScript(op.motor);
    nodo = await window.SignalsmithStretch(audio);
    nodo.connect(audio.destination);
    nodo.setUpdateInterval(0.05, alAvanzar);
    return nodo;
  }

  async function descargar(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(r.status === 404 ? "Esta grabación ya no existe." : "No se pudo descargar el audio (" + r.status + ").");
    const total = Number(r.headers.get("Content-Length")) || 0;
    if (!r.body || !total) return r.arrayBuffer();
    const lector = r.body.getReader();
    const trozos = [];
    let recibido = 0;
    for (;;) {
      const { done, value } = await lector.read();
      if (done) break;
      trozos.push(value);
      recibido += value.length;
      avisar("Descargando la grabación… " + Math.round((recibido / total) * 100) + " %");
    }
    const todo = new Uint8Array(recibido);
    let i = 0;
    for (const t of trozos) { todo.set(t, i); i += t.length; }
    return todo.buffer;
  }

  function cargar(pista) {
    if (cargada === pista.id) return Promise.resolve();
    if (cargando && cargando.id === pista.id) return cargando.promesa;
    const promesa = (async () => {
      await motor();
      avisar("Descargando la grabación…");
      const bytes = await descargar(pista.audio);
      avisar("Preparando la grabación…");
      let buf;
      try {
        buf = await ctx.decodeAudioData(bytes);
      } catch (e) {
        throw new Error("Este navegador no sabe leer ese formato de audio. Prueba con MP3.");
      }
      if (actual !== pista) return;   // se cambió de pista mientras bajaba
      await nodo.dropBuffers();
      // Copias propias de cada canal, que se TRANSFIEREN al worklet: el búfer
      // decodificado se libera y no hay dos copias de la canción en memoria.
      const canales = [];
      for (let i = 0; i < Math.min(2, buf.numberOfChannels); i++) canales.push(new Float32Array(buf.getChannelData(i)));
      if (canales.length === 1) canales.push(new Float32Array(canales[0]));
      duracion = await nodo.addBuffers(canales, canales.map((a) => a.buffer));
      cargada = pista.id;
      posicion = 0;
      avisar("");
      pintarControles();
    })();
    cargando = { id: pista.id, promesa };
    promesa.catch(() => {}).then(() => { if (cargando && cargando.promesa === promesa) cargando = null; });
    return promesa;
  }

  function aplicar(extra) {
    if (!nodo) return;
    if (extra && "input" in extra) ignorarHasta = performance.now() + 200;
    nodo.schedule(Object.assign({
      active: sonando,
      rate: velocidad,
      semitones: semitonosAudio(),
      loopStart: bucle ? bucle.inicio : 0,
      loopEnd: bucle ? bucle.fin : 0,
    }, extra || {}));
  }

  // Justo después de un salto, el motor aún manda alguna posición de antes: sin
  // esto el resaltado (y con «Seguir», la letra) iría y volvería.
  let ignorarHasta = 0;

  function alAvanzar(t) {
    if (destruido) return;
    if (!visor.isConnected) { destruir(); return; }
    if (cargada === null || !sonando || performance.now() < ignorarHasta) return;
    posicion = t;
    if (sonando && !bucle && duracion && t >= duracion - 0.03) {
      sonando = false;
      posicion = duracion;
      aplicar();
      pintarControles();
    }
    pintarPosicion();
    pintarSeccion();
  }

  async function reproducir() {
    if (!actual) return;
    contexto();
    try {
      await cargar(actual);
    } catch (e) {
      avisar(e.message);
      return;
    }
    if (posicion >= duracion - 0.05) posicion = bucle ? bucle.inicio : 0;
    sonando = true;
    aplicar({ input: posicion });
    pintarControles();
    pintarSeccion(true);
  }

  function pausar() {
    sonando = false;
    aplicar();
    pintarControles();
  }

  function ir(t, conservarBucle) {
    if (cargada === null) return;
    posicion = Math.max(0, Math.min(duracion, t));
    // Saltar fuera del bucle lo quita: si no, al llegar a su final volvería
    // atrás a un tramo que ya no se está mirando.
    if (bucle && !conservarBucle && (posicion < bucle.inicio || posicion >= bucle.fin)) bucle = null;
    aplicar({ input: posicion });
    pintarControles();
    pintarSeccion(true);
  }

  function ponerBucle(inicio, fin, tipo) {
    if (fin - inicio < 0.2) return;
    bucle = { inicio, fin, tipo };
    puntoA = null;
    if (posicion < inicio || posicion >= fin) ir(inicio, true);
    else aplicar();
    pintarControles();
  }

  function bucleDeSeccion(i) {
    const tramo = P.tramoDe(marcas, i, duracion);
    if (tramo) ponerBucle(tramo.inicio, tramo.fin, "seccion");
  }

  function cambiarVelocidad(delta) {
    velocidad = Math.round(Math.max(VELOCIDAD_MIN, Math.min(VELOCIDAD_MAX, velocidad + delta)) * 100) / 100;
    if (actual) guardarLocal("cpr-vel:" + actual.id, String(velocidad));
    aplicar();
    pintarControles();
  }

  function elegir(pista) {
    if (sonando) pausar();
    actual = pista;
    bucle = null;
    puntoA = null;
    cargada = cargada === (pista && pista.id) ? cargada : null;
    duracion = cargada === null ? 0 : duracion;
    posicion = 0;
    velocidad = Number(pista && leerLocal("cpr-vel:" + pista.id)) || 1;
    pintarSelector();
    decorar();
    pintarControles();
    if (pista && abierto) cargar(pista).catch((e) => avisar(e.message));
  }

  // ── Guardar (solo profesorado) ──
  let guardando = null;
  function guardarPronto(cambios) {
    if (!actual) return;
    const pista = actual;
    clearTimeout(guardando);
    v("guardado").textContent = "…";
    guardando = setTimeout(() => {
      fetch(pista.guardar, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
        body: JSON.stringify(cambios()),
      })
        .then((r) => r.json().then((j) => { if (!r.ok) throw new Error(j.error || r.status); return j; }))
        .then((j) => {
          pista.marcas = j.marcas;
          pista.semitonos = j.semitonos;
          v("guardado").textContent = "✓ Guardado";
        })
        .catch((e) => { v("guardado").textContent = "No se ha guardado: " + e.message; avisar("No se ha guardado: " + e.message); });
    }, 600);
  }

  function guardarMarcas() {
    actual.marcas = marcas.slice();
    decorar();
    guardarPronto(() => ({ marcas: actual.marcas }));
  }

  function marcarParrafo(i, t) {
    if (!actual || i < 0 || i >= parrafos.length) return;
    marcas = P.marcar(marcas, i, t, P.ancla(textoDe(parrafos[i])));
    guardarMarcas();
  }

  function marcaAqui() {
    if (cargada === null) return;
    const sig = P.siguientePorMarcar(marcas, parrafos.length, posicion);
    if (sig < 0) return;
    marcarParrafo(sig, Math.max(0, posicion - (sonando ? REACCION * velocidad : 0)));
  }

  function cambiarDesfase(delta) {
    if (!actual) return;
    actual.semitonos = Math.max(-11, Math.min(11, actual.semitonos + delta));
    aplicar();
    pintarControles();
    guardarPronto(() => ({ semitonos: actual.semitonos }));
  }

  let confirmarBorrado = null;
  function borrar() {
    const b = c("borrar");
    if (!confirmarBorrado) {
      b.textContent = "¿Borrar «" + actual.nombre + "»? Sí";
      confirmarBorrado = setTimeout(() => { confirmarBorrado = null; b.textContent = "🗑"; }, 4000);
      return;
    }
    clearTimeout(confirmarBorrado);
    confirmarBorrado = null;
    b.textContent = "🗑";
    const pista = actual;
    fetch(pista.borrar, {
      method: "POST", credentials: "same-origin",
      headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
    })
      .then((r) => { if (!r.ok) throw new Error(r.status); })
      .then(() => {
        pistas.splice(pistas.indexOf(pista), 1);
        cargada = null;
        if (nodo) nodo.dropBuffers();
        elegir(pistas[0] || null);
        if (!pistas.length) mostrarFormulario(true);
      })
      .catch((e) => avisar("No se ha borrado: " + e.message));
  }

  function mostrarFormulario(si) {
    const f = v("form");
    if (!f) return;
    f.hidden = !si;
    colocar();
  }

  function subir(e) {
    e.preventDefault();
    const f = v("form");
    const boton = f.querySelector('button[type="submit"]');
    boton.disabled = true;
    avisar("Subiendo la grabación…");
    fetch(datos.subir, {
      method: "POST", credentials: "same-origin",
      headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
      body: new FormData(f),
    })
      .then((r) => r.json().then((j) => { if (!r.ok) throw new Error(j.error || r.status); return j; }))
      .then((pista) => {
        pistas.push(pista);
        f.reset();
        mostrarFormulario(false);
        avisar("");
        elegir(pista);
      })
      .catch((err) => avisar("No se ha subido: " + err.message))
      .then(() => { boton.disabled = false; });
  }

  // ── Colocación: encima de la barra del visor, sin tapar la letra ──
  function colocar() {
    if (destruido) return;
    panel.style.bottom = barra.offsetHeight + "px";
    visor.style.paddingBottom = abierto ? barra.offsetHeight + panel.offsetHeight + 24 + "px" : paddingOriginal;
  }
  const vigia = "ResizeObserver" in window ? new ResizeObserver(colocar) : null;
  if (vigia) { vigia.observe(barra); vigia.observe(panel); }
  window.addEventListener("resize", colocar);

  // ── Abrir, cerrar, destruir ──
  function abrir() {
    abierto = true;
    panel.hidden = false;
    pintarSelector();
    decorar();
    pintarControles();
    colocar();
    if (actual) {
      // El 🎧 es un toque: aquí ya se puede crear el audio y adelantar la descarga.
      try { contexto(); } catch (e) { avisar(e.message); return; }
      cargar(actual).catch((e) => avisar(e.message));
    } else if (puedeEditar) {
      mostrarFormulario(true);
    }
  }

  function cerrar() {
    if (sonando) pausar();
    abierto = false;
    marcando = false;
    panel.hidden = true;
    decorar();
    colocar();
  }

  function destruir() {
    if (destruido) return;
    destruido = true;
    sonando = false;
    try { if (nodo) { nodo.stop(); nodo.disconnect(); } } catch (e) { /* ya parado */ }
    try { if (ctx) ctx.close(); } catch (e) { /* ya cerrado */ }
    if (vigia) vigia.disconnect();
    window.removeEventListener("resize", colocar);
    document.removeEventListener("keydown", teclado);
    clearInterval(guardia);
    panel.remove();
  }

  // El modo proyector cambia el elemento sin avisar a nadie: si el visor ya no
  // está en la página, el audio se apaga solo.
  const guardia = setInterval(() => { if (!visor.isConnected) destruir(); }, 1000);

  // ── Eventos ──
  panel.addEventListener("click", (e) => {
    const b = e.target.closest("[data-c]");
    if (!b || b.disabled) return;
    const n = b.getAttribute("data-c");
    if (n === "play") sonando ? pausar() : reproducir();
    else if (n === "cerrar") cerrar();
    else if (n === "vel-") cambiarVelocidad(-0.05);
    else if (n === "vel+") cambiarVelocidad(0.05);
    else if (n === "tono") { tonoDeLetra = !tonoDeLetra; aplicar(); pintarControles(); }
    else if (n === "a") { puntoA = posicion; pintarControles(); }
    else if (n === "b") {
      if (puntoA !== null && posicion > puntoA) ponerBucle(puntoA, posicion, "ab");
      else if (bucle) ponerBucle(bucle.inicio, posicion, "ab");
    }
    else if (n === "seccion") {
      if (bucle && bucle.tipo === "seccion") { bucle = null; aplicar(); pintarControles(); }
      else bucleDeSeccion(Math.max(0, P.seccionEn(marcas, posicion)));
    }
    else if (n === "sinbucle") { bucle = null; puntoA = null; aplicar(); pintarControles(); }
    else if (n === "seguir") { seguir = !seguir; pintarControles(); }
    else if (n === "marcar") { marcando = !marcando; decorar(); pintarControles(); colocar(); }
    else if (n === "marca") marcaAqui();
    else if (n === "deshacer") {
      if (!marcas.length) return;
      const ultima = marcas.reduce((a, m) => (m.p > a.p ? m : a));
      marcas = marcas.filter((m) => m !== ultima);
      guardarMarcas();
    }
    else if (n === "limpiar") { marcas = []; guardarMarcas(); }
    else if (n === "des-") cambiarDesfase(-1);
    else if (n === "des+") cambiarDesfase(1);
    else if (n === "nueva") mostrarFormulario(v("form").hidden);
    else if (n === "cancelar") mostrarFormulario(false);
    else if (n === "borrar") borrar();
  });
  c("pista").addEventListener("change", (e) => {
    const p = pistas.find((x) => String(x.id) === e.target.value);
    if (p) elegir(p);
  });
  c("pos").addEventListener("input", (e) => {
    posicion = Number(e.target.value);
    v("tiempo").textContent = P.formatoTiempo(posicion) + " / " + P.formatoTiempo(duracion);
  });
  c("pos").addEventListener("change", (e) => ir(Number(e.target.value)));
  if (v("form")) v("form").addEventListener("submit", subir);

  // Tocar un párrafo: en modo marcar le pone el segundo actual; si no, salta
  // a su marca. Tocar un acorde sigue abriendo su diagrama.
  salida.addEventListener("click", (e) => {
    if (!abierto || cargada === null) return;
    const acorde = e.target.closest(".chord");
    if (acorde && acorde.textContent.trim()) return;
    const parrafo = e.target.closest(".paragraph");
    if (!parrafo) return;
    const i = parrafos.indexOf(parrafo);
    if (marcando) { marcarParrafo(i, posicion); return; }
    const k = marcas.findIndex((m) => m.p === i);
    if (k < 0) return;
    if (bucle && bucle.tipo === "seccion") bucleDeSeccion(k);
    else ir(marcas[k].t);
    if (!sonando) reproducir();
  });

  // El visor avisa cada vez que repinta la letra (transporte, edición): las
  // marcas se vuelven a colgar de los párrafos y el audio sigue al tono.
  visor.addEventListener("cpv:pintado", () => {
    if (destruido) return;
    decorar();
    aplicar();
    pintarControles();
  });

  function teclado(e) {
    if (!visor.isConnected) { destruir(); return; }
    if (!abierto || escribiendo(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    const accion = TECLAS[e.key.toLowerCase()];
    if (!accion) return;
    e.preventDefault();
    if (accion === "play") c("play").click();
    else if (accion === "marca") { if (marcando) marcaAqui(); }
    else if (accion === "seccion") c("seccion").click();
    else if (accion === "a") c("a").click();
    else if (accion === "b") c("b").click();
    else if (accion === "atras") ir(posicion - 5);
    else if (accion === "adelante") ir(posicion + 5);
  }
  document.addEventListener("keydown", teclado);

  if (actual) velocidad = Number(leerLocal("cpr-vel:" + actual.id)) || 1;
  pintarSelector();
  pintarControles();

  const api = {
    abrir, cerrar,
    alternar() { abierto ? cerrar() : abrir(); return abierto; },
    destruir,
    // Para comprobar en el navegador que el audio hace lo que dice (fase 82):
    // el contexto y el nodo para medir la salida, y el estado.
    get contexto() { return ctx; },
    get nodo() { return nodo; },
    get estado() {
      return { pista: actual && actual.id, cargada, duracion, posicion, sonando, velocidad,
        semitonos: semitonosAudio(), bucle, marcas: marcas.slice(), seccion };
    },
  };
  visor.reproductorPractica = api;
  return api;
}

window.ReproductorPractica = { montar };
