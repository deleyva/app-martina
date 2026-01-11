# Sistema de Publicación Musical Asistido por IA

## Introducción

El sistema de publicación con IA permite crear ScorePages en Wagtail de forma automática mediante procesamiento de lenguaje natural con Google Gemini. El sistema reduce el proceso de publicación de ~15 pasos manuales a solo 2 pasos.

## Arquitectura

```
┌─────────────────────────────────┐
│  Formulario Web                 │
│  /ai-publish/                   │
│  - Upload archivos              │
│  - Descripción natural          │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  API REST                       │
│  POST /api/cms/ai-publish       │
│  - Validación                   │
│  - Orquestación                 │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  AIMetadataExtractor            │
│  - Prompt engineering           │
│  - Llamada a Gemini API         │
│  - Parsing y validación         │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  ContentPublisher               │
│  - Crear Documents/Images       │
│  - Auto-crear Composer/Tags     │
│  - Construir StreamField        │
│  - Crear ScorePage              │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  Wagtail CMS                    │
│  - ScorePage como borrador      │
│  - Edición manual si necesario  │
│  - Publicación                  │
└─────────────────────────────────┘
```

## Componentes

### 1. AIMetadataExtractor (`cms/services/ai_metadata_extractor.py`)

**Responsabilidad**: Extraer metadata estructurada de descripciones en lenguaje natural.

**Características**:
- Usa Google Gemini (modelo `gemini-2.0-flash-exp`)
- Temperatura baja (0.1) para resultados consistentes
- Retry con exponential backoff (3 intentos)
- Fallbacks para manejo de errores
- Respuesta en formato JSON

**Campos extraídos**:
```python
{
    "title": str,              # Título de la obra
    "composer": str,           # Compositor/autor
    "key_signature": str,      # Tonalidad (ej: "C mayor")
    "tempo": str,              # Tempo (ej: "Allegro", "120 BPM")
    "time_signature": str,     # Compás (ej: "4/4")
    "difficulty": str,         # beginner|easy|intermediate|advanced|expert
    "duration_minutes": int,   # Duración en minutos
    "reference_catalog": str,  # Opus, BWV, etc.
    "categories": list[str],   # Categorías (ej: ["Jazz", "Vocal"])
    "tags": list[str],         # Tags (ej: ["piano", "voz"])
    "description": str,        # Descripción mejorada
    "notes": str,              # Notas de interpretación
}
```

**Validación**:
- Difficulty debe ser uno de: beginner, easy, intermediate, advanced, expert
- Duration debe ser entero positivo o null
- Categorías y tags se deduplicación y limpian

### 2. ContentPublisher (`cms/services/content_publisher.py`)

**Responsabilidad**: Crear ScorePage en Wagtail con los datos extraídos.

**Características**:
- Operaciones atómicas con `transaction.atomic()`
- Auto-creación de entidades relacionadas (case-insensitive)
- Construcción automática de StreamField
- Generación de slugs únicos

**Métodos principales**:

```python
def create_scorepage_from_ai(
    metadata: dict,
    pdf_files: list[UploadedFile],
    audio_files: list[UploadedFile],
    image_files: list[UploadedFile],
    midi_files: list[UploadedFile],
    publish: bool = False,
) -> ScorePage
```

**Auto-creación**:
- `MusicComposer`: Búsqueda case-insensitive, crea si no existe
- `MusicCategory`: Búsqueda case-insensitive, solo categorías raíz
- `MusicTag`: Búsqueda case-insensitive, color aleatorio

**StreamField construido**:
1. Bloque PDF principal (con descripción)
2. Bloque Metadata musical (tonalidad, tempo, etc.)
3. Bloque Notes (notas de interpretación)
4. Bloques Audio (para cada archivo)
5. Bloques MIDI (como Audio)
6. Bloques Image (para cada imagen)

### 3. API REST (`cms/api.py`)

**Endpoint**: `POST /api/cms/ai-publish`

**Autenticación**: API Key mediante `DatabaseApiKey()`

**Request**:
```
Content-Type: multipart/form-data

description: string (required)
publish_immediately: boolean (default: false)
parent_page_id: integer (optional)
pdf_files: file[] (optional)
audio_files: file[] (optional)
image_files: file[] (optional)
midi_files: file[] (optional)
```

**Response** (success):
```json
{
  "success": true,
  "score_page_id": 123,
  "title": "All of Me",
  "edit_url": "/cms/pages/123/edit/",
  "preview_url": "/cms/pages/123/view_draft/",
  "message": "ScorePage creada como borrador...",
  "created_items": {
    "composer": "John Legend",
    "categories": ["Pop", "Vocal"],
    "tags": ["piano", "voz", "balada"]
  }
}
```

**Códigos de error**:
- `400`: Descripción vacía, sin archivos, página padre inexistente
- `500`: Error de IA, error de creación de página

### 4. Formulario Web (`cms/templates/cms/ai_publish_form.html`)

**URL**: `/ai-publish/` (requiere login)

**Características**:
- UI con Tailwind CSS + DaisyUI
- Upload drag-and-drop para 4 tipos de archivos
- Textarea con placeholder de ejemplo
- Validación client-side (al menos un archivo)
- Loading state durante procesamiento
- Alertas de éxito/error con detalles
- Sección de ejemplos expandible
- Scroll automático al resultado

**JavaScript incluido**:
- Validación de archivos antes de submit
- Fetch API para llamada al endpoint
- Manejo de respuestas y errores
- Reset de formulario tras éxito

## Configuración

### Variables de Entorno

Añadir en `.envs/.local/.django`:

```bash
GEMINI_API_KEY=AIzaSy...tu-api-key-aqui
```

### Obtener API Key

1. Ir a https://makersuite.google.com/app/apikey
2. Crear nuevo proyecto (o usar existente)
3. Generar API key
4. Copiar y pegar en `.env`

**Límites gratuitos**:
- 15 requests por minuto
- 1M tokens por día
- Suficiente para uso normal

### Formatos Soportados

Configurado en `config/settings/base.py`:

```python
WAGTAILDOCS_EXTENSIONS = [
    # ... otros formatos
    "mp3", "wav", "ogg", "m4a", "aac", "flac",  # Audio
    "mid", "midi",  # MIDI (nuevo)
]
```

## Uso

### Formulario Web

1. **Acceder**: http://localhost:8000/ai-publish/
2. **Subir archivos**: Seleccionar PDFs, audios, imágenes, MIDI
3. **Describir**:
   ```
   Partitura de "Shape of You" de Ed Sheeran en Do sostenido menor,
   nivel principiante. Incluyo PDF de la partitura simplificada para
   ukelele y audio de referencia.
   ```
4. **Enviar**: La IA procesa (5-15 segundos típicamente)
5. **Revisar**: Abrir en Wagtail admin para editar
6. **Publicar**: Cuando esté listo

### API REST

```bash
curl -X POST http://localhost:8000/api/cms/ai-publish \
  -H "Authorization: Api-Key tu-api-key" \
  -F "description=Minueto en Sol mayor de Bach..." \
  -F "pdf_files=@partitura.pdf" \
  -F "audio_files=@audio.mp3" \
  -F "publish_immediately=false"
```

### Ejemplos de Descripciones

**Canción Pop**:
```
Partitura de 'All of Me' de John Legend en Do mayor, nivel intermedio
para piano y voz. Incluyo PDF de la partitura, audio de mi interpretación,
y la portada del álbum Love in the Future.
```

**Pieza Clásica**:
```
Minueto en Sol mayor de Bach (BWV Anh. 114), nivel fácil para piano.
Partitura en PDF y grabación MIDI incluida. Compás 3/4, tempo Moderato.
```

**Ejercicio Técnico**:
```
Ejercicio de escalas cromáticas para guitarra, nivel avanzado. Incluyo
PDF con digitaciones y archivo MIDI de acompañamiento. Dificultad alta,
enfocado en velocidad y precisión.
```

## Flujo de Datos

### Descripción → Metadata

```
Input:
"Partitura de All of Me de John Legend en Do mayor, nivel intermedio..."

↓ AIMetadataExtractor

Output:
{
  "title": "All of Me",
  "composer": "John Legend",
  "key_signature": "C mayor",
  "tempo": "Moderato",
  "time_signature": "4/4",
  "difficulty": "intermediate",
  "categories": ["Pop", "Vocal"],
  "tags": ["piano", "voz", "balada", "romantica"]
}
```

### Metadata → ScorePage

```
Metadata + Archivos

↓ ContentPublisher

1. Crear Documents en Wagtail (PDFs, audios, MIDI)
2. Crear Images en Wagtail
3. Get/Create Composer: "John Legend"
4. Get/Create Categories: ["Pop", "Vocal"]
5. Get/Create Tags: ["piano", "voz", "balada", "romantica"]
6. Construir StreamField:
   - PDFBlock(title="All of Me", pdf=document)
   - MetadataBlock(key="C mayor", tempo="Moderato", ...)
   - AudioBlock(audio=audio_document)
   - ImageBlock(image=image)
7. Crear ScorePage (draft)
8. Asignar composer, categories, tags
9. Guardar revisión

↓

ScorePage creada con ID 123
```

## Manejo de Errores

### Error de IA

**Problema**: Gemini API falla o responde JSON inválido

**Solución**:
1. Retry con exponential backoff (3 intentos)
2. Fallback a metadata por defecto
3. Descripción original preservada
4. Nota indicando fallo de IA

### Error de Creación

**Problema**: Fallo al crear ScorePage (ej: parent page no existe)

**Solución**:
1. Transaction rollback automático
2. Error HTTP 400/500 con mensaje descriptivo
3. No se crean entidades parciales
4. Usuario ve mensaje de error en formulario

### Validación

**Client-side**:
- Descripción no vacía
- Al menos un archivo subido

**Server-side**:
- Descripción no vacía
- Al menos un archivo
- Parent page válido (si se especifica)
- Archivos con extensiones permitidas

## Performance

### Tiempos Típicos

- Procesamiento con IA: 5-15 segundos
- Creación de ScorePage: <1 segundo
- Total: ~10-20 segundos

### Optimizaciones

- Temperatura baja (0.1) → respuestas más rápidas
- Modelo flash (gemini-2.0-flash-exp) → latencia baja
- Operación atómica → rollback rápido en error
- Sin procesamiento de imágenes → upload directo

### Límites

- Google Gemini free tier: 15 req/min, 1M tokens/día
- Tamaño de archivos: límite de Django (2.5MB default, configurable)
- Tokens por request: ~500-1000 típico, límite 2048

## Testing

### Tests Unitarios Recomendados

```python
# cms/tests/test_ai_metadata_extractor.py
def test_extract_metadata_complete()
def test_extract_metadata_minimal()
def test_extract_metadata_invalid_json()
def test_extract_metadata_timeout()

# cms/tests/test_content_publisher.py
def test_create_scorepage_from_ai_complete()
def test_get_or_create_composer_existing()
def test_get_or_create_composer_new()
def test_build_streamfield_content()

# cms/tests/test_ai_api.py
def test_ai_publish_success()
def test_ai_publish_no_description()
def test_ai_publish_no_files()
def test_ai_publish_draft_mode()
```

### Tests de Integración

```bash
# Test manual con curl
just shell

# Dentro del contenedor
python manage.py shell
>>> from cms.services import AIMetadataExtractor
>>> extractor = AIMetadataExtractor()
>>> metadata = extractor.extract_metadata(
...     "Partitura de All of Me...",
...     ["PDF: partitura.pdf"]
... )
>>> print(metadata)
```

## Troubleshooting

### Error: "GEMINI_API_KEY not configured"

**Causa**: Variable de entorno no está configurada

**Solución**:
1. Añadir `GEMINI_API_KEY` en `.envs/.local/.django`
2. Rebuild containers: `just build && just up`

### Error: "No MusicLibraryIndexPage found"

**Causa**: No existe página padre para ScorePages

**Solución**:
1. Ir a Wagtail admin: http://localhost:8000/cms/
2. Crear una MusicLibraryIndexPage
3. Publicarla
4. Intentar de nuevo

### Error 404 al acceder a /cms/ai-publish/

**Causa**: URL incorrecta

**Solución**: Usar `/ai-publish/` (sin prefijo `/cms/`)

### La IA extrae datos incorrectos

**Causa**: Descripción ambigua o incompleta

**Solución**:
1. Ser más específico en la descripción
2. Incluir todos los campos relevantes
3. Revisar y corregir en Wagtail admin antes de publicar

## Mejoras Futuras

### Roadmap

- [ ] Batch upload (múltiples obras a la vez)
- [ ] Búsqueda de metadata en APIs externas (IMSLP, MusicBrainz)
- [ ] Mejora del prompt con few-shot examples
- [ ] Soporte multi-idioma (inglés, catalán)
- [ ] Extracción de metadata de archivos PDF (PyPDF2)
- [ ] Preview de ScorePage antes de crear
- [ ] Estadísticas de uso del sistema
- [ ] Fine-tuning del modelo con datos propios

### Optimizaciones Posibles

- Cache de respuestas de IA para descripciones similares
- Procesamiento asíncrono con Celery/Huey
- Compresión automática de imágenes
- OCR de PDFs para extracción de texto

## Referencias

### Archivos Clave

- `cms/services/ai_metadata_extractor.py` (291 líneas)
- `cms/services/content_publisher.py` (377 líneas)
- `cms/api.py` (endpoint ai-publish)
- `cms/views.py` (vista ai_publish_form)
- `cms/urls.py` (URL mapping)
- `cms/templates/cms/ai_publish_form.html` (254 líneas)
- `config/settings/base.py` (configuración GEMINI_API_KEY)

### Dependencias

- `google-genai==1.16.1` (SDK de Google Gemini)
- `django-ninja==1.3.0` (API REST)
- `wagtail` (CMS)

### Enlaces Útiles

- Google Gemini API: https://ai.google.dev/
- API Keys: https://makersuite.google.com/app/apikey
- Django Ninja: https://django-ninja.dev/
- Wagtail: https://wagtail.org/
