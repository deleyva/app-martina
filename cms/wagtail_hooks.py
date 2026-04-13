import logging

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from wagtail import hooks

from martina_bescos_app.utils.email import send_email

from .models import BlogIndexPage
from .models import BlogPage
from .models import MusicLibraryIndexPage

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
def require_login_for_music_library_children(page, request, serve_args, serve_kwargs):
    """Redirect unauthenticated users away from pages under MusicLibraryIndexPage."""
    if request.user.is_authenticated:
        return
    # Skip if the page itself is MusicLibraryIndexPage (handled by its own serve())
    if isinstance(page, MusicLibraryIndexPage):
        return
    # Check if any ancestor is a MusicLibraryIndexPage
    if page.get_ancestors().type(MusicLibraryIndexPage).exists():
        login_url = reverse(settings.LOGIN_URL)
        return redirect(f"{login_url}?next={request.path}")
