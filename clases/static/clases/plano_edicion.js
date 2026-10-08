/* Guardar, deshacer y copiar un plano (fases 70 y 71). Una sola pieza para el
 * editor del grupo y para «Cambiar sitios» dentro de la clase.
 *
 * `plano` es un `Plano` en modo "editar"; esto le cuelga `onCambio` y habla
 * con el servidor. `cfg`:
 *   csrf, alumnado (para copiar del otro aula),
 *   urlGuardar(), urlRestaurar(id), urlOtra() — funciones, porque en clase
 *     el aula cambia sin recargar la página,
 *   el: { guardar, estado, motivo, errores, versiones } — nodos ya en la página,
 *   onAplicado(cuerpo) — opcional, tras guardar o restaurar.
 *
 * Las marcas de asistencia que tenga el plano se conservan al recargarlo: el
 * servidor no las manda al guardar, y en clase no pueden desaparecer.
 */
(function () {
  'use strict';

  var ORIGENES = { pantalla: 'en pantalla', api: 'por API', restaurar: 'restaurada' };

  function PlanoEdicion(plano, cfg) {
    var self = this;
    this.plano = plano;
    this.cfg = cfg;
    this.el = cfg.el;
    this.alumnado = cfg.alumnado || [];
    this.sucio = false;
    plano.o.onCambio = function () { self.marcarSucio(true); };
    this.marcarSucio(false);
  }

  PlanoEdicion.prototype.marcarSucio = function (valor) {
    this.sucio = valor;
    this.el.guardar.disabled = !valor;
    this.el.estado.textContent = valor ? 'Cambios sin guardar' : 'Guardado';
  };

  // Antes de cualquier cosa que tire los cambios pendientes.
  PlanoEdicion.prototype.puedoDescartar = function () {
    return !this.sucio || window.confirm('Tienes cambios sin guardar y se perderán. ¿Sigo?');
  };

  PlanoEdicion.prototype.errores = function (lista) {
    this.el.errores.classList.toggle('hidden', !lista);
    this.el.errores.hidden = !lista;
    this.el.errores.textContent = lista ? lista.join(' · ') : '';
  };

  PlanoEdicion.prototype.pintarVersiones = function (versiones) {
    var self = this, ul = this.el.versiones;
    ul.innerHTML = '';
    if (!versiones || !versiones.length) {
      ul.innerHTML = '<li class="plano-sin-versiones">Aún no se ha guardado nunca.</li>';
      return;
    }
    versiones.forEach(function (v, i) {
      var li = document.createElement('li');
      li.className = 'flex items-center gap-2';
      var fecha = new Date(v.fecha).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' });
      var texto = document.createElement('span');
      texto.textContent = fecha + ' · ' + (v.autor || '¿?') + ' ' + (ORIGENES[v.origen] || v.origen) + (v.motivo ? ' — ' + v.motivo : '');
      li.appendChild(texto);
      if (i === 0) {
        var actual = document.createElement('span');
        actual.className = 'badge badge-sm';
        actual.textContent = 'actual';
        li.appendChild(actual);
      } else {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn btn-xs';
        b.textContent = 'Volver a esta';
        b.onclick = function () { self.restaurar(v.id); };
        li.appendChild(b);
      }
      ul.appendChild(li);
    });
  };

  // Un 403 por sesión caducada o un 500 llegan en HTML: también se dicen.
  PlanoEdicion.prototype.recibir = function (r) {
    var self = this;
    return r.json().catch(function () { return {}; }).then(function (cuerpo) {
      if (!r.ok) {
        self.errores(cuerpo.errores || ['No se ha podido guardar (' + r.status + '). Si llevas rato con la página abierta, recárgala.']);
        throw new Error('rechazado');
      }
      return cuerpo;
    });
  };

  PlanoEdicion.prototype.sinConexion = function (e) {
    if (e && e.message !== 'rechazado') this.errores(['Sin conexión con el servidor: no se ha guardado.']);
  };

  // Datos del servidor (plano + alumnado + versiones) → pantalla.
  PlanoEdicion.prototype.aplicar = function (cuerpo) {
    this.errores(null);
    if (cuerpo.alumnado) this.alumnado = cuerpo.alumnado;
    this.plano.cargar(Object.assign({ asistencia: this.plano.asistencia }, cuerpo));
    this.pintarVersiones(cuerpo.versiones);
    this.marcarSucio(false);
    if (this.cfg.onAplicado) this.cfg.onAplicado(cuerpo);
  };

  PlanoEdicion.prototype.guardar = function () {
    var self = this;
    fetch(this.cfg.urlGuardar(), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.cfg.csrf },
      body: JSON.stringify({ disposicion: this.plano.disposicion, motivo: this.el.motivo.value }),
    }).then(function (r) { return self.recibir(r); }).then(function (cuerpo) {
      self.el.motivo.value = '';
      self.aplicar(cuerpo);
    }).catch(function (e) { self.sinConexion(e); });
  };

  PlanoEdicion.prototype.restaurar = function (id) {
    var self = this;
    if (!this.puedoDescartar()) return;
    fetch(this.cfg.urlRestaurar(id), {
      method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': this.cfg.csrf },
    }).then(function (r) { return self.recibir(r); }).then(function (c) { self.aplicar(c); })
      .catch(function (e) { self.sinConexion(e); });
  };

  // Trae las mesas del otro aula y deja los sitios como están allí. No guarda:
  // queda como cambio pendiente para retocarlo antes.
  PlanoEdicion.prototype.copiarDeLaOtra = function () {
    var self = this;
    fetch(this.cfg.urlOtra(), { credentials: 'same-origin' }).then(function (r) { return self.recibir(r); }).then(function (otra) {
      if (!otra.disposicion.mesas || !otra.disposicion.mesas.length) {
        self.errores(['El otro aula aún no tiene mesas']);
        return;
      }
      self.plano.cargar({ disposicion: otra.disposicion, alumnado: self.alumnado, asistencia: self.plano.asistencia });
      self.marcarSucio(true);
    }).catch(function (e) { self.sinConexion(e); });
  };

  window.PlanoEdicion = PlanoEdicion;
})();
