// Información sobre la evaluación. La página de `notas`, escrita a partir del
// plan real de cada evaluación en vez de a mano.

import { useState } from 'react';
import { Download, HelpCircle, Keyboard, Settings } from 'lucide-react';
import { rutaExportar, rutaPlan } from './api.js';
import { CLAVE_ENTRADA } from './Registro.jsx';
import { TERMS, TERM_LARGOS } from './estilos.js';

const COLORES = ['indigo', 'amber', 'emerald', 'rose'];
const colorMap = {
  indigo: { bg: 'bg-indigo-50', border: 'border-indigo-200', badge: 'bg-indigo-600', text: 'text-indigo-700', light: 'text-indigo-500' },
  amber: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-500', text: 'text-amber-700', light: 'text-amber-500' },
  emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-600', text: 'text-emerald-700', light: 'text-emerald-500' },
  rose: { bg: 'bg-rose-50', border: 'border-rose-200', badge: 'bg-rose-500', text: 'text-rose-700', light: 'text-rose-500' },
};
const ETIQUETA_TRIMESTRE = {
  1: 'bg-amber-100 text-amber-700',
  2: 'bg-blue-100 text-blue-700',
  3: 'bg-emerald-100 text-emerald-700',
};

function CriteriaCard({ item, color }) {
  const c = colorMap[color];
  return (
    <div className={`${c.bg} border ${c.border} rounded-xl p-4 space-y-2`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`${c.badge} text-white text-[9px] font-black px-2 py-0.5 rounded-md uppercase tracking-wider`}>
            {item.codigo}
          </span>
          <span className={`text-sm font-bold ${c.text}`}>
            {item.criterios.map((k) => k.codigo).join(' · ')}
          </span>
        </div>
        <span className={`text-lg font-black ${c.light}`}>{item.peso}%</span>
      </div>
      <div className="text-[11px] text-slate-600 leading-relaxed">
        <span className="font-semibold text-slate-500 uppercase text-[9px] tracking-wider">Instrumentos: </span>
        {item.instrumentos.map((i) => i.nombre).join(' + ') || 'ninguno'}
      </div>
    </div>
  );
}

function leerEntrada() {
  try { return window.localStorage.getItem(CLAVE_ENTRADA) || 'auto'; } catch { return 'auto'; }
}

export default function Info({ datos }) {
  const [entrada, setEntrada] = useState(leerEntrada);

  const elegirEntrada = (valor) => {
    try { window.localStorage.setItem(CLAVE_ENTRADA, valor); } catch { /* sin almacenamiento */ }
    setEntrada(valor);
    window.dispatchEvent(new Event('calificaciones:entrada'));
  };

  const conPlan = TERMS.filter((t) => datos.trimestres[t].plan);
  // Las escalas distintas que se usan, para no repetir la misma tarjeta nueve veces.
  const escalas = new Map();
  conPlan.forEach((t) => datos.trimestres[t].instrumentos.forEach((i) => {
    if (i.tipo !== 'opciones') return;
    const clave = i.opciones.map((o) => `${o.etiqueta}=${o.valor}`).join('|');
    if (!escalas.has(clave)) escalas.set(clave, { opciones: i.opciones, instrumentos: new Set() });
    escalas.get(clave).instrumentos.add(i.nombre);
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-indigo-100 p-2 rounded-xl">
            <HelpCircle size={20} className="text-indigo-600" />
          </div>
          <div>
            <h2 className="text-lg font-black text-slate-800">Información sobre la evaluación</h2>
            <p className="text-[11px] text-slate-400 font-medium">
              Criterios LOMLOE · {datos.grupo.marco || `${datos.grupo.materia} · ${datos.grupo.curso}`}
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed mt-3">
          La nota de cada evaluación se calcula mediante <strong>criterios de evaluación competenciales (LOMLOE)</strong>.
          Cada instrumento reparte su porcentaje entre uno o más criterios, y cada criterio tiene el peso que le da
          la programación. La nota final del curso pondera las evaluaciones
          {' '}({TERMS.map((t) => `${TERM_LARGOS[t]}: ${datos.pesos_trimestre[t]}`).join(' · ')}) y solo cuenta
          las que tienen alguna nota.
        </p>
      </div>

      {/* Una tarjeta por evaluación con plan */}
      {conPlan.map((t) => {
        const bloque = datos.trimestres[t];
        return (
          <div key={t} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 pt-5 pb-3 border-b border-slate-100 flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <span className={`${ETIQUETA_TRIMESTRE[t]} text-[9px] font-black px-2 py-0.5 rounded-md uppercase`}>
                  {t}ª EVAL
                </span>
                <h3 className="text-sm font-bold text-slate-700">{bloque.plan.nombre}</h3>
                {!bloque.plan.cuadra && (
                  <span className="bg-red-100 text-red-700 text-[9px] font-black px-2 py-0.5 rounded-md">
                    SUMA {bloque.plan.total}% · NO CUADRA
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <a
                  href={rutaExportar(t, 'criterio')}
                  className="bg-white border border-slate-200 text-slate-600 px-3 py-1.5 rounded-xl hover:border-indigo-300 hover:text-indigo-600 transition-all flex items-center gap-1.5 text-[11px] font-bold"
                >
                  <Download size={12} /> CSV por criterio
                </a>
                <a
                  href={rutaExportar(t, 'instrumento')}
                  className="bg-white border border-slate-200 text-slate-600 px-3 py-1.5 rounded-xl hover:border-indigo-300 hover:text-indigo-600 transition-all flex items-center gap-1.5 text-[11px] font-bold"
                >
                  <Download size={12} /> CSV por instrumento
                </a>
                <a
                  href={rutaPlan(bloque.plan.id)}
                  className="bg-slate-900 text-white px-3 py-1.5 rounded-xl hover:bg-slate-800 transition-all flex items-center gap-1.5 text-[11px] font-bold"
                >
                  <Settings size={12} /> Instrumentos y pesos
                </a>
              </div>
            </div>
            <div className="p-4 grid gap-3 sm:grid-cols-2">
              {bloque.competencias.map((item, i) => (
                <CriteriaCard key={item.codigo} item={item} color={COLORES[i % COLORES.length]} />
              ))}
            </div>
            <div className="px-4 pb-4 grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
              {bloque.instrumentos.map((i) => (
                <div key={i.id} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-center">
                  <div className="text-[9px] text-slate-400 font-bold truncate" title={i.nombre}>{i.nombre}</div>
                  <div className="text-lg font-black text-slate-700">{i.peso}%</div>
                </div>
              ))}
            </div>
            <p className="px-5 pb-4 text-[11px] text-slate-500">
              {bloque.plan.hueco_cuenta_cero
                ? 'Una celda vacía cuenta como 0.'
                : 'Una celda vacía no cuenta: la media se hace con el resto.'}
              {bloque.plan.compartido_con > 0 && ` Este plan lo comparten ${bloque.plan.compartido_con + 1} grupos: las columnas y los pesos son los mismos para todos.`}
            </p>
          </div>
        );
      })}

      {conPlan.length === 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 text-center text-slate-400 text-sm">
          Este grupo todavía no tiene instrumentos en ninguna evaluación. Elígelos en Registro.
        </div>
      )}

      {/* Escala cualitativa */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
        <h3 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-3">Escala cualitativa</h3>
        <div className="flex flex-wrap gap-2">
          {[
            { label: 'IN', full: 'Insuficiente', range: '0 – 4.9', bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-600' },
            { label: 'SU', full: 'Suficiente', range: '5 – 5.9', bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-600' },
            { label: 'BI', full: 'Bien', range: '6 – 6.9', bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-600' },
            { label: 'NT', full: 'Notable', range: '7 – 8.9', bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-600' },
            { label: 'SB', full: 'Sobresaliente', range: '9 – 10', bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-600' },
          ].map((q) => (
            <div key={q.label} className={`${q.bg} border ${q.border} rounded-xl px-3 py-2 flex items-center gap-2`}>
              <span className={`font-black text-sm ${q.text}`}>{q.label}</span>
              <div className="text-[10px] text-slate-500 leading-tight">
                <div className="font-semibold">{q.full}</div>
                <div>{q.range}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Las escalas de las celdas */}
      {[...escalas.values()].map((escala) => (
        <div key={escala.opciones.map((o) => o.etiqueta).join()} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-3">
            Escala de las celdas — {escala.opciones.map((o) => o.etiqueta).join(' · ')}
          </h3>
          <p className="text-[11px] text-slate-500 mb-3">
            Cada celda se califica con una de estas opciones, que entra en el cálculo con su nota sobre 10.
            {' '}Se usa en: {[...escala.instrumentos].join(', ')}.
          </p>
          <div className="flex flex-wrap gap-2">
            {escala.opciones.map((o) => (
              <div key={o.etiqueta} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-center min-w-[70px]">
                <div className="text-lg font-black text-slate-700">{o.etiqueta}</div>
                <div className="text-[10px] text-indigo-600 font-bold mt-0.5">→ {o.valor}</div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Cómo se escribe */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
        <h3 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Keyboard size={12} /> Cómo se escribe en este dispositivo
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {[
            { clave: 'auto', nombre: 'Automático' },
            { clave: 'teclado', nombre: 'Siempre teclado' },
            { clave: 'selector', nombre: 'Siempre desplegable' },
          ].map(({ clave, nombre }) => (
            <button
              key={clave}
              onClick={() => elegirEntrada(clave)}
              className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition-colors ${
                entrada === clave
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white border border-slate-200 text-slate-500 hover:border-indigo-300 hover:text-indigo-600'
              }`}
            >
              {nombre}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-slate-500 mt-3">
          En automático, con ratón y teclado se teclea la letra y Enter baja al siguiente alumno; en una pantalla
          táctil cada celda es un desplegable. Se recuerda en este dispositivo.
        </p>
      </div>
    </div>
  );
}
