# Incidencias App

Aplicación para la gestión de incidencias informáticas en el instituto. Permite a los profesores reportar problemas de forma pública (sin necesidad de login) y a los técnicos gestionarlas mediante un panel Kanban.

## Características

### 🌍 Parte Pública (Profesores)
*   **Landing Page**: Buscador en vivo de incidencias existentes para evitar duplicados.
*   **Reporte Sencillo**: Formulario optimizado con autocompletado de ubicaciones (Aulas) y etiquetas comunes.
*   **Privacidad**: Opción para marcar incidencias como privadas.
*   **Seguimiento**: Detalle de la incidencia con estado, comentarios y adjuntos.

### 🛠️ Panel de Gestión (Técnicos)
*   **Dashboard Kanban**: Vista de columnas (Pendiente, En Progreso, Resuelta) con filtros por planta, urgencia y técnico.
*   **Mis Incidencias**: Sección destacada con las tareas asignadas al técnico actual.
*   **Gestión de Asignaciones**: 
    *   Auto-asignación ("Coger para mí").
    *   Asignar a otros compañeros.
    *   Historial completo de cambios de asignación.
*   **Gestión de Técnicos**: Interfaz sencilla para dar de alta/baja técnicos (creación automática de usuarios).

## Instalación y Datos Iniciales

La app incluye **fixtures** para cargar datos iniciales de ubicaciones (aulas) y etiquetas comunes.

```bash
# Cargar datos iniciales (si no se ejecutó en la migración)
python manage.py call_command load_fixtures
```

## Estructura

*   `models.py`: Definición de `Incidencia`, `Ubicacion`, `Etiqueta`, `Tecnico`, `Comentario`, `Adjunto`, `HistorialAsignacion`.
*   `views.py`: Vistas basadas en clases para el frontend público y el panel de administración.
*   `templates/incidencias/`: Plantillas HTML usando DaisyUI y HTMX.
