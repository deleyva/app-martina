import { expect, test } from 'bun:test';
import { esDeUnaTecla, resolverEntrada } from './entrada.js';

const AD = [
  { etiqueta: 'A', valor: '10' },
  { etiqueta: 'B', valor: '8' },
  { etiqueta: 'C', valor: '6' },
  { etiqueta: 'D', valor: '4' },
];
const CUADERNO = [
  { etiqueta: 'Sin cuaderno', valor: '0' },
  { etiqueta: 'Incompleto', valor: '3' },
  { etiqueta: 'Bien', valor: '6' },
  { etiqueta: 'Muy bien', valor: '9' },
];
const CON_ACENTO = [{ etiqueta: 'Á', valor: '10' }, { etiqueta: 'É', valor: '5' }];

test('vacío borra la nota', () => {
  expect(resolverEntrada('', AD)).toEqual({ tipo: 'vacio' });
  expect(resolverEntrada('   ', AD)).toEqual({ tipo: 'vacio' });
});

test('toda letra de la escala vale, en mayúscula o minúscula', () => {
  for (const opcion of AD) {
    expect(resolverEntrada(opcion.etiqueta, AD).opcion).toBe(opcion);
    expect(resolverEntrada(opcion.etiqueta.toLowerCase(), AD).opcion).toBe(opcion);
    expect(resolverEntrada(` ${opcion.etiqueta} `, AD).opcion).toBe(opcion);
  }
});

test('ninguna otra tecla vale', () => {
  const teclas = 'efghijklmnopqrstuvwxyz1235790.,-+?'.split('');
  for (const tecla of teclas) {
    expect(resolverEntrada(tecla, AD)).toEqual({ tipo: 'invalido' });
  }
});

test('el valor de una opción también la elige', () => {
  expect(resolverEntrada('8', AD).opcion.etiqueta).toBe('B');
  expect(resolverEntrada('10', AD).opcion.etiqueta).toBe('A');
  expect(resolverEntrada('6,0', AD).opcion.etiqueta).toBe('C');
  expect(resolverEntrada('7', AD)).toEqual({ tipo: 'invalido' });
});

test('con etiquetas largas basta el principio, si no es ambiguo', () => {
  expect(resolverEntrada('bi', CUADERNO).opcion.etiqueta).toBe('Bien');
  expect(resolverEntrada('muy', CUADERNO).opcion.etiqueta).toBe('Muy bien');
  expect(resolverEntrada('i', CUADERNO).opcion.etiqueta).toBe('Incompleto');
  expect(resolverEntrada('x', CUADERNO)).toEqual({ tipo: 'invalido' });
});

test('lo exacto gana a lo que empieza igual', () => {
  const opciones = [{ etiqueta: 'B', valor: '8' }, { etiqueta: 'Bien', valor: '6' }];
  expect(resolverEntrada('b', opciones).opcion.valor).toBe('8');
  expect(resolverEntrada('bi', opciones).opcion.valor).toBe('6');
});

test('los acentos no cuentan', () => {
  expect(resolverEntrada('a', CON_ACENTO).opcion.valor).toBe('10');
  expect(resolverEntrada('É', CON_ACENTO).opcion.valor).toBe('5');
});

test('una tecla es una nota entera solo si todas las etiquetas son de un carácter', () => {
  expect(esDeUnaTecla(AD)).toBe(true);
  expect(esDeUnaTecla(CUADERNO)).toBe(false);
  expect(esDeUnaTecla([])).toBe(false);
});
