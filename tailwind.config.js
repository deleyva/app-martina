/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      './martina_bescos_app/templates/**/*.html', // Escanea plantillas HTML
      './martina_bescos_app/**/*.py',          // Escanea archivos Python (si usas clases en vistas, etc.)
      './martina_bescos_app/static/js/**/*.js',   // Escanea archivos JS (si añades clases dinámicamente)
      // Añade aquí cualquier otra ruta donde uses clases de Tailwind/DaisyUI
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