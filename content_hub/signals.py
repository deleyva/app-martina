"""
Content Hub Signals - Auto-indexing for Meilisearch

Automatically indexes ContentItems when they are created or updated,
and removes them from the index when deleted.
"""

import logging

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from .models import ContentItem

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ContentItem)
def index_content_on_save(sender, instance, created, **kwargs):
    """Index ContentItem when created or updated"""
    try:
        from .search import index_content_item

        index_content_item(instance)
        action = "indexed" if created else "reindexed"
        logger.debug(f"ContentItem {instance.id} {action}")
    except Exception as e:
        # Don't fail the save if indexing fails
        logger.warning(f"Failed to index ContentItem {instance.id}: {e}")


@receiver(post_delete, sender=ContentItem)
def remove_content_from_index(sender, instance, **kwargs):
    """Remove ContentItem from index when deleted"""
    try:
        from .search import remove_from_index

        remove_from_index(instance.id)
        logger.debug(f"ContentItem {instance.id} removed from index")
    except Exception as e:
        logger.warning(f"Failed to remove ContentItem {instance.id} from index: {e}")


@receiver(m2m_changed, sender=ContentItem.tags.through)
def reindex_on_tags_change(sender, instance, action, **kwargs):
    """Reindex ContentItem when tags are added or removed"""
    if action in ("post_add", "post_remove", "post_clear"):
        try:
            from .search import index_content_item

            index_content_item(instance)
            logger.debug(f"ContentItem {instance.id} reindexed after tag change")
        except Exception as e:
            logger.warning(f"Failed to reindex ContentItem {instance.id} after tag change: {e}")
