"""Hooks globales del CMS.

Solo queda lo que aplica a CUALQUIER página, de la app que sea. La notificación
al moderador de un departamento se fue a `blogs/wagtail_hooks.py`, que es donde
vive ese concepto desde la fase 25.
"""

from wagtail import hooks

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
