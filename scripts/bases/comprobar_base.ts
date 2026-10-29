// Comprueba que una base generada suena a lo que dice la ficha (fase 83).
//
//   bun scripts/bases/comprobar_base.ts <base.wav> <compases.json> <tempo> [pulsos]
//
// En cada compás mide, con Goertzel, cuánto suena cada clase de altura entre
// Mi1 y Mi3 —donde están el bajo y la mano izquierda del piano— y comprueba que
// la que más suena es el bajo del acorde que pone la ficha. Si la base se
// desplazara un compás, o un acorde saliera mal, la cuenta de aciertos cae.

const [wav, compasesJson, tempoTxt, pulsosTxt] = process.argv.slice(2);
const tempo = Number(tempoTxt);
const pulsos = Number(pulsosTxt || 4);
const NOMBRES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

function leerWav(buf: ArrayBuffer) {
  const v = new DataView(buf);
  let i = 12, canales = 2, muestreo = 44100, bits = 16, datos = 0, largo = 0;
  while (i < v.byteLength - 8) {
    const id = String.fromCharCode(v.getUint8(i), v.getUint8(i + 1), v.getUint8(i + 2), v.getUint8(i + 3));
    const tam = v.getUint32(i + 4, true);
    if (id === "fmt ") { canales = v.getUint16(i + 10, true); muestreo = v.getUint32(i + 12, true); bits = v.getUint16(i + 22, true); }
    if (id === "data") { datos = i + 8; largo = tam; break; }
    i += 8 + tam + (tam % 2);
  }
  if (bits !== 16) throw new Error(`Solo WAV de 16 bits (este es de ${bits})`);
  const n = Math.floor(largo / 2 / canales);
  const mono = new Float32Array(n);
  for (let k = 0; k < n; k++) {
    let s = 0;
    for (let c = 0; c < canales; c++) s += v.getInt16(datos + (k * canales + c) * 2, true);
    mono[k] = s / canales / 32768;
  }
  return { mono, muestreo };
}

function goertzel(x: Float32Array, ini: number, fin: number, f: number, sr: number) {
  const w = (2 * Math.PI * f) / sr, c = 2 * Math.cos(w);
  let s1 = 0, s2 = 0;
  for (let k = ini; k < fin; k++) { const s0 = x[k] + c * s1 - s2; s2 = s1; s1 = s0; }
  return s1 * s1 + s2 * s2 - c * s1 * s2;
}

const { mono, muestreo } = leerWav(await Bun.file(wav).arrayBuffer());
const compases: { compas: number; acorde: string; bajo: number | null }[] = JSON.parse(await Bun.file(compasesJson).text());
const seg = (60 / tempo) * pulsos;
let aciertos = 0, medidos = 0;
const fallos: string[] = [];
for (const c of compases) {
  if (c.bajo === null) continue;
  const ini = Math.floor((c.compas * seg + 0.15) * muestreo);
  const fin = Math.floor(((c.compas + 1) * seg - 0.1) * muestreo);
  const energia = new Array(12).fill(0);
  for (let midi = 28; midi <= 52; midi++) {
    energia[midi % 12] += goertzel(mono, ini, fin, 440 * 2 ** ((midi - 69) / 12), muestreo);
  }
  const ganadora = energia.indexOf(Math.max(...energia));
  medidos++;
  if (ganadora === c.bajo) aciertos++;
  else fallos.push(`compás ${c.compas} (${c.acorde}): suena ${NOMBRES[ganadora]}`);
}
console.log(`${aciertos}/${medidos} compases con el bajo de la ficha`);
for (const f of fallos.slice(0, 20)) console.log("  " + f);
process.exit(aciertos === medidos ? 0 : 1);
