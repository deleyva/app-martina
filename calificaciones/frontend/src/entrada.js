// De lo que se teclea en una celda de opciones a la opción que es.
//
// Vale para cualquier lista de opciones, no solo A-B-C-D: «Bien», «Muy bien»…
// El orden importa: primero lo exacto, luego el valor, luego el principio.

export function normalizar(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim()
    .toUpperCase();
}

// Devuelve { tipo: 'vacio' } | { tipo: 'opcion', opcion } | { tipo: 'invalido' }.
export function resolverEntrada(texto, opciones) {
  const clave = normalizar(texto);
  if (clave === '') return { tipo: 'vacio' };

  const exacta = opciones.find((o) => normalizar(o.etiqueta) === clave);
  if (exacta) return { tipo: 'opcion', opcion: exacta };

  const comoNumero = Number(clave.replace(',', '.'));
  if (!Number.isNaN(comoNumero)) {
    const porValor = opciones.find((o) => Number(o.valor) === comoNumero);
    if (porValor) return { tipo: 'opcion', opcion: porValor };
    return { tipo: 'invalido' };
  }

  const empiezan = opciones.filter((o) => normalizar(o.etiqueta).startsWith(clave));
  if (empiezan.length === 1) return { tipo: 'opcion', opcion: empiezan[0] };
  return { tipo: 'invalido' };
}

// Si todas las etiquetas son de un carácter, una tecla ya es una nota completa
// y se puede guardar sin esperar.
export function esDeUnaTecla(opciones) {
  return opciones.length > 0 && opciones.every((o) => normalizar(o.etiqueta).length === 1);
}
