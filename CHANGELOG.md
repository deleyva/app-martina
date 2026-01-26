# CHANGELOG

## [2026-01-26] - AI Publishing System Enhancements

### ✨ Features

- **Duplicate Detection**: El sistema ahora detecta ScorePages existentes con el mismo título y añade archivos a páginas existentes en lugar de crear duplicados
- **AI-Based File Tagging**: Extracción inteligente de etiquetas desde la descripción del usuario, no solo del nombre de archivo
  - Análisis del contenido de la descripción (ej: "para coro" → `voice/choir`)
  - Detección de instrumentos, voces y tipos de partitura
  - Fallback automático cuando la IA no provee tags específicos
- **Tag Normalization**: Sistema de normalización de etiquetas para mantener coherencia
  - Búsqueda case-insensitive de tags existentes
  - Reutilización automática de tags (ej: `Instrument/Piano` reutiliza `instrument/piano`)
  - Todo normalizado a minúsculas en formato `namespace/valor`
- **Descriptive Document Titles**: Los documentos obtienen nombres descriptivos basados en sus tags
  - Antes: "Si te vas 1", "Si te vas 2"
  - Ahora: "Si te vas piano tenor", "Si te vas guitar chordsheet"
- **PDF Score Block Title**: El campo Title del bloque PDF Score ahora usa el título descriptivo del documento

### 🔧 Changes

- Actualizado `AIMetadataExtractor` para solicitar tags por archivo en el prompt
- Añadido `_extract_tags_from_description()` para análisis de texto como fallback
- Añadido `_generate_descriptive_title()` para generar nombres desde tags
- Implementado `_normalize_tag_name()` y `_find_existing_tag()` para normalización
- Modificado `_apply_tags_to_document()` y `_apply_tags_to_image()` para usar normalización
- Actualizado `_build_streamfield_content()` para usar títulos de documentos en bloques PDF

### 📁 Files Modified

- `cms/services/ai_metadata_extractor.py`: Prompt actualizado con instrucciones para tags por archivo
- `cms/services/content_publisher.py`: Lógica de tagging, normalización y títulos descriptivos

## Unreleased

### 🤖 Sistema de Publicación Musical Asistido por IA

-   **Nueva funcionalidad**: Sistema completo de publicación de contenido musical usando IA (Google Gemini).

-   **Formulario web** en `/ai-publish/`:
    -   Upload de múltiples archivos (PDFs, audios MP3/WAV/OGG/FLAC, imágenes, MIDI).
    -   Descripción en lenguaje natural del contenido.
    -   Modo borrador por defecto con opción de publicación inmediata.
    -   UI con Tailwind + DaisyUI, ejemplos de uso incluidos.

-   **Procesamiento con IA** (`cms/services/ai_metadata_extractor.py`):
    -   Extracción automática de metadata estructurada: título, compositor, tonalidad, tempo, compás, dificultad.
    -   Generación inteligente de categorías y tags.
    -   Descripción mejorada y notas de interpretación.
    -   Manejo robusto de errores con retry y fallbacks.

-   **Servicio de publicación** (`cms/services/content_publisher.py`):
    -   Creación automática de ScorePages en Wagtail.
    -   Auto-creación de compositores, categorías y tags si no existen (case-insensitive).
    -   Construcción automática de StreamField con bloques PDF, Audio, Metadata, Imágenes.
    -   Soporte para archivos MIDI.

-   **API REST** en `POST /api/cms/ai-publish`:
    -   Endpoint Django Ninja con autenticación por API key.
    -   Validación de archivos y descripción.
    -   Respuesta estructurada con URLs de edición y preview.
    -   Manejo de errores con códigos HTTP apropiados.

-   **Configuración**:
    -   Variable de entorno `GEMINI_API_KEY` en settings.
    -   Soporte para formatos MIDI en `WAGTAILDOCS_EXTENSIONS`.
    -   Integración con `google-genai==1.16.1`.

-   **Documentación**:
    -   README actualizado con guía de uso completa.
    -   Ejemplos de descripciones en lenguaje natural.
    -   Instrucciones de configuración de API key.

-   Añadida barra superior invisible en viewers fullscreen (`my_library` y biblioteca de grupo) con panel "Media".

-   El panel "Media" incluye:
    -   Audio: selector + reproductor único HTML5.
    -   Embeds: lista de enlaces con carga bajo demanda (endpoint `cms/scores/embed-html/`).

-   La barra se muestra solo al hacer scroll hasta arriba, al click/tap en el centro o al pulsar el botón central para dispositivos táctiles.

-   Permitir añadir artículos de blog (`cms.BlogPage`) como items en sesiones de clase (`clases.ClassSessionItem`).

-   Visor dedicado para artículos de blog en sesiones con botón de cierre y soporte de tecla ESC.

-   Hotfix: migración correctiva para crear tablas M2M faltantes de `BlogPage` (`cms_blogpage_categories`, `cms_blogpage_tags`) cuando la migración estaba marcada como aplicada pero las tablas no existían.

-   Botón/modal "Añadir a bibliotecas" para `BlogPage` (misma UI que otros items):
    -   Cards en `cms/templates/cms/music_library_index_page.html` (sección "Contenido Editorial").
    -   Cards en `cms/templates/cms/blog_index_page.html`.
    -   Página individual en `cms/templates/cms/blog_page.html`.

-   Visor fullscreen: desactivada la reproducción automática de audio al abrir/cambiar pista (se mantiene reproducción manual):
    -   `my_library/templates/my_library/viewer.html`
    -   `clases/templates/clases/group_library/viewer.html`

-   Hotfix: resolución determinista de la ScorePage relacionada (texto "De: ...") para `Document`/`Image` en sesiones y bibliotecas.
    -   Se prioriza la ScorePage más reciente (`last_published_at`/`first_published_at`/`pk`) para evitar resultados no deterministas entre entornos.
    -   Archivos: `clases/models.py`, `my_library/models.py`.

-   **Zonas táctiles invisibles** en viewers fullscreen (mejora UX móvil):
    -   Reemplazado el botón visible "Dispositivos de pantalla táctil" por 3 zonas táctiles invisibles.
    -   25% izquierda: retroceder página/scroll.
    -   50% centro: mostrar/ocultar controles (topbar).
    -   25% derecha: avanzar página/scroll.
    -   Solo visible en dispositivos táctiles (`@media (pointer: coarse)`).
    -   No tapa el contenido de la partitura.
    -   Archivos: `my_library/templates/my_library/viewer.html`, `clases/templates/clases/group_library/viewer.html`.

### 🧪 API REST para Tests Musicales

-   **Nuevo endpoint**: `POST /api/cms/tests` para crear `TestPage` (tests tipo quiz) programáticamente.

-   **Autenticación**: API Key mediante `DatabaseApiKey()`.

-   **Request** (JSON):
    ```json
    {
      "title": "Test de Teoría Musical",
      "intro": "Evalúa tus conocimientos",
      "date": "2026-01-12",
      "featured_image_id": 123,
      "parent_page_id": 456,
      "category_ids": [1, 2],
      "tag_ids": [3, 4],
      "questions": [
        {
          "prompt": "¿Cuántos tiempos tiene un compás de 4/4?",
          "description": "Selecciona la respuesta correcta",
          "explanation": "Un compás de 4/4 tiene 4 tiempos...",
          "illustration_image_id": null,
          "options": [
            {"text": "2 tiempos", "is_correct": false},
            {"text": "3 tiempos", "is_correct": false},
            {"text": "4 tiempos", "is_correct": true},
            {"text": "6 tiempos", "is_correct": false}
          ]
        }
      ]
    }
    ```

-   **Validaciones**:
    -   Cada pregunta debe tener exactamente 4 opciones.
    -   Cada pregunta debe tener exactamente 1 respuesta correcta.
    -   Al menos una pregunta requerida.

-   **Response** (success):
    ```json
    {
      "id": 789,
      "title": "Test de Teoría Musical",
      "url": "/biblioteca/test-de-teoria-musical/",
      "question_count": 1
    }
    ```

-   **Archivo**: `cms/api.py`.
