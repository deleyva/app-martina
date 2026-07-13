# Programaciones de trimestre

El módulo de programación (`/programacion/`) responde a tres preguntas:

1. **¿Qué vamos a hacer este trimestre?** — el plan, una secuencia ordenada de recursos.
2. **¿Por dónde va cada grupo?** — progreso calculado automáticamente a partir de las clases dadas.
3. **¿Qué toca ahora?** — recomendación del siguiente paso y creación de la clase con un clic.

## Crear un plan

En `/programacion/` crea un plan por grupo y periodo (p. ej. "2º Trimestre 2025-26"), con fechas opcionales. Luego añade recursos en orden desde dos fuentes:

- **La biblioteca del grupo**: artículos y partituras que ya añadiste.
- **Libros**: cualquier libro publicado. Al añadirlo se generan automáticamente sus capítulos como sub-items, cada uno con progreso propio. Si publicas capítulos nuevos, usa "Sincronizar capítulos".

## Cómo se calcula el progreso

Cada vez que añades un elemento a una sesión de clase, el sistema sabe de qué artículo salió. Con eso calcula la **cobertura** de cada recurso por grupo:

```
progreso del artículo = adjuntos ya usados en clases del grupo / adjuntos totales
progreso del libro    = media del progreso de sus capítulos
progreso del plan     = media de todos sus items
```

- Es **retroactivo**: al añadir un artículo al plan, su progreso ya refleja las clases pasadas del grupo.
- Puedes **forzar estados manualmente**: marcar un item como completado (aunque falten elementos) o saltarlo (no cuenta para el plan). "Volver a automático" restaura el cálculo.
- "Recalcular progreso" fuerza una actualización si has cambiado los adjuntos de un artículo.

!!! note "Qué cuenta como visto"
    Un elemento cuenta como visto si ha aparecido en **cualquier sesión del grupo**, sin importar desde qué página se añadió.

## El siguiente paso

En la vista del plan, el panel **"👉 Siguiente paso"** muestra el primer recurso incompleto (entrando capítulo a capítulo en los libros) y sus elementos pendientes. El botón **"➕ Crear clase con esto"** genera una sesión con fecha de hoy que contiene solo lo pendiente, y te lleva directamente al editor de la sesión para retocarla.

## Vista comparativa

`/programacion/overview/` muestra todos tus grupos a la vez: progreso de cada plan, siguiente paso, y un mini-mapa con un segmento por recurso (gris = pendiente, morado = en curso, verde = completado). Es la vista para decidir en 10 segundos qué preparar para mañana.
