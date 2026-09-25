/*
 * Lista de revisión de las notas de voz de una clase (fase 40·1).
 *
 * La usan dos pantallas: la de «Clase completada» del visor (present.html) y
 * la de la sesión (view.html). Por eso vive aquí y no dentro de una plantilla.
 *
 * Cada nota trae su audio y lo que Whisper entendió. El profesor lo corrige y
 * lo ACEPTA —pasa a la reflexión con la hora y el elemento delante, y la nota y
 * su audio se borran— o lo DESCARTA. Aceptar también añade la línea al final
 * del cuadro de reflexión de la página: así lo que dice el servidor y lo que
 * se ve coinciden, y pulsar «Finalizar» o «Guardar» después no la borra.
 *
 * Delegación de eventos y nada de <script> en HTML inyectado: un innerHTML no
 * ejecuta sus scripts (la trampa de la fase 39).
 */
(function () {
    'use strict';

    var ESPERA_MS = 3000;

    function el(tag, clase, texto) {
        var e = document.createElement(tag);
        if (clase) e.className = clase;
        if (texto) e.textContent = texto;
        return e;
    }

    function textoDeEstado(nota) {
        if (nota.estado === 'pendiente') return 'Transcribiendo…';
        if (nota.estado === 'error') return 'No se pudo transcribir';
        return '';
    }

    function placeholderDe(nota) {
        if (nota.estado === 'pendiente') return 'Transcribiendo… Puedes ir escribiendo tú.';
        if (nota.estado === 'error') return 'No se pudo transcribir. Escúchala y escribe aquí lo que quieras guardar.';
        return 'Whisper no ha entendido nada. Escríbelo tú o descártala.';
    }

    function montar(opciones) {
        var caja = opciones.contenedor;
        var csrf = opciones.csrf;
        var reflexion = opciones.reflexion; // el <textarea> de la reflexión, si hay
        var temporizador = null;
        var filas = {}; // pk -> {nodo, texto, estado, nota}

        caja.classList.add('nv');
        var titulo = el('div', 'nv-titulo');
        var lista = el('div', 'nv-lista');
        caja.appendChild(titulo);
        caja.appendChild(lista);

        function pintarTitulo() {
            var n = Object.keys(filas).length;
            caja.hidden = n === 0;
            titulo.textContent = '🎤 Notas de voz de la clase (' + n + ')';
        }

        function crearFila(nota) {
            var fila = el('div', 'nv-fila');
            fila.dataset.pk = nota.pk;

            var cabecera = el('div', 'nv-cabecera');
            cabecera.appendChild(el('span', 'nv-cuando', nota.cabecera));
            var estado = el('span', 'nv-estado');
            cabecera.appendChild(estado);
            fila.appendChild(cabecera);

            var audio = el('audio', 'nv-audio');
            audio.controls = true;
            audio.preload = 'none';
            audio.src = nota.audio_url;
            fila.appendChild(audio);

            var texto = el('textarea', 'nv-texto');
            texto.rows = 3;
            texto.value = nota.transcripcion || '';
            // Lo que el profesor escribe manda: una transcripción que llegue
            // después NO lo pisa.
            texto.addEventListener('input', function () {
                texto.dataset.tocado = '1';
                aceptar.disabled = !texto.value.trim();
            });
            fila.appendChild(texto);

            var botones = el('div', 'nv-botones');
            var aceptar = el('button', 'nv-aceptar', 'Aceptar');
            aceptar.type = 'button';
            aceptar.dataset.accion = 'aceptar';
            var descartar = el('button', 'nv-descartar', 'Descartar');
            descartar.type = 'button';
            descartar.dataset.accion = 'descartar';
            botones.appendChild(aceptar);
            botones.appendChild(descartar);
            var aviso = el('span', 'nv-aviso');
            botones.appendChild(aviso);
            fila.appendChild(botones);

            filas[nota.pk] = {nodo: fila, texto: texto, estadoNodo: estado,
                              aceptar: aceptar, descartar: descartar, aviso: aviso, nota: nota};
            actualizarFila(nota);
            lista.appendChild(fila);
        }

        function actualizarFila(nota) {
            var f = filas[nota.pk];
            f.nota = nota;
            f.nodo.dataset.estado = nota.estado;
            f.estadoNodo.textContent = textoDeEstado(nota);
            f.texto.placeholder = placeholderDe(nota);
            if (!f.texto.dataset.tocado && nota.transcripcion && f.texto.value !== nota.transcripcion) {
                f.texto.value = nota.transcripcion;
            }
            f.aceptar.disabled = !f.texto.value.trim();
        }

        function quitarFila(pk) {
            var f = filas[pk];
            if (!f) return;
            f.nodo.remove();
            delete filas[pk];
            pintarTitulo();
        }

        function recargar() {
            clearTimeout(temporizador);
            return fetch(opciones.listaUrl, {credentials: 'same-origin'})
                .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
                .then(function (datos) {
                    var vistas = {};
                    datos.notas.forEach(function (nota) {
                        vistas[nota.pk] = true;
                        if (filas[nota.pk]) actualizarFila(nota); else crearFila(nota);
                    });
                    // Aceptada o descartada desde la otra pantalla.
                    Object.keys(filas).forEach(function (pk) { if (!vistas[pk]) quitarFila(pk); });
                    pintarTitulo();
                    var hayPendientes = datos.notas.some(function (n) { return n.estado === 'pendiente'; });
                    if (hayPendientes) temporizador = setTimeout(recargar, ESPERA_MS);
                })
                .catch(function () {
                    // Sin red, se vuelve a intentar: la lista no debe quedarse muda.
                    temporizador = setTimeout(recargar, ESPERA_MS * 3);
                });
        }

        function enviar(url, datos) {
            var fd = new FormData();
            Object.keys(datos || {}).forEach(function (k) { fd.append(k, datos[k]); });
            return fetch(url, {
                method: 'POST', credentials: 'same-origin', body: fd,
                headers: {'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest'}
            }).then(function (r) {
                return r.json().catch(function () { return {}; }).then(function (j) {
                    if (!r.ok) throw new Error(j.error || ('Error ' + r.status));
                    return j;
                });
            });
        }

        function anadirAReflexion(linea) {
            if (!reflexion) return;
            var actual = reflexion.value.replace(/\s+$/, '');
            reflexion.value = actual ? actual + '\n' + linea : linea;
            reflexion.dispatchEvent(new Event('input', {bubbles: true}));
        }

        caja.addEventListener('click', function (e) {
            var boton = e.target.closest('button[data-accion]');
            if (!boton || boton.disabled) return;
            var fila = boton.closest('.nv-fila');
            var f = filas[fila.dataset.pk];
            if (!f) return;

            if (boton.dataset.accion === 'aceptar') {
                boton.disabled = true;
                enviar(f.nota.aceptar_url, {texto: f.texto.value}).then(function (j) {
                    anadirAReflexion(j.linea);
                    quitarFila(f.nota.pk);
                }).catch(function (err) {
                    boton.disabled = false;
                    f.aviso.textContent = err.message;
                });
                return;
            }

            // Descartar borra el audio para siempre: segundo toque para confirmar.
            if (!boton.dataset.armado) {
                boton.dataset.armado = '1';
                boton.textContent = '¿Seguro? Descartar';
                setTimeout(function () {
                    delete boton.dataset.armado;
                    boton.textContent = 'Descartar';
                }, 3000);
                return;
            }
            boton.disabled = true;
            enviar(f.nota.descartar_url).then(function () {
                quitarFila(f.nota.pk);
            }).catch(function (err) {
                boton.disabled = false;
                f.aviso.textContent = err.message;
            });
        });

        pintarTitulo();
        recargar();
        return {recargar: recargar};
    }

    window.NotasDeVoz = {montar: montar};
})();
