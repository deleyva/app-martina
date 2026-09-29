import { expect, test } from 'bun:test';
import { finalConPesos, mismosPesos, normalizarPesos } from './queSiPasa.js';

test('los pesos se normalizan', () => {
  expect(normalizarPesos({ 1: 20, 2: 30, 3: 50 })).toEqual({ 1: 0.2, 2: 0.3, 3: 0.5 });
  expect(normalizarPesos({ 1: 0, 2: 0, 3: 0 })).toEqual({ 1: 1 / 3, 2: 1 / 3, 3: 1 / 3 });
});

test('con los tres trimestres es la media ponderada', () => {
  expect(finalConPesos({ 1: 8, 2: 6, 3: 5 }, { 1: 20, 2: 30, 3: 50 })).toBe(5.9);
  expect(finalConPesos({ 1: 8, 2: 6, 3: 5 }, { 1: 1, 2: 1, 3: 1 })).toBe(6.33);
});

test('un trimestre sin datos no entra', () => {
  expect(finalConPesos({ 1: 8, 2: null, 3: null }, { 1: 20, 2: 30, 3: 50 })).toBe(8);
  expect(finalConPesos({ 1: 8, 2: 6, 3: null }, { 1: 20, 2: 30, 3: 50 })).toBe(6.8);
  expect(finalConPesos({ 1: null, 2: null, 3: null }, { 1: 1, 2: 1, 3: 1 })).toBe(null);
});

test('un cero con datos sí cuenta', () => {
  expect(finalConPesos({ 1: 0, 2: 10, 3: null }, { 1: 1, 2: 1, 3: 1 })).toBe(5);
});

test('20/30/50 y 2/3/5 son los mismos pesos', () => {
  expect(mismosPesos({ 1: 20, 2: 30, 3: 50 }, { 1: 2, 2: 3, 3: 5 })).toBe(true);
  expect(mismosPesos({ 1: 20, 2: 30, 3: 50 }, { 1: 1, 2: 1, 3: 1 })).toBe(false);
});
