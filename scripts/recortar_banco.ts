// Recorta MuseScore_General.sf3 al banco ligero de las fichas de audición (fase 111).
//
// El banco entero son 40 MB, y solo el piano de cola pesa 11. Los dictados
// tocan cuatro timbres y una claqueta de dos golpes, así que el resto sobra.
// Qué se conserva sale de static/js/src/dictado.js, para que el banco y el
// reproductor no puedan desalinearse:
//
// - los programas de TIMBRES (piano, piano eléctrico, flauta, sinte), de fa3 a
//   la5 (el registro de los dictados de clase) y en el rango de intensidad
//   VEL_MELODIA;
// - del kit estándar, los dos golpes de CLAQUETA (hi-hat cerrado y aro), a
//   cualquier intensidad, para poder subirla o bajarla sin regenerar el banco.
//
// Una nota escrita fuera de fa3-la5 no se queda muda: las zonas de los
// extremos se estiran hasta 0 y 127, y suena la muestra más cercana
// transportada. dictado.test.js comprueba que cada timbre suena en las 128
// teclas.
//
// Las muestras se copian tal cual, comprimidas en Vorbis: no se descomprime ni
// se recomprime nada, así que no se pierde calidad.
//
// Uso, desde la raíz del repo (spessasynth_core sale de node_modules):
//
//   bun scripts/recortar_banco.ts <MuseScore_General.sf3> <salida.sf3>

import { readFileSync, writeFileSync } from "node:fs";
import { SoundBankLoader, type BasicInstrument, type BasicPreset } from "spessasynth_core";
import { CLAQUETA, TIMBRES, VEL_MELODIA } from "../martina_bescos_app/static/js/src/dictado.js";

// fa3 – la5. De do3 a do6 eran 3,84 MB; así son 2,98, dentro de los 3 MB
// que se fijaron para la red del aula.
const TECLAS = { min: 53, max: 81 };

const [entrada, salida] = process.argv.slice(2);
if (!entrada || !salida) {
  console.error("Uso: bun scripts/recortar_banco.ts <MuseScore_General.sf3> <salida.sf3>");
  process.exit(2);
}

const leido = readFileSync(entrada);
const banco = SoundBankLoader.fromArrayBuffer(leido.buffer.slice(leido.byteOffset, leido.byteOffset + leido.byteLength));

const serie = (min: number, max: number) => Array.from({ length: max - min + 1 }, (_, i) => min + i);
const intensidades = new Set(serie(VEL_MELODIA.min, VEL_MELODIA.max));
const todas = new Set(serie(1, 127));

const melodicos: BasicPreset[] = [];
const conservar = new Map<BasicPreset, Map<number, Set<number>>>();
for (const { programa } of Object.values(TIMBRES)) {
  const p = banco.presets.find((x) => !x.isGMGSDrum && x.bankMSB === 0 && x.bankLSB === 0 && x.program === programa);
  if (!p) throw new Error(`El banco no tiene el programa ${programa} en el banco 0.`);
  melodicos.push(p);
  conservar.set(p, new Map(serie(TECLAS.min, TECLAS.max).map((k) => [k, intensidades])));
}
const kit = banco.presets.find((x) => x.isGMGSDrum && x.program === 0);
if (!kit) throw new Error("El banco no tiene el kit de batería estándar (banco 128, programa 0).");
conservar.set(kit, new Map([CLAQUETA.primera, CLAQUETA.resto].map((k) => [k, todas])));

const antes = { presets: banco.presets.length, muestras: banco.samples.length };
banco.trim(conservar);

// Estirar los extremos: en cada instrumento melódico, las zonas más graves
// bajan hasta la tecla 0 y las más agudas suben hasta la 127. Las dos zonas de
// una pareja estéreo comparten rango, así que se estiran juntas.
const instrumentos = new Set<BasicInstrument>();
for (const p of melodicos) for (const z of p.zones) instrumentos.add(z.instrument);
for (const inst of instrumentos) {
  const conRango = inst.zones.filter((z) => z.hasKeyRange);
  if (!conRango.length) continue;
  const grave = Math.min(...conRango.map((z) => z.keyRange.min));
  const aguda = Math.max(...conRango.map((z) => z.keyRange.max));
  for (const z of conRango) {
    if (z.keyRange.min === grave) z.keyRange.min = 0;
    if (z.keyRange.max === aguda) z.keyRange.max = 127;
  }
}

const bytes = new Uint8Array(
  banco.writeSF2({ software: "recortar_banco.ts (app IES Martina Bescós)", writeDefaultModulators: true, writeExtendedLimits: true }),
);
writeFileSync(salida, bytes);

console.log(`Presets: ${antes.presets} → ${banco.presets.length}`);
for (const p of banco.presets) {
  console.log(`  ${p.isGMGSDrum ? "batería" : "banco " + p.bankMSB} · programa ${p.program} · ${p.name}`);
}
console.log(`Muestras: ${antes.muestras} → ${banco.samples.length} (comprimidas: ${banco.samples.filter((s) => s.isCompressed).length})`);
console.log(`Tamaño: ${leido.byteLength} → ${bytes.byteLength} bytes`);
