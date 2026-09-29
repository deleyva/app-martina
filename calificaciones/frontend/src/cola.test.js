import { expect, test } from 'bun:test';
import { crearCola } from './cola.js';

// Un reloj y un servidor de pega: los temporizadores se disparan a mano y cada
// petición se contesta cuando el test lo dice, en el orden que el test quiera.
function montar() {
  const temporizadores = new Map();
  let siguiente = 1;
  const reloj = {
    setTimeout: (fn) => { const id = siguiente++; temporizadores.set(id, fn); return id; },
    clearTimeout: (id) => temporizadores.delete(id),
  };
  const enviadas = [];
  const recibidas = [];
  const estados = [];
  const fallos = [];
  const cola = crearCola({
    enviar: (alumno, celdas) => new Promise((resolver, rechazar) => {
      enviadas.push({ alumno, celdas, valor: celdas.at(-1)[1], resolver, rechazar });
    }),
    alRecibir: (alumno, respuesta, quedan) => recibidas.push({ alumno, respuesta, quedan }),
    alFallar: (alumno, celdas) => fallos.push({ alumno, celdas }),
    alCambiar: (estado) => estados.push(estado),
    reloj,
  });
  const pasarElTiempo = () => { [...temporizadores.values()].forEach((fn) => fn()); temporizadores.clear(); };
  const respirar = () => new Promise((r) => setTimeout(r, 0));
  return { cola, enviadas, recibidas, estados, fallos, pasarElTiempo, respirar };
}

test('teclear varias veces la misma celda manda solo lo último', async () => {
  const { cola, enviadas, pasarElTiempo } = montar();
  cola.poner(1, 'teoria', '7');
  cola.poner(1, 'teoria', '7.');
  cola.poner(1, 'teoria', '7.5');
  expect(enviadas).toHaveLength(0);
  expect(cola.estado()).toBe('unsaved');
  pasarElTiempo();
  expect(enviadas.map((e) => e.valor)).toEqual(['7.5']);
  expect(cola.estado()).toBe('saving');
});

test('nunca hay dos peticiones del mismo alumno a la vez', async () => {
  const { cola, enviadas, recibidas, respirar } = montar();
  cola.poner(1, 'teoria', '10', { yaMismo: true });
  cola.poner(1, 'teoria', '8', { yaMismo: true });
  cola.poner(1, 'dictado', '6', { yaMismo: true });
  expect(enviadas).toHaveLength(1);

  expect(enviadas[0].celdas).toEqual([['teoria', '10']]);

  enviadas[0].resolver('bloque con A');
  await respirar();
  // El bloque de la primera ya es viejo: quedaba algo por mandar.
  expect(recibidas[0]).toMatchObject({ respuesta: 'bloque con A', quedan: true });
  // Lo que se escribió mientras tanto sale junto, con el último valor de cada celda.
  expect(enviadas).toHaveLength(2);
  expect(enviadas[1].celdas).toEqual([['teoria', '8'], ['dictado', '6']]);

  enviadas[1].resolver('bloque final');
  await respirar();
  expect(recibidas.at(-1)).toMatchObject({ respuesta: 'bloque final', quedan: false });
  expect(cola.estado()).toBe('saved');
});

test('lo último tecleado es lo último que llega al servidor', async () => {
  const { cola, enviadas, respirar, pasarElTiempo } = montar();
  const secuencia = ['10', '8', '6', '4', '', '8'];
  for (const valor of secuencia) {
    cola.poner(1, 'teoria', valor, { yaMismo: true });
    if (enviadas.length && enviadas.at(-1).resolver) {
      enviadas.at(-1).resolver('ok');
      enviadas.at(-1).resolver = null;
      await respirar();
    }
  }
  pasarElTiempo();
  while (enviadas.some((e) => e.resolver)) {
    enviadas.filter((e) => e.resolver).forEach((e) => { e.resolver('ok'); e.resolver = null; });
    await respirar();
  }
  expect(enviadas.at(-1).valor).toBe('8');
  expect(cola.estado()).toBe('saved');
});

test('alumnos distintos van en paralelo', () => {
  const { cola, enviadas } = montar();
  cola.poner(1, 'teoria', '10', { yaMismo: true });
  cola.poner(2, 'teoria', '8', { yaMismo: true });
  cola.poner(3, 'teoria', '6', { yaMismo: true });
  expect(enviadas.map((e) => e.alumno)).toEqual([1, 2, 3]);
});

test('rellenar una fila es un solo viaje', () => {
  const { cola, enviadas, pasarElTiempo } = montar();
  'ABCDABCDA'.split('').forEach((letra, i) => cola.poner(1, `prueba${i}`, letra));
  pasarElTiempo();
  expect(enviadas).toHaveLength(1);
  expect(enviadas[0].celdas).toHaveLength(9);
  expect(enviadas[0].celdas[8]).toEqual(['prueba8', 'A']);
});

test('salir de la celda manda lo pendiente sin esperar', () => {
  const { cola, enviadas } = montar();
  cola.poner(1, 'teoria', '7.5');
  expect(enviadas).toHaveLength(0);
  cola.vaciar(1);
  expect(enviadas.map((e) => e.valor)).toEqual(['7.5']);
});

test('un fallo se ve, y volver a escribir lo reintenta', async () => {
  const { cola, enviadas, fallos, respirar } = montar();
  cola.poner(1, 'teoria', '10', { yaMismo: true });
  enviadas[0].rechazar(new Error('sin red'));
  await respirar();
  expect(cola.estado()).toBe('error');
  expect(fallos).toEqual([{ alumno: 1, celdas: [['teoria', '10']] }]);

  cola.poner(1, 'teoria', '10', { yaMismo: true });
  enviadas[1].resolver('ok');
  await respirar();
  expect(cola.estado()).toBe('saved');
});
