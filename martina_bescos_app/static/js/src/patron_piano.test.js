import { describe, expect, test } from "bun:test";
import { CANAL_CLAQUETA, CLAQUETA, VEL_MELODIA, aMidi } from "./dictado.js";
import {
  CANAL_DERECHA,
  CANAL_IZQUIERDA,
  CORCHEAS_POR_COMPAS,
  MAX_VUELTAS,
  MINUTOS_DE_BUCLE,
  PATRONES,
  TONALIDADES,
  abc,
  bajo,
  compasQueSuena,
  compases,
  defectoDelPatron,
  disposicion,
  nombreDeNota,
  nota,
  octavasDeLaIzquierda,
  patron,
  planPatron,
  quinta,
  tonalidad,
  voces,
} from "./patron_piano.js";

// El mismo abcjs que sirve la página.
const ABCJS = require("../../vendor/abcjs/abcjs-basic-min.js");

const SEMITONOS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const midiDe = (n) => 12 * (n.octava + 1) + SEMITONOS[n.letra] + n.alter;
const nombres = (ns) => ns.map(nombreDeNota).join(" ");
const PROGRESIONES = [[1, 5, 5, 1], [1, 4, 5, 1], [1, 6, 4, 5], [1, 5, 6, 4], [1, 2, 3, 4, 5, 6, 7, 1]];
const todas = TONALIDADES.map((x) => tonalidad(x.id));

describe("el catálogo", () => {
  test("ningún patrón tiene defecto: cada mano llena el compás con figuras que se escriben", () => {
    expect(PATRONES.length).toBeGreaterThanOrEqual(3);
    for (const p of PATRONES) expect(defectoDelPatron(p)).toBe("");
    expect(new Set(PATRONES.map((p) => p.id)).size).toBe(PATRONES.length);
    for (const p of PATRONES) expect(p.nombre.length).toBeGreaterThan(3);
  });

  test("el falsador falla cuando debe: compás corto, figura rara y mano que no sabe", () => {
    expect(defectoDelPatron({ id: "x", derecha: [["acorde", 4]], izquierda: [["bajo", 8]] })).toContain("suma 4");
    expect(defectoDelPatron({ id: "x", derecha: [["acorde", 5], ["acorde", 3]], izquierda: [["bajo", 8]] })).toContain("5 corcheas");
    expect(defectoDelPatron({ id: "x", derecha: [["bajo", 8]], izquierda: [["bajo", 8]] })).toContain("no sabe tocar «bajo»");
    expect(defectoDelPatron({ id: "x", derecha: [["acorde", 8]] })).toContain("le falta la mano izquierda");
  });

  test("las doce tonalidades mayores, sin repetir ninguna", () => {
    expect(TONALIDADES.length).toBe(12);
    expect(new Set(todas.map((t) => t.semitono)).size).toBe(12);
    expect(() => tonalidad("H")).toThrow("Tonalidad desconocida");
    expect(() => patron("vals")).toThrow("Patrón desconocido");
  });
});

describe("las notas", () => {
  test("letra, alteración y octava dan siempre el MIDI de la nota, en las doce tonalidades", () => {
    for (const t of todas) {
      for (let paso = -21; paso <= 21; paso++) {
        const n = nota(t, paso);
        expect(midiDe(n)).toBe(n.midi);
        expect(Math.abs(n.alter)).toBeLessThanOrEqual(1);
      }
      // Una escala: las siete letras, una vez cada una.
      const escala = [0, 1, 2, 3, 4, 5, 6].map((p) => nota(t, p));
      expect(new Set(escala.map((n) => n.letra)).size).toBe(7);
    }
  });

  test("cada tonalidad lleva las alteraciones de su armadura y ninguna más", () => {
    const esperado = { C: 0, G: 1, F: -1, D: 2, Bb: -2, A: 3, Eb: -3, E: 4, Ab: -4, B: 5, Db: -5, "F#": 6 };
    for (const t of todas) {
      const alteraciones = [0, 1, 2, 3, 4, 5, 6].map((p) => nota(t, p).alter);
      const suma = alteraciones.reduce((a, b) => a + b, 0);
      expect([t.id, suma]).toEqual([t.id, esperado[t.id]]);
      // Sostenidos o bemoles, nunca mezclados.
      expect(alteraciones.some((a) => a > 0) && alteraciones.some((a) => a < 0)).toBe(false);
    }
  });

  test("I–V en do mayor: do4 mi4 sol4 y, sin mover la mano, si3 re4 sol4", () => {
    const v = voces(tonalidad("C"), [1, 5, 5, 1]);
    expect(v.map(nombres)).toEqual(["C4 E4 G4", "B3 D4 G4", "B3 D4 G4", "C4 E4 G4"]);
  });

  test("I–IV–V–I en do: la subdominante en segunda inversión y la dominante en primera", () => {
    const v = voces(tonalidad("C"), [1, 4, 5, 1]);
    expect(v.map(nombres)).toEqual(["C4 E4 G4", "C4 F4 A4", "B3 D4 G4", "C4 E4 G4"]);
  });

  test("en sol y en si bemol, las notas se escriben con su alteración", () => {
    expect(voces(tonalidad("G"), [1, 5]).map(nombres)).toEqual(["G4 B4 D5", "F#4 A4 D5"]);
    expect(voces(tonalidad("Bb"), [1, 4]).map(nombres)).toEqual(["Bb4 D5 F5", "Bb4 Eb5 G5"]);
    expect(voces(tonalidad("F#"), [1, 5]).map(nombres)).toEqual(["F#4 A#4 C#5", "E#4 G#4 C#5"]);
  });

  test("la primera tríada cabe en el pentagrama de sol: fundamental entre do4 y si4, empiece en el grado que empiece", () => {
    for (const t of todas) {
      for (let g = 1; g <= 7; g++) {
        const [primera] = voces(t, [g]);
        expect(primera[0].letra).toBe(nota(t, g - 1).letra);
        expect(primera[0].midi).toBeGreaterThanOrEqual(60);
        expect(primera[0].midi).toBeLessThanOrEqual(71);
      }
    }
    // Una progresión que empieza en la dominante: sol4, no sol3 con tres líneas adicionales.
    expect(voces(tonalidad("C"), [5, 1]).map(nombres)).toEqual(["G4 B4 D5", "G4 C5 E5"]);
  });

  test("entre dos acordes seguidos la mano se mueve poco, en cualquier tonalidad", () => {
    for (const t of todas) {
      for (const grados of PROGRESIONES) {
        const v = voces(t, grados);
        expect(v.length).toBe(grados.length);
        for (let i = 1; i < v.length; i++) {
          const movimiento = v[i].reduce((s, n, j) => s + Math.abs(n.midi - v[i - 1][j].midi), 0);
          expect(movimiento).toBeLessThanOrEqual(8);
        }
        for (const triada of v) {
          expect(triada[0].midi).toBeGreaterThanOrEqual(57);
          expect(triada[2].midi).toBeLessThanOrEqual(84);
          expect(triada[0].midi < triada[1].midi && triada[1].midi < triada[2].midi).toBe(true);
        }
      }
    }
  });

  test("el bajo es la fundamental entre fa2 y mi3, y su quinta es la del acorde", () => {
    for (const t of todas) {
      for (let g = 1; g <= 7; g++) {
        const b = bajo(t, g);
        expect(b.midi).toBeGreaterThanOrEqual(41);
        expect(b.midi).toBeLessThanOrEqual(52);
        expect(b.letra).toBe(nota(t, g - 1).letra);
        const q = quinta(t, b);
        expect(q.midi).toBeGreaterThanOrEqual(41);
        expect(q.midi).toBeLessThanOrEqual(52);
        expect(q.letra).toBe(nota(t, g - 1 + 4).letra);
      }
    }
    expect(nombreDeNota(bajo(tonalidad("C"), 1))).toBe("C3");
    expect(nombreDeNota(quinta(tonalidad("C"), bajo(tonalidad("C"), 1)))).toBe("G2");
    // En fa, la quinta por debajo sería do2: va por encima.
    expect(nombreDeNota(quinta(tonalidad("F"), bajo(tonalidad("F"), 1)))).toBe("C3");
  });

  test("un grado que no existe no se inventa", () => {
    expect(() => voces(tonalidad("C"), [1, 8])).toThrow("Grado desconocido");
    expect(() => voces(tonalidad("C"), [0])).toThrow("Grado desconocido");
  });
});

describe("los compases", () => {
  test("cada mano llena su compás, en todos los patrones", () => {
    for (const p of PATRONES) {
      const cs = compases(tonalidad("C"), [1, 5, 5, 1], p);
      expect(cs.length).toBe(4);
      for (const c of cs) {
        for (const mano of ["derecha", "izquierda"]) {
          expect(c[mano].reduce((s, e) => s + e.dur, 0)).toBe(CORCHEAS_POR_COMPAS);
        }
      }
    }
  });

  test("el bajo Alberti recorre la tríada de la izquierda: grave, agudo, medio, agudo", () => {
    const [c] = compases(tonalidad("C"), [1], patron("alberti"));
    expect(c.izquierda.slice(0, 4).map((e) => nombres(e.notas))).toEqual(["C3", "G3", "E3", "G3"]);
    expect(nombres(c.derecha[0].notas)).toBe("C4 E4 G4");
  });

  test("la tríada de la izquierda no baja de fa2 y no salta de octava entre dos acordes", () => {
    // En do va una octava por debajo de la derecha; en sol, dos (una sola la dejaría sobre el do central).
    expect(octavasDeLaIzquierda(voces(tonalidad("C"), [1, 5, 5, 1]))).toBe(1);
    expect(octavasDeLaIzquierda(voces(tonalidad("G"), [1, 5, 5, 1]))).toBe(2);
    const enSol = compases(tonalidad("G"), [1, 5], patron("alberti"));
    expect(enSol[0].izquierda.slice(0, 4).map((e) => nombres(e.notas))).toEqual(["G2", "D3", "B2", "D3"]);
    expect(enSol[1].izquierda.slice(0, 4).map((e) => nombres(e.notas))).toEqual(["F#2", "D3", "A2", "D3"]);
    for (const t of todas) {
      for (const grados of PROGRESIONES) {
        const cs = compases(t, grados, patron("alberti"));
        const graves = cs.map((c) => c.izquierda[0].notas[0].midi);
        expect(Math.min(...graves)).toBeGreaterThanOrEqual(41);
        // La misma distancia a la derecha en todos los compases.
        const distancias = new Set(cs.map((c) => c.derecha[0].notas[0].midi - c.izquierda[0].notas[0].midi));
        expect([t.id, [...distancias]]).toEqual([t.id, [12 * octavasDeLaIzquierda(voces(t, grados))]]);
      }
    }
  });

  test("un patrón mal escrito no llega a la partitura", () => {
    const roto = { id: "roto", derecha: [["acorde", 4]], izquierda: [["bajo", 8]] };
    expect(() => compases(tonalidad("C"), [1], roto)).toThrow("suma 4");
  });
});

describe("el ABC", () => {
  test("I–V–V–I con bajo y acorde en do: dos pentagramas, cifrado encima y grados debajo", () => {
    expect(abc(tonalidad("C"), [1, 5, 5, 1], patron("bajo-acorde"))).toBe(
      [
        "X:1",
        "M:4/4",
        "L:1/8",
        "%%stretchlast 1",
        "%%score {1 2}",
        "V:1 clef=treble",
        "V:2 clef=bass",
        "K:C",
        '[V:1] "C"z2 [CEG]2 z2 [CEG]2 | "G"z2 [B,DG]2 z2 [B,DG]2 | "G"z2 [B,DG]2 z2 [B,DG]2 | "C"z2 [CEG]2 z2 [CEG]2 |]',
        '[V:2] "_I"C,2 z2 G,,2 z2 | "_V"G,,2 z2 D,2 z2 | "_V"G,,2 z2 D,2 z2 | "_I"C,2 z2 G,,2 z2 |]',
        "",
      ].join("\n"),
    );
  });

  test("en el móvil, dos compases por línea: cuatro compases son dos sistemas", () => {
    const texto = abc(tonalidad("C"), [1, 5, 5, 1], patron("blancas"), { porLinea: 2 });
    const lineas = texto.split("\n").filter((l) => l.startsWith("[V:"));
    expect(lineas.length).toBe(4);
    expect(lineas[0].endsWith(" |")).toBe(true);
    expect(lineas[2].endsWith(" |]")).toBe(true);
    const tune = ABCJS.parseOnly(texto)[0];
    const sistemas = tune.lines.filter((l) => l.staff);
    expect(sistemas.length).toBe(2);
    for (const s of sistemas) expect(s.staff.length).toBe(2);
  });

  test("las corcheas del Alberti van barradas de cuatro en cuatro", () => {
    const texto = abc(tonalidad("C"), [1], patron("alberti"));
    expect(texto).toContain('[V:2] "_I"C,G,E,G, C,G,E,G, |]');
  });

  test("abcjs lee cada patrón en cada tonalidad sin avisos, y entiende las mismas notas", () => {
    let leidos = 0;
    for (const t of todas) {
      for (const p of PATRONES) {
        for (const grados of [[1, 5, 5, 1], [1, 6, 4, 5, 2, 3, 7, 1]]) {
          const texto = abc(t, grados, p, { porLinea: 4 });
          const tune = ABCJS.parseOnly(texto)[0];
          expect([t.id, p.id, tune.warnings || []]).toEqual([t.id, p.id, []]);
          const sistemas = tune.lines.filter((l) => l.staff);
          expect(sistemas.length).toBe(Math.ceil(grados.length / 4));
          for (const s of sistemas) expect(s.staff.length).toBe(2);

          // Lo que abcjs entiende (con la armadura puesta) son las mismas
          // notas, en el mismo sitio, que salieron del generador.
          // (`chordsOff`: sin él, abcjs añade su propio acompañamiento a
          // partir del cifrado, y no es eso lo que se compara.)
          const sonidos = tune.setUpAudio({ chordsOff: true }).tracks.flat().filter((e) => e.cmd === "note");
          const final = Math.max(...sonidos.map((n) => n.start + n.duration));
          expect(Math.round(final / tune.getBarLength())).toBe(grados.length);
          const deAbcjs = sonidos.map((n) => Math.round(n.start * 8) + ":" + n.pitch).sort();
          const nuestras = [];
          compases(t, grados, p).forEach((c, i) => {
            for (const mano of ["derecha", "izquierda"]) {
              let o = 0;
              for (const e of c[mano]) {
                for (const n of e.notas) nuestras.push(i * 8 + o + ":" + n.midi);
                o += e.dur;
              }
            }
          });
          expect(deAbcjs).toEqual(nuestras.sort());
          leidos++;
        }
      }
    }
    expect(leidos).toBe(12 * PATRONES.length * 2);
  });
});

describe("el sonido", () => {
  const cs = compases(tonalidad("C"), [1, 5, 5, 1], patron("bajo-acorde"));
  const plan = planPatron(cs, { tempo: 80, claqueta: CLAQUETA, canalClaqueta: CANAL_CLAQUETA });

  test("a negra 80 un compás dura 3 s; primero, un compás de cuenta solo de claqueta", () => {
    expect(plan.segPorCompas).toBeCloseTo(3, 9);
    expect(plan.inicio).toBeCloseTo(3, 9);
    expect(plan.vuelta).toBeCloseTo(12, 9);
    const cuenta = plan.eventos.filter((e) => e.t < plan.inicio - 1e-9);
    expect(cuenta.length).toBe(4);
    expect(cuenta.every((e) => e.canal === CANAL_CLAQUETA)).toBe(true);
    expect(cuenta[0].nota).toBe(CLAQUETA.primera);
    expect(cuenta.slice(1).every((e) => e.nota === CLAQUETA.resto)).toBe(true);
  });

  test("el bucle va escrito: cada vuelta empieza justo donde acaba la anterior, sin hueco", () => {
    expect(plan.vueltas).toBe(Math.ceil((MINUTOS_DE_BUCLE * 60) / 12));
    const musica = plan.eventos.filter((e) => e.canal !== CANAL_CLAQUETA);
    const deLaVuelta = (v) =>
      musica
        .filter((e) => e.t >= plan.inicio + v * plan.vuelta - 1e-9 && e.t < plan.inicio + (v + 1) * plan.vuelta - 1e-9)
        .map((e) => [Math.round((e.t - plan.inicio - v * plan.vuelta) * 1000), e.canal, e.nota].join(":"));
    const primera = deLaVuelta(0);
    expect(primera.length).toBe(4 * (6 + 2));
    expect(primera[0].startsWith("0:")).toBe(true);
    for (const v of [1, 2, plan.vueltas - 1]) expect(deLaVuelta(v)).toEqual(primera);
    expect(deLaVuelta(plan.vueltas)).toEqual([]);
    // Ninguna nota pasa del final de su vuelta: la siguiente entra limpia.
    for (const e of musica) {
      const v = Math.floor((e.t - plan.inicio + 1e-9) / plan.vuelta);
      expect(e.t + e.dur).toBeLessThan(plan.inicio + (v + 1) * plan.vuelta);
    }
  });

  test("no pasa de MAX_VUELTAS ni de unos cinco minutos, y se puede pedir una sola vuelta", () => {
    const rapido = planPatron(compases(tonalidad("C"), [1], patron("redondas")), { tempo: 200 });
    expect(rapido.vueltas).toBe(MAX_VUELTAS);
    expect(plan.duracion).toBeLessThan(MINUTOS_DE_BUCLE * 60 + 20);
    expect(planPatron(cs, { tempo: 80, vueltas: 1 }).vueltas).toBe(1);
  });

  test("cada mano va por su canal, con una intensidad que el banco tiene", () => {
    const derecha = plan.eventos.filter((e) => e.canal === CANAL_DERECHA);
    const izquierda = plan.eventos.filter((e) => e.canal === CANAL_IZQUIERDA);
    expect(derecha.length).toBe(plan.vueltas * 4 * 6);
    expect(izquierda.length).toBe(plan.vueltas * 4 * 2);
    expect(Math.min(...derecha.map((e) => e.nota))).toBeGreaterThanOrEqual(57);
    expect(Math.max(...izquierda.map((e) => e.nota))).toBeLessThanOrEqual(52);
    for (const e of [...derecha, ...izquierda]) {
      expect(e.vel).toBeGreaterThanOrEqual(VEL_MELODIA.min);
      expect(e.vel).toBeLessThanOrEqual(VEL_MELODIA.max);
      expect(e.dur).toBeGreaterThan(0.04);
    }
  });

  test("sin claqueta que pasar, el plan solo lleva las manos", () => {
    const mudo = planPatron(cs, { tempo: 80, vueltas: 1 });
    expect(mudo.eventos.every((e) => e.canal === CANAL_DERECHA || e.canal === CANAL_IZQUIERDA)).toBe(true);
  });

  test("qué compás suena en cada momento: la cuenta, el primero y la segunda vuelta", () => {
    expect(compasQueSuena(plan, 0)).toBe(-1);
    expect(compasQueSuena(plan, 2.99)).toBe(-1);
    expect(compasQueSuena(plan, 3)).toBe(0);
    expect(compasQueSuena(plan, 5.99)).toBe(0);
    expect(compasQueSuena(plan, 6)).toBe(1);
    expect(compasQueSuena(plan, 14.9)).toBe(3);
    expect(compasQueSuena(plan, 15)).toBe(0);
  });

  test("el MIDI pone el piano en los dos canales de las manos", () => {
    const corto = planPatron(cs, { tempo: 80, vueltas: 1, claqueta: CLAQUETA, canalClaqueta: CANAL_CLAQUETA });
    const bytes = aMidi(corto, { programa: 0, canales: [CANAL_DERECHA, CANAL_IZQUIERDA] });
    expect(String.fromCharCode(...bytes.slice(0, 4))).toBe("MThd");
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join(" ");
    // Cambio de programa (Cn) y volumen (Bn 07 64) en el canal 0 y en el 1.
    expect(hex).toContain("c0 00 00 b0 07 64 00 c1 00 00 b1 07 64");
    const encendidos = (canal) => bytes.reduce((n, b, i) => n + (b === (0x90 | canal) && bytes[i + 2] > 0 && bytes[i + 1] < 128 ? 1 : 0), 0);
    expect(encendidos(CANAL_DERECHA)).toBeGreaterThanOrEqual(4 * 6);
    expect(encendidos(CANAL_IZQUIERDA)).toBeGreaterThanOrEqual(4 * 2);
  });
});

describe("la disposición", () => {

  test("en un móvil, dos compases por línea a su tamaño; con sitio, cuatro", () => {
    expect(disposicion(350)).toEqual({ porLinea: 2, staffwidth: 320 });
    expect(disposicion(559).porLinea).toBe(2);
    expect(disposicion(560).porLinea).toBe(4);
    expect(disposicion(1600)).toEqual({ porLinea: 4, staffwidth: 740 });
    expect(disposicion(120).staffwidth).toBe(280);
  });
});
