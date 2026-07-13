# Contenidos: artículos, partituras y libros

Todo el contenido se crea en **Wagtail** (`/cms/`). Hay varios tipos de página, cada uno con un propósito.

## Artículos de blog (BlogPage)

El tipo más habitual para publicar **canciones con tutoriales**. Un artículo tiene:

- **Cuerpo** en texto enriquecido (puede incluir vídeos embebidos e imágenes).
- **Adjuntos** (StreamField): PDFs (partituras), audios, imágenes con pie, vídeos y enlaces externos. Cada adjunto se muestra como una tarjeta con descarga, visor y **botón de librería**.
- Categorías y tags musicales, imagen destacada, y opciones de visibilidad (protegida = requiere login; privada = solo el creador).

!!! tip "Los adjuntos son la unidad de trabajo"
    Cada adjunto individual puede añadirse a bibliotecas y a sesiones de clase por separado. El sistema de programaciones mide el progreso de un artículo contando qué adjuntos se han usado ya en clase.

## Libros (BlogIndexPage con capítulos)

Un **BlogIndexPage** actúa como libro cuando contiene artículos hijos (capítulos) y tiene portada. Se usan para materiales largos (métodos, cancioneros). Hay comandos de importación (`import_book_chapter`, `extract_pdf_book.py`, `extract_epub_book.py`) para crear libros desde PDF/EPUB.

En las [programaciones](programaciones.md), un libro se añade completo y genera automáticamente un item por capítulo, con seguimiento individual.

## Partituras (ScorePage — Music Pills)

Páginas de partitura con compositor, categorías, tags y contenido flexible: PDF, audios, imágenes, embeds, marcadores y notas. Viven bajo la **biblioteca musical** (`MusicLibraryIndexPage`) y se pueden filtrar por múltiples criterios en `/scores/filtered/`.

## Otros tipos

- **DictadoPage**: dictados con audio y soluciones.
- **TestPage**: cuestionarios con opciones de respuesta.
- **SlidesConAudioPage**: presentaciones con audio.
- **Publicación asistida por IA**: puedes subir archivos (PDF, audio, imágenes, MIDI) y describir el contenido en lenguaje natural; Gemini extrae título, compositor, dificultad, categorías y tags.
