# CHANGELOG

## [2026-08-12] - Arranque de sesion por faceta

### Features

- **`/my-library/empezar/`**: elige instrumento, concepto, estilo, tipo, tonalidad o dificultad y monta la sesion con lo que coincida. Recuento en vivo por HTMX y vista previa de que entraria hoy.
- Y entre facetas, O dentro de cada faceta. La seleccion viaja en la URL: una combinacion util se guarda en marcadores.
- Boton "Empezar a estudiar" en la cabecera de la biblioteca.


## [2026-08-12] - Facetas de etiquetas

### Features

- **Facetas `faceta:valor`** (`my_library/facets.py`): instrumento, concepto, estilo, tipo, tonalidad, compas, progresion, voz, dificultad, autor, artista, obra, curso, evaluacion, tema, lugar, idioma.
- **El separador es `:` y NO `/`**: hay etiquetas de compas (3/4, 6/8, 2/4, 3/8, 4/4) que con barra se parsean como faceta "3" o "6". Ya ocurria.
- **La sesion de estudio solo agrupa por etiquetas CON faceta**, y el concepto manda sobre el instrumento. Arregla un defecto: antes agrupaba por `4-eso` o `10points`.
- **Comando `migrar_etiquetas`**: en seco por defecto, `--ejecutar` para aplicar, todo en una transaccion. El mapa revisable esta en `my_library/migracion/mapa_etiquetas.txt`.


## [2026-08-12] - Notas y etiquetas en el visor de estudio

### Features

- **Etiquetas visibles mientras practicas**: el visor muestra los tags del item en el panel del flyout (tecla `M`).
- **Notas de práctica**: `LibraryItem.notes` existia en el modelo desde siempre y no tenia NINGUNA UI, ni de lectura ni de escritura. Ahora se lee y se escribe desde el propio visor, con guardado automatico (debounce de 900ms + al perder el foco). Resuelve el caso "vi el video una vez, apunte que hay que hacer, y ya no necesito volver a verlo".
- Dos caminos de perdida de datos tapados: `flushNotes()` vuelca lo pendiente antes de cambiar de item, y `Escape` dentro del campo sale del campo guardando, en vez de abandonar la sesion.


## [2026-08-12] - Histórico de repasos (`ReviewLog`)

### ✨ Features

- **`ReviewLog`**: histórico de práctica en `my_library`. Una fila por repaso, con nivel antes/después, duración, mazo de origen y `session_uuid` que agrupa la tanda.
  - Guarda hechos observados, no predicciones: sin `next_review_date` ni `ease_factor`. Un futuro planificador se derivará de estas filas en vez de venir precocinado en ellas.
  - `source` distingue práctica real (`study`) de valorar desde el índice (`manual`), para que un planificador pueda filtrar.
  - `LibraryItem.last_review` y `.days_since_last_review` derivan del histórico, no de `last_viewed` (abrir el visor no es repasar).
  - Duración capada a 1 hora por item: dejar la pestaña abierta toda la noche no debe meter un outlier.
- **Endpoint `log_review`**: el visor de estudio pasa de dos POST por item a uno solo, que graba el histórico y actualiza los contadores.

### 🗑️ Removals

- **App `study_sessions` eliminada**. Contenía un SM-2 completo (`StudyContext`, `UniversalStudyItem`, `StudySession`, `StudyProgress`) pero llevaba tiempo fuera de `INSTALLED_APPS` y sin un solo import externo: código muerto. Sus tablas pueden seguir existiendo en la BD de producción, inertes; no se han tocado.

### 🐛 Fixes

- Este `User` define `username = None` (`USERNAME_FIELD = "email"`), así que todo `user.username` vale `None`. Corregidos los 3 sitios de `my_library`; uno era un crash real (`search_fields = ["user__username"]` reventaba la búsqueda del admin con `FieldError`). Quedan 6 sitios en otras apps, reportados sin tocar.

### 📁 Files Modified

- `my_library/models.py`: modelo `ReviewLog`, propiedades `last_review` / `days_since_last_review`
- `my_library/views.py`: vista `log_review`, registro `manual` en `update_proficiency`, propagación del mazo
- `my_library/templates/my_library/study_viewer.html`: un solo POST por item, cronometraje y `session_uuid`
- `my_library/admin.py`: `ReviewLogAdmin` en solo lectura
- `my_library/tests.py`: cobertura del histórico

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
