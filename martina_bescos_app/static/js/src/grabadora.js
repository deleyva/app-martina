// Fichas de audición (fase 111): grabar el audio de un ejercicio desde la web.
//
// **La grabación se guarda en el navegador ANTES de subirla** (IndexedDB) y no
// se borra hasta que el servidor contesta que la tiene. Es la lección de la
// fase 109: la wifi del aula se cae, y un «Failed to fetch» no puede costar una
// toma. Lo pendiente se reintenta al volver a la página y con el botón
// «Reintentar»; la misma `clave` en cada intento hace que el servidor no
// duplique nada si la primera subida llegó y se perdió la respuesta.
//
// Formato: el primero que acepte el navegador de webm/opus (Chrome, Firefox) o
// mp4/aac (Safari), igual que el panel de evaluar.
//
// Queda en `window.Grabadora` (`montar`, y `subirBlob` para las pruebas: es el
// mismo camino que sigue una grabación al terminar).

const BD = "audicion-grabaciones";
const ALMACEN = "pendientes";

export const TIPOS = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

export function elegirTipo(candidatos, admite) {
  return candidatos.find((t) => admite(t)) || "";
}

export function extensionDe(tipo) {
  if ((tipo || "").includes("mp4")) return "m4a";
  if ((tipo || "").includes("ogg")) return "ogg";
  return "webm";
}

// --- IndexedDB -------------------------------------------------------------

function abrir() {
  return new Promise((ok, mal) => {
    const pet = indexedDB.open(BD, 1);
    pet.onupgradeneeded = () => pet.result.createObjectStore(ALMACEN, { keyPath: "clave" });
    pet.onsuccess = () => ok(pet.result);
    pet.onerror = () => mal(pet.error);
  });
}

async function operar(modo, fn) {
  const bd = await abrir();
  return new Promise((ok, mal) => {
    const tx = bd.transaction(ALMACEN, modo);
    const pet = fn(tx.objectStore(ALMACEN));
    tx.oncomplete = () => { bd.close(); ok(pet && pet.result); };
    tx.onerror = () => { bd.close(); mal(tx.error); };
  });
}

const guardar = (reg) => operar("readwrite", (a) => a.put(reg));
const borrar = (clave) => operar("readwrite", (a) => a.delete(clave));
const todas = () => operar("readonly", (a) => a.getAll());

// --- Subir -------------------------------------------------------------------

function nuevaClave() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

async function subir(reg) {
  const datos = new FormData();
  datos.append("clave", reg.clave);
  datos.append("archivo", reg.blob, reg.nombre);
  const r = await fetch(reg.url, {
    method: "POST",
    body: datos,
    credentials: "same-origin",
    headers: { "X-CSRFToken": reg.csrf, "HX-Request": "true" },
  });
  if (!r.ok) {
    const texto = (await r.text()).slice(0, 200);
    const error = new Error(texto || "El servidor dijo " + r.status);
    // 4xx: el servidor la ha visto y no la quiere; reintentar no la arregla.
    error.definitivo = r.status >= 400 && r.status < 500;
    throw error;
  }
  return r.text();
}

// Una subida por clave aunque haya dos pestañas abiertas (Web Locks).
function conCerrojo(clave, fn) {
  if (navigator.locks && navigator.locks.request) {
    return navigator.locks.request("audicion-" + clave, { ifAvailable: true }, (cerrojo) => (cerrojo ? fn() : null));
  }
  return fn();
}

function decir(caja, texto, pendiente) {
  const estado = caja.querySelector("[data-estado-grabacion]");
  if (!estado) return;
  estado.textContent = texto;
  estado.classList.toggle("fa-pendiente", !!pendiente);
}

// Sube un audio (grabado o elegido) y, si el servidor lo acepta, recarga la
// página para que suene la grabación nueva.
async function subirBlob(caja, blob, tipo) {
  const reg = {
    clave: nuevaClave(),
    url: caja.dataset.subir,
    csrf: caja.dataset.csrf,
    pagina: location.pathname,
    nombre: "grabacion." + extensionDe(tipo || blob.type),
    blob,
    creada: Date.now(),
  };
  try {
    await guardar(reg);
  } catch (e) {
    console.error("[grabadora] no se pudo guardar en el navegador", e);
  }
  return intentar(caja, reg);
}

async function intentar(caja, reg) {
  decir(caja, "Subiendo…");
  try {
    await conCerrojo(reg.clave, () => subir(reg));
    await borrar(reg.clave).catch(() => {});
    decir(caja, "Subida.");
    location.reload();
    return true;
  } catch (e) {
    console.error("[grabadora]", e);
    if (e.definitivo) {
      await borrar(reg.clave).catch(() => {});
      decir(caja, "No se pudo subir: " + e.message, true);
    } else {
      decir(caja, "Sin conexión: la grabación está guardada en este navegador y se subirá al volver a esta página.", true);
      ofrecerReintento(caja, reg);
    }
    return false;
  }
}

function ofrecerReintento(caja, reg) {
  if (caja.querySelector("[data-reintentar]")) return;
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn btn-sm btn-warning";
  b.dataset.reintentar = "1";
  b.textContent = "↻ Reintentar la subida";
  b.addEventListener("click", () => { b.remove(); intentar(caja, reg); });
  caja.appendChild(b);
}

// --- Grabar ----------------------------------------------------------------

function montarCaja(caja) {
  if (caja.dataset.montado) return;
  caja.dataset.montado = "1";
  const grabar = caja.querySelector("[data-grabar]");
  const detener = caja.querySelector("[data-detener]");
  const fichero = caja.querySelector("[data-fichero]");
  let grabador = null;
  let trozos = [];

  if (grabar) {
    grabar.addEventListener("click", async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        decir(caja, "Este navegador no puede grabar aquí.", true);
        return;
      }
      let flujo;
      try {
        flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (e) {
        decir(caja, "Sin permiso para usar el micrófono.", true);
        return;
      }
      const tipo = elegirTipo(TIPOS, (t) => MediaRecorder.isTypeSupported(t));
      grabador = tipo ? new MediaRecorder(flujo, { mimeType: tipo }) : new MediaRecorder(flujo);
      trozos = [];
      grabador.ondataavailable = (ev) => { if (ev.data && ev.data.size) trozos.push(ev.data); };
      grabador.onstop = () => {
        flujo.getTracks().forEach((t) => t.stop());
        const real = grabador.mimeType || tipo || "audio/webm";
        const blob = new Blob(trozos, { type: real });
        grabar.hidden = false;
        if (detener) detener.hidden = true;
        subirBlob(caja, blob, real);
      };
      grabador.start(1000);
      grabar.hidden = true;
      if (detener) detener.hidden = false;
      decir(caja, "● Grabando… pulsa «Terminar» al acabar.");
    });
  }
  if (detener) {
    detener.addEventListener("click", () => {
      if (grabador && grabador.state !== "inactive") grabador.stop();
    });
  }
  if (fichero) {
    fichero.addEventListener("change", () => {
      const f = fichero.files && fichero.files[0];
      if (f) subirBlob(caja, f, f.type);
    });
  }
}

// Lo que quedó sin subir en esta página (otra visita, otra pestaña).
async function reintentarPendientes(raiz) {
  let lista = [];
  try {
    lista = await todas();
  } catch (e) {
    return;
  }
  for (const reg of lista.filter((r) => r.pagina === location.pathname)) {
    const caja = [...raiz.querySelectorAll("[data-grabacion]")].find((c) => c.dataset.subir === reg.url);
    if (caja) await intentar(caja, reg);
  }
}

export function montar(raiz) {
  const r = raiz || document;
  r.querySelectorAll("[data-grabacion]").forEach(montarCaja);
  reintentarPendientes(r);
}

if (typeof window !== "undefined") {
  window.Grabadora = {
    montar,
    // Las pruebas meten un Blob por el mismo camino que una grabación.
    subirBlob: (caja, blob, tipo) => subirBlob(caja, blob, tipo),
    pendientes: () => todas(),
  };
}
