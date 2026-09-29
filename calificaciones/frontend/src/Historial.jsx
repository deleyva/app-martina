// El historial de cambios, con deshacer. Es el de `notas`.

import { useMemo, useState } from 'react';
import { Filter, History, RotateCcw, Search } from 'lucide-react';
import { TERMS, TERM_LABELS } from './estilos.js';

export default function Historial({ cambios, onRevertir }) {
  const [filtro, setFiltro] = useState({ alumno: '', trimestre: '' });

  const filtrados = useMemo(() => {
    let h = cambios;
    if (filtro.alumno) {
      h = h.filter((e) => e.alumno.toLowerCase().includes(filtro.alumno.toLowerCase()));
    }
    if (filtro.trimestre) {
      h = h.filter((e) => String(e.trimestre) === filtro.trimestre);
    }
    return h;
  }, [cambios, filtro]);

  const formatDate = (ts) => {
    const d = new Date(ts);
    return `${d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })} ${
      d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`;
  };

  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
        <h3 className="text-sm font-black text-slate-800 mb-3 flex items-center gap-2">
          <History size={16} className="text-indigo-600" />
          Historial de Cambios
        </h3>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-4">
          <div className="flex items-center gap-1.5 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
            <Search size={12} className="text-slate-400" />
            <input
              type="text"
              placeholder="Buscar alumno..."
              className="bg-transparent text-xs text-slate-700 outline-none w-32"
              value={filtro.alumno}
              onChange={(e) => setFiltro({ ...filtro, alumno: e.target.value })}
            />
          </div>
          <div className="flex items-center gap-1.5 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
            <Filter size={12} className="text-slate-400" />
            <select
              className="bg-transparent text-xs text-slate-700 outline-none cursor-pointer"
              value={filtro.trimestre}
              onChange={(e) => setFiltro({ ...filtro, trimestre: e.target.value })}
            >
              <option value="">Todas las eval.</option>
              {TERMS.map((t) => <option key={t} value={t}>{TERM_LABELS[t]}</option>)}
            </select>
          </div>
        </div>

        {/* History list */}
        {filtrados.length === 0 ? (
          <div className="text-center text-slate-400 text-sm py-12">
            No hay cambios registrados
          </div>
        ) : (
          <div className="space-y-1.5 max-h-[600px] overflow-y-auto">
            {filtrados.map((entry) => (
              <div
                key={entry.id}
                className={`flex items-center justify-between px-3 py-2 rounded-xl border transition-colors ${
                  entry.es_deshacer
                    ? 'bg-amber-50/50 border-amber-200'
                    : 'bg-slate-50 border-slate-100 hover:bg-slate-100'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="font-bold text-slate-700 truncate">{entry.alumno}</span>
                    <span className="text-[9px] font-bold text-slate-400 uppercase bg-white px-1.5 py-0.5 rounded">
                      {TERM_LABELS[entry.trimestre] || entry.trimestre}
                    </span>
                    {entry.es_deshacer && (
                      <span className="text-[9px] font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">
                        REVERTIDO
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    <span className="font-medium">{entry.columna}</span>:
                    <span className="text-red-500 line-through ml-1">{entry.antes || '0'}</span>
                    <span className="text-slate-400 mx-1">&#8594;</span>
                    <span className="text-green-600 font-bold">{entry.despues || '0'}</span>
                    <span className="text-slate-300 ml-2">{formatDate(entry.fecha)}</span>
                  </div>
                </div>
                {!entry.es_deshacer && (
                  <button
                    onClick={() => onRevertir(entry.id)}
                    className="ml-2 p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Revertir cambio"
                  >
                    <RotateCcw size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
