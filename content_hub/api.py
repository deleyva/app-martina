"""
Content Hub API - Django Ninja Router

Provides RESTful API endpoints for ContentItem CRUD operations,
search, and knowledge graph traversal.
"""

from typing import List, Optional
from datetime import datetime

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from api_keys.auth import DatabaseApiKey
from .models import ContentItem, ContentLink, Category, ContentCategoryOrder
from .search import search_content as meilisearch_content


router = Router(tags=["Content Hub"], auth=[DatabaseApiKey(), django_auth])


# ============================================================================
# Schemas
# ============================================================================


class TagSchema(Schema):
    name: str


class CategorySchema(Schema):
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None


class ContentLinkSchema(Schema):
    id: int
    source_id: int
    target_id: int
    link_type: str
    link_type_display: str
    notes: str
    created_at: datetime


class ContentItemMinimalSchema(Schema):
    """Minimal schema for list views and search results"""
    id: int
    title: str
    slug: str
    content_type: str
    content_type_display: str
    updated_at: datetime


class ContentItemDetailSchema(Schema):
    """Full schema for detail view"""
    id: int
    title: str
    slug: str
    content_type: str
    content_type_display: str
    file_url: Optional[str] = None
    url: Optional[str] = None
    text_content: str
    metadata: dict
    tags: List[str]
    categories: List[CategorySchema]
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    # Graph info
    backlinks_count: int
    outlinks_count: int


class ContentItemCreateSchema(Schema):
    """Schema for creating ContentItem"""
    title: str
    content_type: str
    url: Optional[str] = None
    text_content: Optional[str] = None
    metadata: Optional[dict] = None
    tags: Optional[List[str]] = None
    category_ids: Optional[List[int]] = None


class ContentItemUpdateSchema(Schema):
    """Schema for updating ContentItem"""
    title: Optional[str] = None
    url: Optional[str] = None
    text_content: Optional[str] = None
    metadata: Optional[dict] = None
    tags: Optional[List[str]] = None
    category_ids: Optional[List[int]] = None
    is_archived: Optional[bool] = None


class LinkCreateSchema(Schema):
    """Schema for creating a link"""
    target_id: int
    link_type: str = "related"
    notes: Optional[str] = None


class SearchResultSchema(Schema):
    """Schema for search results"""
    hits: List[dict]
    total: int
    processing_time_ms: int
    source: str


class GraphNodeSchema(Schema):
    """Schema for graph node"""
    id: int
    title: str
    content_type: str
    slug: str


class GraphEdgeSchema(Schema):
    """Schema for graph edge"""
    source_id: int
    target_id: int
    link_type: str


class GraphSchema(Schema):
    """Schema for knowledge graph"""
    nodes: List[GraphNodeSchema]
    edges: List[GraphEdgeSchema]


# ============================================================================
# Helper Functions
# ============================================================================


def _item_to_minimal(item: ContentItem) -> dict:
    """Convert ContentItem to minimal dict"""
    return {
        "id": item.id,
        "title": item.title,
        "slug": item.slug,
        "content_type": item.content_type,
        "content_type_display": item.get_content_type_display(),
        "updated_at": item.updated_at,
    }


def _item_to_detail(item: ContentItem) -> dict:
    """Convert ContentItem to detail dict"""
    return {
        "id": item.id,
        "title": item.title,
        "slug": item.slug,
        "content_type": item.content_type,
        "content_type_display": item.get_content_type_display(),
        "file_url": item.file.url if item.file else None,
        "url": item.url,
        "text_content": item.text_content or "",
        "metadata": item.metadata or {},
        "tags": list(item.tags.names()),
        "categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "parent_id": cat.parent_id,
            }
            for cat in item.categories.all()
        ],
        "is_archived": item.is_archived,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "created_by_id": item.created_by_id,
        "backlinks_count": item.incoming_links.count(),
        "outlinks_count": item.outgoing_links.count(),
    }


# ============================================================================
# Search Endpoint
# ============================================================================


@router.get("/search", response=SearchResultSchema)
def search_content_api(
    request,
    q: str,
    content_type: Optional[str] = None,
    tags: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    """
    Full-text search across ContentItems using Meilisearch.
    Falls back to Django ORM if Meilisearch is unavailable.

    Args:
        q: Search query
        content_type: Filter by type (song, author, pdf, etc.)
        tags: Comma-separated tags to filter by
        include_archived: Include archived items
        limit: Maximum results (default 50)
        offset: Pagination offset
    """
    tag_list = tags.split(",") if tags else None

    result = meilisearch_content(
        query=q,
        content_type=content_type,
        tags=tag_list,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    return result


# ============================================================================
# Content Items CRUD
# ============================================================================


@router.get("/items", response=List[ContentItemMinimalSchema])
def list_items(
    request,
    content_type: Optional[str] = None,
    tag: Optional[str] = None,
    category_id: Optional[int] = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    """
    List ContentItems with optional filters.
    """
    qs = ContentItem.objects.all()

    if not include_archived:
        qs = qs.filter(is_archived=False)

    if content_type:
        qs = qs.filter(content_type=content_type)

    if tag:
        qs = qs.filter(tags__name__iexact=tag)

    if category_id:
        qs = qs.filter(categories__id=category_id)

    qs = qs.distinct().order_by("-updated_at")[offset:offset + limit]

    return [_item_to_minimal(item) for item in qs]


@router.get("/items/{item_id}", response=ContentItemDetailSchema)
def get_item(request, item_id: int):
    """
    Get a single ContentItem by ID with full details.
    """
    item = get_object_or_404(
        ContentItem.objects.prefetch_related("tags", "categories"),
        id=item_id,
    )
    return _item_to_detail(item)


@router.get("/items/by-slug/{slug}", response=ContentItemDetailSchema)
def get_item_by_slug(request, slug: str):
    """
    Get a single ContentItem by slug with full details.
    """
    item = get_object_or_404(
        ContentItem.objects.prefetch_related("tags", "categories"),
        slug=slug,
    )
    return _item_to_detail(item)


@router.post("/items", response=ContentItemDetailSchema)
def create_item(request, payload: ContentItemCreateSchema):
    """
    Create a new ContentItem.
    """
    # Validate content_type
    valid_types = [ct[0] for ct in ContentItem.ContentType.choices]
    if payload.content_type not in valid_types:
        raise HttpError(400, f"Invalid content_type. Must be one of: {valid_types}")

    item = ContentItem(
        title=payload.title,
        content_type=payload.content_type,
        url=payload.url or "",
        text_content=payload.text_content or "",
        metadata=payload.metadata or {},
        created_by=request.auth if hasattr(request, 'auth') and hasattr(request.auth, 'id') else None,
    )
    item.save()

    # Add tags
    if payload.tags:
        item.tags.add(*payload.tags)

    # Add categories
    if payload.category_ids:
        categories = Category.objects.filter(id__in=payload.category_ids)
        for cat in categories:
            ContentCategoryOrder.objects.create(content=item, category=cat)

    return _item_to_detail(item)


@router.put("/items/{item_id}", response=ContentItemDetailSchema)
def update_item(request, item_id: int, payload: ContentItemUpdateSchema):
    """
    Update an existing ContentItem.
    """
    item = get_object_or_404(ContentItem, id=item_id)

    if payload.title is not None:
        item.title = payload.title
    if payload.url is not None:
        item.url = payload.url
    if payload.text_content is not None:
        item.text_content = payload.text_content
    if payload.metadata is not None:
        item.metadata = payload.metadata
    if payload.is_archived is not None:
        item.is_archived = payload.is_archived

    item.save()

    # Update tags (replace)
    if payload.tags is not None:
        item.tags.clear()
        if payload.tags:
            item.tags.add(*payload.tags)

    # Update categories (replace)
    if payload.category_ids is not None:
        ContentCategoryOrder.objects.filter(content=item).delete()
        if payload.category_ids:
            categories = Category.objects.filter(id__in=payload.category_ids)
            for cat in categories:
                ContentCategoryOrder.objects.create(content=item, category=cat)

    return _item_to_detail(item)


@router.delete("/items/{item_id}")
def delete_item(request, item_id: int, hard_delete: bool = False):
    """
    Delete a ContentItem. By default, soft-deletes (archives).
    Use hard_delete=true to permanently delete.
    """
    item = get_object_or_404(ContentItem, id=item_id)

    if hard_delete:
        item.delete()
        return {"success": True, "message": f"ContentItem {item_id} permanently deleted"}
    else:
        item.is_archived = True
        item.save()
        return {"success": True, "message": f"ContentItem {item_id} archived"}


# ============================================================================
# Links (Knowledge Graph)
# ============================================================================


@router.get("/items/{item_id}/links", response=List[ContentLinkSchema])
def get_item_links(request, item_id: int, direction: str = "both"):
    """
    Get links for a ContentItem.

    Args:
        direction: "outgoing", "incoming", or "both" (default)
    """
    item = get_object_or_404(ContentItem, id=item_id)

    links = []

    if direction in ("outgoing", "both"):
        for link in item.outgoing_links.select_related("target").all():
            links.append({
                "id": link.id,
                "source_id": link.source_id,
                "target_id": link.target_id,
                "link_type": link.link_type,
                "link_type_display": link.get_link_type_display(),
                "notes": link.notes,
                "created_at": link.created_at,
            })

    if direction in ("incoming", "both"):
        for link in item.incoming_links.select_related("source").all():
            links.append({
                "id": link.id,
                "source_id": link.source_id,
                "target_id": link.target_id,
                "link_type": link.link_type,
                "link_type_display": link.get_link_type_display(),
                "notes": link.notes,
                "created_at": link.created_at,
            })

    return links


@router.post("/items/{item_id}/links", response=ContentLinkSchema)
def create_item_link(request, item_id: int, payload: LinkCreateSchema):
    """
    Create a link from this item to another item.
    """
    source = get_object_or_404(ContentItem, id=item_id)
    target = get_object_or_404(ContentItem, id=payload.target_id)

    # Validate link_type
    valid_types = [lt[0] for lt in ContentLink.LinkType.choices]
    if payload.link_type not in valid_types:
        raise HttpError(400, f"Invalid link_type. Must be one of: {valid_types}")

    # Check for existing link
    existing = ContentLink.objects.filter(
        source=source,
        target=target,
        link_type=payload.link_type,
    ).first()

    if existing:
        raise HttpError(400, "Link already exists with this type")

    link = ContentLink.objects.create(
        source=source,
        target=target,
        link_type=payload.link_type,
        notes=payload.notes or "",
    )

    return {
        "id": link.id,
        "source_id": link.source_id,
        "target_id": link.target_id,
        "link_type": link.link_type,
        "link_type_display": link.get_link_type_display(),
        "notes": link.notes,
        "created_at": link.created_at,
    }


@router.delete("/items/{item_id}/links/{link_id}")
def delete_item_link(request, item_id: int, link_id: int):
    """
    Delete a link.
    """
    link = get_object_or_404(ContentLink, id=link_id, source_id=item_id)
    link.delete()
    return {"success": True, "message": f"Link {link_id} deleted"}


# ============================================================================
# Knowledge Graph
# ============================================================================


@router.get("/items/{item_id}/graph", response=GraphSchema)
def get_item_graph(request, item_id: int, depth: int = 1):
    """
    Get the knowledge graph around a ContentItem.

    Args:
        depth: How many levels of connections to include (default 1, max 3)
    """
    if depth < 1:
        depth = 1
    if depth > 3:
        depth = 3

    item = get_object_or_404(ContentItem, id=item_id)

    nodes = {}
    edges = []

    def add_node(content_item):
        if content_item.id not in nodes:
            nodes[content_item.id] = {
                "id": content_item.id,
                "title": content_item.title,
                "content_type": content_item.content_type,
                "slug": content_item.slug,
            }

    def traverse(current_item, current_depth):
        if current_depth > depth:
            return

        add_node(current_item)

        # Outgoing links
        for link in current_item.outgoing_links.select_related("target").all():
            add_node(link.target)
            edge = {
                "source_id": link.source_id,
                "target_id": link.target_id,
                "link_type": link.link_type,
            }
            if edge not in edges:
                edges.append(edge)

            if current_depth < depth:
                traverse(link.target, current_depth + 1)

        # Incoming links
        for link in current_item.incoming_links.select_related("source").all():
            add_node(link.source)
            edge = {
                "source_id": link.source_id,
                "target_id": link.target_id,
                "link_type": link.link_type,
            }
            if edge not in edges:
                edges.append(edge)

            if current_depth < depth:
                traverse(link.source, current_depth + 1)

    traverse(item, 1)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
    }


# ============================================================================
# Categories
# ============================================================================


@router.get("/categories", response=List[CategorySchema])
def list_categories(request, parent_id: Optional[int] = None):
    """
    List categories, optionally filtered by parent.
    """
    qs = Category.objects.all()

    if parent_id is not None:
        qs = qs.filter(parent_id=parent_id)
    elif parent_id is None:
        # Only return root categories by default
        pass  # Return all for simplicity

    qs = qs.order_by("order", "name")

    return [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "parent_id": cat.parent_id,
        }
        for cat in qs
    ]


@router.get("/categories/{category_id}/items", response=List[ContentItemMinimalSchema])
def list_category_items(request, category_id: int, limit: int = 50, offset: int = 0):
    """
    List ContentItems in a category, ordered by their position.
    """
    category = get_object_or_404(Category, id=category_id)

    orders = (
        ContentCategoryOrder.objects
        .filter(category=category)
        .select_related("content")
        .order_by("order")[offset:offset + limit]
    )

    return [_item_to_minimal(order.content) for order in orders]


# ============================================================================
# Stats
# ============================================================================


@router.get("/stats")
def get_stats(request):
    """
    Get content hub statistics.
    """
    from django.db.models import Count

    total = ContentItem.objects.filter(is_archived=False).count()
    by_type = (
        ContentItem.objects
        .filter(is_archived=False)
        .values("content_type")
        .annotate(count=Count("id"))
    )

    type_counts = {item["content_type"]: item["count"] for item in by_type}

    return {
        "total_items": total,
        "by_type": type_counts,
        "total_links": ContentLink.objects.count(),
        "total_categories": Category.objects.count(),
    }
