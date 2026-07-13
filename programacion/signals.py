"""
Señales: mantener ContentCoverage al día cuando se añaden o quitan
elementos de sesiones de clase.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from clases.models import ClassSessionItem


def _recompute_for_item(item):
    from .services import recompute_coverage

    try:
        group = item.session.group
    except Exception:
        return
    # Página de origen del elemento
    if item.source_page_id and item.source_page:
        recompute_coverage(group, item.source_page)
    # El propio item puede ser una página completa
    if item.content_type.model in ("blogpage", "scorepage", "dictadopage"):
        obj = item.content_object
        if obj:
            recompute_coverage(group, obj)


@receiver(post_save, sender=ClassSessionItem, dispatch_uid="programacion_item_saved")
def on_session_item_saved(sender, instance, **kwargs):
    _recompute_for_item(instance)


@receiver(
    post_delete, sender=ClassSessionItem, dispatch_uid="programacion_item_deleted"
)
def on_session_item_deleted(sender, instance, **kwargs):
    _recompute_for_item(instance)
