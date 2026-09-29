// La pantalla de calificaciones. Es la de `notas` (la SPA del curso pasado),
// copiada: el mismo marcado y las mismas clases. Lo que cambia es de dónde
// salen los datos —de Django— y que aquí no se calcula ninguna nota.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle, ArrowLeft, Award, BookOpen, CheckCircle, Clock, FileText,
  HelpCircle, History, Layers, Music, Save,
} from 'lucide-react';
import { api, config, rutaGrupo, SesionCaducada } from './api.js';
import { crearCola } from './cola.js';
import { TERMS, TERM_FONDO, TERM_LABELS } from './estilos.js';
import Registro from './Registro.jsx';
import Empezar from './Empezar.jsx';
import Historial from './Historial.jsx';
import Info from './Info.jsx';
import Informes from './Informes.jsx';
import Final from './Final.jsx';

// Cómo se distingue en la cola una calificación puesta a mano de una celda.
const MANUAL = 'manual:';

const PESTANAS = [
  { id: 'registro', label: 'REGISTRO', icon: FileText },
  { id: 'informes', label: 'INFORMES', icon: BookOpen },
  { id: 'historial', label: 'HISTORIAL', icon: History },
  { id: 'final', label: 'FINAL', icon: Award },
  { id: 'info', label: 'INFO', icon: HelpCircle },
];

function pestanaInicial() {
  const hash = window.location.hash.replace('#', '');
  return PESTANAS.some((p) => p.id === hash) ? hash : 'registro';
}

export default function App() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [caducada, setCaducada] = useState(false);
  const [pestana, setPestana] = useState(pestanaInicial);
  const [trimestre, setTrimestre] = useState(String(config.trimestre || 1));
  const [modo, setModo] = useState('lomloe');
  const [alumnoElegido, setAlumnoElegido] = useState(null);
  const [estadoGuardado, setEstadoGuardado] = useState('saved');
  const [subiendo, setSubiendo] = useState(0);
  const [avisos, setAvisos] = useState(config.avisos || []);
  const [cambios, setCambios] = useState([]);

  const atender = useCallback((e) => {
    if (e instanceof SesionCaducada) setCaducada(true);
    else setError(e.message || 'Error');
  }, []);

  const cargar = useCallback(() => api.estado().then(setDatos).catch(atender), [atender]);

  useEffect(() => { cargar(); }, [cargar]);

  // El aviso de «ya puedes poner notas» se quita solo.
  useEffect(() => {
    if (avisos.length === 0) return undefined;
    const id = setTimeout(() => setAvisos([]), 6000);
    return () => clearTimeout(id);
  }, [avisos]);

  const ponerAlumno = useCallback((bloque) => {
    setDatos((previo) => previo && {
      ...previo,
      alumnos: previo.alumnos.map((a) => (a.id === bloque.id ? bloque : a)),
    });
  }, []);

  // ── Guardar notas ──
  const colaRef = useRef(null);
  if (colaRef.current === null) {
    colaRef.current = crearCola({
      // Todo lo de un alumno va por la misma cola, también la calificación
      // puesta a mano: si fueran por caminos distintos, el bloque de cifras de
      // una respuesta podría pisar al de otra más nueva.
      enviar: async (alumno, lote) => {
        const notas = lote.filter(([clave]) => !String(clave).startsWith(MANUAL));
        const manuales = lote.filter(([clave]) => String(clave).startsWith(MANUAL));
        let respuesta = null;
        if (notas.length) respuesta = await api.guardarNotas(alumno, notas);
        for (const [clave, calificacion] of manuales) {
          respuesta = await api.guardarManual(alumno, clave.slice(MANUAL.length), calificacion);
        }
        return respuesta;
      },
      alRecibir: (alumno, respuesta, quedan) => {
        setError(null);
        // Si ese alumno tiene todavía algo por mandar, este bloque ya es viejo.
        if (!quedan) ponerAlumno(respuesta.alumno);
      },
      alFallar: (alumno, celdas, e) => {
        if (e instanceof SesionCaducada) { setCaducada(true); return; }
        setError(e.status ? e.message : 'No se ha podido guardar. Lo escrito sigue aqui y se enviara con el siguiente cambio.');
      },
      alCambiar: setEstadoGuardado,
    });
  }
  const cola = colaRef.current;

  const guardarNota = useCallback((alumno, prueba, valor, opciones) => {
    cola.poner(alumno, prueba, valor, opciones);
  }, [cola]);

  const guardarManual = useCallback((alumno, ambito, calificacion) => {
    // Se pinta ya, como en `notas`; el servidor lo confirma al contestar.
    setDatos((previo) => previo && {
      ...previo,
      alumnos: previo.alumnos.map((a) => {
        if (a.id !== alumno) return a;
        if (ambito === 'curso') return { ...a, curso: { ...a.curso, manual: calificacion } };
        return {
          ...a,
          trimestres: { ...a.trimestres, [ambito]: { ...a.trimestres[ambito], manual: calificacion } },
        };
      }),
    });
    cola.poner(alumno, `${MANUAL}${ambito}`, calificacion, { yaMismo: true });
  }, [cola]);

  // ── Evidencias ──
  const conSubida = useCallback(async (promesa) => {
    setSubiendo((n) => n + 1);
    try {
      const r = await promesa;
      setDatos((previo) => previo && { ...previo, evidencias: [r.evidencia, ...previo.evidencias] });
      return { success: true };
    } catch (e) {
      atender(e);
      return { success: false };
    } finally {
      setSubiendo((n) => n - 1);
    }
  }, [atender]);

  const subirEvidencia = useCallback(
    (alumno, prueba, archivo, tipo) => conSubida(api.subirFichero(prueba, alumno, tipo, archivo)),
    [conSubida],
  );
  const anadirComentario = useCallback(
    (alumno, prueba, texto) => conSubida(api.subirTexto(prueba, alumno, texto)),
    [conSubida],
  );
  const borrarEvidencia = useCallback((id) => {
    api.borrarEvidencia(id)
      .then(() => setDatos((previo) => previo && {
        ...previo,
        evidencias: previo.evidencias.filter((e) => e.id !== id),
      }))
      .catch(atender);
  }, [atender]);

  const evidenciasDe = useCallback(
    (alumno, prueba) => (datos ? datos.evidencias.filter((e) => e.alumno === alumno && e.prueba === prueba) : []),
    [datos],
  );

  // ── Historial ──
  const cargarHistorial = useCallback(
    () => api.historial().then((r) => setCambios(r.cambios)).catch(atender),
    [atender],
  );
  useEffect(() => {
    if (pestana === 'historial') { cola.vaciarTodo(); cargarHistorial(); }
  }, [pestana, cargarHistorial, cola]);

  const revertir = useCallback((id) => {
    api.revertir(id)
      .then((r) => { ponerAlumno(r.alumno); return cargarHistorial(); })
      .catch(atender);
  }, [ponerAlumno, cargarHistorial, atender]);

  // ── Pestañas, y no perder lo que está a medias ──
  useEffect(() => {
    window.history.replaceState(null, '', `?t=${trimestre}#${pestana}`);
  }, [pestana, trimestre]);

  const ocupado = estadoGuardado === 'unsaved' || estadoGuardado === 'saving' || subiendo > 0;
  useEffect(() => {
    if (!ocupado) return undefined;
    const avisar = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', avisar);
    return () => window.removeEventListener('beforeunload', avisar);
  }, [ocupado]);

  // Al volver a la pestaña (otro dispositivo puede haber escrito), se relee.
  useEffect(() => {
    const alVolver = () => {
      if (document.visibilityState === 'visible' && !cola.hayAlgo()) cargar();
    };
    document.addEventListener('visibilitychange', alVolver);
    return () => document.removeEventListener('visibilitychange', alVolver);
  }, [cargar, cola]);

  const bloque = datos?.trimestres[trimestre];
  const alumnos = datos?.alumnos || [];
  const alumno = useMemo(
    () => alumnos.find((a) => a.id === alumnoElegido) || alumnos[0],
    [alumnos, alumnoElegido],
  );

  if (!datos) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        {caducada ? <SesionCaducadaAviso /> : (
          <div className="text-slate-400 text-sm font-bold animate-pulse">
            {error ? `No se han podido cargar los datos: ${error}` : 'Cargando datos...'}
          </div>
        )}
      </div>
    );
  }

  const indicador = subiendo > 0 && estadoGuardado === 'saved' ? 'saving' : estadoGuardado;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans print:bg-white">
      {/* ── NAV ── */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm print:hidden">
        <div className="max-w-[1400px] mx-auto px-4 h-14 flex justify-between items-center gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <a
              href={config.inicio}
              className="text-slate-300 hover:text-slate-500 transition-colors flex-shrink-0"
              title="Volver a Calificaciones"
            >
              <ArrowLeft size={16} />
            </a>
            <div className="bg-indigo-600 p-1.5 rounded-lg flex-shrink-0">
              <Music className="text-white" size={18} />
            </div>
            <span className="font-bold text-base truncate">{datos.grupo.nombre}</span>
            <SaveIndicator status={indicador} />
          </div>
          <div className="flex bg-slate-100 p-0.5 rounded-xl gap-0.5 overflow-x-auto">
            {PESTANAS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setPestana(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all flex items-center gap-1.5 ${
                  pestana === tab.id
                    ? 'bg-white shadow text-indigo-600'
                    : 'text-slate-400 hover:text-slate-600'
                }`}
              >
                <tab.icon size={12} />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-[1400px] mx-auto p-4 sm:p-6">
        {caducada && <div className="mb-4"><SesionCaducadaAviso /></div>}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center justify-between print:hidden">
            <span className="flex items-center gap-2"><AlertCircle size={14} /> {error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">Cerrar</button>
          </div>
        )}
        {avisos.map((aviso) => (
          <div key={aviso} className="mb-4 bg-green-50 border border-green-200 text-green-700 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center gap-2 print:hidden">
            <CheckCircle size={14} /> {aviso}
          </div>
        ))}

        {/* ── CONTROLS BAR ── */}
        {pestana !== 'historial' && pestana !== 'info' && (
          <div className="mb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 print:hidden">
            <div className="flex items-center gap-2">
              {/* Group selector */}
              <div className="flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-sm">
                <Layers size={14} className="text-slate-400" />
                <select
                  className="bg-transparent text-xs font-bold outline-none cursor-pointer text-indigo-600"
                  value={datos.grupo.id}
                  onChange={(e) => { window.location.href = rutaGrupo(e.target.value, trimestre); }}
                >
                  {datos.grupos.map((g) => (
                    <option key={g.id} value={g.id}>{g.nombre}</option>
                  ))}
                </select>
              </div>

              {/* Term selector */}
              <div className="flex bg-white p-0.5 rounded-xl border border-slate-200 shadow-sm">
                {TERMS.map((term) => {
                  const isActive = trimestre === term;
                  return (
                    <button
                      key={term}
                      onClick={() => setTrimestre(term)}
                      className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wide transition-all ${
                        isActive ? 'text-white shadow-sm' : 'text-slate-400 hover:text-slate-600'
                      }`}
                      style={isActive ? { backgroundColor: TERM_FONDO[term] } : {}}
                    >
                      {TERM_LABELS[term]}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* View mode toggle */}
            {pestana === 'registro' && bloque.plan && (
              <div className="flex items-center gap-1 bg-slate-200/50 p-0.5 rounded-xl">
                <button
                  onClick={() => setModo('simple')}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
                    modo === 'simple' ? 'bg-slate-900 text-white' : 'text-slate-500'
                  }`}
                >
                  Media Simple
                </button>
                <button
                  onClick={() => setModo('lomloe')}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
                    modo === 'lomloe' ? 'bg-indigo-600 text-white' : 'text-slate-500'
                  }`}
                >
                  LOMLOE
                </button>
              </div>
            )}
          </div>
        )}

        {pestana === 'registro' && (bloque.plan ? (
          <Registro
            datos={datos}
            trimestre={trimestre}
            modo={modo}
            onNota={guardarNota}
            onSalirDeCelda={(id) => cola.vaciar(id)}
            onManual={guardarManual}
            onSubir={subirEvidencia}
            onBorrar={borrarEvidencia}
            onComentar={anadirComentario}
            evidenciasDe={evidenciasDe}
            onRecargar={cargar}
            onError={atender}
          />
        ) : (
          <Empezar trimestre={trimestre} opciones={bloque.empezar} grupo={datos.grupo} onHecho={cargar} onError={atender} />
        ))}

        {pestana === 'informes' && alumno && (
          <Informes
            datos={datos}
            alumno={alumno}
            trimestre={trimestre}
            modo={modo}
            onElegir={setAlumnoElegido}
          />
        )}

        {pestana === 'historial' && (
          <Historial cambios={cambios} onRevertir={revertir} />
        )}

        {pestana === 'final' && (
          <Final datos={datos} modo={modo} trimestre={trimestre} onManual={guardarManual} />
        )}

        {pestana === 'info' && <Info datos={datos} />}
      </main>

      <footer className="max-w-[1400px] mx-auto px-4 py-8 text-center print:hidden">
        <p className="text-slate-300 text-[10px] font-black uppercase tracking-[0.3em]">
          {datos.grupo.materia}  {datos.grupo.nombre}  {datos.grupo.curso}
        </p>
      </footer>
    </div>
  );
}

function SesionCaducadaAviso() {
  return (
    <div className="bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center gap-2">
      <AlertCircle size={14} />
      La sesión ha caducado y lo último que has escrito no se ha guardado.
      <a href={window.location.href} className="underline">Volver a entrar</a>
    </div>
  );
}

function SaveIndicator({ status }) {
  if (status === 'saved') {
    return (
      <span className="flex items-center gap-1 text-[9px] font-bold text-green-500 bg-green-50 px-2 py-0.5 rounded-full flex-shrink-0">
        <CheckCircle size={10} /> Guardado
      </span>
    );
  }
  if (status === 'saving') {
    return (
      <span className="flex items-center gap-1 text-[9px] font-bold text-amber-500 bg-amber-50 px-2 py-0.5 rounded-full animate-pulse flex-shrink-0">
        <Save size={10} /> Guardando...
      </span>
    );
  }
  if (status === 'unsaved') {
    return (
      <span className="flex items-center gap-1 text-[9px] font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full flex-shrink-0">
        <Clock size={10} /> Sin guardar
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[9px] font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded-full flex-shrink-0">
      <AlertCircle size={10} /> Error
    </span>
  );
}
