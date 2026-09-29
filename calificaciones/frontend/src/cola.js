// La cola de guardado: una petición en vuelo por alumno, y gana el último valor.
//
// Por qué no vale «mandar cada cambio»: dos peticiones de la misma celda
// pueden llegar al servidor al revés y dejar guardado el valor viejo; y un
// bloque de cifras calculado antes de un guardado posterior puede llegar
// después y pisar la nota en pantalla. Con una sola petición en vuelo por
// alumno, ninguna de las dos cosas puede pasar. Alumnos distintos van en
// paralelo.
//
// Todo lo que un alumno tiene pendiente sale en la misma petición: rellenar una
// fila deprisa son nueve celdas y un solo viaje.
//
// `enviar(alumno, celdas)` recibe `[[celda, valor], …]` y devuelve una promesa
// con la respuesta. `alRecibir(alumno, respuesta, quedan)`: `quedan` dice si
// ese alumno tiene todavía algo por mandar; el bloque solo se pinta cuando no
// queda nada.

export function crearCola({ enviar, alRecibir, alFallar, alCambiar, espera = 600, reloj = globalThis }) {
  const pendientes = new Map(); // alumno → Map(celda → valor)
  const temporizadores = new Map(); // alumno → id
  const enVuelo = new Set(); // alumnos con una petición fuera
  let fallo = false;

  function estado() {
    if (fallo && enVuelo.size === 0) return 'error';
    if (enVuelo.size > 0) return 'saving';
    if (pendientes.size > 0) return 'unsaved';
    return 'saved';
  }

  function avisar() {
    if (alCambiar) alCambiar(estado());
  }

  async function vaciar(alumno) {
    reloj.clearTimeout(temporizadores.get(alumno));
    temporizadores.delete(alumno);
    if (enVuelo.has(alumno)) return; // al volver la que está fuera, se sigue
    const celdas = pendientes.get(alumno);
    if (!celdas || celdas.size === 0) return;

    const lote = [...celdas.entries()];
    pendientes.delete(alumno);
    enVuelo.add(alumno);
    avisar();
    try {
      const respuesta = await enviar(alumno, lote);
      fallo = false;
      enVuelo.delete(alumno);
      const quedan = pendientes.has(alumno);
      if (alRecibir) alRecibir(alumno, respuesta, quedan);
    } catch (error) {
      enVuelo.delete(alumno);
      fallo = true;
      // Sin red o con el servidor caído, lo escrito no se tira: vuelve a la
      // cola, por detrás de lo que se haya tecleado después. Un 4xx es un no
      // del servidor y repetirlo daría lo mismo.
      if (!error || !error.status || error.status >= 500) {
        if (!pendientes.has(alumno)) pendientes.set(alumno, new Map());
        const celdas = pendientes.get(alumno);
        lote.forEach(([celda, valor]) => { if (!celdas.has(celda)) celdas.set(celda, valor); });
      }
      if (alFallar) alFallar(alumno, lote, error);
      avisar();
      return; // se reintenta con el siguiente cambio o al pedirlo, no en bucle
    }
    avisar();
    if (pendientes.has(alumno) && !temporizadores.has(alumno)) vaciar(alumno);
  }

  function poner(alumno, celda, valor, { yaMismo = false } = {}) {
    if (!pendientes.has(alumno)) pendientes.set(alumno, new Map());
    pendientes.get(alumno).set(celda, valor);
    reloj.clearTimeout(temporizadores.get(alumno));
    if (yaMismo) {
      temporizadores.delete(alumno);
      vaciar(alumno);
    } else {
      temporizadores.set(alumno, reloj.setTimeout(() => vaciar(alumno), espera));
    }
    avisar();
  }

  function vaciarTodo() {
    for (const alumno of [...pendientes.keys()]) vaciar(alumno);
  }

  function ocupado(alumno) {
    return enVuelo.has(alumno) || pendientes.has(alumno);
  }

  return { poner, vaciar, vaciarTodo, ocupado, estado, hayAlgo: () => estado() !== 'saved' };
}
