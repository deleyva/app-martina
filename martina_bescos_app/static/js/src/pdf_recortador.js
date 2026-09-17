/**
 * Dibujar recortes sobre un PDF.
 *
 * Es la excepción que `AGENTS.md` contempla: "solo usar JavaScript cuando HTMX
 * no pueda manejar la funcionalidad". Arrastrar un rectángulo sobre un canvas y
 * verlo mientras se arrastra no se puede hacer con un intercambio de HTML desde
 * el servidor. Todo lo demás de la pantalla —crear, listar, borrar, colocar en
 * un libro— es HTMX puro y no pasa por aquí.
 *
 * Este fichero NO habla con el servidor. Lo único que hace es escribir en los
 * campos ocultos del formulario, que es quien envía. Así la validación vive en
 * un solo sitio (`Recorte.clean()`), y una petición hecha a mano o desde la API
 * pasa por las mismas comprobaciones que un arrastre.
 */

const CLAVE_PDFJS = 'pdfjs-dist/build/pdf';
const WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

// Cabecera, barra de botones y márgenes: lo que NO puede ocupar la página para
// que los controles sigan a la vista mientras se recorta.
const ALTO_RESERVADO = 230;

function init() {
    const raiz = document.getElementById('recortador');
    if (!raiz) return;

    const pdfjsLib = window[CLAVE_PDFJS];
    if (!pdfjsLib) {
        console.error('[recortador] PDF.js no está cargado');
        return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER;

    const lienzo = document.getElementById('recortador-canvas');
    const ctx = lienzo.getContext('2d');
    const capa = document.getElementById('recortador-capa');
    const marca = document.getElementById('recortador-marca');
    const etiquetaPagina = document.getElementById('recortador-pagina');
    const etiquetaTotal = document.getElementById('recortador-total');
    const etiquetaRect = document.getElementById('recortador-rect');

    const campos = {
        desde: document.getElementById('campo-pagina-desde'),
        hasta: document.getElementById('campo-pagina-hasta'),
        x0: document.getElementById('campo-rect-x0'),
        y0: document.getElementById('campo-rect-y0'),
        x1: document.getElementById('campo-rect-x1'),
        y1: document.getElementById('campo-rect-y1'),
    };

    let pdfDoc = null;
    let pagina = 1;
    let total = 0;
    // Mismo patrón que el visor: un contador de generación en vez de una
    // bandera, para que dos renders solapados no dejen el canvas a medias.
    let generacion = 0;
    let tarea = null;

    function render(num) {
        if (!pdfDoc) return;
        const mia = ++generacion;
        if (tarea) {
            try { tarea.cancel(); } catch (e) { /* ya terminada */ }
            tarea = null;
        }
        pagina = Math.max(1, Math.min(num, total));

        pdfDoc.getPage(pagina).then((page) => {
            if (mia !== generacion) return;
            const base = page.getViewport({ scale: 1 });
            // Que quepa la PÁGINA ENTERA, no que llene el ancho.
            //
            // Aquí no se lee: se elige un trozo, y para eso hay que ver dónde
            // está respecto al resto. Escalando por ancho, una página A4 salía
            // de 1153 px de alto y empujaba los botones de página y el modo
            // franja fuera de la pantalla — inservible en tablet, que es donde
            // se recorta con el método delante.
            // El marco, no el envoltorio: ver el comentario de la plantilla.
            const marco = document.getElementById('recortador-marco');
            const ancho = (marco || capa.parentElement).clientWidth;
            const alto = Math.max(320, window.innerHeight - ALTO_RESERVADO);
            const escala = Math.min(ancho / base.width, alto / base.height);
            const viewport = page.getViewport({ scale: escala });

            lienzo.width = viewport.width;
            lienzo.height = viewport.height;
            capa.style.width = viewport.width + 'px';
            capa.style.height = viewport.height + 'px';

            const t = page.render({ canvasContext: ctx, viewport });
            tarea = t;
            t.promise.then(() => {
                if (mia !== generacion) return;
                tarea = null;
                etiquetaPagina.textContent = pagina;
                sincronizarPaginas();
            }).catch((e) => {
                if (mia !== generacion) return;
                tarea = null;
                if (!e || e.name !== 'RenderingCancelledException') {
                    console.error('[recortador] render fallido:', e);
                }
            });
        });
    }

    // --- Rango de páginas ---
    //
    // La página que se está viendo es la de inicio mientras no haya un rango
    // marcado a mano. Es lo que hace que el caso normal —un recorte de una
    // página— no pida rellenar nada.
    let rangoManual = false;

    function sincronizarPaginas() {
        if (rangoManual) return;
        campos.desde.value = pagina;
        campos.hasta.value = '';
    }

    campos.desde.addEventListener('input', () => { rangoManual = true; });
    campos.hasta.addEventListener('input', () => { rangoManual = true; });

    document.getElementById('recortador-anterior').addEventListener('click', () => render(pagina - 1));
    document.getElementById('recortador-siguiente').addEventListener('click', () => render(pagina + 1));
    document.getElementById('recortador-marcar-fin').addEventListener('click', () => {
        rangoManual = true;
        campos.hasta.value = pagina;
    });

    // --- Dibujo del rectángulo ---

    let arrastrando = false;
    let inicio = null;
    let bandaForzada = false;

    // Modo franja permanente.
    //
    // `Shift` como única forma de marcar una franja era un fallo de diseño: en
    // una tablet NO HAY tecla Shift, y la tablet es donde se recorta de verdad,
    // con el método delante. El interruptor hace lo mismo con el dedo.
    const interruptorFranja = document.getElementById('recortador-modo-franja');
    const modoFranja = () => interruptorFranja.checked;

    function relativo(evento) {
        const caja = capa.getBoundingClientRect();
        const punto = evento.touches ? evento.touches[0] : evento;
        return {
            x: Math.min(1, Math.max(0, (punto.clientX - caja.left) / caja.width)),
            y: Math.min(1, Math.max(0, (punto.clientY - caja.top) / caja.height)),
        };
    }

    function pintarMarca(x0, y0, x1, y1) {
        marca.style.left = (x0 * 100) + '%';
        marca.style.top = (y0 * 100) + '%';
        marca.style.width = ((x1 - x0) * 100) + '%';
        marca.style.height = ((y1 - y0) * 100) + '%';
        marca.hidden = false;
    }

    function escribir(x0, y0, x1, y1) {
        // Sin redondear no: seis decimales sobran para un píxel y evitan que el
        // campo viaje con veinte cifras.
        campos.x0.value = x0.toFixed(6);
        campos.y0.value = y0.toFixed(6);
        campos.x1.value = x1.toFixed(6);
        campos.y1.value = y1.toFixed(6);
        const esBanda = x0 === 0 && x1 === 1;
        etiquetaRect.textContent = esBanda
            ? 'franja horizontal'
            : 'recuadro ' + Math.round((x1 - x0) * 100) + '×' + Math.round((y1 - y0) * 100) + '%';
    }

    function limpiarRect() {
        ['x0', 'y0', 'x1', 'y1'].forEach((k) => { campos[k].value = ''; });
        marca.hidden = true;
        etiquetaRect.textContent = 'página entera';
    }

    function empezar(evento) {
        arrastrando = true;
        // Franja horizontal: el caso normal en partitura, porque el sistema
        // ocupa todo el ancho y lo único que se elige de verdad es la altura.
        // Dos caminos al mismo sitio — el interruptor para el dedo, Shift como
        // atajo de teclado en el escritorio.
        bandaForzada = modoFranja() || evento.shiftKey === true;
        inicio = relativo(evento);
        evento.preventDefault();
    }

    function mover(evento) {
        if (!arrastrando) return;
        const ahora = relativo(evento);
        let x0 = Math.min(inicio.x, ahora.x);
        let x1 = Math.max(inicio.x, ahora.x);
        const y0 = Math.min(inicio.y, ahora.y);
        const y1 = Math.max(inicio.y, ahora.y);
        if (bandaForzada) { x0 = 0; x1 = 1; }
        pintarMarca(x0, y0, x1, y1);
        evento.preventDefault();
    }

    function soltar(evento) {
        if (!arrastrando) return;
        arrastrando = false;
        const ahora = relativo(evento.changedTouches ? { touches: evento.changedTouches } : evento);
        let x0 = Math.min(inicio.x, ahora.x);
        let x1 = Math.max(inicio.x, ahora.x);
        const y0 = Math.min(inicio.y, ahora.y);
        const y1 = Math.max(inicio.y, ahora.y);
        if (bandaForzada) { x0 = 0; x1 = 1; }

        // Un arrastre de dos píxeles es un clic con pulso, no un recorte. Sin
        // este mínimo se guardan rectángulos degenerados que el visor no puede
        // encuadrar, y `Recorte.clean()` los rechazaría con un error que en esta
        // pantalla no se entiende.
        if (x1 - x0 < 0.01 || y1 - y0 < 0.01) {
            limpiarRect();
            return;
        }
        pintarMarca(x0, y0, x1, y1);
        escribir(x0, y0, x1, y1);
    }

    capa.addEventListener('mousedown', empezar);
    window.addEventListener('mousemove', mover);
    window.addEventListener('mouseup', soltar);
    capa.addEventListener('touchstart', empezar, { passive: false });
    capa.addEventListener('touchmove', mover, { passive: false });
    capa.addEventListener('touchend', soltar);

    document.getElementById('recortador-limpiar').addEventListener('click', limpiarRect);

    document.getElementById('recortador-franja').addEventListener('click', () => {
        // Franja del tercio central: un punto de partida razonable para ajustar
        // arrastrando, en vez de obligar a acertar a la primera.
        pintarMarca(0, 0.33, 1, 0.66);
        escribir(0, 0.33, 1, 0.66);
    });

    // Tras crear un recorte, HTMX sustituye la lista. El formulario se limpia
    // aquí y no en el servidor porque el rectángulo solo existe en el cliente.
    //
    // Solo cuando el intercambio viene del PROPIO formulario. Si se resetease en
    // cualquier cambio de la lista, borrar otro recorte a mitad de una edición
    // se llevaría por delante lo que estabas corrigiendo.
    document.body.addEventListener('htmx:afterSwap', (e) => {
        if (e.detail && e.detail.elt === document.getElementById('form-recorte')) {
            salirDeEdicion();
        }
    });

    // --- Editar un recorte que ya existe ---
    //
    // Sin esto, corregir un rango obliga a borrar y rehacer, y al rehacerlo el
    // recorte se va al final del libro. Con cincuenta piezas eso convierte
    // cualquier repaso en una reordenación.

    const formulario = document.getElementById('form-recorte');
    const tituloForm = document.getElementById('titulo-form');
    const botonGuardar = document.getElementById('boton-guardar');
    const botonCancelar = document.getElementById('cancelar-edicion');
    const bloqueDestino = document.getElementById('bloque-destino-id');
    const campoDestino = document.getElementById('campo-destino');

    function entrarEnEdicion(datos) {
        formulario.setAttribute(
            'hx-post', formulario.dataset.urlEditarBase + datos.id + '/editar/'
        );
        // Sin `process`, HTMX puede seguir usando la URL con la que se inicializó.
        if (window.htmx) window.htmx.process(formulario);
        tituloForm.textContent = 'Editando recorte';
        botonGuardar.textContent = 'Guardar cambios';
        botonCancelar.hidden = false;
        // El destino no se toca al editar: el recorte ya está donde está, y
        // volver a colocarlo lo duplicaría como capítulo.
        campoDestino.closest('label').hidden = true;
        bloqueDestino.hidden = true;

        document.getElementById('campo-nombre').value = datos.nombre || '';
        campos.desde.value = datos.desde || '1';
        campos.hasta.value = datos.hasta || '';
        document.getElementById('campo-offset').value = datos.offset || '';
        rangoManual = true;

        if (datos.x0 !== '' && datos.x0 !== undefined) {
            const r = [+datos.x0, +datos.y0, +datos.x1, +datos.y1];
            pintarMarca(r[0], r[1], r[2], r[3]);
            escribir(r[0], r[1], r[2], r[3]);
        } else {
            limpiarRect();
        }

        render(parseInt(datos.desde, 10) || 1);
        formulario.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function salirDeEdicion() {
        formulario.setAttribute('hx-post', formulario.dataset.urlCrear);
        if (window.htmx) window.htmx.process(formulario);
        tituloForm.textContent = 'Nuevo recorte';
        botonGuardar.textContent = 'Crear recorte';
        botonCancelar.hidden = true;
        campoDestino.closest('label').hidden = false;
        bloqueDestino.hidden = campoDestino.value === 'suelto';

        document.getElementById('campo-nombre').value = '';
        document.getElementById('campo-offset').value = '';
        limpiarRect();
        rangoManual = false;
        sincronizarPaginas();
    }

    botonCancelar.addEventListener('click', salirDeEdicion);

    // Delegado en `document`: la lista la sustituye HTMX entera en cada cambio,
    // así que un listener por botón moriría con el primer intercambio.
    document.addEventListener('click', (e) => {
        const boton = e.target.closest('.js-editar-recorte');
        if (boton) entrarEnEdicion(boton.dataset);
    });

    campoDestino.addEventListener('change', () => {
        bloqueDestino.hidden = campoDestino.value === 'suelto';
    });

    // --- Reordenar los capítulos del libro ---

    function activarArrastre() {
        const lista = document.getElementById('capitulos-del-libro');
        if (!lista || !window.Sortable || lista.dataset.listo === '1') return;
        lista.dataset.listo = '1';
        window.Sortable.create(lista, {
            animation: 150,
            onEnd: () => {
                const claves = Array.from(lista.children).map((li) => li.dataset.clave);
                window.htmx.ajax('POST', lista.dataset.url, {
                    values: {
                        claves: JSON.stringify(claves),
                        csrfmiddlewaretoken: (
                            document.querySelector('[name=csrfmiddlewaretoken]') || {}
                        ).value,
                    },
                    swap: 'none',
                });
                // Renumerar en el sitio: el servidor contesta 204 y no manda
                // HTML, así que los números los arregla el cliente o se quedan
                // mintiendo hasta la siguiente recarga.
                Array.from(lista.children).forEach((li, i) => {
                    const n = li.querySelector('span');
                    if (n) n.textContent = i + 1;
                });
            },
        });
    }

    activarArrastre();
    // La lista se reconstruye en cada intercambio de HTMX, y con ella el `ul`.
    document.body.addEventListener('htmx:afterSwap', activarArrastre);

    // `disableRange` y `disableStream` a propósito.
    //
    // PDF.js pide el fichero por trozos (HTTP Range) para no bajarse un PDF
    // entero antes de pintar la primera página. Desde que los documentos se
    // sirven por la vista de Wagtail —que es lo que hace real la restricción—
    // **el servidor ya no atiende peticiones por rango**: contesta el fichero
    // completo a cada una. Resultado medido en este método de 13,7 MB: la
    // primera página tardaba 8 s y las siguientes no llegaban a pintarse nunca.
    //
    // Con esto se baja una vez y todo lo demás sale de memoria.
    //
    // `disableStream` NO: se probó y era peor. Obliga a PDF.js a bufferizar el
    // fichero entero antes de empezar, y con 13,7 MB eso congela la pestaña.
    pdfjsLib.getDocument({
        url: raiz.dataset.pdfUrl,
        disableRange: true,
    }).promise.then((doc) => {
        pdfDoc = doc;
        total = doc.numPages;
        etiquetaTotal.textContent = total;
        render(1);
    }).catch((e) => {
        console.error('[recortador] no se pudo cargar el PDF:', e);
    });

    let esperaResize = null;
    window.addEventListener('resize', () => {
        clearTimeout(esperaResize);
        esperaResize = setTimeout(() => { if (pdfDoc) render(pagina); }, 200);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
