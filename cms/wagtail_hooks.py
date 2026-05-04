import logging

from wagtail import hooks

from martina_bescos_app.utils.email import send_email

from .models import BlogIndexPage
from .models import BlogPage
from .models import _check_page_visibility

logger = logging.getLogger(__name__)


@hooks.register("after_create_page")
def notify_moderator_on_blog_submission(request, page):
    """Notify the department moderator when a new BlogPage is created."""
    if not isinstance(page, BlogPage):
        return

    parent = page.get_parent().specific
    if not isinstance(parent, BlogIndexPage):
        return

    moderator = parent.moderator
    if not moderator or not moderator.email:
        return

    try:
        send_email(
            subject=f"Nuevo artículo pendiente: {page.title}",
            body=(
                f"Se ha creado un nuevo artículo en el departamento «{parent.title}».\n\n"
                f"Título: {page.title}\n"
                f"Autor: {request.user.get_full_name() or request.user.username}\n\n"
                f"Revísalo en el panel de administración de Wagtail."
            ),
            to=[moderator.email],
        )
    except Exception:
        logger.exception("Failed to send moderator notification for page %s", page.title)


@hooks.register("before_serve_page")
def check_page_visibility(page, request, serve_args, serve_kwargs):
    """Enforce is_protected / is_private visibility on BlogPage and BlogIndexPage."""
    return _check_page_visibility(page, request)


def _enforce_private_admin_only(request, page):
    """Only superusers can mark a page as private. Reset if non-admin tries."""
    if hasattr(page, "is_private") and page.is_private and not request.user.is_superuser:
        type(page).objects.filter(pk=page.pk).update(is_private=False)


hooks.register("after_create_page")(_enforce_private_admin_only)
hooks.register("after_edit_page")(_enforce_private_admin_only)
