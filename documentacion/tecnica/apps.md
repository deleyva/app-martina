# Apps Django

Resumen de cada app local y sus modelos principales.

## cms

El corazón del contenido (Wagtail). Tipos de página: `HomePage`, `BlogIndexPage` (índice de blog **y** libro con capítulos), `BlogPage` (artículo con StreamField de adjuntos), `ScorePage` (partitura Music Pills), `MusicLibraryIndexPage`, `SetlistPage`, `DictadoPage`, `TestPage`, `SlidesConAudioPage`, `HelpIndexPage`/`HelpVideoPage`. Snippets: `MusicComposer`, `MusicCategory`, `MusicTag`, `ExternalResource`. Incluye la publicación asistida por IA y los filtros avanzados de partituras.

## clases

Gestión docente:

- `Subject`, `Group`, `Enrollment` (multi-grupo), `Student` (deprecado), `GroupInvitation`.
- `GroupLibraryItem`: biblioteca compartida del grupo (GenericFK a cualquier contenido, con notas y nivel de dominio 1-4).
- `ClassSession` + `ClassSessionItem`: sesiones de clase presentables, con orden, notas por elemento, página de origen (`source_page`) y **cierre con reflexión** (`reflection`, `reflection_audio`, `closed_at`).
- Study Cards: `StudyCardBatch`, `StudyCardItem`, `StudyCardPickup`, `StudyCardLabel`.

## programacion

Planificación de trimestre y seguimiento. Ver [detalle](programacion.md). Modelos: `CoursePlan`, `PlanItem`, `ContentCoverage`.

## my_library

Biblioteca personal: `LibraryDeck`, `LibraryItem` (GenericFK). Visor forScore-like y modo estudio.

## study_sessions

Sistema universal de estudio con repetición espaciada: `StudyContext`, `UniversalStudyItem`, `StudySession`, `StudyParticipation`, `SessionItem`, `StudyProgress`.

## evaluations

`EvaluationItem` (con trimestre y prompt de IA), `Evaluation`, `RubricCategory`, `RubricScore`, `PendingEvaluationStatus`.

## content_hub

Grafo de conocimiento de contenido musical: `ContentItem`, `ContentLink`, `Category`, con búsqueda en Meilisearch.

## Otras

- `songs_ranking`: ranking de canciones con integración Spotify.
- `analytics`: métricas de uso.
- `incidencias`: sistema de incidencias informáticas del centro.
- `api_keys`: gestión de claves de API.
- `martina_bescos_app.users`: modelo de usuario propio (email como username).
