// Transportar una tablatura de alphaTab de verdad: tablatura, pentagrama y
// sonido en el tono nuevo.
//
// Por qué no basta `notation.transpositionPitches` de alphaTab: ese ajuste
// cambia la nota que suena y la del pentagrama, pero el número de traste sale
// del dato (`note.fret`) y la tablatura seguiría diciendo lo mismo. Un alumno
// leería un traste y oiría otro (comprobado en el código de alphaTab 1.8.4,
// `Note.calculateRealValue`, 2026-09-26).
//
// Se decide pista a pista, como lo haría un guitarrista:
//
// 1. Mover trastes. Cada nota va a su tono nuevo en la misma cuerda si cabe
//    (0–24) o en la cuerda libre más cercana de ese golpe. Subiendo casi
//    siempre funciona: es lo que hace una cejilla.
// 2. Si en esa pista alguna nota no cabe —bajando es lo normal: un Mi grave al
//    aire no puede bajar medio tono, y un acorde abierto de seis notas no tiene
//    cuerdas libres (Perfect, −1: 160 notas sin sitio)—, la pista conserva sus
//    trastes y cambia su AFINACIÓN. Es lo que hace un guitarrista para bajar
//    de tono: misma digitación, cuerdas más graves. La partitura lo dice en el
//    nombre de la afinación.
//
// Siempre se parte de lo ORIGINAL (trastes, cuerdas y afinación), así que
// subir y bajar no acumula desplazamientos.
//
// Lo usan `musica/recurso.html` y `my_library/viewers/gp_viewer.html`.
(function () {
  var TRASTE_MAX = 24;

  function notasDeCuerda(staff, fn) {
    staff.bars.forEach(function (bar) {
      bar.voices.forEach(function (voice) {
        voice.beats.forEach(function (beat) {
          var notas = beat.notes.filter(function (n) { return n.isStringed; });
          if (notas.length) fn(beat, notas);
        });
      });
    });
  }

  function guardarOriginal(staff) {
    if (staff.__afinacionOriginal) return;
    staff.__afinacionOriginal = staff.stringTuning.tunings.slice();
    staff.__nombreAfinacion = staff.stringTuning.name;
    staff.__afinacionEstandar = staff.stringTuning.isStandard;
    notasDeCuerda(staff, function (beat, notas) {
      notas.forEach(function (n) {
        n.__trasteOriginal = n.fret;
        n.__cuerdaOriginal = n.string;
      });
    });
  }

  function restaurar(staff) {
    var t = staff.stringTuning;
    t.tunings.length = 0;
    staff.__afinacionOriginal.forEach(function (x) { t.tunings.push(x); });
    t.name = staff.__nombreAfinacion;
    t.isStandard = staff.__afinacionEstandar;
    notasDeCuerda(staff, function (beat, notas) {
      notas.forEach(function (n) {
        n.fret = n.__trasteOriginal;
        n.string = n.__cuerdaOriginal;
      });
    });
  }

  // Altura (MIDI) al aire de la cuerda `s` (1 = la más grave), con cejilla.
  function alAire(staff, s) {
    var t = staff.__afinacionOriginal;
    return (staff.capo || 0) + t[t.length - s];
  }

  // Intenta mover trastes en todo el pentagrama. Devuelve false en cuanto una
  // nota no cabe; el llamador restaura y cambia la afinación.
  function moverTrastes(staff, semitonos) {
    var n = staff.__afinacionOriginal.length;
    var ok = true;
    notasDeCuerda(staff, function (beat, notas) {
      if (!ok) return;
      var ocupadas = {};
      // Primero las que pueden quedarse en su cuerda, para que no se la quite
      // otra nota del mismo acorde.
      var orden = notas.slice().sort(function (a, b) {
        var fa = a.__trasteOriginal + semitonos, fb = b.__trasteOriginal + semitonos;
        return (fa >= 0 && fa <= TRASTE_MAX ? 0 : 1) - (fb >= 0 && fb <= TRASTE_MAX ? 0 : 1);
      });
      for (var j = 0; j < orden.length && ok; j++) {
        var nota = orden[j];
        var s0 = nota.__cuerdaOriginal;
        var altura = alAire(staff, s0) + nota.__trasteOriginal + semitonos;
        var candidatas = [s0];
        for (var d = 1; d < n; d++) {
          if (s0 - d >= 1) candidatas.push(s0 - d);
          if (s0 + d <= n) candidatas.push(s0 + d);
        }
        var colocada = false;
        for (var i = 0; i < candidatas.length; i++) {
          var s = candidatas[i];
          var traste = altura - alAire(staff, s);
          if (!ocupadas[s] && traste >= 0 && traste <= TRASTE_MAX) {
            nota.string = s;
            nota.fret = traste;
            ocupadas[s] = true;
            colocada = true;
            break;
          }
        }
        if (!colocada) ok = false;
      }
    });
    return ok;
  }

  function nombreNota(midi) {
    return ['Do', 'Re♭', 'Re', 'Mi♭', 'Mi', 'Fa', 'Sol♭', 'Sol', 'La♭', 'La', 'Si♭', 'Si'][((midi % 12) + 12) % 12];
  }

  function cambiarAfinacion(staff, semitonos) {
    var t = staff.stringTuning;
    t.tunings.length = 0;
    staff.__afinacionOriginal.forEach(function (x) { t.tunings.push(x + semitonos); });
    t.isStandard = false;
    // De la más grave a la más aguda, como se nombran las afinaciones.
    t.name = 'Afinación ' + (semitonos > 0 ? '+' : '−') + Math.abs(semitonos) + ': ' +
      t.tunings.slice().reverse().map(nombreNota).join(' ');
  }

  // Aplica `semitonos` (respecto al original) a todas las pistas de cuerda.
  // Devuelve `{afinacion}`: cuántos pentagramas cambiaron de afinación en vez
  // de mover trastes.
  function transportar(api, semitonos) {
    var score = api.score;
    var resultado = { afinacion: 0 };
    if (!score) return resultado;
    score.tracks.forEach(function (track) {
      track.staves.forEach(function (staff) {
        // Solo pentagramas de cuerda. La percusión también trae afinación en
        // los .gp, pero sus «trastes» eligen el instrumento de la batería.
        if (staff.isPercussion || track.isPercussion) return;
        if (!staff.stringTuning || !staff.stringTuning.tunings.length) return;
        guardarOriginal(staff);
        restaurar(staff);
        if (!semitonos) return;
        if (!moverTrastes(staff, semitonos)) {
          restaurar(staff);
          cambiarAfinacion(staff, semitonos);
          resultado.afinacion++;
        }
      });
    });
    // El renderizador trabaja en un Worker con su propia copia de la
    // partitura: hay que mandársela otra vez, no basta `render()`. Y el MIDI
    // se genera al cargar: sin regenerarlo, sonaría el tono de antes.
    api.renderScore(score, api.tracks.map(function (t) { return t.index; }));
    api.loadMidiForScore();
    return resultado;
  }

  function etiqueta(semitonos) {
    if (!semitonos) return 'Tono original';
    return (semitonos > 0 ? '+' : '') + semitonos + (Math.abs(semitonos) === 1 ? ' semitono' : ' semitonos');
  }

  function aviso(resultado) {
    if (!resultado.afinacion) return '';
    return resultado.afinacion + (resultado.afinacion === 1 ? ' pista cambia' : ' pistas cambian') +
      ' de afinación en vez de trastes (los trastes no cabían en el mástil)';
  }

  window.TransportarTablatura = { transportar: transportar, etiqueta: etiqueta, aviso: aviso };
})();
