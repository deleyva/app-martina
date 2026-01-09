# CHANGELOG

## Unreleased

-   Añadida barra superior invisible en viewers fullscreen (`my_library` y biblioteca de grupo) con panel "Media".

-   El panel "Media" incluye:
    -   Audio: selector + reproductor único HTML5.
    -   Embeds: lista de enlaces con carga bajo demanda (endpoint `cms/scores/embed-html/`).

-   La barra se muestra solo al hacer scroll hasta arriba, al click/tap en el centro o al pulsar el botón central para dispositivos táctiles.

-   Permitir añadir artículos de blog (`cms.BlogPage`) como items en sesiones de clase (`clases.ClassSessionItem`).

-   Visor dedicado para artículos de blog en sesiones con botón de cierre y soporte de tecla ESC.

-   Hotfix: migración correctiva para crear tablas M2M faltantes de `BlogPage` (`cms_blogpage_categories`, `cms_blogpage_tags`) cuando la migración estaba marcada como aplicada pero las tablas no existían.
