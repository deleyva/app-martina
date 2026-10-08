/* Plano de clase (fase 70). Una sola pieza para dos pantallas:
 *
 *  - modo "editar": se arrastran mesas, la referencia y al alumnado entre
 *    plazas y la bandeja «sin sitio». No guarda solo: avisa con `onCambio`.
 *  - modo "lista": nada se arrastra; tocar a un alumno llama a `onTocar`.
 *
 * Todo va en unidades de la rejilla del servidor (`rejilla.ancho` x
 * `rejilla.alto`) y se pinta en porcentajes, así que el mismo plano encaja en
 * el portátil y en la pizarra. Eventos de puntero, que valen igual para ratón
 * y para dedo.
 *
 * `girado` (fase 71) es solo vista: el aula vista desde la pizarra, con los dos
 * ejes invertidos (180°). Lo guardado no cambia; las posiciones se reflejan al
 * pintar y al leer el puntero, y los nombres siguen derechos.
 */
(function () {
  'use strict';

  var PASO = 20;           // rejilla de encaje: así dos mesas se tocan del todo
  var REF_ANCHO = 160;
  var REF_ALTO = 40;
  var UMBRAL = 6;          // px antes de que un toque se considere arrastre

  function filasYColumnas(plazas, giro) {
    var filas = plazas <= 3 ? 1 : 2;
    var columnas = Math.ceil(plazas / filas);
    return giro === 90 ? [columnas, filas] : [filas, columnas];
  }

  function capitaliza(palabra) {
    palabra = palabra.toLocaleLowerCase('es');
    return palabra.charAt(0).toLocaleUpperCase('es') + palabra.slice(1);
  }

  // «LEO MIÑANA HERMOSO DE MENDOZA» → «Leo Miñana». Nombre y primer apellido
  // es lo que distingue a dos Valerias sin llenar la mesa de letras.
  function nombreCorto(nombre) {
    var partes = (nombre || '').trim().split(/\s+/).filter(Boolean).map(capitaliza);
    if (partes.length <= 2) return partes.join(' ');
    return partes[0] + ' ' + partes[1];
  }

  function encaja(v, max) {
    v = Math.round(v / PASO) * PASO;
    return Math.max(0, Math.min(max, v));
  }

  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto != null) e.textContent = texto;
    return e;
  }

  function Plano(contenedor, opciones) {
    this.c = contenedor;
    this.o = opciones;
    this.r = opciones.rejilla;
    this.modo = opciones.modo || 'editar';
    this.girado = !!opciones.girado;
    this.seleccion = null;
    this.cargar(opciones.datos);
  }

  Plano.prototype.cargar = function (datos) {
    this.disposicion = JSON.parse(JSON.stringify(datos.disposicion || { mesas: [] }));
    if (!this.disposicion.referencia) this.disposicion.referencia = { x: this.r.ancho / 2 - REF_ANCHO / 2, y: 20 };
    if (!this.disposicion.mesas) this.disposicion.mesas = [];
    this.alumnos = {};
    var self = this;
    (datos.alumnado || []).forEach(function (a) { self.alumnos[a.id] = a; });
    this.asistencia = datos.asistencia || {};
    this.pintar();
  };

  Plano.prototype.sentados = function () {
    var s = {};
    this.disposicion.mesas.forEach(function (m) {
      (m.ocupantes || []).forEach(function (o) { if (o) s[o] = true; });
    });
    return s;
  };

  Plano.prototype.sinSitio = function () {
    var s = this.sentados(), self = this;
    return Object.keys(this.alumnos).map(Number).filter(function (id) { return !s[id]; })
      .sort(function (a, b) { return self.alumnos[a].nombre.localeCompare(self.alumnos[b].nombre, 'es'); });
  };

  Plano.prototype.pct = function (v, total) { return (100 * v / total) + '%'; };

  Plano.prototype.pintar = function () {
    var self = this, r = this.r;
    this.c.innerHTML = '';
    this.c.classList.add('plano');
    this.c.lang = 'es';  // para que `hyphens: auto` sepa partir en castellano
    this.c.classList.toggle('plano-lista', this.modo === 'lista');
    this.c.classList.toggle('plano-girado', this.girado);

    var aula = el('div', 'plano-aula');
    aula.style.aspectRatio = r.ancho + ' / ' + r.alto;
    this.aula = aula;

    var ref = this.disposicion.referencia;
    var refEl = el('div', 'plano-ref', 'Pantalla · mesa del profesor');
    this.colocar(refEl, ref.x, ref.y, REF_ANCHO, REF_ALTO);
    if (this.modo === 'editar') this.arrastrable(refEl, 'ref', null);
    aula.appendChild(refEl);

    this.disposicion.mesas.forEach(function (mesa, i) { aula.appendChild(self.pintarMesa(mesa, i)); });
    this.c.appendChild(aula);

    var resto = this.sinSitio();
    if (this.modo === 'editar' || resto.length) {
      var bandeja = el('div', 'plano-bandeja');
      bandeja.dataset.bandeja = '1';
      bandeja.appendChild(el('div', 'plano-bandeja-titulo',
        resto.length ? 'Sin sitio (' + resto.length + ')' : 'Todo el grupo tiene sitio'));
      var fila = el('div', 'plano-bandeja-fila');
      resto.forEach(function (id) { fila.appendChild(self.pintarAlumno(id, null, null)); });
      bandeja.appendChild(fila);
      this.c.appendChild(bandeja);
    }
  };

  Plano.prototype.colocar = function (nodo, x, y, ancho, alto) {
    if (this.girado) { x = this.r.ancho - x - ancho; y = this.r.alto - y - alto; }
    nodo.style.left = this.pct(x, this.r.ancho);
    nodo.style.top = this.pct(y, this.r.alto);
    nodo.style.width = this.pct(ancho, this.r.ancho);
    nodo.style.height = this.pct(alto, this.r.alto);
  };

  Plano.prototype.medidas = function (mesa) {
    var fc = filasYColumnas(mesa.plazas, mesa.giro || 0);
    return { filas: fc[0], columnas: fc[1], ancho: fc[1] * this.r.plaza_ancho, alto: fc[0] * this.r.plaza_alto };
  };

  Plano.prototype.pintarMesa = function (mesa, i) {
    var self = this, m = this.medidas(mesa);
    var nodo = el('div', 'plano-mesa' + (this.seleccion === i ? ' seleccionada' : ''));
    nodo.dataset.mesa = i;
    this.colocar(nodo, mesa.x, mesa.y, m.ancho, m.alto);
    nodo.style.gridTemplateColumns = 'repeat(' + m.columnas + ', 1fr)';
    nodo.style.gridTemplateRows = 'repeat(' + m.filas + ', 1fr)';
    for (var k = 0; k < mesa.plazas; k++) {
      // Girado, el orden de las plazas al revés es la mesa vista desde enfrente.
      var p = this.girado ? mesa.plazas - 1 - k : k;
      var plaza = el('div', 'plano-plaza');
      plaza.dataset.mesa = i;
      plaza.dataset.plaza = p;
      var id = (mesa.ocupantes || [])[p];
      if (id && this.alumnos[id]) plaza.appendChild(this.pintarAlumno(id, i, p));
      nodo.appendChild(plaza);
    }
    if (this.modo === 'editar') {
      this.arrastrable(nodo, 'mesa', i);
      if (this.seleccion === i) nodo.appendChild(this.barraDeMesa(i));
    }
    return nodo;
  };

  Plano.prototype.pintarAlumno = function (id, mesa, plaza) {
    var a = this.alumnos[id];
    var chip = el('div', 'plano-alumno');
    chip.dataset.alumno = id;
    chip.title = a.nombre;
    chip.appendChild(el('span', 'plano-nombre', nombreCorto(a.nombre)));
    var marca = this.asistencia[id];
    if (marca) {
      if (marca.estado === 'falta') chip.classList.add('falta');
      if (marca.estado === 'retraso') {
        chip.classList.add('retraso');
        chip.appendChild(el('span', 'plano-hora', marca.hora));
      }
      if (marca.sin_material && marca.sin_material.length) {
        chip.appendChild(el('span', 'plano-material', 'sin ' + marca.sin_material.join(', ')));
      }
      if (marca.nota) chip.classList.add('con-nota');
    }
    if (this.modo === 'editar') {
      this.arrastrable(chip, 'alumno', { id: id, mesa: mesa, plaza: plaza });
    } else {
      var self = this;
      chip.setAttribute('role', 'button');
      chip.addEventListener('click', function (e) {
        e.stopPropagation();
        if (self.o.onTocar) self.o.onTocar(id, chip);
      });
    }
    return chip;
  };

  Plano.prototype.barraDeMesa = function (i) {
    var self = this, mesa = this.disposicion.mesas[i];
    var barra = el('div', 'plano-barra');
    function boton(texto, titulo, accion) {
      var b = el('button', '', texto);
      b.type = 'button';
      b.title = titulo;
      b.addEventListener('pointerdown', function (e) { e.stopPropagation(); });
      b.addEventListener('click', function (e) { e.stopPropagation(); accion(); self.cambio(); });
      barra.appendChild(b);
    }
    boton('⟳', 'Girar', function () { mesa.giro = mesa.giro === 90 ? 0 : 90; });
    boton('+', 'Una plaza más', function () {
      if (mesa.plazas < 6) { mesa.plazas++; mesa.ocupantes.push(null); }
    });
    boton('−', 'Una plaza menos (quien estaba en la última pasa a «sin sitio»)', function () {
      if (mesa.plazas > 1) { mesa.plazas--; mesa.ocupantes = mesa.ocupantes.slice(0, mesa.plazas); }
    });
    boton('🗑', 'Quitar la mesa (su alumnado pasa a «sin sitio»)', function () {
      self.disposicion.mesas.splice(i, 1);
      self.seleccion = null;
    });
    return barra;
  };

  // --- Arrastrar -------------------------------------------------------------

  Plano.prototype.aUnidades = function (clientX, clientY) {
    var rect = this.aula.getBoundingClientRect();
    var x = (clientX - rect.left) / rect.width * this.r.ancho;
    var y = (clientY - rect.top) / rect.height * this.r.alto;
    return this.girado ? { x: this.r.ancho - x, y: this.r.alto - y } : { x: x, y: y };
  };

  Plano.prototype.arrastrable = function (nodo, tipo, dato) {
    var self = this;
    nodo.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      e.stopPropagation();
      e.preventDefault();
      var inicio = { x: e.clientX, y: e.clientY };
      var origen = self.aUnidades(e.clientX, e.clientY);
      var base = tipo === 'ref' ? self.disposicion.referencia
        : tipo === 'mesa' ? self.disposicion.mesas[dato] : null;
      var baseXY = base ? { x: base.x, y: base.y } : null;
      var moviendo = false, fantasma = null;

      function mover(ev) {
        if (!moviendo && Math.hypot(ev.clientX - inicio.x, ev.clientY - inicio.y) < UMBRAL) return;
        moviendo = true;
        if (tipo === 'alumno') {
          if (!fantasma) {
            fantasma = nodo.cloneNode(true);
            fantasma.classList.add('plano-fantasma');
            fantasma.style.width = nodo.getBoundingClientRect().width + 'px';
            document.body.appendChild(fantasma);
            nodo.classList.add('plano-origen');
          }
          fantasma.style.left = ev.clientX + 'px';
          fantasma.style.top = ev.clientY + 'px';
          return;
        }
        var ahora = self.aUnidades(ev.clientX, ev.clientY);
        var ancho = tipo === 'ref' ? REF_ANCHO : self.medidas(base).ancho;
        var alto = tipo === 'ref' ? REF_ALTO : self.medidas(base).alto;
        base.x = Math.max(0, Math.min(self.r.ancho - ancho, baseXY.x + ahora.x - origen.x));
        base.y = Math.max(0, Math.min(self.r.alto - alto, baseXY.y + ahora.y - origen.y));
        self.colocar(nodo, base.x, base.y, ancho, alto);
      }

      function soltar(ev) {
        document.removeEventListener('pointermove', mover);
        document.removeEventListener('pointerup', soltar);
        document.removeEventListener('pointercancel', soltar);
        if (fantasma) fantasma.remove();
        if (!moviendo) {
          if (tipo === 'mesa') { self.seleccion = self.seleccion === dato ? null : dato; self.pintar(); }
          return;
        }
        if (tipo === 'alumno') {
          var debajo = document.elementFromPoint(ev.clientX, ev.clientY);
          self.soltarAlumno(dato, debajo);
        } else {
          var ancho = tipo === 'ref' ? REF_ANCHO : self.medidas(base).ancho;
          var alto = tipo === 'ref' ? REF_ALTO : self.medidas(base).alto;
          base.x = encaja(base.x, self.r.ancho - ancho);
          base.y = encaja(base.y, self.r.alto - alto);
        }
        self.cambio();
      }

      document.addEventListener('pointermove', mover);
      document.addEventListener('pointerup', soltar);
      document.addEventListener('pointercancel', soltar);
    });
  };

  // Soltar en una plaza: si está ocupada, se cambian los sitios. En la bandeja:
  // se queda sin sitio. En cualquier otra parte: no pasa nada.
  Plano.prototype.soltarAlumno = function (dato, debajo) {
    if (!debajo) return;
    var plaza = debajo.closest('.plano-plaza');
    var mesas = this.disposicion.mesas;
    if (plaza && this.c.contains(plaza)) {
      var mi = Number(plaza.dataset.mesa), pi = Number(plaza.dataset.plaza);
      if (dato.mesa === mi && dato.plaza === pi) return;
      var ocupante = mesas[mi].ocupantes[pi] || null;
      mesas[mi].ocupantes[pi] = dato.id;
      if (dato.mesa !== null) mesas[dato.mesa].ocupantes[dato.plaza] = ocupante;
      return;
    }
    if (debajo.closest('[data-bandeja]') && dato.mesa !== null) {
      mesas[dato.mesa].ocupantes[dato.plaza] = null;
    }
  };

  Plano.prototype.cambio = function () {
    this.pintar();
    if (this.o.onCambio) this.o.onCambio(this.disposicion);
  };

  // Una mesa nueva va al primer hueco libre de la rejilla, de delante atrás.
  Plano.prototype.anadirMesa = function (plazas) {
    var r = this.r, self = this;
    var nueva = { id: 'm' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), x: 0, y: 0, plazas: plazas, giro: 0, ocupantes: [] };
    for (var k = 0; k < plazas; k++) nueva.ocupantes.push(null);
    var m = this.medidas(nueva);
    var ocupado = this.disposicion.mesas.map(function (o) {
      var mo = self.medidas(o); return { x: o.x, y: o.y, a: mo.ancho, h: mo.alto };
    });
    var ref = this.disposicion.referencia;
    ocupado.push({ x: ref.x, y: ref.y, a: REF_ANCHO, h: REF_ALTO });
    buscar:
    for (var y = 100; y <= r.alto - m.alto; y += PASO) {
      for (var x = 20; x <= r.ancho - m.ancho; x += PASO) {
        var libre = ocupado.every(function (o) {
          return x + m.ancho + PASO <= o.x || o.x + o.a + PASO <= x || y + m.alto + PASO <= o.y || o.y + o.h + PASO <= y;
        });
        if (libre) { nueva.x = x; nueva.y = y; break buscar; }
      }
    }
    this.disposicion.mesas.push(nueva);
    this.seleccion = this.disposicion.mesas.length - 1;
    this.cambio();
  };

  // En clase se pasa de pasar lista a cambiar sitios sin rehacer el plano.
  Plano.prototype.ponerModo = function (modo) {
    this.modo = modo;
    this.seleccion = null;
    this.pintar();
  };

  Plano.prototype.ponerGirado = function (girado) {
    this.girado = !!girado;
    this.pintar();
  };

  Plano.prototype.marcar = function (id, asistencia) {
    if (asistencia) this.asistencia[id] = asistencia; else delete this.asistencia[id];
    this.pintar();
  };

  window.Plano = Plano;
  window.Plano.nombreCorto = nombreCorto;
})();
