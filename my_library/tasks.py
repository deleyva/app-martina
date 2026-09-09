"""Trabajo de la biblioteca que no cabe dentro de una petición."""

import logging

from huey.contrib.djhuey import db_task

logger = logging.getLogger(__name__)


@db_task()
def recalcular_orden_del_libro(libro_pk: int) -> int:
    """Recoloca el material de un libro para todos los que lo estudian.

    **Va en segundo plano y no en la señal.** Recalcular obliga a recorrer el
    libro entero parseando el StreamField y el RichText de cada capítulo, y hay
    libros de 302 medios: hacerlo dentro de la petición congelaría el editor de
    Wagtail justo al pulsar «Publicar», que es el peor momento posible.

    Devuelve a cuántos usuarios se les movió algo.
    """
    from wagtail.models import Page

    from my_library.orden import recolocar_libro_para_todos

    libro = Page.objects.filter(pk=libro_pk).first()
    if libro is None:
        logger.info("recalcular_orden: la página %s ya no existe", libro_pk)
        return 0

    tocados = recolocar_libro_para_todos(libro.specific)
    if tocados:
        logger.info(
            "recalcular_orden: «%s» recolocado para %s usuario(s): %s",
            libro.title,
            len(tocados),
            ", ".join(f"{correo} ({n})" for correo, n in tocados.items()),
        )
    return len(tocados)
