// bun test martina_bescos_app/static/js/src/ritmos.test.js
import { test, expect } from "bun:test";
import { ChordProParser, HtmlDivFormatter } from "chordsheetjs";
import { parsearRitmo, cuenta, svgRitmo } from "./ritmos.js";

const ROCK = "compás: 4/4\nSH: x x x x x x x x\nCA: . . x . . . x .\nBO: x . . . x x . .";

test("rock en corcheas: tres voces, ocho pasos, sin errores", () => {
  const p = parsearRitmo(ROCK);
  expect(p.errores).toEqual([]);
  expect(p.pasos).toBe(8);
  expect(p.porPulso).toBe(2);
  expect(p.voces.map((v) => v.voz)).toEqual(["SH", "CA", "BO"]);
  expect(p.voces[1].golpes).toEqual([0, 0, 1, 0, 0, 0, 1, 0]);
});

test("acento, barras y espacios", () => {
  const p = parsearRitmo("SH: X x x x | X x x x");
  expect(p.errores).toEqual([]);
  expect(p.voces[0].golpes).toEqual([2, 1, 1, 1, 2, 1, 1, 1]);
});

test("las voces salen en orden SH, CA, BO aunque se escriban al revés", () => {
  expect(parsearRitmo("BO: x . x .\nSH: x x x x").voces.map((v) => v.voz)).toEqual(["SH", "BO"]);
});

test("cuenta en voz alta: corcheas, semicorcheas y 12/8", () => {
  expect(cuenta(parsearRitmo(ROCK))).toEqual(["1", "y", "2", "y", "3", "y", "4", "y"]);
  expect(cuenta(parsearRitmo("SH: " + "x".repeat(16))).slice(0, 4)).toEqual(["1", "e", "y", "a"]);
  expect(cuenta(parsearRitmo("compás: 12/8\nSH: " + "x".repeat(12))).slice(0, 6)).toEqual(["1", "y", "a", "2", "y", "a"]);
});

test("tempo leído y acotado", () => {
  expect(parsearRitmo("tempo: 96\n" + ROCK).tempo).toBe(96);
  expect(parsearRitmo("tempo: 500\n" + ROCK).errores.join()).toMatch(/Tempo/);
});

test.each([
  ["voces de distinta longitud", "SH: x x x x x x x x\nCA: x x x x", /no miden lo mismo/],
  ["voz desconocida", "TOM: x x x x", /desconocida/],
  ["símbolo raro", "SH: x x o x", /Símbolo/],
  ["compás no admitido", "compás: 5/4\nSH: x x x x", /no admitido/],
  ["pasos que no caben en el compás", "SH: x x x x x x", /tiene que tener/],
  ["12/8 con ocho golpes", "compás: 12/8\nSH: x x x x x x x x", /12 golpes/],
  ["sin voces", "compás: 4/4", /ninguna voz/],
  ["línea sin dos puntos", "x x x x", /No entiendo/],
])("inválido: %s", (_, texto, error) => {
  expect(parsearRitmo(texto).errores.join(" ")).toMatch(error);
});

test("el SVG lleva un icono por golpe y la cuenta", () => {
  const svg = svgRitmo(parsearRitmo(ROCK));
  // 8 + 2 + 3 golpes + 3 iconos de la leyenda = 16 grupos con transform
  expect((svg.match(/<g transform=/g) || []).length).toBe(16);
  expect(svg).toContain(">y<");
});

test("ChordSheetJS deja el bloque intacto como paragraph ritmo, también al transportar", () => {
  const texto = "{start_of_ritmo: Rock}\n" + ROCK + "\n{end_of_ritmo}\n[G]Hola";
  const cancion = new ChordProParser().parse(texto);
  for (const c of [cancion, cancion.transpose(3)]) {
    const html = new HtmlDivFormatter().format(c);
    expect(html).toContain('class="paragraph ritmo"');
    expect(html).toContain("CA: . . x . . . x .");
  }
});
