ROADMAP

## ✅ Barra superior invisible en viewers (ScorePage Media) - COMPLETADO

### Objetivo

Añadir una barra superior tipo "Ultimate Guitar" en los visualizadores fullscreen (los distintos `viewer.html`) que permita:

-   Acceder a audios asociados al `ScorePage` desde un único reproductor seleccionable.
-   Acceder a embeds asociados al `ScorePage` como lista de enlaces y, al elegir uno, abrirlo en un iframe (render HTML del embed) dentro del viewer.

La barra debe ser invisible por defecto:

-   Al cargar el viewer.
-   Mientras se avanza/navega por la partitura.

Solo debe aparecer si:

-   El usuario hace scroll hasta arriba.
-   El usuario hace click/tap en el centro de la pantalla.
-   **Zonas táctiles invisibles** (reemplaza el botón visible "Dispositivos de pantalla táctil").

### Alcance

-   `my_library/templates/my_library/viewer.html`
-   `clases/templates/clases/group_library/viewer.html`
-   `my_library/templates/my_library/viewers/pdf_viewer.html` (ajustes mínimos para click central y altura)

### Backend (Fat Models)

-   `cms.models.ScorePage`
    -   Añadir `get_embeds()` para extraer los bloques `embed` del `StreamField` `content`.
-   `my_library.models.LibraryItem`
    -   Añadir `get_related_scorepage_media()` que devuelva:
        -   `audios`: `ScorePage.get_audios()`
        -   `embeds`: `ScorePage.get_embeds()`
-   `clases.models.GroupLibraryItem`
    -   Añadir `get_related_scorepage_media()` equivalente.

### Backend (Tiny Views)

-   `my_library.views.view_library_item`
    -   Pasar `score_media` al template del viewer.
-   `clases.views.group_library_item_viewer`
    -   Pasar `score_media` al template del viewer.

### Frontend (UI/UX)

-   Barra superior (overlay) con:
    -   Cerrar
    -   Título
    -   Botón "Media" (si hay audios/embeds)
-   Panel "Media":
    -   Audio:
        -   Selector (dropdown) + reproductor único HTML5.
        -   JavaScript mínimo para cambiar la fuente y reproducir.
    -   Embeds:
        -   Lista de enlaces.
        -   Al elegir, renderizar el embed (HTML/iframe) en un contenedor del panel.
-   Comportamiento de visibilidad:
    -   Oculta por defecto.
    -   Aparece temporalmente al llegar arriba con scroll (sin mostrarla por cambios de página del PDF).
    -   Toggle al click en el centro.

### Zonas Táctiles Invisibles (Mejora UX Móvil)

Se reemplazó el botón visible "Dispositivos de pantalla táctil" por **3 zonas táctiles invisibles** que solo aparecen en dispositivos táctiles (`@media (pointer: coarse)`):

    ┌─────────┬───────────────────────────┬─────────┐
    │         │                           │         │
    │  ◀ 25%  │      Centro 50%           │  25% ▶  │
    │ Atrás   │   Toggle controles        │ Adelante│
    │         │                           │         │
    └─────────┴───────────────────────────┴─────────┘

| Zona          | Ancho | Acción                                  |
| ------------- | ----- | --------------------------------------- |
| **Izquierda** | 25%   | Retrocede (scroll up / página anterior) |
| **Centro**    | 50%   | Muestra/oculta controles (topbar)       |
| **Derecha**   | 25%   | Avanza (scroll down / página siguiente) |

**Ventajas**:

-   No tapa el contenido de la partitura.
-   Navegación intuitiva con taps en los laterales.
-   Solo visible en dispositivos táctiles (móviles/tablets).
-   En desktop se usa el comportamiento existente (click en zonas del PDF).

### Tests

-   `my_library/tests.py`
    -   Tests unitarios de `LibraryItem.get_related_scorepage_media()` con objetos mock.
-   `clases/tests.py`
    -   Tests unitarios de `GroupLibraryItem.get_related_scorepage_media()` con objetos mock.

### Documentación

-   Añadir entrada en `CHANGELOG` describiendo el nuevo panel de Media en viewers.
