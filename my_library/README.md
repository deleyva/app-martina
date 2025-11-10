# My Library - Biblioteca Personal de Usuario

Sistema simple de biblioteca personal que permite a los usuarios guardar y organizar contenido de Wagtail para revisarlo más tarde.

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
