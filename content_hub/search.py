"""
Content Hub Search - Meilisearch Integration

Provides full-text search with typo-tolerance, filtering, and faceting.
Falls back to Django ORM search if Meilisearch is unavailable.
"""

import logging
from typing import Optional

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)

# Meilisearch client (lazy initialization)
_client = None
_index = None


def get_meilisearch_client():
    """Get or create Meilisearch client"""
    global _client

    if _client is not None:
        return _client

    try:
        import meilisearch

        meilisearch_url = getattr(settings, "MEILISEARCH_URL", "http://localhost:7700")
        meilisearch_key = getattr(settings, "MEILISEARCH_API_KEY", None)

        _client = meilisearch.Client(meilisearch_url, meilisearch_key)
        logger.info(f"Connected to Meilisearch at {meilisearch_url}")
        return _client

    except ImportError:
        logger.warning("meilisearch package not installed. Using Django ORM fallback.")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to Meilisearch: {e}. Using Django ORM fallback.")
        return None


def get_index():
    """Get or create the content_items index"""
    global _index

    if _index is not None:
        return _index

    client = get_meilisearch_client()
    if client is None:
        return None

    try:
        _index = client.index("content_items")

        # Configure index settings
        _index.update_settings({
            "searchableAttributes": [
                "title",
                "text_content",
                "tags",
                "metadata",
            ],
            "filterableAttributes": [
                "content_type",
                "tags",
                "is_archived",
                "created_by_id",
            ],
            "sortableAttributes": [
                "created_at",
                "updated_at",
                "title",
            ],
            "rankingRules": [
                "words",
                "typo",
                "proximity",
                "attribute",
                "sort",
                "exactness",
            ],
        })

        return _index
    except Exception as e:
        logger.error(f"Failed to configure Meilisearch index: {e}")
        return None


def index_content_item(item) -> bool:
    """
    Index a ContentItem in Meilisearch.

    Args:
        item: ContentItem instance

    Returns:
        True if indexed successfully, False otherwise
    """
    index = get_index()
    if index is None:
        return False

    try:
        document = {
            "id": item.id,
            "title": item.title,
            "slug": item.slug,
            "content_type": item.content_type,
            "text_content": item.text_content or "",
            "url": item.url or "",
            "tags": list(item.tags.names()),
            "metadata": item.metadata or {},
            "is_archived": item.is_archived,
            "created_by_id": item.created_by_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

        index.add_documents([document], primary_key="id")
        logger.debug(f"Indexed ContentItem {item.id}: {item.title}")
        return True

    except Exception as e:
        logger.error(f"Failed to index ContentItem {item.id}: {e}")
        return False


def remove_from_index(item_id: int) -> bool:
    """
    Remove a ContentItem from the search index.

    Args:
        item_id: ID of the ContentItem to remove

    Returns:
        True if removed successfully, False otherwise
    """
    index = get_index()
    if index is None:
        return False

    try:
        index.delete_document(item_id)
        logger.debug(f"Removed ContentItem {item_id} from index")
        return True
    except Exception as e:
        logger.error(f"Failed to remove ContentItem {item_id} from index: {e}")
        return False


def search_content(
    query: str,
    content_type: Optional[str] = None,
    tags: Optional[list] = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Search content items using Meilisearch.

    Args:
        query: Search query string
        content_type: Filter by content type
        tags: Filter by tags (AND logic)
        include_archived: Whether to include archived items
        limit: Maximum results to return
        offset: Pagination offset

    Returns:
        dict with 'hits', 'total', 'processing_time_ms'
    """
    index = get_index()

    # Build filters
    filters = []
    if not include_archived:
        filters.append("is_archived = false")
    if content_type:
        filters.append(f'content_type = "{content_type}"')
    if tags:
        for tag in tags:
            filters.append(f'tags = "{tag}"')

    filter_str = " AND ".join(filters) if filters else None

    # Try Meilisearch first
    if index is not None:
        try:
            search_params = {
                "limit": limit,
                "offset": offset,
                "attributesToRetrieve": [
                    "id", "title", "slug", "content_type", "tags", "updated_at"
                ],
            }
            if filter_str:
                search_params["filter"] = filter_str

            result = index.search(query, search_params)

            return {
                "hits": result.get("hits", []),
                "total": result.get("estimatedTotalHits", 0),
                "processing_time_ms": result.get("processingTimeMs", 0),
                "source": "meilisearch",
            }
        except Exception as e:
            logger.warning(f"Meilisearch search failed: {e}. Falling back to Django ORM.")

    # Fallback to Django ORM
    return _django_orm_search(
        query=query,
        content_type=content_type,
        tags=tags,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


def _django_orm_search(
    query: str,
    content_type: Optional[str] = None,
    tags: Optional[list] = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Django ORM fallback for search"""
    from .models import ContentItem

    queryset = ContentItem.objects.all()

    # Basic text search
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(text_content__icontains=query)
            | Q(tags__name__icontains=query)
        ).distinct()

    # Filters
    if not include_archived:
        queryset = queryset.filter(is_archived=False)
    if content_type:
        queryset = queryset.filter(content_type=content_type)
    if tags:
        for tag in tags:
            queryset = queryset.filter(tags__name__iexact=tag)

    total = queryset.count()
    items = queryset.order_by("-updated_at")[offset:offset + limit]

    hits = [
        {
            "id": item.id,
            "title": item.title,
            "slug": item.slug,
            "content_type": item.content_type,
            "tags": list(item.tags.names()),
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        for item in items
    ]

    return {
        "hits": hits,
        "total": total,
        "processing_time_ms": 0,
        "source": "django_orm",
    }


def reindex_all() -> dict:
    """
    Reindex all ContentItems. Use for initial setup or recovery.

    Returns:
        dict with 'indexed', 'failed', 'total'
    """
    from .models import ContentItem

    index = get_index()
    if index is None:
        return {"error": "Meilisearch not available", "indexed": 0, "failed": 0, "total": 0}

    items = ContentItem.objects.prefetch_related("tags").all()
    total = items.count()
    indexed = 0
    failed = 0

    # Process in batches
    batch_size = 100
    documents = []

    for item in items:
        document = {
            "id": item.id,
            "title": item.title,
            "slug": item.slug,
            "content_type": item.content_type,
            "text_content": item.text_content or "",
            "url": item.url or "",
            "tags": list(item.tags.names()),
            "metadata": item.metadata or {},
            "is_archived": item.is_archived,
            "created_by_id": item.created_by_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        documents.append(document)

        if len(documents) >= batch_size:
            try:
                index.add_documents(documents, primary_key="id")
                indexed += len(documents)
            except Exception as e:
                logger.error(f"Batch indexing failed: {e}")
                failed += len(documents)
            documents = []

    # Index remaining documents
    if documents:
        try:
            index.add_documents(documents, primary_key="id")
            indexed += len(documents)
        except Exception as e:
            logger.error(f"Final batch indexing failed: {e}")
            failed += len(documents)

    logger.info(f"Reindex complete: {indexed} indexed, {failed} failed, {total} total")

    return {
        "indexed": indexed,
        "failed": failed,
        "total": total,
    }


def clear_index() -> bool:
    """Clear all documents from the index"""
    index = get_index()
    if index is None:
        return False

    try:
        index.delete_all_documents()
        logger.info("Search index cleared")
        return True
    except Exception as e:
        logger.error(f"Failed to clear index: {e}")
        return False
