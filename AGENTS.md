# Guía para Agentes de IA - Martina Bescós App

Este documento contiene las reglas y preferencias que deben seguir los agentes de IA al trabajar en este proyecto Django.

## Tabla de Contenidos

-   [Filosofía General](#filosofía-general)
-   [Arquitectura Backend (Django)](#arquitectura-backend-django)
-   [Frontend (Tailwind CSS, DaisyUI y HTMX)](#frontend-tailwind-css-daisyui-y-htmx)
-   [Estructura de Archivos](#estructura-de-archivos)
-   [Herramientas y Formateo](#herramientas-y-formateo)
-   [Referencias de forScore](#referencias-de-forscore)

* * *

## Filosofía General

### Principios de Desarrollo

-   **Experiencia**: Actúa como un programador experto en Django que valora la simplicidad y la eficiencia
-   **Estilo de código**: Sigue estrictamente la guía PEP 8 para todo el código Python
-   **Legibilidad primero**: Prioriza la legibilidad y la claridad sobre la optimización prematura
-   **Modularidad**: Escribe código modular, manteniendo las responsabilidades bien separadas en cada aplicación Django

* * *

## Arquitectura Backend (Django)

### Patrón "Tiny Views - Fat Models"

**IMPORTANTE**: Este patrón debe aplicarse estrictamente en todo el código.

#### Fat Models (Modelos Robustos)

Toda la lógica de negocio debe residir en los modelos:

-   **Consultas complejas (QuerySets)**: Implementar en `models.py` o en managers personalizados
-   **Manipulación de datos**: Los métodos de modelo deben manejar toda la lógica de transformación
-   **Validación de negocio**: Las reglas de negocio pertenecen a los modelos
-   **Métodos auxiliares**: Cualquier lógica reutilizable debe estar en el modelo

#### Tiny Views (Vistas Delgadas)

Las vistas deben ser extremadamente delgadas:

-   **Única responsabilidad**: Conectar peticiones HTTP con la lógica del modelo y renderizar la plantilla
-   **Sin lógica de negocio**: Nunca colocar lógica de negocio en las vistas
-   **Orquestación simple**: Solo coordinar llamadas a métodos del modelo

### Vistas Basadas en Funciones vs Clases

**PREFERENCIA**: Siempre usa **Vistas Basadas en Funciones (Function Views)** sobre Vistas Basadas en Clases (CBVs)

**Razones**:

-   Mayor explicitud
-   Mayor sencillez
-   Más fácil de entender y mantener

### Entorno de Desarrollo

-   **Docker**: Todo el desarrollo y despliegue se realiza usando Docker
-   **Just**: Usar `just` para ejecutar comandos (ver `.justfile` en la raíz del proyecto)
-   **Comandos comunes**:
    -   `just manage <comando>`: Ejecutar comandos de Django
    -   Ver `.justfile` para todos los comandos disponibles

* * *

## Frontend (Tailwind CSS, DaisyUI y HTMX)

### Stack de Frontend

#### Tailwind CSS

-   **Framework principal** para toda la estilización
-   **Utility-first approach**: Usar clases de utilidad directamente en el HTML
-   **Configuración**: `tailwind.config.js` en la raíz del proyecto
-   **CSS compilado**: Se encuentra en `static/css/dist/`

#### DaisyUI 5.0

-   **Plugin de Tailwind** para componentes predefinidos
-   **Componentes disponibles**: Botones, cards, modales, badges, etc.
-   **Objetivo**: Acelerar el desarrollo de la interfaz sin escribir CSS custom
-   **Documentación**: <https://daisyui.com/>

#### HTMX

-   **Filosofía principal**: La interactividad del frontend se gestiona **completamente con HTMX**
-   **Objetivo**: Mejorar el HTML directamente desde el backend
-   **Integración**: Usar <https://github.com/adamchainz/django-htmx>

### Reglas Importantes de Frontend

#### ❌ Evitar JavaScript Custom

-   **Mínimo JavaScript**: Evita escribir bloques de JavaScript personalizados
-   **Lógica en el backend**: La lógica debe residir en el backend y ser activada mediante atributos `hx-*`
-   **Excepciones**: Solo usar JavaScript cuando HTMX no pueda manejar la funcionalidad (ej: librerías de renderizado musical)

#### ❌ NO Usar Alpine.js

-   **Prohibido**: No se utiliza Alpine.js en este proyecto
-   **Alternativa**: Cualquier necesidad de manipulación ligera del DOM debe resolverse con HTMX y respuestas HTML desde el servidor
-   **Razón**: Mantener la arquitectura simple y server-side

#### ✅ Patrón Preferido para Funcionalidades

1.  **Crear endpoint Django** que procese la lógica
2.  **Devolver HTML parcial** desde el endpoint
3.  **Usar atributos HTMX** para hacer la llamada y el swap (`hx-post`, `hx-get`, `hx-target`, `hx-swap`)
4.  **Mínimo o cero JavaScript** custom

**Ejemplo**:

```html
<!-- ✅ CORRECTO: Usar HTMX -->
<button hx-post="/api/convert-chordpro/" 
        hx-target="#content" 
        hx-swap="outerHTML">
    Convertir
</button>

<!-- ❌ INCORRECTO: Interceptar con JavaScript -->
<button onclick="convertChordPro()">
    Convertir
</button>
```

* * *

## Estructura de Archivos

### Organización de Apps Django

Cada aplicación Django sigue esta estructura:

```plaintext
[nombre_app]/
├── models.py          # Lógica de negocio y modelos (FAT)
├── views.py           # Vistas delgadas basadas en funciones (TINY)
├── urls.py            # Configuración de URLs
├── admin.py           # Configuración del admin
├── forms.py           # Formularios (si son necesarios)
├── templates/         # Plantillas HTML
│   └── [nombre_app]/  # Subdirectorio con el nombre de la app
├── static/            # Archivos estáticos (si son necesarios)
└── migrations/        # Migraciones de base de datos
```

### Ubicaciones Clave

-   **Modelos y lógica de negocio**: `[nombre_app]/models.py`
-   **Vistas delgadas**: `[nombre_app]/views.py`
-   **Plantillas Django**: `templates/[nombre_app]/`
    -   Enriquecidas con clases de Tailwind/DaisyUI
    -   Atributos HTMX para interactividad
-   **URLs**: `[nombre_app]/urls.py`
-   **Config de Tailwind**: `tailwind.config.js` (raíz del proyecto)
-   **CSS compilado**: `static/css/dist/`

* * *

## Herramientas y Formateo

### Formateo de Código

#### Python: Black

-   **Herramienta**: Black (<https://github.com/psf/black>)
-   **Uso**: Formateo automático del código Python
-   **Comando**: `black .` o configurar en el editor

#### HTML: djhtml

-   **Herramienta**: djhtml (<https://github.com/rtts/djhtml>)
-   **Uso**: Formatear las plantillas HTML de Django
-   **Comando**: `djhtml templates/`

### Desarrollo en Vivo

-   **django-browser-reload**: Recomendado para desarrollo en vivo
-   **Tailwind watch**: Proceso "watch" de Tailwind para compilación automática
-   **Comando típico**: `npm run dev` o similar (ver `package.json`)

* * *

## Referencias de forScore

Este proyecto implementa funcionalidades inspiradas en **forScore**, una aplicación profesional de partituras digitales para músicos.

### Conceptos Clave de forScore

-   **Biblioteca de partituras**: Gestión de PDFs musicales
-   **Anotaciones**: Markup sobre partituras
-   **Setlists**: Listas de reproducción organizadas
-   **Bookmarks**: Marcadores dentro de PDFs
-   **Metadatos**: Compositor, género, dificultad, tempo, etc.
-   **Audio vinculado**: Pistas de audio asociadas a partituras
-   **Modo de performance**: Visualización pantalla completa

### Documentación Incluida

El archivo `.windsurfrules` contiene una versión parseada automáticamente del manual de forScore 15.0 (líneas 52-133). Este texto puede contener typos debido al parsing automático - debes ignorar los typos y reconstruir el significado.

**Secciones principales del manual**:

-   Getting Started / Basics
-   Adding Files / File Management
-   Menus and Navigation
-   Scores and Libraries
-   Bookmarks (page vs item bookmarks)
-   Setlists
-   Metadata
-   Audio Integration
-   Search
-   Tools (Annotate, Links, Buttons, Rearrange, Crop, Share, etc.)
-   Apple Pencil Support

* * *

## Resumen de Reglas Críticas

### ✅ HACER

1.  **Backend**: Patrón "Tiny Views - Fat Models" estrictamente
2.  **Vistas**: Usar Function-Based Views (no CBVs)
3.  **Frontend**: HTMX para toda la interactividad
4.  **Estilo**: Tailwind CSS + DaisyUI para componentes
5.  **Formateo**: Black para Python, djhtml para HTML
6.  **Lógica**: Server-side siempre que sea posible
7.  **Docker**: Usar `just` para comandos

### ❌ NO HACER

1.  **No Alpine.js**: Nunca usar Alpine.js
2.  **No JavaScript custom**: Evitar JavaScript excepto cuando sea absolutamente necesario
3.  **No lógica en vistas**: Las vistas deben ser extremadamente delgadas
4.  **No CBVs**: Preferir Function Views sobre Class-Based Views
5.  **No CSS custom**: Usar Tailwind/DaisyUI en lugar de CSS personalizado

* * *

## Ejemplos de Código

### Modelo Fat (Correcto)

```python
# models.py
class MusicItem(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    def convert_to_chordpro(self):
        """Lógica de conversión en el modelo"""
        # Toda la lógica aquí
        converted_content = self._parse_chords(self.content)
        return converted_content
    
    def _parse_chords(self, text):
        """Método privado auxiliar"""
        # Implementación...
        pass
```

### Vista Tiny (Correcto)

```python
# views.py
def music_item_convert(request, pk):
    """Vista delgada que solo orquesta"""
    music_item = get_object_or_404(MusicItem, pk=pk)
    
    # Llamar al método del modelo
    converted = music_item.convert_to_chordpro()
    
    # Renderizar respuesta HTML parcial para HTMX
    return render(request, 'partials/music_item_content.html', {
        'content': converted
    })
```

### Template con HTMX (Correcto)

```html
<!-- music_item_detail.html -->
<div id="music-content">
    {{ content }}
</div>

<button hx-post="{% url 'music_item_convert' item.pk %}"
        hx-target="#music-content"
        hx-swap="outerHTML"
        class="btn btn-primary">
    Convertir a ChordPro
</button>
```

* * *

## Información Adicional

-   **Proyecto**: Martina Bescós App
-   **Framework**: Django (con Wagtail CMS)
-   **Base de datos**: PostgreSQL
-   **Deployment**: Docker
-   **Task runner**: Just (`.justfile`)

## Tests

-   **pytest**: Usar pytest para tests unitarios y de integración

-   **Coverage**: Medir cobertura con pytest-cov

-   **Fixtures**: Usar fixtures para datos de prueba

-   **Mocking**: Usar unittest.mock para mocking

-   **Comandos**: Usar `just test` para ejecutar tests

-   Después de desarrollar una nueva funcionalidad, es importante ejecutar los tests para asegurarse de que todo funcione correctamente y desarrollar tests adicionales si es necesario.

## Documentation

-   **CHANGELOG**: Historial de cambios

-   **ROADMAP**: Planificación de funcionalidades

-   **AGENTS**: Reglas y patrones de desarrollo

-   **README**: Documentación general

-   Después de desarrollar una nueva funcionalidad, revisa la documentación para asegurarte de que todo esté correctamente documentado. Si es necesario, actualiza la documentación.
