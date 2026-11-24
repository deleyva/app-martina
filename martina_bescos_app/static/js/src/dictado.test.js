import { describe, expect, test } from "bun:test";
import { CANAL_CLAQUETA, CANAL_MELODIA, CLAQUETA, DO_RITMICO, TIMBRES, VEL_MELODIA, aMidi, analizar, parejas, planDictado, pulsos } from "./dictado.js";

// El mismo abcjs que sirve la página.
const ABCJS = require("../../vendor/abcjs/abcjs-basic-min.js");

const OCHO_EN_3_4 = `X:1
M:3/4
L:1/4
K:C
C D E|F2 G|A B c|c3|B A G|F E D|E D C|C3|`;

const OCHO_EN_6_8 = `X:1
M:6/8
L:1/8
K:C
C2 D E2 F|G3 G3|A2 G F2 E|D6|E2 F G2 A|B3 c3|B2 A G2 F|E6|`;

const opciones = { tempo: 60, tipo: "melodico", repeticiones: 2, silencio: 10, cuenta_previa: true };

describe("lo que abcjs nos da", () => {
  test("un dictado de 8 compases en 3/4", () => {
    const a = analizar(ABCJS, OCHO_EN_3_4);
    expect(a.compases).toBe(8);
    expect(a.metrica).toEqual({ num: 3, den: 4 });
    expect(a.compas).toBeCloseTo(0.75, 9);
    expect(a.notas[0].pitch).toBe(60);
  });

  test("las parejas: 1–2, 3–4, 5–6, 7–8; con 7 compases, el último solo", () => {
    expect(parejas(8)).toEqual([[1, 2], [3, 4], [5, 6], [7, 8]]);
    expect(parejas(7)).toEqual([[1, 2], [3, 4], [5, 6], [7, 7]]);
  });
});

describe("la metodología", () => {
  const plan = planDictado(analizar(ABCJS, OCHO_EN_3_4), opciones);
  const musicales = plan.tramos.filter((t) => t.clase !== "silencio");

  test("entero, cada pareja dos veces con su silencio, y entero al final", () => {
    const resumen = plan.tramos.map((t) => (t.clase === "silencio" ? "✎" : t.clase === "entero" ? "E" : `${t.desde}-${t.hasta}`));
    expect(resumen).toEqual([
      "E",
      "1-2", "1-2", "✎",
      "3-4", "3-4", "✎",
      "5-6", "5-6", "✎",
      "7-8", "7-8", "✎",
      "E",
    ]);
  });

  test("los tramos van uno detrás de otro, sin huecos ni solapes", () => {
    plan.tramos.forEach((t, i) => {
      if (i) expect(t.inicio).toBeCloseTo(plan.tramos[i - 1].fin, 9);
    });
    expect(plan.tramos.filter((t) => t.clase === "silencio").every((t) => Math.abs(t.fin - t.inicio - 10) < 1e-9)).toBe(true);
  });

  test("cada tramo empieza con un compás de cuenta previa solo de claqueta", () => {
    for (const tr of musicales) {
      const enLaCuenta = plan.eventos.filter((e) => e.t >= tr.inicio - 1e-9 && e.t < tr.inicio + plan.segPorCompas - 1e-9);
      expect(enLaCuenta.length).toBe(3);
      expect(enLaCuenta.every((e) => e.canal === CANAL_CLAQUETA)).toBe(true);
    }
  });

  test("en la pareja 3–4 suenan las notas de los compases 3 y 4, y solo esas", () => {
    const tr = musicales.find((t) => t.desde === 3);
    const notas = plan.eventos.filter((e) => e.canal === CANAL_MELODIA && e.t >= tr.inicio && e.t < tr.fin);
    expect(notas.map((e) => e.nota)).toEqual([69, 71, 72, 72]); // A B c | c3
  });

  test("a negra = 60 un compás de 3/4 dura 3 s, y la pareja con su cuenta 9 s", () => {
    expect(plan.segPorCompas).toBeCloseTo(3, 9);
    const tr = musicales.find((t) => t.desde === 1 && t.clase === "pareja");
    expect(tr.fin - tr.inicio).toBeCloseTo(9, 9);
  });

  test("sin silencio ni cuenta previa siguen separadas las repeticiones", () => {
    const p = planDictado(analizar(ABCJS, OCHO_EN_3_4), { ...opciones, silencio: 0, cuenta_previa: false });
    expect(p.tramos.some((t) => t.clase === "silencio")).toBe(false);
    expect(p.eventos.filter((e) => e.canal === CANAL_CLAQUETA).length).toBe(
      // 8 + (2·4 compases ·2 veces) + 8 compases de música, a 3 pulsos
      (8 + 16 + 8) * 3,
    );
  });
});

describe("la claqueta", () => {
  test("hi-hat en la primera parte del compás y golpe plano en las demás, flojitos", () => {
    const plan = planDictado(analizar(ABCJS, OCHO_EN_3_4), opciones);
    const golpes = plan.eventos.filter((e) => e.canal === CANAL_CLAQUETA);
    const porCompas = plan.segPorCompas;
    // La fase se mide desde el inicio de cada tramo: los silencios de 10 s
    // desplazan la rejilla de compases de un tramo al siguiente.
    for (const g of golpes) {
      const tr = plan.tramos.find((t) => g.t >= t.inicio - 1e-9 && g.t < t.fin - 1e-9);
      expect(tr.clase).not.toBe("silencio");
      const fase = ((g.t - tr.inicio) / porCompas) % 1;
      const primera = Math.abs(fase) < 1e-6 || Math.abs(fase - 1) < 1e-6;
      expect(g.nota).toBe(primera ? CLAQUETA.primera : CLAQUETA.resto);
      expect(g.vel).toBeLessThanOrEqual(50);
    }
    expect(golpes.filter((g) => g.nota === CLAQUETA.primera).length * 3).toBe(golpes.length);
  });

  test("en 6/8 cuenta dos pulsos de negra con puntillo", () => {
    expect(pulsos({ num: 6, den: 8 })).toEqual({ porCompas: 2, duracion: 3 / 8 });
    expect(pulsos({ num: 12, den: 8 })).toEqual({ porCompas: 4, duracion: 3 / 8 });
    expect(pulsos({ num: 3, den: 8 })).toEqual({ porCompas: 3, duracion: 1 / 8 });
    const plan = planDictado(analizar(ABCJS, OCHO_EN_6_8), opciones);
    const tr = plan.tramos[0];
    const cuenta = plan.eventos.filter((e) => e.t >= tr.inicio && e.t < tr.inicio + plan.segPorCompas - 1e-9);
    expect(cuenta.map((e) => e.nota)).toEqual([CLAQUETA.primera, CLAQUETA.resto]);
    // Negra con puntillo a 60: el compás de 6/8 dura 2 s.
    expect(plan.segPorCompas).toBeCloseTo(2, 9);
  });
});

describe("los rítmicos", () => {
  test("todas las notas suenan en do y mantenidas, no como golpes", () => {
    const plan = planDictado(analizar(ABCJS, OCHO_EN_3_4), { ...opciones, tipo: "ritmico" });
    const notas = plan.eventos.filter((e) => e.canal === CANAL_MELODIA);
    expect(new Set(notas.map((e) => e.nota))).toEqual(new Set([DO_RITMICO]));
    // La blanca del compás 2 (2 s a negra = 60) dura casi 2 s.
    expect(Math.max(...notas.map((e) => e.dur))).toBeGreaterThan(2.5);
    expect(notas.find((e) => e.dur > 1.5 && e.dur < 2).dur).toBeGreaterThan(1.8);
  });
});

describe("el MIDI", () => {
  test("es un SMF de formato 0 con todas las notas encendidas y apagadas", () => {
    const plan = planDictado(analizar(ABCJS, OCHO_EN_3_4), opciones);
    const bytes = aMidi(plan, { programa: 73 });
    const texto = String.fromCharCode(...bytes.slice(0, 4));
    expect(texto).toBe("MThd");
    expect(String.fromCharCode(...bytes.slice(14, 18))).toBe("MTrk");
    const largo = (bytes[18] << 24) | (bytes[19] << 16) | (bytes[20] << 8) | bytes[21];
    expect(largo).toBe(bytes.length - 22);
    // Cuenta encendidos (0x9n) y apagados (0x8n) recorriendo la pista.
    let i = 22, on = 0, off = 0, programa = null;
    while (i < bytes.length) {
      while (bytes[i] & 0x80) i++;
      i++;
      const st = bytes[i];
      if (st === 0xff) { i += 3 + bytes[i + 2]; continue; }
      const tipo = st & 0xf0;
      if (tipo === 0x90) on++;
      if (tipo === 0x80) off++;
      if (tipo === 0xc0) programa = bytes[i + 1];
      i += tipo === 0xc0 ? 2 : 3;
    }
    expect(on).toBe(plan.eventos.length);
    expect(off).toBe(plan.eventos.length);
    expect(programa).toBe(73);
  });
});

describe("el banco de las fichas (MuseScore General recortado)", () => {
  const { readFileSync, statSync } = require("node:fs");
  const { SoundBankLoader } = require("spessasynth_core");
  const RUTA = require("node:path").join(__dirname, "../../vendor/musescore/MuseScore_General_fichas.sf3");
  const bytes = readFileSync(RUTA);
  const banco = SoundBankLoader.fromArrayBuffer(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  const suena = (p, tecla, vel) => p.getVoiceParameters(tecla, vel).length > 0;

  test("no pasa de 3 MB (C783)", () => {
    expect(statSync(RUTA).size).toBeLessThanOrEqual(3_000_000);
  });

  test("cada timbre suena en las 128 teclas y en todo el rango de intensidad de la melodía", () => {
    for (const { programa } of Object.values(TIMBRES)) {
      const p = banco.presets.find((x) => !x.isGMGSDrum && x.bankMSB === 0 && x.program === programa);
      expect(p).toBeTruthy();
      const mudas = [];
      for (let tecla = 0; tecla < 128; tecla++) {
        for (let vel = VEL_MELODIA.min; vel <= VEL_MELODIA.max; vel++) if (!suena(p, tecla, vel)) mudas.push(`${tecla}/${vel}`);
      }
      expect(mudas).toEqual([]);
    }
  });

  test("la claqueta suena a cualquier intensidad, para poder subirla o bajarla", () => {
    const kit = banco.presets.find((x) => x.isGMGSDrum && x.program === 0);
    expect(kit).toBeTruthy();
    for (const tecla of [CLAQUETA.primera, CLAQUETA.resto]) {
      for (let vel = 1; vel <= 127; vel++) expect(suena(kit, tecla, vel)).toBe(true);
    }
  });

  test("las notas de la melodía nunca salen del rango que lleva el banco", () => {
    const abc = OCHO_EN_3_4.replace("C D E|", "!pp! C D E|").replace("B A G|", "!fff! B A G|");
    const plan = planDictado(analizar(ABCJS, abc), opciones);
    const vels = plan.eventos.filter((e) => e.canal === CANAL_MELODIA).map((e) => e.vel);
    expect(Math.min(...vels)).toBeGreaterThanOrEqual(VEL_MELODIA.min);
    expect(Math.max(...vels)).toBeLessThanOrEqual(VEL_MELODIA.max);
  });
});

describe("el aviso del editor", () => {
  test("8 compases no avisa; otro número sí", async () => {
    const { avisoDeCompases } = await import("./dictado.js");
    expect(avisoDeCompases(8)).toBe("");
    expect(avisoDeCompases(6)).toBe("Este dictado tiene 6 compases; los de clase tienen 8.");
    expect(avisoDeCompases(1)).toBe("Este dictado tiene 1 compás; los de clase tienen 8.");
  });
});

// Fase 114: `aMidi` aprendió a poner el timbre en más de un canal para los
// patrones de piano. Con uno solo, que es como lo llaman los dictados, tiene
// que dar byte a byte el MIDI de antes: las huellas son del código anterior.
describe("los dictados suenan como antes de la fase 114", () => {
  const { createHash } = require("node:crypto");
  const huella = (bytes) => createHash("sha256").update(bytes).digest("hex");
  const plan = planDictado(analizar(ABCJS, OCHO_EN_3_4), opciones);

  test("con un solo canal, el MIDI es el mismo", () => {
    const piano = aMidi(plan, { programa: 0 });
    expect(piano.length).toBe(1800);
    expect(huella(piano)).toBe("a65aa656abdb002f1dc97a35c77c11b6c617d45622fe04c06dada67998aab32e");
    expect(huella(aMidi(plan, { programa: 73 }))).toBe("90bfaa5c8754446afe51f62f503e06a185950af3dbcdb4fa1f136619e766aaa2");
    expect(huella(aMidi(plan))).toBe(huella(piano));
  });

  test("y la huella falla si cambia un solo canal", () => {
    expect(huella(aMidi(plan, { programa: 0, canales: [0, 1] }))).not.toBe(huella(aMidi(plan, { programa: 0 })));
  });
});
