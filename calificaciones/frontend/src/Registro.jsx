// El Registro: la rejilla de `notas`. Una columna por prueba activa.

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronRight, EyeOff, Info, Plus, TrendingUp } from 'lucide-react';
import { api } from './api.js';
import Celda from './Celda.jsx';
import BotonEvidencia from './evidencias/BotonEvidencia.jsx';
import {
  QUALITATIVE_OPTIONS, QUALITATIVE_STYLES, TERM_LARGOS, estiloCualitativa, notaDe, numero,
} from './estilos.js';

// Teclado o desplegable. Se mira el puntero principal, no si la pantalla es
// táctil: un portátil con pantalla táctil sigue teniendo teclado. En Info se
// puede forzar una de las dos (un iPad con teclado, por ejemplo).
export const CLAVE_ENTRADA = 'calificaciones.entrada';

export function useTactil() {
  const consulta = useMemo(() => window.matchMedia('(pointer: coarse)'), []);
  const [grueso, setGrueso] = useState(consulta.matches);
  const [forzado, setForzado] = useState(() => {
    try { return window.localStorage.getItem(CLAVE_ENTRADA) || 'auto'; } catch { return 'auto'; }
  });
  useEffect(() => {
    const alCambiar = (e) => setGrueso(e.matches);
    const alGuardar = () => {
      try { setForzado(window.localStorage.getItem(CLAVE_ENTRADA) || 'auto'); } catch { /* sin almacenamiento */ }
    };
    consulta.addEventListener('change', alCambiar);
    window.addEventListener('calificaciones:entrada', alGuardar);
    return () => {
      consulta.removeEventListener('change', alCambiar);
      window.removeEventListener('calificaciones:entrada', alGuardar);
    };
  }, [consulta]);
  if (forzado === 'selector') return true;
  if (forzado === 'teclado') return false;
  return grueso;
}

export default function Registro({
  datos, trimestre, modo, onNota, onSalirDeCelda, onManual,
  onSubir, onBorrar, onComentar, evidenciasDe, onRecargar, onError,
}) {
  const bloque = datos.trimestres[trimestre];
  const tactil = useTactil();

  const notas = datos.alumnos.map((a) => numero(notaDe(a.trimestres[trimestre], modo).exacta) ?? 0);
  const promedio = notas.length ? (notas.reduce((a, b) => a + b, 0) / notas.length).toFixed(2) : '0.00';

  return (
    <div className="space-y-4 print:hidden">
      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-b-4 border-b-indigo-500">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Promedio</div>
          <div className="text-3xl font-black text-indigo-600">{promedio}</div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-b-4 border-b-green-500">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Aprobados</div>
          <div className="text-3xl font-black text-green-600">{notas.filter((n) => n >= 5).length}</div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-b-4 border-b-red-500">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Pendientes</div>
          <div className="text-3xl font-black text-red-600">{notas.filter((n) => n < 5).length}</div>
        </div>
      </div>

      {/* Weight info banner */}
      <Ponderacion bloque={bloque} trimestre={trimestre} />

      {/* Grade table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-auto max-h-[70vh]">
          <table className="w-full text-left text-[11px]">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-20">
              <tr>
                <th className="px-4 py-3 font-bold text-slate-400 uppercase sticky left-0 bg-slate-50 z-30">Estudiante</th>
                {bloque.columnas.map((columna) => (
                  <Cabecera
                    key={columna.prueba}
                    columna={columna}
                    instrumento={bloque.instrumentos.find((i) => i.id === columna.instrumento)}
                    onRecargar={onRecargar}
                    onError={onError}
                  />
                ))}
                <th className="px-4 py-3 text-right font-black text-indigo-600 bg-indigo-50/30">NOTA</th>
                <th className="px-3 py-3 text-center font-bold text-slate-400 uppercase">Obs.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {datos.alumnos.map((alumno, fila) => {
                const suyo = alumno.trimestres[trimestre];
                const nota = notaDe(suyo, modo);
                const q = estiloCualitativa(nota.cualitativa);
                return (
                  <tr key={alumno.id} className="hover:bg-indigo-50/10 transition-colors">
                    <td className="px-4 py-3 sticky left-0 bg-white z-10">
                      <div className="font-bold text-slate-700 text-[11px]">{alumno.nombre}</div>
                      <div className="text-[9px] text-slate-400 font-bold uppercase">{datos.grupo.nombre}</div>
                    </td>
                    {bloque.columnas.map((columna, col) => (
                      <td key={columna.prueba} className="px-1 py-3 text-center">
                        <div className="flex items-center justify-center gap-0.5">
                          <Celda
                            columna={columna}
                            celda={suyo.notas[columna.prueba]}
                            tactil={tactil}
                            col={col}
                            fila={fila}
                            onCambio={(valor, opciones) => onNota(alumno.id, columna.prueba, valor, opciones)}
                            onSalir={() => onSalirDeCelda(alumno.id)}
                          />
                          <BotonEvidencia
                            alumno={alumno.id}
                            prueba={columna.prueba}
                            items={evidenciasDe(alumno.id, columna.prueba)}
                            onUpload={onSubir}
                            onDelete={onBorrar}
                            onAddComment={onComentar}
                          />
                        </div>
                      </td>
                    ))}
                    <td className="px-4 py-3 text-right bg-indigo-50/5">
                      <span
                        className={`px-2 py-1 rounded-lg font-black ${q.color} ${q.bg} border ${q.border} inline-block w-12 text-center text-[11px]`}
                        title={suyo.huecos ? `${suyo.huecos} celda(s) sin nota` : 'Todas las celdas tienen nota'}
                      >
                        {nota.texto || '—'}
                      </span>
                    </td>
                    <td className="px-2 py-3 text-center border-l border-slate-200">
                      <select
                        className={`w-14 text-[10px] font-bold border rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-amber-400 cursor-pointer ${suyo.manual ? QUALITATIVE_STYLES[suyo.manual] : 'text-slate-300 bg-slate-50 border-slate-200'}`}
                        value={suyo.manual}
                        onChange={(e) => onManual(alumno.id, trimestre, e.target.value)}
                      >
                        {QUALITATIVE_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>{opt || '—'}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
              {datos.alumnos.length === 0 && (
                <tr>
                  <td colSpan={bloque.columnas.length + 3} className="text-center text-slate-400 text-sm py-12">
                    No hay alumnado matriculado en este grupo.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-slate-400 px-1 italic">
        <Info size={12} /> Los cambios se guardan automaticamente.
        {bloque.plan.hueco_cuenta_cero && ' Una celda vacia cuenta como 0.'}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// La cabecera de una columna, y sus pruebas
// ─────────────────────────────────────────────
function Cabecera({ columna, instrumento, onRecargar, onError }) {
  const [abierto, setAbierto] = useState(false);
  const [estilo, setEstilo] = useState({});
  const [nombre, setNombre] = useState(columna.nombre);
  const boton = useRef(null);
  const menu = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;
    const cerrar = (e) => {
      if (menu.current?.contains(e.target) || boton.current?.contains(e.target)) return;
      setAbierto(false);
    };
    document.addEventListener('mousedown', cerrar);
    return () => document.removeEventListener('mousedown', cerrar);
  }, [abierto]);

  const abrir = () => {
    const rect = boton.current.getBoundingClientRect();
    setEstilo({
      position: 'fixed',
      top: rect.bottom + 4,
      left: Math.max(8, Math.min(rect.left, window.innerWidth - 232)),
      zIndex: 9999,
    });
    setNombre(columna.nombre);
    setAbierto((a) => !a);
  };

  const hacer = (promesa) => promesa.then(() => { setAbierto(false); return onRecargar(); }).catch(onError);
  const activas = instrumento.pruebas.filter((p) => p.activa).length;
  const ocultas = instrumento.pruebas.filter((p) => !p.activa);

  return (
    <th className="px-1.5 py-3 text-center font-bold text-slate-400 uppercase whitespace-nowrap">
      <button
        ref={boton}
        onClick={abrir}
        className="uppercase font-bold hover:text-indigo-600 transition-colors"
        title={`${columna.nombre} · ${instrumento.nombre} cuenta un ${instrumento.peso} %`}
      >
        {columna.corto}
      </button>
      {abierto && createPortal(
        <div ref={menu} style={estilo} className="bg-white rounded-xl shadow-xl border border-slate-200 p-2 w-56 animate-in text-left normal-case">
          <div className="text-[9px] font-black text-slate-400 uppercase tracking-wider px-1 mb-1">
            {instrumento.nombre} · {instrumento.peso} %
          </div>
          <input
            className="w-full bg-slate-50 border border-slate-200 rounded-lg text-[11px] p-2 outline-none focus:ring-1 focus:ring-indigo-500"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && nombre.trim()) hacer(api.editarPrueba(columna.prueba, { nombre: nombre.trim() }));
            }}
          />
          <div className="flex justify-end mt-1">
            <button
              onClick={() => nombre.trim() && hacer(api.editarPrueba(columna.prueba, { nombre: nombre.trim() }))}
              className="px-2 py-1 text-[10px] font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded"
            >
              Cambiar nombre
            </button>
          </div>
          <div className="border-t border-slate-100 my-1" />
          <button
            onClick={() => hacer(api.crearPrueba(instrumento.id, ''))}
            className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Plus size={13} className="text-indigo-500" />
            Otra prueba de {instrumento.corto}
          </button>
          {activas > 1 && (
            <button
              onClick={() => hacer(api.editarPrueba(columna.prueba, { nombre: columna.nombre, activa: 'off' }))}
              className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <EyeOff size={13} className="text-slate-400" />
              Ocultar esta columna
            </button>
          )}
          {ocultas.map((p) => (
            <button
              key={p.id}
              onClick={() => hacer(api.editarPrueba(p.id, { nombre: p.nombre, activa: 'on' }))}
              className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-[11px] font-medium text-slate-500 hover:bg-slate-50 transition-colors"
            >
              <ChevronRight size={13} className="text-slate-300" />
              Volver a mostrar «{p.nombre}»
            </button>
          ))}
          {activas > 1 && (
            <p className="text-[9px] text-slate-400 px-2 pt-1 leading-snug">
              Con varias pruebas cuenta: {instrumento.agregacion_texto.toLowerCase()}.
            </p>
          )}
        </div>,
        document.body,
      )}
    </th>
  );
}

// ─────────────────────────────────────────────
// Term Weights Banner
// ─────────────────────────────────────────────
export function Ponderacion({ bloque, trimestre }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-left"
      >
        <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <TrendingUp size={12} />
          Ponderacion {TERM_LARGOS[trimestre]}
        </span>
        {expanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
      </button>
      {expanded && (
        <div className="px-4 pb-3 border-t border-slate-100">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
            {bloque.competencias.map((ce) => (
              <div key={ce.codigo} className="bg-slate-50 rounded-xl p-2.5">
                <div className="text-[9px] font-black text-slate-400 uppercase">{ce.codigo}</div>
                <div className="text-sm font-black text-indigo-600">{ce.peso}%</div>
                <div className="text-[9px] text-slate-400">
                  {ce.instrumentos.map((i) => i.corto).join(', ')}
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2 mt-2">
            {bloque.instrumentos.map((i) => (
              <div key={i.id} className="bg-slate-50 rounded-xl p-2.5">
                <div className="text-[9px] font-black text-slate-400 uppercase truncate" title={i.nombre}>{i.corto}</div>
                <div className="text-sm font-black text-slate-600">{i.peso}%</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
