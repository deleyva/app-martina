// La pantalla no se apaga ni se atenúa mientras la app está abierta (petición
// de Jesús, 2026-10-04): en clase la tablet se queda en el atril o proyectando,
// y que se bloquee a mitad de una lectura corta la clase.
//
// Screen Wake Lock API. No sube ni fija el brillo, eso solo lo hace el
// sistema; lo que evita es que la pantalla se oscurezca y se apague sola.
//
// Lo que corrige frente a la receta habitual (la que propuso Gemini):
//   - Si la primera petición falla, se reintenta al primer toque. Safari puede
//     rechazarla si la página se carga sin que el usuario la haya tocado, y la
//     receta solo reintentaba cuando ya tenía un bloqueo.
//   - El sistema suelta el bloqueo al cambiar de pestaña o bloquear el
//     dispositivo; al volver se pide otra vez si está suelto (`released`), no
//     solo si existe.
//   - Sin la API (navegadores viejos) o fuera de HTTPS no hace nada ni rompe.
(function () {
  if (!('wakeLock' in navigator)) return;

  var bloqueo = null;
  var pidiendo = false;

  function activo() {
    return bloqueo !== null && !bloqueo.released;
  }

  function pedir() {
    if (pidiendo || activo() || document.visibilityState !== 'visible') return;
    pidiendo = true;
    navigator.wakeLock.request('screen')
      .then(function (b) {
        bloqueo = b;
        b.addEventListener('release', function () {
          // Lo ha soltado el sistema. Si la página se sigue viendo (p. ej.
          // ahorro de batería), se vuelve a intentar al siguiente toque.
          if (bloqueo === b) bloqueo = null;
        });
      })
      .catch(function (e) {
        // Rechazado (sin gesto del usuario, batería baja…): se reintentará.
        console.debug('Pantalla encendida: no concedido (' + e.name + ')');
      })
      .then(function () { pidiendo = false; });
  }

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') pedir();
  });
  // Cada toque o tecla es una ocasión de recuperarlo si se perdió. `pedir` no
  // hace nada si ya está activo, así que no cuesta nada.
  ['pointerdown', 'keydown'].forEach(function (evento) {
    document.addEventListener(evento, pedir, { capture: true, passive: true });
  });

  pedir();

  // Para comprobarlo desde la consola.
  window.pantallaEncendida = activo;
})();
