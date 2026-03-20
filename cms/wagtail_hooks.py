import logging

from wagtail import hooks

from martina_bescos_app.utils.email import send_email

from .models import BlogIndexPage
from .models import BlogPage

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
