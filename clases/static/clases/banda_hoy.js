/* La banda de hoy (fase 92): el panel de la tecla B en la clase.
 *
 * Pinta lo que devuelve `clases:banda_hoy`: quién toca cada puesto, quién le
 * ayuda (o, el último día del turno, a quién enseña) y, si falta un titular,
 * a quién poner. Un toque acepta el sustituto propuesto. Toda regla vive en
 * `clases/banda.py`; aquí solo se pinta y se envía.
 */
(function () {
  var panel = document.getElementById('panel-banda');
  if (!panel) return;
  var cuerpo = panel.querySelector('#banda-tabla tbody');
  var eleccion = document.getElementById('banda-elegir');
  var datos = null;

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
    panel.classList.remove('abierto');
  };

  function traer() {
    fetch(panel.dataset.url, { credentials: 'same-origin' })
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
      body: JSON.stringify({ plaza: plaza, alumno: alumno }),
    })
      .then(function (r) { return r.json().then(function (c) { return { ok: r.ok, c: c }; }); })
      .then(function (res) {
        if (!res.ok) { aviso((res.c.errores || ['No se ha guardado.']).join(' ')); return; }
        pintar(res.c);
      })
      .catch(function () { aviso('Sin conexión: el cambio no se ha guardado.'); });
  }

  function cerrarEleccion() { eleccion.hidden = true; eleccion.innerHTML = ''; }

  function elegir(fila) {
    eleccion.innerHTML = '';
    eleccion.appendChild(el('div', 'pregunta', '¿Quién toca hoy ' + fila.etiqueta + '?'));
    var lista = el('div', 'opciones');
    if (!datos.libres.length) lista.appendChild(el('span', 'nadie', 'No queda nadie presente sin puesto.'));
    datos.libres.forEach(function (a) {
      var texto = a.nombre + ' (' + a.turnos + ')' + (a.fuera ? ' · xilófono' : '');
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
