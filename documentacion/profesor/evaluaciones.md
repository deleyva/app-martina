# Evaluaciones

El módulo de evaluaciones (`/evaluations/`) gestiona entregas y calificación con rúbricas.

## Elementos

- **EvaluationItem**: cada actividad evaluable, asignada a un trimestre (primera/segunda/tercera evaluación). Puede exigir entrega web o entrega vía Classroom.
- **Rúbricas**: categorías y criterios con puntuaciones (RubricCategory / RubricScore).
- **Retroalimentación asistida por IA**: cada item puede definir un prompt para que Gemini reescriba/mejore la retroalimentación al alumnado.

## Flujo

1. El profesor crea el item de evaluación con su rúbrica.
2. El alumno entrega (formulario web o subida de archivo según configuración).
3. El profesor puntúa con la rúbrica; la nota y la retroalimentación quedan registradas.

También existen herramientas de importación de notas (`import_grades.py`, `import_grades_api.py`) para volcar calificaciones desde fuentes externas.
