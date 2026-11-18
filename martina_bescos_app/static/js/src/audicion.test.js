import { describe, expect, test } from "bun:test";
import { ARMONICOS, PERIODO, TIEMPOS, frecuencias, plan } from "./audicion.js";

const pares = [
  { f: 400, sube: true },
  { f: 300, sube: false },
  { f: 500, sube: true },
];

describe("frecuencias de un par", () => {
  test("si sube, primero la base y luego 50 cents más arriba", () => {
    const [a, b] = frecuencias({ f: 440, sube: true }, 50);
    expect(a).toBe(440);
    expect(b).toBeCloseTo(440 * 2 ** (50 / 1200), 9);
    expect(b).toBeGreaterThan(a);
  });

  test("si baja, primero el agudo y luego la base", () => {
    const [a, b] = frecuencias({ f: 440, sube: false }, 25);
    expect(a).toBeCloseTo(440 * 2 ** (25 / 1200), 9);
    expect(b).toBe(440);
    expect(b).toBeLessThan(a);
  });
});

describe("timbre", () => {
  test("seno con los armónicos 2, 3 y 4 a −10, −20 y −30 dB, como el script de 2022", () => {
    expect(ARMONICOS[0]).toBe(0);
    expect(ARMONICOS[1]).toBe(1);
    expect(20 * Math.log10(ARMONICOS[2])).toBeCloseTo(-10, 9);
    expect(20 * Math.log10(ARMONICOS[3])).toBeCloseTo(-20, 9);
    expect(20 * Math.log10(ARMONICOS[4])).toBeCloseTo(-30, 9);
  });
});

describe("plan de reproducción", () => {
  test("un par suelto suena enseguida: dos sonidos de 2 s separados por 0,5 s", () => {
    const [p] = plan(pares, 50, 1, false);
    expect(p.indice).toBe(1);
    expect(p.t1).toBeLessThan(0.2);
    expect(p.t2 - p.t1).toBeCloseTo(TIEMPOS.tono + TIEMPOS.entre, 9);
    expect(p.f1).toBeGreaterThan(p.f2); // el par 2 baja
  });

  test("todo seguido: cada par 10,5 s después del anterior, con 2 s antes del primer sonido", () => {
    const todos = plan(pares, 50, 0, true);
    expect(todos.map((p) => p.indice)).toEqual([0, 1, 2]);
    expect(PERIODO).toBeCloseTo(10.5, 9);
    todos.forEach((p, k) => {
      expect(p.iluminar).toBeCloseTo(k * PERIODO, 9);
      expect(p.t1 - p.iluminar).toBeCloseTo(TIEMPOS.previo, 9);
    });
  });
});
