// Los pesos «y si…» de la pestaña Final. Es la única cuenta de notas que hace
// el navegador, y no es la oficial: la nota de curso oficial viene calculada
// del servidor con los pesos de la programación. Esto contesta a «¿y si la 3ª
// contara el doble?» sin guardar nada.

export function normalizarPesos(pesos) {
  const total = Object.values(pesos).reduce((a, b) => a + b, 0);
  if (total === 0) return { 1: 1 / 3, 2: 1 / 3, 3: 1 / 3 };
  return { 1: pesos[1] / total, 2: pesos[2] / total, 3: pesos[3] / total };
}

// `notas`: { 1: número | null, … }. Un trimestre sin datos (null) no entra.
export function finalConPesos(notas, pesos) {
  const normalizados = normalizarPesos(pesos);
  let total = 0;
  let peso = 0;
  for (const t of [1, 2, 3]) {
    if (notas[t] === null || notas[t] === undefined) continue;
    total += notas[t] * normalizados[t];
    peso += normalizados[t];
  }
  return peso > 0 ? parseFloat((total / peso).toFixed(2)) : null;
}

export function mismosPesos(a, b) {
  const na = normalizarPesos(a);
  const nb = normalizarPesos(b);
  return [1, 2, 3].every((t) => Math.abs(na[t] - nb[t]) < 1e-9);
}
