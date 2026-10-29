// Motor de las pistas MIDI del reproductor de práctica (fase 85).
//
// Un MIDI no es audio ya hecho: el navegador lo toca nota a nota con un banco
// de sonidos, y por eso cada parte (bajo, melodía, batería…) se puede apagar,
// subir o dejar sola, el tono cambia moviendo notas en vez de estirar el audio,
// y la velocidad cambia el tempo sin deformar nada. El sintetizador es
// SpessaSynth (Apache-2.0): spessasynth_lib 4.3.14 con spessasynth_core 4.3.20,
// fijados en package.json; su procesador de AudioWorklet se sirve aparte desde
// static/vendor/spessasynth/ (ver el LEEME.txt de esa carpeta).
//
// Tiene la misma cara que el nodo de Signalsmith que usa el reproductor
// (`schedule`, `setUpdateInterval`, `dropBuffers`, `stop`), más `cargar(bytes)`
// y `mezclar(sonido)`. Lo carga reproductor_practica.js solo cuando la pista
// elegida es MIDI: quien solo tiene grabaciones no descarga nada de esto.
//
// Queda en `window.MotorMidi.crear(contexto, { procesador, banco })`.

import { Sequencer, WorkletSynthesizer } from "spessasynth_lib";
import { BasicMIDI } from "spessasynth_core";
import { resumirCanales } from "./mezcla.js";

const NOTA_ON = 0x90;
const PROGRAMA = 0xc0;

// Los eventos que necesita el mezclador, en orden de tiempo.
function eventosDe(midi) {
  const todos = [];
  for (const pista of midi.tracks) {
    for (const e of pista.events) {
      const tipo = e.statusByte & 0xf0;
      const canal = e.statusByte & 0x0f;
      if (tipo === PROGRAMA) todos.push({ ticks: e.ticks, canal, tipo: "programa", programa: e.data[0] });
      else if (tipo === NOTA_ON && e.data[1] > 0) todos.push({ ticks: e.ticks, canal, tipo: "nota" });
    }
  }
  return todos.sort((a, b) => a.ticks - b.ticks);
}

async function crear(ctx, op) {
  await ctx.audioWorklet.addModule(op.procesador);
  const synth = new WorkletSynthesizer(ctx);
  // Un nodo de ganancia entre el sintetizador y los altavoces: es el punto
  // donde se puede medir la salida (fase 85, comprobaciones con AnalyserNode).
  const salida = ctx.createGain();
  synth.connect(salida);
  salida.connect(ctx.destination);
  const r = await fetch(op.banco, { credentials: "same-origin" });
  if (!r.ok) throw new Error("No se pudo descargar el banco de sonidos (" + r.status + ").");
  await synth.soundBankManager.addSoundBank(await r.arrayBuffer(), "main");
  await synth.isReady;
  const seq = new Sequencer(synth);

  let duracion = 0;
  let activo = false;
  let bucle = null;
  let canales = [];
  let reloj = null;
  let alAvanzar = null;
  // Saltar es un mensaje al worklet: hasta que contesta, `seq.currentTime`
  // sigue dando la posición de antes. Durante ese rato vale la del salto.
  let salto = null;           // { t, desde, hasta }

  function saltar(t) {
    seq.currentTime = t;
    salto = { t, desde: performance.now(), hasta: performance.now() + 250 };
  }

  function ahora() {
    if (salto && performance.now() < salto.hasta) {
      return salto.t + (activo ? ((performance.now() - salto.desde) / 1000) * seq.playbackRate : 0);
    }
    salto = null;
    return seq.currentTime;
  }

  function tic() {
    if (!activo) return;
    let t = ahora();
    // El bucle lo lleva el motor: el secuenciador solo sabe repetir la
    // canción entera. Volver atrás es un salto, como al tocar un párrafo.
    if (bucle && t >= bucle.fin && !salto) { saltar(bucle.inicio); t = bucle.inicio; }
    if (alAvanzar) alAvanzar(t);
  }

  return {
    salida,
    synth,
    seq,
    get canales() { return canales; },

    // Deja el MIDI listo y parado. Devuelve su duración en segundos.
    async cargar(bytes) {
      const midi = BasicMIDI.fromArrayBuffer(bytes.slice(0));
      canales = resumirCanales(eventosDe(midi));
      duracion = midi.duration;
      // Si el worklet no contesta, mejor un aviso que un «Descargando…» eterno.
      let plazo = null;
      const cambiada = new Promise((ok, mal) => {
        seq.eventHandler.addEvent("songChange", "cpr-carga", () => ok());
        plazo = setTimeout(() => mal(new Error("No se pudo preparar el MIDI.")), 20000);
      });
      seq.loadNewSongList([{ binary: bytes, fileName: "pista.mid" }]);
      try {
        await cambiada;
      } finally {
        clearTimeout(plazo);
        seq.eventHandler.removeEvent("songChange", "cpr-carga");
      }
      seq.loopCount = 0;
      seq.pause();
      activo = false;
      return duracion;
    },

    // Lo mismo que `schedule` de Signalsmith: { active, input, rate,
    // semitones, loopStart, loopEnd }. El tono es el `keyShift` global, que la
    // batería no sigue (spessasynth_core: «Drum channels ignore this value»).
    schedule(o) {
      if ("rate" in o) seq.playbackRate = o.rate;
      if ("semitones" in o) synth.setSystemParameter("keyShift", o.semitones);
      if ("loopStart" in o || "loopEnd" in o) {
        bucle = o.loopEnd > o.loopStart ? { inicio: o.loopStart, fin: o.loopEnd } : null;
      }
      if ("input" in o) saltar(o.input);
      if ("active" in o && o.active !== activo) {
        activo = o.active;
        if (activo) seq.play(); else seq.pause();
      }
    },

    setUpdateInterval(segundos, cb) {
      alAvanzar = cb;
      clearInterval(reloj);
      reloj = setInterval(tic, segundos * 1000);
    },

    // `sonido` sale de mezcla.js: Map canal → { mudo, ganancia }.
    mezclar(sonido) {
      for (const [canal, s] of sonido) {
        const ch = synth.midiChannels[canal];
        if (!ch) continue;
        ch.setSystemParameter("isMuted", s.mudo);
        ch.setSystemParameter("gain", s.ganancia);
      }
    },

    async dropBuffers() {
      activo = false;
      seq.pause();
    },

    stop() {
      activo = false;
      clearInterval(reloj);
      try { seq.pause(); } catch (e) { /* ya parado */ }
    },

    disconnect() {
      try { salida.disconnect(); synth.disconnect(); } catch (e) { /* ya desconectado */ }
    },
  };
}

window.MotorMidi = { crear };
