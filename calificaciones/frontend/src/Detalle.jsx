// El detalle de una casilla que es la media de varias miradas: el dado del
// cuaderno (fase 78) y los pases de teoría (76·3), que además traen las
// preguntas falladas de cada pase y el acierto por concepto.
//
// Junto a la celda sale un botón pequeño con cuántas veces («×3»); al
// pulsarlo, un desplegable con la media, la letra y cada revisión (fecha,
// letra, comentario). Solo lectura: la casilla se sigue pudiendo teclear.

import { useEffect, useRef, useState } from 'react';

const TITULOS = { cuaderno: 'Cuaderno', teoria: 'Teoría' };

function fecha(iso) {
  const [, m, d] = iso.split('-');
  return `${d}/${m}`;
}

export default function Detalle({ detalle, columna }) {
  const [abierto, setAbierto] = useState(false);
  const [estilo, setEstilo] = useState({});
  const btnRef = useRef(null);
  const cajaRef = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;
    const fuera = (e) => {
      if (btnRef.current?.contains(e.target) || cajaRef.current?.contains(e.target)) return;
      setAbierto(false);
    };
    document.addEventListener('mousedown', fuera);
    return () => document.removeEventListener('mousedown', fuera);
  }, [abierto]);

  if (!detalle || !detalle.n) return null;

  const abrir = () => {
    const r = btnRef.current?.getBoundingClientRect();
    if (r) {
      const arriba = r.bottom + 220 > window.innerHeight;
      setEstilo({
        position: 'fixed',
        left: Math.max(8, Math.min(window.innerWidth - 300, r.left - 120)),
        ...(arriba ? { bottom: window.innerHeight - r.top + 4 } : { top: r.bottom + 4 }),
        zIndex: 9999,
      });
    }
    setAbierto((v) => !v);
  };

  const titulo = TITULOS[detalle.tipo] || columna?.nombre || 'Detalle';
  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={abrir}
        className="text-[9px] font-bold text-fuchsia-700 bg-fuchsia-50 border border-fuchsia-200 rounded px-1 leading-4 hover:bg-fuchsia-100"
        title={`${titulo}: ${detalle.n} revisión${detalle.n === 1 ? '' : 'es'}, media ${detalle.media}`}
        aria-label="Ver el detalle"
      >
        ×{detalle.n}
      </button>
      {abierto && (
        <div
          ref={cajaRef}
          style={estilo}
          className="w-72 bg-white border border-slate-200 rounded-lg shadow-xl p-3 text-left"
        >
          <div className="text-[11px] font-bold text-slate-700 mb-1">
            {titulo} · {detalle.n} revisión{detalle.n === 1 ? '' : 'es'}
          </div>
          <div className="text-[10px] text-slate-500 mb-2">
            Media {detalle.media} → <span className="font-bold text-slate-700">{detalle.letra}</span>.
            {' '}La casilla es la letra de la media; si la tecleas a mano, la siguiente revisión la recalcula.
          </div>
          <ul className="divide-y divide-slate-100">
            {detalle.revisiones.map((r, i) => (
              <li key={`${r.sesion}-${i}`} className="py-1 text-[10px]">
                <div className="flex gap-2">
                  <span className="font-mono text-slate-400 w-10 shrink-0">{fecha(r.fecha)}</span>
                  <span className="font-bold w-6 shrink-0">{r.letra}</span>
                  <span className="text-slate-600 break-words">{r.comentario}</span>
                </div>
                {r.fallos?.length > 0 && (
                  <ul className="ml-12 mt-0.5 text-slate-500">
                    {r.fallos.map((f) => (
                      <li key={f.pregunta} className="truncate" title={f.enunciado}>
                        ✗ {f.enunciado}
                        {f.conceptos?.length > 0 && <span className="text-slate-400"> · {f.conceptos.join(', ')}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
          {detalle.conceptos?.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-100 text-[10px]">
              <div className="font-bold text-slate-600 mb-0.5">Por concepto</div>
              {detalle.conceptos.map((c) => (
                <div key={c.concepto} className="flex justify-between gap-2">
                  <span className="text-slate-600 truncate">{c.concepto}</span>
                  <span className="font-mono text-slate-500 shrink-0">{c.aciertos}/{c.total}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
