// Hablar con Django. Todo lo que la pantalla sabe sale de aquí.

export const config = JSON.parse(document.getElementById('config').textContent);
const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

// Con la sesión caducada Django redirige al login y `fetch` lo sigue: llega un
// 200 con HTML. Se reconoce porque la respuesta no es JSON.
export class SesionCaducada extends Error {
  constructor() {
    super('La sesión ha caducado');
    this.name = 'SesionCaducada';
  }
}

async function pedir(url, opciones = {}) {
  const respuesta = await fetch(url, {
    credentials: 'same-origin',
    ...opciones,
    headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf, ...(opciones.headers || {}) },
  });
  const tipo = respuesta.headers.get('content-type') || '';
  if (!tipo.includes('application/json')) {
    if (respuesta.redirected || respuesta.ok) throw new SesionCaducada();
    const error = new Error(respuesta.status === 404 ? 'No encontrado' : `Error ${respuesta.status}`);
    error.status = respuesta.status;
    throw error;
  }
  const datos = await respuesta.json();
  if (!respuesta.ok) {
    const error = new Error(datos.error || `Error ${respuesta.status}`);
    error.status = respuesta.status;
    throw error;
  }
  return datos;
}

function formulario(campos) {
  const datos = new FormData();
  // `append` con tres argumentos exige un Blob: un texto va con dos. Una lista
  // repite la clave, que es como Django lee varios valores.
  Object.entries(campos).forEach(([clave, valor]) => {
    if (valor instanceof Blob) datos.append(clave, valor, valor.name || 'archivo');
    else if (Array.isArray(valor)) valor.forEach((v) => datos.append(clave, v));
    else datos.append(clave, valor);
  });
  return datos;
}

const enviar = (url, campos) => pedir(url, { method: 'POST', body: formulario(campos) });

export const api = {
  estado: () => pedir(`${config.base}estado/`),
  historial: () => pedir(`${config.base}historial.json`),
  // `celdas`: [[prueba, valor], …] de un mismo alumno. Van todas en una petición.
  guardarNotas: (alumno, celdas) =>
    enviar(`${config.base}nota/`, {
      alumno,
      prueba: celdas.map(([prueba]) => prueba),
      valor: celdas.map(([, valor]) => valor),
    }),
  guardarManual: (alumno, ambito, calificacion) =>
    enviar(`${config.base}nota-manual/`, { alumno, ambito, calificacion }),
  subirFichero: (prueba, alumno, tipo, archivo) =>
    enviar(`${config.base}evidencia/`, { prueba, alumno, tipo, archivo }),
  subirTexto: (prueba, alumno, texto) =>
    enviar(`${config.base}evidencia/`, {
      prueba,
      alumno,
      tipo: /^https?:\/\//.test(texto) ? 'enlace' : 'texto',
      texto,
    }),
  borrarEvidencia: (id) => enviar(`/calificaciones/evidencia/${id}/borrar/`, {}),
  revertir: (id) => enviar(`/calificaciones/cambio/${id}/revertir/`, { grupo: config.grupo }),
  empezar: (trimestre, campos) => enviar(`${config.base}plan/adoptar/?t=${trimestre}`, campos),
  crearPrueba: (instrumento, nombre, fecha) =>
    enviar(`/calificaciones/instrumento/${instrumento}/prueba/`, fecha ? { nombre, fecha } : { nombre }),
  editarPrueba: (id, campos) => enviar(`/calificaciones/prueba/${id}/`, campos),
};

export const rutaGrupo = (id, trimestre) => `${config.ruta_grupo.replace('{id}', id)}?t=${trimestre}`;
export const rutaPlan = (id) => `/calificaciones/plan/${id}/`;
export const rutaExportar = (trimestre, por) => `${config.base}exportar/?t=${trimestre}&por=${por}`;
