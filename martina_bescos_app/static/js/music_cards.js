/* Music Cards specific JavaScript */

// Función para inicializar ABCJS cuando esté disponible
function initializeABCJS() {
  console.log('Attempting to initialize ABCJS...');
  
  if (typeof ABCJS !== 'undefined') {
    console.log('ABCJS loaded successfully, version:', ABCJS.signature);
    
    // Buscar contenedores ABC
    const containers = document.querySelectorAll('.abc-notation-container');
    console.log('Found', containers.length, 'ABC containers');
    
    // Renderizar todas las notaciones ABC existentes en la página
    containers.forEach(function(container, index) {
      const abcContent = container.getAttribute('data-abc-content');
      console.log('Container', index + 1, '- ID:', container.id, '- Content length:', abcContent ? abcContent.length : 0);
      
      if (abcContent && abcContent.trim() !== '') {
        try {
          console.log('Rendering ABC for container:', container.id);
          console.log('ABC Content preview:', abcContent.substring(0, 100) + '...');
          
          const result = ABCJS.renderAbc(container.id, abcContent, {
            viewportHorizontal: true,
            scrollHorizontal: true,
            responsive: "resize",
            scale: 0.8,
            staffwidth: 400
          });
          
          console.log('Render result:', result);
          
          // Verificar si se creó contenido SVG
          const svgElements = container.querySelectorAll('svg');
          console.log('SVG elements created:', svgElements.length);
          
        } catch (error) {
          console.error('Error rendering ABC notation for', container.id, ':', error);
        }
      } else {
        console.warn('No ABC content found for container:', container.id);
      }
    });
  } else {
    console.error('ABCJS not loaded, retrying in 500ms...');
    // Intentar de nuevo en 500ms
    setTimeout(initializeABCJS, 500);
  }
}

// Función para renderizar una notación ABC específica
function renderABCNotation(containerId, abcContent, options = {}) {
  if (typeof ABCJS === 'undefined') {
    console.error('ABCJS not loaded');
    return;
  }
  
  const defaultOptions = {
    viewportHorizontal: true,
    scrollHorizontal: true,
    responsive: "resize"
  };
  
  const finalOptions = Object.assign(defaultOptions, options);
  
  try {
    ABCJS.renderAbc(containerId, abcContent, finalOptions);
  } catch (error) {
    console.error('Error rendering ABC notation:', error);
  }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
  // Esperar un poco para asegurar que ABCJS se ha cargado
  setTimeout(initializeABCJS, 100);
});

// También inicializar después de peticiones HTMX
document.addEventListener('htmx:afterSwap', function() {
  setTimeout(initializeABCJS, 100);
});

// Función de test para probar ABCJS manualmente
function testABCJS() {
  console.log('Testing ABCJS...');
  
  // Crear un contenedor de prueba
  const testContainer = document.createElement('div');
  testContainer.id = 'test-abc-container';
  testContainer.style.border = '2px solid red';
  testContainer.style.padding = '10px';
  testContainer.style.margin = '10px';
  document.body.appendChild(testContainer);
  
  // Notación ABC simple de prueba
  const testABC = `X:1
T:Test Song
M:4/4
L:1/4
K:C
C D E F | G A B c |`;
  
  console.log('Test ABC content:', testABC);
  
  try {
    const result = ABCJS.renderAbc('test-abc-container', testABC, {
      scale: 1.0,
      staffwidth: 400
    });
    console.log('Test render result:', result);
  } catch (error) {
    console.error('Test render error:', error);
  }
}

// Exportar funciones para uso global
window.renderABCNotation = renderABCNotation;
window.initializeABCJS = initializeABCJS;
window.testABCJS = testABCJS;
