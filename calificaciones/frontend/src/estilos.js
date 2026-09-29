// Los colores de `notas`, tal cual. Aquí no se calcula ninguna nota: solo se
// decide de qué color se pinta una cifra que ya viene calculada.

export const TERMS = ['1', '2', '3'];
export const TERM_LABELS = { 1: '1a Eval', 2: '2a Eval', 3: '3a Eval' };
export const TERM_LARGOS = { 1: '1a Evaluacion', 2: '2a Evaluacion', 3: '3a Evaluacion' };
export const TERM_FONDO = { 1: '#d97706', 2: '#4f46e5', 3: '#059669' };

export function gradeInputBg(val) {
  if (!val || val === 0) return 'bg-red-100/60';
  if (val < 5) return 'bg-red-100/60';
  if (val < 7) return 'bg-yellow-100/60';
  if (val < 8.5) return 'bg-blue-100/60';
  return 'bg-green-100/60';
}

export const QUALITATIVE_OPTIONS = ['', 'IN', 'SU', 'BI', 'NT', 'SB'];
export const QUALITATIVE_STYLES = {
  IN: 'text-red-600 bg-red-50 border-red-300',
  SU: 'text-orange-600 bg-orange-50 border-orange-300',
  BI: 'text-yellow-600 bg-yellow-50 border-yellow-300',
  NT: 'text-blue-600 bg-blue-50 border-blue-300',
  SB: 'text-green-600 bg-green-50 border-green-300',
};

const CUALITATIVAS = {
  IN: { label: 'IN', full: 'Insuficiente', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
  SU: { label: 'SU', full: 'Suficiente', color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200' },
  BI: { label: 'BI', full: 'Bien', color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  NT: { label: 'NT', full: 'Notable', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
  SB: { label: 'SB', full: 'Sobresaliente', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' },
};
const SIN_NOTA = { label: '', full: 'Sin nota', color: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200' };

// El estilo de una calificación que ya viene puesta por el servidor.
export function estiloCualitativa(clave) {
  return CUALITATIVAS[clave] || SIN_NOTA;
}

// Para pintar una cifra suelta (una competencia, un «y si…»): los mismos
// tramos que usa el servidor para la calificación.
export function estiloDeNota(nota) {
  if (nota === null || nota === undefined || Number.isNaN(nota)) return SIN_NOTA;
  if (nota < 5) return CUALITATIVAS.IN;
  if (nota < 6) return CUALITATIVAS.SU;
  if (nota < 7) return CUALITATIVAS.BI;
  if (nota < 9) return CUALITATIVAS.NT;
  return CUALITATIVAS.SB;
}

export function numero(texto) {
  if (texto === '' || texto === null || texto === undefined) return null;
  const n = parseFloat(texto);
  return Number.isNaN(n) ? null : n;
}

// Qué cifra de un trimestre se enseña según el conmutador Media simple / LOMLOE.
export function notaDe(bloque, modo) {
  return modo === 'simple'
    ? { texto: bloque.simple, exacta: bloque.simple2, cualitativa: bloque.simple_cualitativa }
    : { texto: bloque.nota, exacta: bloque.nota2, cualitativa: bloque.cualitativa };
}
