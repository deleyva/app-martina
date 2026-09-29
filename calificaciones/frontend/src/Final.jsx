// Las notas finales de curso. Es la pestaña de `notas`, sin las notas de otras
// asignaturas (decisión de Jesús, 2026-09-29).
//
// La nota de curso oficial viene calculada del servidor con los pesos de la
// programación. Si se mueven los pesos aquí, la columna pasa a ser un «y si…»
// calculado en pantalla, y se avisa: no se guarda en ningún sitio.

import { Fragment, useMemo, useState } from 'react';
import { Award } from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { rutaGrupo } from './api.js';
import {
  QUALITATIVE_OPTIONS, QUALITATIVE_STYLES, TERMS, TERM_LABELS, estiloCualitativa, estiloDeNota, notaDe, numero,
} from './estilos.js';
import { finalConPesos, mismosPesos, normalizarPesos } from './queSiPasa.js';

export default function Final({ datos, modo, trimestre, onManual }) {
  const oficiales = useMemo(() => ({
    1: numero(datos.pesos_trimestre[1]) ?? 1,
    2: numero(datos.pesos_trimestre[2]) ?? 1,
    3: numero(datos.pesos_trimestre[3]) ?? 1,
  }), [datos.pesos_trimestre]);
  const [pesos, setPesos] = useState(oficiales);
  const [modoLocal, setModoLocal] = useState(modo || 'lomloe');
  const normalizados = useMemo(() => normalizarPesos(pesos), [pesos]);
  const deLaProgramacion = mismosPesos(pesos, oficiales);

  const ordenados = useMemo(() => datos.alumnos.map((a) => {
    const calcular = (m) => {
      if (deLaProgramacion) {
        const texto = m === 'simple' ? a.curso.simple : a.curso.nota;
        return { texto, valor: numero(texto), cualitativa: m === 'simple' ? a.curso.simple_cualitativa : a.curso.cualitativa };
      }
      const notas = {};
      TERMS.forEach((t) => {
        const suyo = a.trimestres[t];
        notas[t] = suyo.con_datos ? numero(notaDe(suyo, m).exacta) : null;
      });
      const valor = finalConPesos(notas, pesos);
      return { texto: valor === null ? '' : valor.toFixed(1), valor, cualitativa: estiloDeNota(valor).label };
    };
    const legal = calcular('lomloe');
    const simple = calcular('simple');
    const final = modoLocal === 'simple' ? simple : legal;
    const delta = legal.valor === null || simple.valor === null
      ? 0
      : parseFloat((legal.valor - simple.valor).toFixed(1));
    return { ...a, final, delta };
  }).sort((x, y) => (y.final.valor ?? -1) - (x.final.valor ?? -1)), [datos.alumnos, pesos, modoLocal, deLaProgramacion]);

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      {/* Toolbar: group filter + viewmode toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {datos.grupos.map((g) => (
            <a
              key={g.id}
              href={`${rutaGrupo(g.id, trimestre)}#final`}
              className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition-colors ${
                g.id === datos.grupo.id
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white border border-slate-200 text-slate-500 hover:border-indigo-300 hover:text-indigo-600'
              }`}
            >
              {g.nombre}
            </a>
          ))}
        </div>
        <div className="flex rounded-lg overflow-hidden border border-slate-200 text-[11px] font-bold">
          {['simple', 'lomloe'].map((m) => (
            <button
              key={m}
              onClick={() => setModoLocal(m)}
              className={`px-3 py-1.5 transition-colors ${
                modoLocal === m
                  ? 'bg-slate-800 text-white'
                  : 'bg-white text-slate-500 hover:bg-slate-50'
              }`}
            >
              {m === 'simple' ? 'Media Simple' : 'LOMLOE'}
            </button>
          ))}
        </div>
      </div>

      {/* Weight config */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
        <h3 className="text-sm font-black text-slate-800 mb-3 flex items-center gap-2">
          <Award size={16} className="text-indigo-600" />
          Notas Finales  Ponderacion por Evaluacion
        </h3>
        <div className="flex flex-wrap gap-4 mb-2">
          {TERMS.map((term) => (
            <div key={term} className="flex items-center gap-2">
              <label className="text-[10px] font-black text-slate-400 uppercase">{TERM_LABELS[term]}</label>
              <input
                type="number"
                min="0"
                max="100"
                step="5"
                className="w-14 bg-slate-50 border border-slate-200 rounded-lg text-center text-slate-700 py-1 text-xs font-bold outline-none focus:ring-1 focus:ring-indigo-500"
                value={pesos[term]}
                onChange={(e) => setPesos((prev) => ({ ...prev, [term]: parseFloat(e.target.value) || 0 }))}
              />
              <span className="text-[10px] text-slate-400">
                ({(normalizados[term] * 100).toFixed(0)}%)
              </span>
            </div>
          ))}
          {!deLaProgramacion && (
            <button
              onClick={() => setPesos(oficiales)}
              className="px-3 py-1 rounded-lg text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors"
            >
              Volver a los de la programacion
            </button>
          )}
        </div>
        <p className="text-[10px] text-slate-400 italic">
          {deLaProgramacion
            ? 'Son los pesos de la programacion. Se normalizan automaticamente. Solo se cuentan las evaluaciones con datos.'
            : 'Estas probando otros pesos: la nota final de esta pantalla es una simulacion y no se guarda.'}
        </p>
      </div>

      {/* Final grades table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-auto max-h-[70vh]">
          <table className="w-full text-left text-[11px]">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-20">
              <tr>
                <th className="px-4 py-3 font-bold text-slate-400 uppercase">#</th>
                <th className="px-4 py-3 font-bold text-slate-400 uppercase">Estudiante</th>
                {TERMS.map((t) => (
                  <th key={t} className="px-3 py-3 text-center font-bold text-slate-400 uppercase" colSpan={2}>
                    {TERM_LABELS[t]}
                  </th>
                ))}
                <th className="px-4 py-3 text-center font-black text-indigo-600 bg-indigo-50/30 uppercase">Final</th>
                <th className="px-2 py-3 text-center font-bold text-slate-400 uppercase text-[9px]">Δ</th>
                <th className="px-3 py-3 text-center font-bold text-slate-400 uppercase">Calif.</th>
                <th className="px-3 py-3 text-center font-bold text-amber-600 bg-amber-50/30 uppercase">Nota Final</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ordenados.map((s, i) => {
                const fq = estiloCualitativa(s.final.cualitativa);
                return (
                  <tr key={s.id} className="hover:bg-indigo-50/10 transition-colors">
                    <td className="px-4 py-2.5 text-slate-300 font-bold">{i + 1}</td>
                    <td className="px-4 py-2.5">
                      <span className="font-bold text-slate-700">{s.nombre}</span>
                      <div className="text-[9px] text-slate-400 font-bold uppercase">{datos.grupo.nombre}</div>
                    </td>
                    {TERMS.map((term) => {
                      const suyo = s.trimestres[term];
                      const n = notaDe(suyo, modoLocal);
                      const tq = estiloCualitativa(n.cualitativa);
                      return (
                        <Fragment key={term}>
                          <td className="px-3 py-2.5 text-center">
                            {suyo.con_datos ? (
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tq.color} ${tq.bg}`}>
                                {n.texto}
                              </span>
                            ) : (
                              <span className="text-slate-300 text-[10px]">-</span>
                            )}
                          </td>
                          <td className="px-1 py-2.5 text-center">
                            <select
                              className={`w-14 text-[10px] font-bold border rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-amber-400 cursor-pointer ${suyo.manual ? QUALITATIVE_STYLES[suyo.manual] : 'text-slate-300 bg-slate-50 border-slate-200'}`}
                              value={suyo.manual}
                              onChange={(e) => onManual(s.id, term, e.target.value)}
                            >
                              {QUALITATIVE_OPTIONS.map((opt) => (
                                <option key={opt} value={opt}>{opt || '—'}</option>
                              ))}
                            </select>
                          </td>
                        </Fragment>
                      );
                    })}
                    <td className="px-4 py-2.5 text-center bg-indigo-50/5">
                      <div className="flex flex-col items-center gap-0.5">
                        <span className={`px-2 py-1 rounded-lg font-black ${fq.color} ${fq.bg} border ${fq.border} inline-block min-w-[3rem] text-center`}>
                          {s.final.texto || '—'}
                        </span>
                        <span className="text-[8px] text-slate-300 font-bold">
                          {modoLocal === 'simple' ? 'Simple' : 'LOMLOE'}{!deLaProgramacion && ' · simulada'}
                        </span>
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      {s.delta !== 0 && (
                        <span className={`text-[10px] font-black ${s.delta > 0 ? 'text-green-500' : 'text-red-400'}`}>
                          {s.delta > 0 ? '+' : ''}{s.delta.toFixed(1)}
                        </span>
                      )}
                      {s.delta === 0 && <span className="text-[10px] text-slate-200">—</span>}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <span className={`text-xs font-black ${fq.color}`}>{fq.label}</span>
                    </td>
                    <td className="px-1 py-2.5 text-center">
                      <select
                        className={`w-14 text-[10px] font-bold border rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-amber-400 cursor-pointer ${s.curso.manual ? QUALITATIVE_STYLES[s.curso.manual] : 'text-slate-300 bg-slate-50 border-slate-200'}`}
                        value={s.curso.manual}
                        onChange={(e) => onManual(s.id, 'curso', e.target.value)}
                      >
                        {QUALITATIVE_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>{opt || '—'}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Class summary chart */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
        <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-3">
          Distribucion de Calificaciones Finales
        </h4>
        <div className="h-48">
          <Distribucion alumnos={ordenados} />
        </div>
      </div>
    </div>
  );
}

function Distribucion({ alumnos }) {
  const data = useMemo(() => {
    const buckets = { IN: 0, SU: 0, BI: 0, NT: 0, SB: 0 };
    alumnos.forEach((s) => {
      if (s.final.cualitativa in buckets) buckets[s.final.cualitativa] += 1;
    });
    return [
      { name: 'IN', count: buckets.IN, fill: '#dc2626' },
      { name: 'SU', count: buckets.SU, fill: '#ea580c' },
      { name: 'BI', count: buckets.BI, fill: '#ca8a04' },
      { name: 'NT', count: buckets.NT, fill: '#2563eb' },
      { name: 'SB', count: buckets.SB, fill: '#16a34a' },
    ];
  }, [alumnos]);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="name" tick={{ fontSize: 11, fontWeight: 800 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
        <Tooltip />
        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
