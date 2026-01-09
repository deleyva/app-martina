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
