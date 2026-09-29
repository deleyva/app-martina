// Un trimestre sin plan: elegir con qué instrumentos se califica, con un clic.
// `notas` no tenía esta pantalla (sus instrumentos venían escritos en el
// código); va en su mismo lenguaje visual.

import { useState } from 'react';
import { Layers, Play } from 'lucide-react';
import { api } from './api.js';
import { TERM_LARGOS } from './estilos.js';

function Resumen({ filas }) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
      {filas.map((f) => (
        <div key={f.nombre} className="bg-slate-50 rounded-xl p-2.5">
          <div className="text-[9px] font-black text-slate-400 uppercase truncate" title={f.nombre}>{f.nombre}</div>
          <div className="text-sm font-black text-indigo-600">{f.peso}%</div>
        </div>
      ))}
    </div>
  );
}

export default function Empezar({ trimestre, opciones, grupo, onHecho, onError }) {
  const [enviando, setEnviando] = useState(false);

  const elegir = (campos) => {
    setEnviando(true);
    api.empezar(trimestre, campos).then(onHecho).catch(onError).finally(() => setEnviando(false));
  };

  const vacio = !opciones.anterior && opciones.plantillas.length === 0;

  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-indigo-100 p-2 rounded-xl">
            <Layers size={20} className="text-indigo-600" />
          </div>
          <div>
            <h2 className="text-lg font-black text-slate-800">Elige con que instrumentos calificas</h2>
            <p className="text-[11px] text-slate-400 font-medium">{grupo.nombre} · {TERM_LARGOS[trimestre]}</p>
          </div>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed mt-3">
          Un clic y ya puedes poner notas. Los porcentajes vienen repartidos entre los criterios de la
          programacion, y luego puedes quitar, anadir o cambiar lo que quieras.
        </p>
      </div>

      {vacio && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold px-4 py-3 rounded-xl">
          No hay ningun marco de evaluacion para {grupo.materia} en {grupo.curso}.
        </div>
      )}

      {opciones.anterior && (
        <div className="bg-white rounded-2xl border border-indigo-300 shadow-sm overflow-hidden">
          <div className="px-5 pt-5 pb-3 border-b border-slate-100 flex items-center gap-2">
            <span className="bg-indigo-100 text-indigo-700 text-[9px] font-black px-2 py-0.5 rounded-md">RECOMENDADO</span>
            <h3 className="text-sm font-bold text-slate-700">
              Lo mismo que en la {TERM_LARGOS[opciones.anterior.trimestre]}
            </h3>
          </div>
          <div className="p-4 space-y-3">
            <Resumen filas={opciones.anterior.resumen} />
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] text-slate-400">Mismos instrumentos y mismos porcentajes, sin notas.</p>
              <button
                disabled={enviando}
                onClick={() => elegir({ copiar_de: opciones.anterior.id })}
                className="bg-indigo-600 text-white px-4 py-2 rounded-xl hover:bg-indigo-700 transition-all flex items-center gap-1.5 text-xs font-bold disabled:opacity-50"
              >
                <Play size={12} /> Seguir con estos
              </button>
            </div>
          </div>
        </div>
      )}

      {opciones.plantillas.map((p) => (
        <div
          key={p.clave}
          className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${p.recomendada ? 'border-indigo-300' : 'border-slate-200'}`}
        >
          <div className="px-5 pt-5 pb-3 border-b border-slate-100 flex items-center gap-2">
            {p.recomendada && (
              <span className="bg-indigo-100 text-indigo-700 text-[9px] font-black px-2 py-0.5 rounded-md">RECOMENDADA</span>
            )}
            <h3 className="text-sm font-bold text-slate-700">Plantilla de {p.nombre}</h3>
          </div>
          <div className="p-4 space-y-3">
            <Resumen filas={p.resumen} />
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] text-slate-400">Se califica con letra: A, B, C o D.</p>
              <button
                disabled={enviando}
                onClick={() => elegir({ plantilla: p.clave })}
                className={`px-4 py-2 rounded-xl transition-all flex items-center gap-1.5 text-xs font-bold disabled:opacity-50 ${
                  p.recomendada
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                    : 'bg-slate-900 text-white hover:bg-slate-800'
                }`}
              >
                <Play size={12} /> Empezar con esta
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
