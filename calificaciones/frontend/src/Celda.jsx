// Una celda del registro: la casilla de `notas`, con tres formas de escribir.
//
// - Número: la casilla de siempre.
// - Opciones con teclado: la misma casilla, y se teclea la etiqueta (A, B…).
// - Opciones en pantalla táctil: un desplegable, como el cuaderno en `notas`.
//
// La celda guarda un borrador propio mientras se escribe. Lo que llega del
// servidor nunca pisa una celda que tiene el foco o que está a medias: si no,
// una respuesta lenta borraría lo que se está tecleando.

import { useEffect, useRef, useState } from 'react';
import { esDeUnaTecla, resolverEntrada } from './entrada.js';
import { gradeInputBg, numero } from './estilos.js';

const CASILLA = 'w-11 border rounded text-center py-1 font-mono text-[10px] outline-none';
const NORMAL = 'border-slate-200 focus:ring-1 focus:ring-indigo-500';
// Lo que no es una opción se ve aunque la celda tenga el foco.
const NO_VALE = 'border-red-500 ring-2 ring-red-500 text-red-700';

export function irAVecina(origen, salto) {
  const { col, fila } = origen.dataset;
  const destino = document.querySelector(
    `[data-celda][data-col="${col}"][data-fila="${Number(fila) + salto}"]`,
  );
  if (destino) {
    destino.focus();
    if (destino.select) destino.select();
  }
  return Boolean(destino);
}

export default function Celda({ columna, celda, tactil, col, fila, onCambio, onSalir }) {
  const guardado = celda?.valor ?? '';
  const etiqueta = celda?.etiqueta ?? '';
  const esOpciones = columna.tipo === 'opciones';
  const mostrado = esOpciones ? etiqueta : guardado;

  const [borrador, setBorrador] = useState(null); // null = no se está escribiendo
  const [invalido, setInvalido] = useState(false);

  // Cuando el servidor confirma lo que se escribió, el borrador sobra. Pero
  // no mientras la celda tiene el foco: ahí manda quien está escribiendo.
  const conFoco = useRef(false);
  useEffect(() => {
    if (!conFoco.current) { setBorrador(null); setInvalido(false); }
  }, [guardado]);

  const valorPintado = borrador === null ? numero(guardado) : borradorANumero(borrador);
  const fondo = gradeInputBg(valorPintado);
  const comunes = { 'data-celda': true, 'data-col': col, 'data-fila': fila };

  function borradorANumero(texto) {
    if (!esOpciones) return numero(texto);
    const r = resolverEntrada(texto, columna.opciones);
    return r.tipo === 'opcion' ? numero(r.opcion.valor) : null;
  }

  function alPulsar(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (invalido) return;
    if (!irAVecina(e.currentTarget, e.shiftKey ? -1 : 1)) e.currentTarget.blur();
  }

  // ── Desplegable ──
  if (esOpciones && tactil) {
    const fuera = guardado !== '' && !columna.opciones.some((o) => o.valor === guardado);
    return (
      <select
        {...comunes}
        className={`${fondo} border border-slate-200 rounded text-[10px] py-1 px-0.5 outline-none cursor-pointer`}
        value={guardado}
        title={columna.nombre}
        onChange={(e) => onCambio(e.target.value, { yaMismo: true })}
      >
        <option value="">0</option>
        {fuera && <option value={guardado}>{guardado}</option>}
        {columna.opciones.map((o) => (
          <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
        ))}
      </select>
    );
  }

  // ── Opciones con teclado ──
  if (esOpciones) {
    const lista = columna.opciones.map((o) => o.etiqueta).join(', ');
    return (
      <input
        {...comunes}
        type="text"
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        className={`${CASILLA} ${fondo} uppercase ${invalido ? NO_VALE : NORMAL}`}
        value={borrador === null ? mostrado : borrador}
        placeholder="0"
        title={invalido ? `No vale. Opciones: ${lista}` : `${columna.nombre}: ${lista}`}
        onFocus={(e) => { conFoco.current = true; e.target.select(); }}
        onKeyDown={alPulsar}
        onChange={(e) => {
          const texto = e.target.value;
          const r = resolverEntrada(texto, columna.opciones);
          setBorrador(texto);
          setInvalido(r.tipo === 'invalido');
          if (r.tipo === 'vacio') onCambio('');
          // Con etiquetas de una letra, una tecla ya es la nota entera.
          if (r.tipo === 'opcion') onCambio(r.opcion.valor, { yaMismo: esDeUnaTecla(columna.opciones) });
        }}
        onBlur={() => {
          conFoco.current = false;
          const r = borrador === null ? null : resolverEntrada(borrador, columna.opciones);
          // Lo que no es una opción no se guarda: vuelve lo último guardado.
          if (r && r.tipo === 'invalido') { setBorrador(null); setInvalido(false); }
          if (r && r.tipo === 'opcion' && r.opcion.valor === guardado) setBorrador(null);
          if (r && r.tipo === 'vacio' && guardado === '') setBorrador(null);
          onSalir();
        }}
      />
    );
  }

  // ── Número ──
  return (
    <input
      {...comunes}
      type="number"
      className={`${CASILLA} ${fondo} ${NORMAL}`}
      value={borrador === null ? guardado : borrador}
      placeholder="0"
      min="0"
      max="10"
      step="0.1"
      title={columna.nombre}
      onFocus={(e) => { conFoco.current = true; e.target.select(); }}
      onKeyDown={alPulsar}
      onChange={(e) => {
        const texto = e.target.value;
        setBorrador(texto);
        if (texto === '') { onCambio(''); return; }
        const n = parseFloat(texto.replace(',', '.'));
        if (Number.isNaN(n)) return;
        onCambio(String(Math.min(10, Math.max(0, n))));
      }}
      onBlur={() => {
        conFoco.current = false;
        if (borrador !== null && (borrador === guardado || Number(borrador) === Number(guardado))) setBorrador(null);
        onSalir();
      }}
    />
  );
}
