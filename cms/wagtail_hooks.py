"""Hooks globales del CMS.

Solo queda lo que aplica a CUALQUIER página, de la app que sea. La notificación
al moderador de un departamento se fue a `blogs/wagtail_hooks.py`, que es donde
vive ese concepto desde la fase 25.
"""

from wagtail import hooks
from wagtail.admin.views.pages.bulk_actions.delete import DeleteBulkAction
from wagtail.models import Page

from cms.visibilidad import check_page_visibility


@hooks.register("before_serve_page")
def enforce_page_visibility(page, request, serve_args, serve_kwargs):
    """Aplica `is_protected` / `is_private` a cualquier página que los declare.

    Un solo punto de control para todo el árbol. Los modelos no lo repiten en su
    `serve()`: al partir la app llegué a poner ambos y era el mismo cheque dos
    veces, con dos sitios donde equivocarse.
    """
    return check_page_visibility(page, request)


def _enforce_private_admin_only(request, page):
    """Solo un superusuario puede marcar una página como privada."""
    if hasattr(page, "is_private") and page.is_private and not request.user.is_superuser:
        type(page).objects.filter(pk=page.pk).update(is_private=False)


hooks.register("after_create_page")(_enforce_private_admin_only)
hooks.register("after_edit_page")(_enforce_private_admin_only)


class BorradoMasivoTolerante(DeleteBulkAction):
    """El borrado masivo del explorador, a prueba de dos envíos a la vez.

    El 25-09-2026 se borraron 29 artículos de un departamento desde el
    explorador y la confirmación llegó dos veces con un segundo de diferencia
    (doble clic, o un reintento del navegador). La primera petición borró las
    29 páginas; la segunda ya las había leído, y al ir a borrar la primera
    `DeletePageAction` pidió `page.specific` sobre una fila que ya no existía:
    `ArticuloPage matching query does not exist`, un 500 y un correo, con el
    trabajo hecho.

    Mismo `action_type` que la acción de Wagtail: el registro guarda una clase
    por tipo y la última en registrarse gana, y `cms` va después de
    `wagtail.admin` en `INSTALLED_APPS`. En la interfaz no cambia nada.

    Dos defensas, y hacen falta las dos:

    - `select_for_update` sobre las filas antes de tocar nada. Si otra
      petición las está borrando, esta espera a que termine y entonces las ve
      desaparecidas. Sin el bloqueo, comprobar y borrar seguirían siendo dos
      pasos entre los que la otra petición puede colarse.
    - Comprobar cada página justo antes de borrarla. Cubre el caso en que una
      página de la lista cuelga de otra de la misma lista y ya cayó con ella:
      con el bloqueo tomado nadie más puede quitarla, así que la comprobación
      es fiable.
    """

    @classmethod
    def execute_action(cls, objects, user=None, **kwargs):
        # Bloquea (y espera, si hace falta) antes de leer nada.
        list(
            Page.objects.filter(pk__in=[p.pk for p in objects])
            .select_for_update()
            .values_list("pk", flat=True)
        )
        num_parent_objects, num_child_objects = 0, 0
        for page in objects:
            if not Page.objects.filter(pk=page.pk).exists():
                continue
            num_parent_objects += 1
            num_child_objects += page.get_descendant_count()
            page.delete(user=user)
        return num_parent_objects, num_child_objects


hooks.register("register_bulk_action", BorradoMasivoTolerante)
