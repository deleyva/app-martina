/* La banda de hoy (fase 92): el panel de la tecla B en la clase.
 *
 * Pinta lo que devuelve `clases:banda_hoy`: quién toca cada puesto, quién le
 * ayuda (o, el último día del turno, a quién enseña) y, si falta un titular,
 * a quién poner. Un toque acepta el sustituto propuesto. Toda regla vive en
 * `clases/banda.py`; aquí solo se pinta y se envía.
 *
 * Debajo (fase 117), los que hoy no tienen puesto, en tres columnas: ukelele,
 * xilófono y coros. Cada uno sale en lo que prefiere; tocar un nombre y luego
 * otra columna lo cambia para la canción que está en pantalla.
 */
(function () {
  var panel = document.getElementById('panel-banda');
  if (!panel) return;
  var cuerpo = panel.querySelector('#banda-tabla tbody');
  var eleccion = document.getElementById('banda-elegir');
  var datos = null;
  var elegido = null; // el alumno de «Los demás» que se está moviendo de columna

  // El elemento que está en pantalla: de él sale la canción. `playlist` y
  // `currentIndex` son de present.html.
  function itemActual() {
    var lista = window.playlist || [];
    var item = lista[window.currentIndex];
    return item && item.pk ? item.pk : null;
  }

  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined && texto !== null) e.textContent = texto;
    return e;
  }

  function boton(texto, clase, alPulsar) {
    var b = el('button', clase, texto);
    b.type = 'button';
    b.addEventListener('click', function (ev) { ev.stopPropagation(); alPulsar(); });
    return b;
  }

  function aviso(texto, enlace) {
    var a = document.getElementById('banda-aviso');
    a.textContent = texto || '';
    if (enlace) {
      a.appendChild(document.createTextNode(' '));
      var l = el('a', '', enlace.texto);
      l.href = enlace.url;
      l.target = '_blank';
      a.appendChild(l);
    }
    a.hidden = !texto;
  }

  window.bandaAbierta = function () { return panel.classList.contains('abierto'); };

  window.abrirBanda = function () {
    panel.classList.add('abierto');
    traer();
  };

  window.cerrarBanda = function () {
    cerrarEleccion();
    elegido = null;
    panel.classList.remove('abierto');
  };

  function traer() {
    var item = itemActual();
    fetch(panel.dataset.url + (item ? '?item=' + item : ''), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(pintar)
      .catch(function () { aviso('No he podido traer la banda.'); });
  }

  function enviar(plaza, alumno) {
    cerrarEleccion();
    fetch(panel.dataset.cambio, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': panel.dataset.csrf },
      body: JSON.stringify({ plaza: plaza, alumno: alumno, item: itemActual() }),
    })
      .then(function (r) { return r.json().then(function (c) { return { ok: r.ok, c: c }; }); })
      .then(function (res) {
        if (!res.ok) { aviso((res.c.errores || ['No se ha guardado.']).join(' ')); return; }
        pintar(res.c);
      })
      .catch(function () { aviso('Sin conexión: el cambio no se ha guardado.'); });
  }

  function cerrarEleccion() { eleccion.hidden = true; eleccion.innerHTML = ''; }

  function enviarResto(alumno, papel) {
    elegido = null;
    fetch(panel.dataset.resto, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': panel.dataset.csrf },
      body: JSON.stringify({ item: datos.resto.item, alumno: alumno, papel: papel }),
    })
      .then(function (r) { return r.json().then(function (c) { return { ok: r.ok, c: c }; }); })
      .then(function (res) {
        if (!res.ok) { aviso((res.c.errores || ['No se ha guardado.']).join(' ')); pintarResto(); return; }
        pintar(res.c);
      })
      .catch(function () { aviso('Sin conexión: el cambio no se ha guardado.'); pintarResto(); });
  }

  // Los que no tienen puesto hoy. Dos toques: el nombre y la columna a la que va.
  function pintarResto() {
    var caja = document.getElementById('banda-resto');
    var columnas = document.getElementById('banda-columnas');
    var pista = document.getElementById('banda-resto-pista');
    var volver = document.getElementById('banda-resto-reset');
    var r = datos && datos.resto;
    var cuantos = r ? r.columnas.reduce(function (n, c) { return n + c.alumnos.length; }, 0) : 0;
    columnas.innerHTML = '';
    if (!r || !cuantos) { caja.hidden = true; return; }
    caja.hidden = false;
    var seApunta = r.item !== null;
    var nombreElegido = '';
    r.columnas.forEach(function (c) {
      c.alumnos.forEach(function (a) { if (a.id === elegido) nombreElegido = a.nombre; });
    });
    if (!nombreElegido) elegido = null;
    document.getElementById('banda-cancion').textContent = r.cancion ? 'en «' + r.cancion + '»' : '';
    volver.hidden = !r.cambiados;
    volver.onclick = function () { enviarResto(null, null); };
    pista.classList.toggle('activa', !!nombreElegido);
    pista.textContent = !seApunta ? 'Así lo prefieren. Abre una canción para apuntar su reparto.'
      : nombreElegido ? '¿A dónde va ' + nombreElegido + '? Toca una columna.'
      : 'Toca un nombre y después la columna a la que va. Queda guardado para esta canción.';

    r.columnas.forEach(function (c) {
      var esSuya = c.alumnos.some(function (a) { return a.id === elegido; });
      var destino = elegido !== null && !esSuya;
      var col = el('div', 'columna' + (destino ? ' destino' : ''));
      var titulo = el('h3', '', c.icono + ' ' + c.nombre);
      titulo.appendChild(el('small', '', String(c.alumnos.length)));
      col.appendChild(titulo);
      var nombres = el('div', 'nombres');
      if (!c.alumnos.length) nombres.appendChild(el('span', 'nadie', 'Nadie'));
      c.alumnos.forEach(function (a) {
        var clase = 'nombre' + (a.cambiado ? ' cambiado' : '') + (a.id === elegido ? ' elegido' : '');
        var b = boton(a.nombre, clase, function () {
          if (destino) { enviarResto(elegido, c.papel); return; }
          elegido = a.id === elegido ? null : a.id;
          pintarResto();
        });
        b.disabled = !seApunta;
        if (a.cambiado) b.title = 'Solo en esta canción: suele preferir ' + (a.prefiere === 'xilofono' ? 'xilófono' : a.prefiere);
        nombres.appendChild(b);
      });
      col.appendChild(nombres);
      col.appendChild(el('div', 'aqui', 'Pasar aquí a ' + nombreElegido));
      if (destino) col.addEventListener('click', function () { enviarResto(elegido, c.papel); });
      columnas.appendChild(col);
    });
  }

  function elegir(fila) {
    eleccion.innerHTML = '';
    eleccion.appendChild(el('div', 'pregunta', '¿Quién toca hoy ' + fila.etiqueta + '?'));
    var lista = el('div', 'opciones');
    if (!datos.libres.length) lista.appendChild(el('span', 'nadie', 'No queda nadie presente sin puesto.'));
    datos.libres.forEach(function (a) {
      var texto = a.nombre + ' (' + a.turnos + ')' + (a.fuera ? ' · no entra en la banda' : '');
      lista.appendChild(boton(texto, 'opcion', function () { enviar(fila.plaza, a.id); }));
    });
    eleccion.appendChild(lista);
    eleccion.appendChild(boton('Cancelar', 'cancelar', cerrarEleccion));
    eleccion.hidden = false;
  }

  function pintar(d) {
    datos = d;
    document.getElementById('banda-rejilla').href = d.url_rejilla;
    cuerpo.innerHTML = '';
    var tabla = document.getElementById('banda-tabla');
    pintarResto();
    if (!d.hay_banda) {
      tabla.hidden = true;
      document.getElementById('banda-turno').textContent = '';
      aviso('Este grupo aún no tiene banda.', { texto: 'Prepárala en la rejilla del curso', url: d.url_rejilla });
      return;
    }
    document.getElementById('banda-titulo').textContent = d.relevo ? '🔁 Relevo' : '🎸 La banda de hoy';
    var turno = 'Turno ' + d.turno + ' · sesión ' + d.sesion + ' de ' + d.sesiones_por_turno;
    document.getElementById('banda-turno').textContent = turno;
    if (d.fuera_del_plan) {
      tabla.hidden = true;
      aviso('Esta sesión cae en el turno ' + d.turno + ' y el curso tiene ' + d.total_turnos + '.',
            { texto: 'Añade turnos en la rejilla', url: d.url_rejilla });
      return;
    }
    aviso(d.cuenta ? '' : 'Esta sesión no es en el aula de música: al cerrarla, el turno no avanza.');
    tabla.hidden = false;
    document.getElementById('banda-col3').textContent = d.relevo ? 'Enseña a' : 'Le ayuda si se atasca';

    d.filas.forEach(function (f) {
      var tr = el('tr', f.falta ? 'falta' : '');
      tr.appendChild(el('td', 'puesto', f.icono + ' ' + f.etiqueta));

      var hoy = el('td', 'hoy');
      if (f.cambio) {
        hoy.appendChild(el('b', '', f.cambio_nombre));
        var motivo = f.falta ? ', sustituye a ' + f.titular_nombre + ', que falta'
          : (f.titular ? ', en lugar de ' + f.titular_nombre : '');
        hoy.appendChild(document.createTextNode(motivo + ' '));
        hoy.appendChild(boton('Deshacer', 'deshacer', function () { enviar(f.plaza, null); }));
      } else if (f.falta || !f.titular) {
        // Tachado, solo el nombre: «falta» se tiene que leer desde el fondo.
        function quien() {
          if (f.titular) {
            hoy.appendChild(el('span', 'ausente', f.titular_nombre));
            hoy.appendChild(document.createTextNode(' falta'));
          } else {
            hoy.appendChild(el('span', 'vacia', 'Plaza vacía'));
          }
        }
        if (f.lo_cubre_el_profesor) {
          quien();
          hoy.appendChild(document.createTextNode(' · lo cubres tú'));
        } else if (f.propuesto) {
          quien();
          hoy.appendChild(document.createTextNode(' → '));
          hoy.appendChild(boton('Que toque ' + f.propuesto_nombre + ' ✓', 'aceptar', function () { enviar(f.plaza, f.propuesto); }));
          hoy.appendChild(boton('otro…', 'otro', function () { elegir(f); }));
        } else {
          quien();
          hoy.appendChild(document.createTextNode(' · no queda nadie libre'));
        }
      } else {
        hoy.appendChild(el('b', '', f.titular_nombre));
        hoy.appendChild(document.createTextNode(' '));
        hoy.appendChild(boton('cambiar', 'otro discreto', function () { elegir(f); }));
      }
      tr.appendChild(hoy);

      var tercera = d.relevo ? f.entra_nombre : (f.ayuda_nombre ? f.ayuda_nombre + (f.ayuda_falta ? ' (falta)' : '') : '');
      tr.appendChild(el('td', 'ayuda', tercera || '—'));
      cuerpo.appendChild(tr);
    });
  }
})();
