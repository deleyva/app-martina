// Un MIDI con su banco de sonidos dentro (.rmi), para el 🎧 del visor (fase 85).
//
//   bun scripts/bases/midi_con_banco.ts <entrada.mid> <salida.rmi> [banco.sf2|sf3]
//
// Un .mid suelto suena en el navegador con sonivox (1,3 MB, el de alphaTab), que
// es ligero pero pobre. Este script recorta un banco bueno —por defecto «MS
// Basic» de MuseScore 4 (MIT), 49 MB— a los instrumentos y notas que usa la
// canción y lo mete dentro del MIDI: Stand by Me se queda en 7,7 MB y suena con
// MS Basic. SpessaSynth da prioridad al banco que trae el .rmi.
//
// Usa spessasynth_core de node_modules (la versión fijada en package.json).

import { BasicMIDI, SoundBankLoader } from "spessasynth_core";

const MS_BASIC = "/Applications/MuseScore 4.app/Contents/Resources/sound/MS Basic.sf3";
const [entrada, salida, bancoRuta = MS_BASIC] = process.argv.slice(2);
if (!entrada || !salida) {
  console.error("Uso: bun scripts/bases/midi_con_banco.ts <entrada.mid> <salida.rmi> [banco.sf2|sf3]");
  process.exit(2);
}

const midi = BasicMIDI.fromArrayBuffer(await Bun.file(entrada).arrayBuffer());
const banco = SoundBankLoader.fromArrayBuffer(await Bun.file(bancoRuta).arrayBuffer());
const usados = midi.getUsedProgramsAndKeys(banco);
banco.trim(usados);
// Si el banco de origen es SF3, las muestras siguen comprimidas: no se recodifican.
const recortado = banco.writeSF2();
const rmi = midi.writeRMIDI(recortado, { bankOffset: 0, soundBank: banco });
await Bun.write(salida, new Uint8Array(rmi));

const mb = (n: number) => (n / 1024 / 1024).toFixed(2) + " MB";
console.log(`${usados.size} instrumentos (${[...usados.keys()].map((p) => p.name).join(", ")})`);
console.log(`banco recortado ${mb(recortado.byteLength)} · ${salida}: ${mb(rmi.byteLength)} · ${midi.duration.toFixed(1)} s`);
