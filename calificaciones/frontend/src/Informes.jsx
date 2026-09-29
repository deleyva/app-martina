// El informe de un alumno, para leer o imprimir. Es el de `notas`.

import { BookOpen, Printer } from 'lucide-react';
import {
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip,
} from 'recharts';
import {
  TERMS, TERM_LABELS, TERM_LARGOS, estiloCualitativa, estiloDeNota, notaDe, numero,
} from './estilos.js';

export default function Informes({ datos, alumno, trimestre, modo, onElegir }) {
  const bloque = datos.trimestres[trimestre];
  const suyo = alumno.trimestres[trimestre];
  const nota = notaDe(suyo, modo);
  const q = estiloCualitativa(nota.cualitativa);
  const score = numero(nota.exacta) ?? 0;

  const competencias = bloque.competencias.map((ce) => ({
    name: ce.codigo,
    texto: suyo.competencias[ce.codigo] || '',
    display: numero(suyo.competencias[ce.codigo]) ?? 0,
    peso: ce.peso,
  }));

  return (
    <div className="space-y-4 max-w-5xl mx-auto">
      {/* Controls */}
      <div className="flex justify-between items-center print:hidden bg-white p-2.5 rounded-2xl border border-slate-200 shadow-sm">
        <select
          className="bg-slate-50 border border-slate-200 text-xs text-slate-700 font-bold px-3 py-1.5 rounded-xl outline-none"
          value={alumno.id}
          onChange={(e) => onElegir(parseInt(e.target.value, 10))}
        >
          {datos.alumnos.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
        </select>
        <button
          onClick={() => window.print()}
          className="bg-slate-900 text-white px-3 py-1.5 rounded-xl hover:bg-slate-800 transition-all flex items-center gap-1.5 text-xs font-bold"
        >
          <Printer size={12} /> Imprimir
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 print:block">
        {/* Left panel — student card */}
        <div className="lg:col-span-4 space-y-4 print:mb-8">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm print:shadow-none">
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center text-white text-2xl font-black mb-3 shadow-lg shadow-indigo-100">
                {alumno.nombre.charAt(0)}
              </div>
              <h2 className="text-xl font-black text-slate-800 mb-0.5">{alumno.nombre}</h2>
              <p className="text-slate-400 text-[9px] font-black uppercase tracking-widest mb-4">
                {datos.grupo.nombre} / {TERM_LARGOS[trimestre]} / {datos.grupo.materia}
              </p>

              <div className="w-full grid grid-cols-2 gap-2 mb-6">
                <div className="bg-indigo-50 p-3 rounded-2xl border border-indigo-100">
                  <div className="text-[9px] font-black text-indigo-400 uppercase mb-0.5">Nota Final</div>
                  <div className="text-2xl font-black text-indigo-600">{nota.texto || '—'}</div>
                </div>
                <div className="bg-slate-50 p-3 rounded-2xl border border-slate-100">
                  <div className="text-[9px] font-black text-slate-400 uppercase mb-0.5">Cualitativa</div>
                  <div className={`text-lg font-black ${q.color}`}>{q.full}</div>
                </div>
              </div>

              {/* Detailed grades */}
              <div className="w-full pt-4 border-t border-slate-100">
                <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest text-left mb-3">
                  Registro Detallado
                </h4>
                <div className="space-y-1">
                  {bloque.columnas.map((columna) => (
                    <div key={columna.prueba} className="flex justify-between items-center text-[11px] py-1 border-b border-slate-50 last:border-0">
                      <span className="text-slate-500">{columna.nombre}</span>
                      <span className="font-bold text-slate-800">{suyo.notas[columna.prueba]?.etiqueta || '0'}</span>
                    </div>
                  ))}
                  {bloque.columnas.length === 0 && (
                    <div className="text-slate-300 text-[10px]">Sin instrumentos en esta evaluacion</div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Multi-term comparison */}
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm print:shadow-none">
            <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">
              Progresion por Evaluacion
            </h4>
            <div className="space-y-1.5">
              {TERMS.map((term) => {
                const deEse = alumno.trimestres[term];
                const n = notaDe(deEse, modo);
                const tq = estiloCualitativa(n.cualitativa);
                return (
                  <div key={term} className={`flex justify-between items-center text-[11px] py-1.5 px-2 rounded-lg ${trimestre === term ? 'bg-indigo-50' : ''}`}>
                    <span className={`font-bold ${trimestre === term ? 'text-indigo-600' : 'text-slate-500'}`}>
                      {TERM_LABELS[term]}
                    </span>
                    {deEse.con_datos ? (
                      <span className={`px-2 py-0.5 rounded font-black text-[10px] ${tq.color} ${tq.bg}`}>
                        {n.texto} ({tq.label})
                      </span>
                    ) : (
                      <span className="text-slate-300 text-[10px]">Sin datos</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right panel — competencies + observations */}
        <div className="lg:col-span-8 space-y-4 print:block">
          {/* Radar chart */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm print:shadow-none">
            <h3 className="text-sm font-black mb-4 flex items-center gap-2 text-slate-800">
              <BookOpen className="text-indigo-600" size={16} />
              DIAGNOSTICO COMPETENCIAL (LOMLOE)
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={competencias}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 9, fontWeight: 800 }} />
                  <PolarRadiusAxis domain={[0, 10]} axisLine={false} tick={false} />
                  <Radar name="Logro" dataKey="display" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.25} strokeWidth={2.5} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Competency detail table */}
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
              {competencias.map((ce) => {
                const cq = estiloDeNota(ce.texto === '' ? null : ce.display);
                return (
                  <div key={ce.name} className={`p-2.5 rounded-xl border ${cq.bg} ${cq.border}`}>
                    <div className="text-[9px] font-black text-slate-500 uppercase">{ce.name}</div>
                    <div className={`text-lg font-black ${cq.color}`}>{ce.texto || '—'}</div>
                    <div className="text-[9px] font-bold text-slate-400">{ce.peso}% peso</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Observations */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm print:border-slate-300">
            <h3 className="text-sm font-black mb-3 text-slate-800">OBSERVACIONES FORMATIVAS</h3>
            <p className="text-slate-500 text-sm leading-relaxed mb-4">
              El desempeno de <strong>{alumno.nombre}</strong> en el area de {datos.grupo.materia} durante
              la {TERM_LARGOS[trimestre].toLowerCase()} se situa
              en un nivel <strong className={q.color}>{q.full} ({q.label})</strong> con una puntuacion
              de <strong>{nota.texto || '0.0'}</strong> sobre 10.
              {score < 5
                ? ' El alumno/a presenta dificultades que requieren atencion inmediata para completar las tareas y pruebas no calificadas.'
                : score >= 9
                  ? ' Demuestra un dominio excelente de las competencias musicales evaluadas, destacando en todas las areas.'
                  : ' Muestra un progreso adecuado, integrando los conocimientos teoricos con la practica instrumental y el analisis auditivo.'}
            </p>
            {suyo.manual && (
              <p className="text-slate-600 text-sm italic border-l-2 border-indigo-200 pl-3 mb-4">
                Calificacion puesta por el profesor: <strong>{estiloCualitativa(suyo.manual).full}</strong>
                {suyo.motivo && ` — ${suyo.motivo}`}
              </p>
            )}
            <div className="flex gap-2 print:hidden">
              <span className="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full text-[9px] font-black border border-indigo-100 uppercase">
                LOMLOE Aragon
              </span>
              <span className="px-2 py-0.5 bg-slate-50 text-slate-600 rounded-full text-[9px] font-black border border-slate-100 uppercase">
                {datos.grupo.marco || datos.grupo.materia}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
