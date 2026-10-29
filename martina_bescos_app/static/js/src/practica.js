// Cuentas del reproductor de práctica (fase 82), sin DOM ni audio para que se
// puedan probar con `bun test`.
//
// Una marca es { p, t, ancla }: el párrafo `p` de la letra empieza en el
// segundo `t` de la grabación. Es el `points[]` de Songsterr (un segundo por
// compás) llevado a la unidad que tiene el ChordPro, que no tiene compases pero
// sí párrafos. El ancla son las primeras palabras del párrafo, para no perder
// la marca si alguien edita la letra y los párrafos cambian de número.

// Las marcas, ordenadas por tiempo (el servidor ya las guarda así).
export function ordenar(marcas) {
  return [...(marcas || [])].sort((a, b) => a.t - b.t || a.p - b.p);
}

// Índice (en `marcas`, ya ordenadas) de la sección que suena en el segundo `t`;
// -1 antes de la primera marca.
export function seccionEn(marcas, t) {
  let actual = -1;
  for (let i = 0; i < marcas.length; i++) {
    if (marcas[i].t <= t + 1e-6) actual = i;
    else break;
  }
  return actual;
}

// Tramo [inicio, fin) de la sección `i`: hasta la marca siguiente o el final.
export function tramoDe(marcas, i, duracion) {
  if (i < 0 || i >= marcas.length) return null;
  const fin = i + 1 < marcas.length ? marcas[i + 1].t : duracion;
  return { inicio: marcas[i].t, fin: Math.max(fin, marcas[i].t) };
}

// El párrafo que toca marcar al pulsar X: el siguiente párrafo MARCABLE después
// del último marcado antes del segundo `t` (marcar es ir siguiendo la canción).
// `marcables` son los índices, en orden, de los párrafos que se tocan (los que
// tienen acordes): sin esto, la primera X caía en «Tonalidad de Sol…» y no en
// la intro (Jesús, 2026-10-29: «No entiendo el botón Marcar»). -1 si no quedan.
export function siguientePorMarcar(marcas, marcables, t) {
  let ultimo = -1;
  for (const m of marcas) if (m.t <= t + 1e-6 && m.p > ultimo) ultimo = m.p;
  const siguiente = marcables.find((p) => p > ultimo);
  return siguiente === undefined ? -1 : siguiente;
}

// Pone (o mueve) la marca del párrafo `p` en el segundo `t`.
export function marcar(marcas, p, t, ancla) {
  const resto = marcas.filter((m) => m.p !== p);
  resto.push({ p, t: Math.max(0, Math.round(t * 100) / 100), ancla: ancla || "" });
  return ordenar(resto);
}

// Primeras palabras de un párrafo, sin mayúsculas ni espacios de más.
export function ancla(texto) {
  return (texto || "").replace(/\s+/g, " ").trim().toLowerCase().slice(0, 40);
}

// Ajusta las marcas a la letra de ahora (`anclas[i]` es el ancla del párrafo i).
// Si el párrafo de una marca sigue diciendo lo mismo, se queda. Si no, busca su
// texto hacia delante desde la marca anterior —un estribillo que se repite tiene
// la misma ancla tres veces y el orden es lo que las distingue—, y si no lo
// encuentra la descarta: una marca nunca se pega a un párrafo que no es el suyo.
export function reanclar(marcas, anclas) {
  const fuera = [];
  const dentro = [];
  let desde = 0;
  for (const m of ordenar(marcas)) {
    let p = -1;
    if (!m.ancla || anclas[m.p] === m.ancla) {
      if (m.p < anclas.length) p = m.p;
    } else {
      for (let j = desde; j < anclas.length; j++) {
        if (anclas[j] === m.ancla && !dentro.some((d) => d.p === j)) { p = j; break; }
      }
    }
    if (p < 0) { fuera.push(m); continue; }
    dentro.push({ ...m, p });
    desde = p + 1;
  }
  return { marcas: dentro, descartadas: fuera };
}

// Semitonos que hay que mover la grabación para que suene en el tono de la
// letra en pantalla. `desfase` es cuánto suena la grabación por encima del
// ChordPro tal como está escrito. Se lleva al intervalo más corto (−6 … +5):
// para practicar da igual la octava, y mover el audio una quinta hacia arriba
// suena mucho peor que una cuarta hacia abajo.
export function semitonosDelAudio(tonoLetra, desfase) {
  const crudo = (tonoLetra || 0) - (desfase || 0);
  return ((((crudo % 12) + 12) % 12) + 6) % 12 - 6;
}

// 83.4 → «1:23».
export function formatoTiempo(segundos) {
  const s = Math.max(0, Math.floor(segundos || 0));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
