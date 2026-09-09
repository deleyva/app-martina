"""Cuando un libro cambia, su material se recoloca solo.

**Dos señales, no una.** `page_published` cubre editar o añadir un capítulo, pero
**arrastrar una página en el explorador de Wagtail cambia su `path` sin publicar
nada**, y ese es justamente el caso de "he reordenado el libro". Para eso está
`post_page_move`. Con solo la primera, el defecto que esto viene a evitar seguiría
ocurriendo en el gesto más obvio.

Nada de esto sustituye a `recalcular_orden`: las señales no se disparan en un
`queryset.update()`, ni en una migración de datos, ni en un script. La señal cubre
lo que venga; el comando repara lo que ya pasó.
"""

import logging

from django.dispatch import receiver
from wagtail.signals import page_published

logger = logging.getLogger(__name__)

try:  # `post_page_move` existe desde Wagtail 2.x, pero no se da por hecho
    from wagtail.signals import post_page_move
except ImportError:  # pragma: no cover
    post_page_move = None


def _libro_afectado(pagina):
    """El libro cuyo orden hay que rehacer, o `None` si la página no es de uno.

    Dos formas de libro y dos caminos, como en `my_library.libros.capitulos_de`:

    - **Por árbol**: la señal llega del CAPÍTULO, así que el libro es su padre.
      Un `LibroPage` publicado también vale, y entonces es él mismo.
    - **Por referencia**: la señal llega del propio `LibroDeEstudioPage`.

    Se distingue por capacidad y no por `isinstance`, para no atar esto a un tipo
    concreto de `musica`: cualquier página que sepa decir qué páginas referencia
    se comporta como un libro por referencia.
    """
    from my_library.models import LibraryItem

    concreta = pagina.specific

    # ¿Es ella misma un libro? Por referencia, o por tener material colgando.
    if callable(getattr(concreta, "paginas_referenciadas", None)):
        return concreta
    if LibraryItem.objects.filter(source_page__path__startswith=pagina.path).exclude(
        source_page=pagina
    ).exists():
        return concreta

    # Si no, es un capítulo: el libro es su padre.
    padre = pagina.get_parent()
    return padre.specific if padre else None


def _encolar(pagina, motivo):
    """Lanza el recálculo en segundo plano, sin poder tumbar lo que la disparó.

    Un manejador que revienta dentro de `page_published` se lleva por delante la
    publicación de la página. Editar en Wagtail no puede fallar porque a la
    biblioteca le pase algo.
    """
    try:
        from my_library.tasks import recalcular_orden_del_libro

        libro = _libro_afectado(pagina)
        if libro is None:
            return
        recalcular_orden_del_libro(libro.pk)
        logger.info("orden: encolado «%s» por %s", libro.title, motivo)
    except Exception:  # noqa: BLE001 - a propósito: no puede romper la edición
        logger.exception("orden: no se pudo encolar el recálculo de %s", pagina.pk)


@receiver(page_published, dispatch_uid="my_library_orden_al_publicar")
def al_publicar(sender, instance, **kwargs):
    _encolar(instance, "publicación")


if post_page_move is not None:

    @receiver(post_page_move, dispatch_uid="my_library_orden_al_mover")
    def al_mover(sender, instance, **kwargs):
        """Reordenar en el explorador no publica nada, y es EL caso que importa."""
        _encolar(instance, "movimiento en el árbol")
