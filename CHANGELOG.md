# CHANGELOG

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
