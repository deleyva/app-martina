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

  // Nuevo manejador para elementos con data-post y data-trigger (checkboxes, inputs, etc.)
  document.addEventListener('change', function(event) {
    const element = event.target;
    
    // Verificar si el elemento tiene el atributo data-post y data-trigger="change"
    if (element.hasAttribute('data-post') && element.getAttribute('data-trigger') === 'change') {
      const postUrl = element.getAttribute('data-post');
      const target = element.getAttribute('data-target');
      const swap = element.getAttribute('data-swap') || 'innerHTML';
      
      // Obtener los valores a enviar
      let postData = new FormData();
      let valsData = {};
      
      if (element.hasAttribute('data-vals')) {
        try {
          // Obtener el objeto JSON de data-vals y procesarlo
          valsData = JSON.parse(element.getAttribute('data-vals'));
          
          // Reemplazar cualquier placeholder como CHECKED_VALUE con los valores reales
          Object.keys(valsData).forEach(key => {
            if (valsData[key] === 'CHECKED_VALUE') {
              valsData[key] = element.checked ? 'true' : 'false';
            }
            postData.append(key, valsData[key]);
          });
        } catch (e) {
          console.error('Error al procesar data-vals:', e);
        }
      }
      
      // Realizar la petición POST
      fetch(postUrl, {
        method: 'POST',
        body: postData,
        headers: {
          'X-CSRFToken': window.dataStarConfig.headers['X-CSRFToken']
        }
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text();
      })
      .then(html => {
        // Si swap no es "none", actualizar el objetivo con la respuesta
        if (swap !== 'none' && target) {
          const targetElement = document.querySelector(target);
          if (targetElement) {
            if (swap === 'innerHTML') {
              targetElement.innerHTML = html;
            } else if (swap === 'outerHTML') {
              targetElement.outerHTML = html;
            }
          }
        }
      })
      .catch(error => {
        console.error('Error en la petición data-post:', error);
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
