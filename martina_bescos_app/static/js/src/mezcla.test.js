// bun test martina_bescos_app/static/js/src/mezcla.test.js
import { test, expect } from "bun:test";
import { CANAL_BATERIA, nombreGM, resumirCanales, sonido } from "./mezcla.js";

// Los ocho canales del MIDI karaoke de Stand by Me (fase 85).
const STAND_BY_ME = [
  { canal: 9, tipo: "nota" },
  { canal: 1, tipo: "programa", programa: 32 }, { canal: 1, tipo: "nota" },
  { canal: 2, tipo: "programa", programa: 24 }, { canal: 3, tipo: "programa", programa: 24 },
  { canal: 15, tipo: "programa", programa: 65 }, { canal: 15, tipo: "nota" },
  { canal: 3, tipo: "nota" }, { canal: 2, tipo: "nota" }, { canal: 2, tipo: "nota" },
  { canal: 4, tipo: "programa", programa: 48 }, { canal: 4, tipo: "nota" },
  { canal: 14, tipo: "programa", programa: 52 }, { canal: 14, tipo: "nota" },
  { canal: 5, tipo: "programa", programa: 48 }, { canal: 5, tipo: "nota" },
];

test("cada canal con notas es una fila, en orden, con el instrumento en castellano", () => {
  const c = resumirCanales(STAND_BY_ME);
  expect(c.map((x) => [x.canal, x.nombre])).toEqual([
    [1, "Bajo acústico"], [2, "Guitarra española 1"], [3, "Guitarra española 2"],
    [4, "Cuerdas 1"], [5, "Cuerdas 2"], [9, "Batería"], [14, "Coro"], [15, "Saxo alto"],
  ]);
  expect(c.find((x) => x.canal === 2).notas).toBe(2);
});

test("el canal 10 es batería aunque pida un programa, y un canal sin notas no sale", () => {
  const c = resumirCanales([
    { canal: CANAL_BATERIA, tipo: "programa", programa: 25 }, { canal: CANAL_BATERIA, tipo: "nota" },
    { canal: 0, tipo: "programa", programa: 73 },
  ]);
  expect(c).toEqual([{ canal: 9, programa: 25, bateria: true, notas: 1, nombre: "Batería" }]);
});

test("el nombre es el instrumento de la primera nota, no el de un cambio posterior", () => {
  const c = resumirCanales([
    { canal: 0, tipo: "nota" },
    { canal: 0, tipo: "programa", programa: 40 }, { canal: 0, tipo: "nota" },
  ]);
  expect(c[0].nombre).toBe("Piano");
  expect(c[0].notas).toBe(2);
});

test("hay un nombre para los 128 programas", () => {
  for (let p = 0; p < 128; p++) expect(nombreGM(p, false)).toBeTruthy();
  expect(nombreGM(65, false)).toBe("Saxo alto");
  expect(nombreGM(0, true)).toBe("Batería");
});

const CANALES = [{ canal: 1 }, { canal: 2 }, { canal: 9 }];

test("sin tocar nada suena todo al 100 %", () => {
  const s = sonido(CANALES, {});
  for (const c of CANALES) expect(s.get(c.canal)).toEqual({ mudo: false, ganancia: 1 });
});

test("apagar un canal solo apaga ese", () => {
  const s = sonido(CANALES, { 2: { apagado: true } });
  expect([1, 2, 9].map((c) => s.get(c).mudo)).toEqual([false, true, false]);
});

test("con un solo suena solo ese; con dos, esos dos", () => {
  expect([1, 2, 9].map((c) => sonido(CANALES, { 1: { solo: true } }).get(c).mudo)).toEqual([false, true, true]);
  expect([1, 2, 9].map((c) => sonido(CANALES, { 1: { solo: true }, 9: { solo: true } }).get(c).mudo))
    .toEqual([false, true, false]);
});

test("apagado gana a solo", () => {
  const s = sonido(CANALES, { 1: { solo: true, apagado: true } });
  expect([1, 2, 9].map((c) => s.get(c).mudo)).toEqual([true, true, true]);
});

test("el volumen se queda entre 0 y 150 %", () => {
  expect(sonido(CANALES, { 1: { volumen: 0.4 } }).get(1).ganancia).toBe(0.4);
  expect(sonido(CANALES, { 1: { volumen: 9 } }).get(1).ganancia).toBe(1.5);
  expect(sonido(CANALES, { 1: { volumen: -1 } }).get(1).ganancia).toBe(0);
});
