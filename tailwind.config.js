/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      './martina_bescos_app/templates/**/*.html',
      './cms/templates/**/*.html',
      './clases/templates/**/*.html',
      './my_library/templates/**/*.html',
      './incidencias/templates/**/*.html',
      './content_hub/templates/**/*.html',
      './martina_bescos_app/**/*.py',
      './martina_bescos_app/static/js/**/*.js',
    ],
    theme: {
      extend: {},
    },
    plugins: [
      require('daisyui'), // Asegúrate de que DaisyUI esté listado como plugin
    ],
    // Configuración específica de DaisyUI (opcional)
    daisyui: {
      themes: ["light", "dark"], // O los temas que quieras usar
      logs: true, // Muestra logs de DaisyUI en desarrollo (útil para depurar)
    },
  }