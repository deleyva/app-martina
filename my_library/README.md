# My Library - Biblioteca Personal Musical

Sistema de biblioteca personal integrado con Wagtail CMS que permite a los usuarios guardar y organizar contenido musical.

## ✅ Implementación Completa

### Arquitectura

- **FAT Models**: Toda la lógica de negocio en `LibraryItem`
- **TINY Views**: Vistas delgadas que solo orquestan
- **HTMX-first**: Botones añadir/quitar sin JavaScript
- **GenericForeignKey**: Apunta a cualquier modelo Django/Wagtail

### Componentes Implementados

#### 1. Modelo (`models.py`)
- `LibraryItem`: Modelo central con GenericForeignKey
- Métodos: `get_content_title()`, `get_documents()`, `add_to_library()`, `is_in_library()`
- Soporta: ScorePage, Document, Image de Wagtail

#### 2. Vistas (`views.py`)
- `my_library_index`: Lista de biblioteca
- `add_to_library`: Añadir item (HTMX)
- `remove_from_library`: Quitar item (HTMX)
- `view_library_item`: Visor fullscreen

#### 3. Templates
- `index.html`: Lista de biblioteca con stats
- `viewer.html`: Visor fullscreen con ESC para salir
- `partials/add_button.html`: Botón HTMX
- `viewers/pdf_viewer.html`: Visor PDF con PDF.js
- `viewers/image_viewer.html`: Visor de imágenes
- `viewers/audio_viewer.html`: Reproductor de audio

#### 4. Template Tags (`library_tags.py`)
- `{% library_button score %}`: Botón HTMX en Wagtail templates
- `{% is_in_library content_object %}`: Verificar si está en biblioteca

#### 5. Integración
- ✅ Añadida a `LOCAL_APPS` en settings
- ✅ URLs configuradas en `/my-library/`
- ✅ Botón integrado en `music_library_index_page.html`
- ✅ Migraciones aplicadas

## 🚀 Uso

### Para usuarios

1. **Navega a la biblioteca musical**: `/cms/` o páginas de Wagtail
2. **Click en botón "+"**: Añade partitura a tu biblioteca personal
3. **Accede a tu biblioteca**: `/my-library/`
4. **Click en "Ver"**: Abre visor fullscreen
5. **Navega PDFs**: Usa flechas ← → o botones
6. **Salir**: Pulsa ESC o botón X arriba derecha

### Para desarrolladores

```python
# Añadir contenido a biblioteca
from my_library.models import LibraryItem
item, created = LibraryItem.add_to_library(user, score_page)

# Verificar si está en biblioteca
is_in = LibraryItem.is_in_library(user, score_page)

# Obtener documentos de un item
documents = item.get_documents()
# Retorna: {'pdfs': [...], 'audios': [...], 'images': [...]}
```

## 📝 URLs Disponibles

- `/my-library/` - Lista de biblioteca personal
- `/my-library/view/<id>/` - Visor fullscreen de item
- `/my-library/add/` - Endpoint HTMX para añadir
- `/my-library/remove-by-content/` - Endpoint HTMX para quitar

## 🎨 Características UI

- **DaisyUI components**: Botones, badges, cards, stats
- **Tailwind CSS**: Utilidades y responsive design
- **HTMX**: Interactividad sin JavaScript
- **PDF.js**: Renderizado de PDFs en canvas
- **Navegación teclado**: Flechas y ESC
- **Fullscreen**: Visor optimizado para lectura

## 🔧 Extensión Futura

Para añadir soporte a nuevos tipos de contenido:

1. **Añadir mapping en `get_content_type_name()`**:
```python
def get_content_type_name(self):
    mapping = {
        'scorepage': 'Partitura',
        'nuevotipo': 'Nuevo Tipo',  # <-- Añadir aquí
    }
```

2. **Añadir icono en `get_icon()`**
3. **Añadir extracción en `get_documents()`** si tiene archivos
4. **Crear viewer en `templates/my_library/viewers/`** si es necesario

## 📊 Modelo de Datos

```
LibraryItem
├── user (FK User)
├── content_type (FK ContentType)
├── object_id (Integer)
├── content_object (GenericFK) → ScorePage, Document, Image, etc.
├── added_at (DateTime)
├── last_viewed (DateTime)
├── times_viewed (Integer)
├── favorite (Boolean)
└── notes (Text)
```

## ✅ Seguimiento de Principios

- ✅ **Tiny Views - Fat Models**: Toda lógica en modelo
- ✅ **Function-Based Views**: Sin CBVs
- ✅ **HTMX**: Sin Alpine.js ni JavaScript innecesario
- ✅ **Tailwind + DaisyUI**: Componentes predefinidos
- ✅ **Docker + Just**: Comandos con `just manage`

---

## 🎵 Visor de Partituras - Sistema de Scroll Inteligente (forScore Style)

### Características del Visor

El visor de PDFs implementa un **sistema de navegación con solapamiento visual** inspirado en forScore, optimizado para músicos.

#### Comportamiento Clave

- **Avance con solapamiento**: 75% de avance + 25% de overlap visual
- **Sin saltos bruscos**: Siempre ves el final de lo que acabas de tocar
- **Último scroll inteligente**: Va al final exacto antes de cambiar de página
- **Fullscreen optimizado**: PDF renderizado a todo el ancho de pantalla
- **Smooth scroll**: Transiciones fluidas entre vistas

### Lógica de Navegación

#### Comportamiento del Avance (→ o click derecho)

```text
Vista 1 (inicio):
┌─────────────────┐
│ █████████ (100%)│ ← Todo el contenido visible
│ █████████       │
│ █████████       │
│ █████████       │
└─────────────────┘
        ↓ Avanzar (75%)

Vista 2:
┌─────────────────┐
│ █████████ (25%) │ ← OVERLAP: Ya lo viste (contexto)
│ █████████       │ ← NUEVO contenido (75%)
│ █████████       │
│ █████████       │
└─────────────────┘
        ↓ Avanzar (75%)

Vista 3:
┌─────────────────┐
│ █████████ (25%) │ ← OVERLAP de vista anterior
│ █████████       │ ← NUEVO contenido
│ █████████       │
│ █████████       │
└─────────────────┘
        ↓ Avanzar (75% se pasaría del final)

Última Vista (final exacto):
┌─────────────────┐
│ █████████ (25%) │ ← OVERLAP de vista anterior
│ █████████       │ ← Contenido visible
│ █████████       │
│ █████████ ◄──── Final exacto alineado abajo
└─────────────────┘
        ↓ Avanzar de nuevo

→ AHORA SÍ cambia a Página 2
```

#### Algoritmo de Navegación

```javascript
// Calcular avance con solapamiento
var overlap = viewportHeight * 0.25;  // 25% de overlap
var advance = viewportHeight - overlap; // 75% de avance
var newScroll = currentScroll + advance;

// Lógica inteligente de final de página
if (newScroll > maxScroll) {
    if (currentScroll >= maxScroll - 5) {
        // YA estamos al final exacto → cambiar a siguiente página
        renderPage(currentPage + 1);
    } else {
        // NO estamos al final → hacer último scroll al final exacto
        container.scrollTo({ top: maxScroll, behavior: 'smooth' });
    }
} else {
    // Scroll normal con solapamiento
    container.scrollTo({ top: newScroll, behavior: 'smooth' });
}
```

### Controles Disponibles

#### Teclado

- `→` `↓` `PageDown` `Espacio` → Avanzar con overlap
- `←` `↑` `PageUp` → Retroceder con overlap
- `ESC` → Cerrar visor y volver a biblioteca

#### Mouse/Touch

- **Click derecho** (70% de pantalla) → Avanzar
- **Click izquierdo** (30% de pantalla) → Retroceder
- **Botón X** (arriba derecha) → Cerrar visor
  - Se auto-oculta después de 3 segundos (opacity: 0.3)
  - Reaparece al mover el ratón

### Ventajas para Músicos

✅ **Nunca pierdes el contexto**: El 25% de overlap siempre muestra el final de lo que acabas de tocar

✅ **No se salta contenido**: El último scroll va al final exacto, mostrando todos los pentagramas

✅ **Transición fluida**: Smooth scroll hace que el avance sea natural, no abrupto

✅ **Sin espacio en blanco**: El final de la página se alinea exactamente con el borde inferior

✅ **Optimizado para lectura**: PDF a todo el ancho, máximo aprovechamiento del espacio

### Detalles Técnicos

**Archivo**: `my_library/templates/my_library/viewers/pdf_viewer.html`

**Función clave**: `scrollByThird(direction)`

**CSS**: Inline (no depende de Tailwind compilado)

**Renderizado**: PDF.js con escala dinámica según ancho de ventana

**Indicador de página**: Badge discreto abajo-centro que aparece al navegar (auto-oculta 1.5s)

### Ejemplo de Uso Real

```text
Músico tocando una partitura:

1. Carga PDF → Vista 1 (inicio perfecto arriba)
2. Toca primeros pentagramas
3. Click → Vista 2 (ve el final de lo que tocó + siguientes pentagramas)
4. Continúa tocando
5. Click → Vista 3 (overlap permite no perderse)
...
N. Último click → Final exacto (ve últimos pentagramas completos)
N+1. Click → Cambia a siguiente página de PDF
```

Este sistema emula perfectamente el comportamiento de **forScore**, la app profesional de partituras para músicos.
