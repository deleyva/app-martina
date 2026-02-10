# Changelog

## [0.1.0] - 2026-02-10

### Añadido
*   **Landing Page**: `/incidencias/` con barra de búsqueda y estadísticas en vivo.
*   **Creación de Incidencias**: `/incidencias/crear/`. Formulario para reportar incidencias sin login, con subida de imágenes/vídeos.
*   **Panel de Administración**: `/incidencias/panel/`. Dashboard Kanban protegido para técnicos.
*   **Gestión de Técnicos**: `/incidencias/panel/tecnicos/`. Alta y baja de técnicos (creación automática de usuarios).
*   **Asignaciones**:
    *   Modelo `HistorialAsignacion` para trazar cambios.
    *   Dropdown en tarjetas Kanban para asignar técnicos.
    *   Sección "Mis incidencias" destacada en el dashboard.
    *   Línea de tiempo de historial en el detalle de la incidencia.
*   **Detalle de Incidencia**: `/incidencias/<id>/`. Vista completa con estado, urgencia, ubicación, etiquetas, adjuntos, y sistema de comentarios.
*   **Modelos**: `Incidencia`, `Ubicacion`, `Etiqueta`, `Tecnico`, `Comentario`, `Adjunto`, `HistorialAsignacion`.
*   **Fixtures**: `ubicaciones_fixture` (56 aulas) y `etiquetas_fixture` (12 categorías).

### Cambiado
*   **Configuración**: La app `incidencias` ahora está en `LOCAL_APPS` de `settings/base.py`.
*   **Rutas**: Rutas de la app en `/incidencias/` definidas en `config/urls.py`.
