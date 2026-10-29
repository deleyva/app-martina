// bun test martina_bescos_app/static/js/src/practica.test.js
import { test, expect } from "bun:test";
import {
  ancla, formatoTiempo, marcar, ordenar, reanclar, seccionEn,
  semitonosDelAudio, siguientePorMarcar, tramoDe,
} from "./practica.js";

const MARCAS = [
  { p: 0, t: 0, ancla: "intro" },
  { p: 1, t: 12.5, ancla: "verso uno" },
  { p: 2, t: 40, ancla: "estribillo" },
];

test("la sección que suena es la de la última marca ya pasada", () => {
  expect(seccionEn(MARCAS, 0)).toBe(0);
  expect(seccionEn(MARCAS, 12.49)).toBe(0);
  expect(seccionEn(MARCAS, 12.5)).toBe(1);
  expect(seccionEn(MARCAS, 300)).toBe(2);
  expect(seccionEn([{ p: 3, t: 5 }], 2)).toBe(-1);
  expect(seccionEn([], 10)).toBe(-1);
});

test("el tramo de una sección acaba donde empieza la siguiente, y la última al final", () => {
  expect(tramoDe(MARCAS, 1, 200)).toEqual({ inicio: 12.5, fin: 40 });
  expect(tramoDe(MARCAS, 2, 200)).toEqual({ inicio: 40, fin: 200 });
  expect(tramoDe(MARCAS, 5, 200)).toBeNull();
});

test("marcar sigue la canción: el siguiente al último párrafo marcado antes de ahora", () => {
  const todos = [0, 1, 2, 3, 4];
  expect(siguientePorMarcar([], todos, 0)).toBe(0);
  expect(siguientePorMarcar(MARCAS, todos, 41)).toBe(3);
  // Volviendo atrás para rehacer: cuenta lo marcado ANTES del segundo actual.
  expect(siguientePorMarcar(MARCAS, todos, 20)).toBe(2);
  expect(siguientePorMarcar(MARCAS, [0, 1, 2], 41)).toBe(-1);
});

test("marcar se salta los párrafos que no se tocan (comentarios, datos de la ficha)", () => {
  // Stand by Me: 0 = comentario de la cejilla, 1 = datos; la intro es el 2.
  const marcables = [2, 3, 4, 5, 6, 7, 8];
  expect(siguientePorMarcar([], marcables, 0)).toBe(2);
  expect(siguientePorMarcar([{ p: 2, t: 2 }], marcables, 5)).toBe(3);
  // Un párrafo sin acordes marcado a mano (tocándolo) no rompe la cuenta.
  expect(siguientePorMarcar([{ p: 1, t: 0.5 }], marcables, 1)).toBe(2);
  expect(siguientePorMarcar([{ p: 8, t: 146 }], marcables, 150)).toBe(-1);
});

test("marcar un párrafo ya marcado lo mueve, no lo duplica", () => {
  const m = marcar(MARCAS, 1, 10.123, "verso uno");
  expect(m.filter((x) => x.p === 1)).toEqual([{ p: 1, t: 10.12, ancla: "verso uno" }]);
  expect(m.map((x) => x.p)).toEqual([0, 1, 2]);
  expect(marcar([], 0, -3, "").at(0).t).toBe(0);
});

test("ordenar no toca el original", () => {
  const desordenadas = [{ p: 2, t: 40 }, { p: 0, t: 0 }];
  expect(ordenar(desordenadas).map((m) => m.p)).toEqual([0, 2]);
  expect(desordenadas[0].p).toBe(2);
});

test("el ancla ignora mayúsculas y espacios y se queda en 40 caracteres", () => {
  expect(ancla("  I'm in   LOVE\nwith ")).toBe("i'm in love with");
  expect(ancla("x".repeat(80)).length).toBe(40);
});

test("reanclar: si la letra no cambia, las marcas se quedan", () => {
  const r = reanclar(MARCAS, ["intro", "verso uno", "estribillo"]);
  expect(r.marcas.map((m) => m.p)).toEqual([0, 1, 2]);
  expect(r.descartadas).toEqual([]);
});

test("reanclar: un párrafo nuevo arriba desplaza las marcas a su texto", () => {
  const r = reanclar(MARCAS, ["{comment}", "intro", "verso uno", "estribillo"]);
  expect(r.marcas.map((m) => m.p)).toEqual([1, 2, 3]);
});

test("reanclar: un estribillo repetido se reengancha en orden, sin repetir párrafo", () => {
  const marcas = [
    { p: 1, t: 10, ancla: "estribillo" },
    { p: 3, t: 50, ancla: "estribillo" },
  ];
  const r = reanclar(marcas, ["nuevo", "verso", "estribillo", "verso 2", "estribillo"]);
  expect(r.marcas.map((m) => m.p)).toEqual([2, 4]);
});

test("reanclar: una marca cuyo texto ya no existe se descarta, nunca se pega a otro", () => {
  const r = reanclar(MARCAS, ["intro", "otra letra", "estribillo"]);
  expect(r.marcas.map((m) => m.p)).toEqual([0, 2]);
  expect(r.descartadas.map((m) => m.ancla)).toEqual(["verso uno"]);
});

test("el audio va al tono de la letra menos el desfase, por el camino más corto", () => {
  expect(semitonosDelAudio(0, 0)).toBe(0);
  expect(semitonosDelAudio(2, 0)).toBe(2);
  expect(semitonosDelAudio(0, 2)).toBe(-2);   // disco en La, letra en Sol
  expect(semitonosDelAudio(2, 2)).toBe(0);
  expect(semitonosDelAudio(7, 0)).toBe(-5);   // una quinta arriba = una cuarta abajo
  expect(semitonosDelAudio(-3, 0)).toBe(-3);
  expect(semitonosDelAudio(11, -11)).toBe(-2);
  for (let a = -11; a <= 11; a++) for (let d = -11; d <= 11; d++) {
    const s = semitonosDelAudio(a, d);
    expect(s >= -6 && s <= 5).toBe(true);
    expect((((s - (a - d)) % 12) + 12) % 12).toBe(0);
  }
});

test("formato de tiempo", () => {
  expect(formatoTiempo(0)).toBe("0:00");
  expect(formatoTiempo(83.9)).toBe("1:23");
  expect(formatoTiempo(-4)).toBe("0:00");
});
