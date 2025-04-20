/* Project specific Javascript goes here. */

// Configuración de data-star.dev para reemplazar la funcionalidad de HTMX
document.addEventListener('DOMContentLoaded', function() {
  // Configuración global para data-star
  window.dataStarConfig = {
    headers: {
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
    }
  };

  // Manejador para formularios que usan data-star
  document.addEventListener('submit', function(event) {
    const form = event.target;
    
    // Verificar si el formulario tiene atributos data-star
    if (form.hasAttribute('data-path')) {
      event.preventDefault();
      
      const path = form.getAttribute('data-path');
      const method = form.getAttribute('data-method') || 'GET';
      const target = form.getAttribute('data-target');
      const replace = form.getAttribute('data-replace') || 'innerHTML';
      
      // Construir los parámetros de la solicitud
      const formData = new FormData(form);
      let url = path;
      
      if (method === 'GET') {
        // Convertir FormData a URLSearchParams para solicitudes GET
        const params = new URLSearchParams();
        for (const [key, value] of formData.entries()) {
          params.append(key, value);
        }
        url = `${path}?${params.toString()}`;
      }
      
      // Realizar la solicitud
      fetch(url, {
        method: method,
        body: method !== 'GET' ? formData : undefined,
        headers: {
          'X-CSRFToken': window.dataStarConfig.headers['X-CSRFToken']
        }
      })
      .then(response => response.text())
      .then(html => {
        // Actualizar el objetivo con la respuesta
        if (target) {
          const targetElement = document.querySelector(target);
          if (targetElement) {
            if (replace === 'innerHTML') {
              targetElement.innerHTML = html;
            } else if (replace === 'outerHTML') {
              targetElement.outerHTML = html;
            }
          }
        }
      })
      .catch(error => {
        console.error('Error en la petición data-star:', error);
      });
    }
  });
  
  // Theme toggler para DaisyUI 5
  const themeToggler = document.getElementById('theme-toggle');
  if (themeToggler) {
    const checkboxInput = themeToggler.querySelector('input[type="checkbox"]');
    
    // Inicializar el estado del checkbox según el tema actual
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    checkboxInput.checked = currentTheme === 'dark';
    
    // Escuchar cambios en el checkbox
    checkboxInput.addEventListener('change', function() {
      const newTheme = this.checked ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
    });
  }
});
