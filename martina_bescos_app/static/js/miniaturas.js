/**
 * Miniaturas de PDF y de recorte, pintadas con pdf.js en el navegador.
 *
 * En el servidor no se rasteriza: haría falta PyMuPDF, que es AGPL y está
 * descartada a conciencia (ver `musica/servido.py`). Y pdf.js ya está cargado
 * en estas pantallas para el vistazo previo, así que esto no añade ni un byte.
 *
 * **Solo lo que se ve.** Un libro como *Ukulele Aerobics* tiene 283 elementos;
 * bajarse 283 PDF para pintar 283 sellos de 96px sería peor que no tener
 * miniaturas. Un IntersectionObserver los pinta conforme aparecen, una vez cada
 * uno, y cada fichero se descarga una sola vez aunque salga en varias filas.
 *
 * Si algo falla —fichero restringido, borrado, PDF ilegible— se deja el icono
 * que ya hay debajo y no se dice nada: es una miniatura, no un visor.
 */
(function () {
  'use strict';

  var documentos = {};   // url -> Promise del PDF, para no bajarlo dos veces
  var observador = null;

  // El worker lo configuran hoy los visores, cada uno en su fragmento, y aquí
  // no hay ningún visor abierto: sin esto pdf.js cae al worker de mentira y las
  // miniaturas no llegan a pintarse. Misma versión que el resto de la app.
  var WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  function pdfDe(url) {
    if (!window.pdfjsLib.GlobalWorkerOptions.workerSrc) {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER;
    }
    if (!documentos[url]) {
      documentos[url] = window.pdfjsLib.getDocument(url).promise;
    }
    return documentos[url];
  }

  function pintar(lienzo) {
    var url = lienzo.dataset.miniaturaPdf;
    var numero = parseInt(lienzo.dataset.pagina || '1', 10);
    var recorte = lienzo.dataset.recorte;

    return pdfDe(url).then(function (pdf) {
      return pdf.getPage(Math.min(numero, pdf.numPages));
    }).then(function (pagina) {
      var base = pagina.getViewport({ scale: 1 });

      // El rectángulo del recorte viene normalizado (0..1) con el origen
      // arriba a la izquierda, igual que en el visor grande.
      var trozo = { x: 0, y: 0, ancho: 1, alto: 1 };
      if (recorte) {
        var l = recorte.split(',').map(Number);
        if (l.length === 4 && l.every(function (n) { return !isNaN(n); })) {
          trozo = { x: l[0], y: l[1], ancho: l[2] - l[0], alto: l[3] - l[1] };
        }
      }

      // Se rellena la caja: el ancho manda, porque una partitura recortada es
      // casi siempre una franja horizontal.
      var anchoCaja = lienzo.clientWidth || 96;
      var escala = anchoCaja / (base.width * trozo.ancho);
      var vista = pagina.getViewport({ scale: escala });

      var entero = document.createElement('canvas');
      entero.width = Math.ceil(vista.width);
      entero.height = Math.ceil(vista.height);

      return pagina.render({
        canvasContext: entero.getContext('2d'),
        viewport: vista,
      }).promise.then(function () {
        lienzo.width = Math.ceil(entero.width * trozo.ancho);
        lienzo.height = Math.ceil(entero.height * trozo.alto);
        lienzo.getContext('2d').drawImage(
          entero,
          entero.width * trozo.x, entero.height * trozo.y,
          lienzo.width, lienzo.height,
          0, 0, lienzo.width, lienzo.height
        );
        lienzo.classList.remove('hidden');
      });
    });
  }

  function mirar(lienzo) {
    if (lienzo.dataset.pintada) return;
    lienzo.dataset.pintada = '1';
    pintar(lienzo).catch(function () {
      // Se queda el icono de debajo. Una miniatura que no sale no es un error
      // que haya que contarle a nadie en mitad de una clase.
    });
  }

  function observar(raiz) {
    if (!window.pdfjsLib) return;
    if (!observador) {
      if (!('IntersectionObserver' in window)) {
        // Sin observador, se pintan todas: es peor, pero es mejor que nada.
        (raiz || document).querySelectorAll('[data-miniatura-pdf]').forEach(mirar);
        return;
      }
      observador = new IntersectionObserver(function (entradas) {
        entradas.forEach(function (entrada) {
          if (!entrada.isIntersecting) return;
          observador.unobserve(entrada.target);
          mirar(entrada.target);
        });
      }, { rootMargin: '200px' });
    }
    (raiz || document).querySelectorAll('[data-miniatura-pdf]:not([data-pintada])')
      .forEach(function (lienzo) { observador.observe(lienzo); });
  }

  function arrancar() {
    observar();
    // Las listas de esta pantalla llegan por htmx: cada fragmento nuevo trae
    // miniaturas que nadie está mirando todavía.
    document.body.addEventListener('htmx:afterSwap', function (e) { observar(e.target); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', arrancar);
  } else {
    arrancar();
  }

  window.miniaturasPdf = { observar: observar };
})();
