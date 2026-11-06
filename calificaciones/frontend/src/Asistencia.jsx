// La pestaña ASISTENCIA (fase 102): lo que se marcó al pasar lista, por alumno,
// en el trimestre de la barra. Es del profesor y lo enseña todo, también las
// notas que no van al informe. Lo que va al informe se elige aquí o en clase.

import { Fragment, useState } from 'react';
import { ChevronDown, ChevronRight, ClipboardList, FileText } from 'lucide-react';
import { TERM_LARGOS } from './estilos.js';

// «2026-10-07» → «07/10». Sin `Date`, que con la zona horaria puede correr un día.
export function fechaCorta(iso) {
  const [, mes, dia] = iso.split('-');
  return `${dia}/${mes}`;
}

const ESTADOS = {
  falta: { texto: 'Falta', clase: 'bg-red-50 text-red-600 border-red-200' },
  retraso: { texto: 'Retraso', clase: 'bg-amber-50 text-amber-700 border-amber-200' },
};

function Cifra({ valor, color }) {
  return (
    <td className={`px-3 py-2 text-center text-sm font-black ${valor ? color : 'text-slate-200'}`}>
      {valor || '0'}
    </td>
  );
}

function Marca({ marca, materiales, onNotaEnInforme, guardando }) {
  const estado = ESTADOS[marca.estado];
  return (
    <li className="flex flex-col sm:flex-row sm:items-start gap-2 py-2 border-b border-slate-100 last:border-0">
      <div className="flex items-center gap-2 sm:w-56 flex-shrink-0">
        <span className="text-xs font-black text-slate-700 w-12">{fechaCorta(marca.fecha)}</span>
        <span className="text-[11px] text-slate-400 truncate">{marca.titulo}</span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 flex-1 min-w-0">
        {estado && (
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-black border ${estado.clase}`}>
            {estado.texto}{marca.hora ? ` ${marca.hora}` : ''}
          </span>
        )}
        {marca.sin_material.map((clave) => (
          <span key={clave} className="px-2 py-0.5 rounded-full text-[10px] font-black border bg-rose-50 text-rose-700 border-rose-200">
            Sin {(materiales[clave] || clave).toLowerCase()}
          </span>
        ))}
        {marca.nota && (
          <span className="text-xs text-slate-600 basis-full sm:basis-auto">{marca.nota}</span>
        )}
      </div>
      {marca.nota && (
        <label className={`flex items-center gap-1.5 text-[11px] font-bold flex-shrink-0 cursor-pointer ${marca.nota_en_informe ? 'text-indigo-600' : 'text-slate-400'}`}>
          <input
            type="checkbox"
            className="w-4 h-4 accent-indigo-600"
            checked={marca.nota_en_informe}
            disabled={guardando}
            onChange={(e) => onNotaEnInforme(marca.sesion, e.target.checked)}
          />
          En el informe
        </label>
      )}
    </li>
  );
}

export default function Asistencia({ datos, asistencia, trimestre, onNotaEnInforme, onVerInforme, guardando }) {
  const [abierto, setAbierto] = useState(null);
  const [soloConAlgo, setSoloConAlgo] = useState(false);

  if (!asistencia) {
    return <div className="text-center text-xs text-slate-400 py-12">Cargando la asistencia…</div>;
  }

  const materiales = Object.fromEntries(asistencia.materiales.map((m) => [m.clave, m.nombre]));
  const clases = asistencia.clases[trimestre] || 0;
  const filas = datos.alumnos
    .map((a) => ({ alumno: a, bloque: asistencia.alumnos[String(a.id)]?.[trimestre] }))
    .filter((f) => f.bloque && (!soloConAlgo || f.bloque.marcas.length));

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-slate-800 flex items-center gap-2">
            <ClipboardList size={16} className="text-indigo-600" />
            ASISTENCIA · {TERM_LARGOS[trimestre].toUpperCase()}
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {clases === 1 ? '1 clase' : `${clases} clases`} con lista pasada. Las notas solo salen en el informe si las marcas.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs font-bold text-slate-500 cursor-pointer">
          <input type="checkbox" className="w-4 h-4 accent-indigo-600" checked={soloConAlgo} onChange={(e) => setSoloConAlgo(e.target.checked)} />
          Solo quien tiene algo marcado
        </label>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr className="border-b border-slate-100 text-[9px] font-black text-slate-400 uppercase tracking-widest">
              <th className="px-4 py-3 text-left">Alumno</th>
              <th className="px-3 py-3">Faltas</th>
              <th className="px-3 py-3">Retrasos</th>
              {asistencia.materiales.map((m) => (
                <th key={m.clave} className="px-3 py-3">Sin {m.nombre.toLowerCase()}</th>
              ))}
              <th className="px-3 py-3">Notas</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {filas.map(({ alumno, bloque }) => {
              const notas = bloque.marcas.filter((m) => m.nota);
              const enInforme = notas.filter((m) => m.nota_en_informe).length;
              const estaAbierto = abierto === alumno.id;
              const conAlgo = bloque.marcas.length > 0;
              return (
                <Fragment key={alumno.id}>
                  <tr
                    className={`border-b border-slate-50 ${conAlgo ? 'cursor-pointer hover:bg-slate-50' : ''} ${estaAbierto ? 'bg-indigo-50/40' : ''}`}
                    onClick={() => conAlgo && setAbierto(estaAbierto ? null : alumno.id)}
                  >
                    <td className="px-4 py-2 text-sm font-bold text-slate-700">
                      <span className="inline-flex items-center gap-1.5">
                        {conAlgo
                          ? (estaAbierto ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />)
                          : <span className="w-[14px]" />}
                        {alumno.nombre}
                      </span>
                    </td>
                    <Cifra valor={bloque.faltas} color="text-red-600" />
                    <Cifra valor={bloque.retrasos} color="text-amber-600" />
                    {asistencia.materiales.map((m) => (
                      <Cifra key={m.clave} valor={bloque.sin_material[m.clave]} color="text-rose-600" />
                    ))}
                    <td className="px-3 py-2 text-center text-xs font-bold text-slate-500">
                      {notas.length ? `${notas.length}${enInforme ? ` · ${enInforme} en informe` : ''}` : <span className="text-slate-200">—</span>}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        title="Ver su informe"
                        className="text-slate-300 hover:text-indigo-600 p-1"
                        onClick={(e) => { e.stopPropagation(); onVerInforme(alumno.id); }}
                      >
                        <FileText size={14} />
                      </button>
                    </td>
                  </tr>
                  {estaAbierto && (
                    <tr className="border-b border-slate-100 bg-indigo-50/20">
                      <td colSpan={5 + asistencia.materiales.length} className="px-6 py-2">
                        <ul>
                          {bloque.marcas.map((marca) => (
                            <Marca
                              key={marca.sesion}
                              marca={marca}
                              materiales={materiales}
                              guardando={guardando}
                              onNotaEnInforme={(sesion, valor) => onNotaEnInforme(sesion, alumno.id, valor)}
                            />
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {filas.length === 0 && (
              <tr>
                <td colSpan={5 + asistencia.materiales.length} className="px-4 py-8 text-center text-xs text-slate-400">
                  {soloConAlgo ? 'Nadie tiene nada marcado en esta evaluación.' : 'No hay alumnado matriculado.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
