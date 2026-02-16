"""
Content Hub Admin - Enhanced Django Admin with Knowledge Graph Features
"""

from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse

from .models import ContentItem, ContentLink, Category, ContentCategoryOrder


class ContentLinkInline(admin.TabularInline):
    """Inline for outgoing links from a ContentItem"""

    model = ContentLink
    fk_name = "source"
    extra = 1
    autocomplete_fields = ["target"]
    verbose_name = "Enlace saliente"
    verbose_name_plural = "Enlaces salientes"


class ContentCategoryOrderInline(admin.TabularInline):
    """Inline for category assignments with ordering"""

    model = ContentCategoryOrder
    extra = 1
    autocomplete_fields = ["category"]
    verbose_name = "Categoría"
    verbose_name_plural = "Categorías"


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "content_type",
        "tag_list",
        "link_count",
        "is_archived",
        "updated_at",
    ]
    list_filter = ["content_type", "is_archived", "tags", "categories"]
    search_fields = ["title", "text_content", "slug"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
    list_editable = ["is_archived"]
    list_per_page = 50

    readonly_fields = [
        "created_at",
        "updated_at",
        "backlinks_display",
        "outlinks_display",
        "related_by_tags_display",
    ]
    autocomplete_fields = []

    inlines = [ContentLinkInline, ContentCategoryOrderInline]

    fieldsets = (
        (
            None,
            {
                "fields": ("content_type", "title", "slug"),
            },
        ),
        (
            "Contenido",
            {
                "fields": ("file", "url", "text_content", "metadata"),
                "classes": ("collapse",),
                "description": "Rellena según el tipo de contenido: archivo, URL, o texto.",
            },
        ),
        (
            "Organización",
            {
                "fields": ("tags",),
            },
        ),
        (
            "Grafo de Conocimiento",
            {
                "fields": (
                    "backlinks_display",
                    "outlinks_display",
                    "related_by_tags_display",
                ),
                "classes": ("collapse",),
                "description": "Visualización de conexiones con otros contenidos.",
            },
        ),
        (
            "Auditoría",
            {
                "fields": ("is_archived", "created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def tag_list(self, obj):
        tags = list(obj.tags.all()[:5])
        if not tags:
            return "-"
        tag_str = ", ".join(t.name for t in tags)
        if obj.tags.count() > 5:
            tag_str += f" (+{obj.tags.count() - 5})"
        return tag_str

    tag_list.short_description = "Tags"

    def link_count(self, obj):
        out = obj.outgoing_links.count()
        inc = obj.incoming_links.count()
        return format_html(
            '<span title="Salientes">↗{}</span> '
            '<span title="Entrantes">↙{}</span>',
            out,
            inc,
        )

    link_count.short_description = "Links"

    def backlinks_display(self, obj):
        """Display items that link TO this item (backlinks)"""
        backlinks = obj.get_backlinks()[:15]
        if not backlinks:
            return format_html(
                '<span style="color: #888;">Sin backlinks (ningún item enlaza aquí)</span>'
            )

        items = []
        for b in backlinks:
            url = reverse("admin:content_hub_contentitem_change", args=[b.id])
            items.append(
                f'<li><a href="{url}">[{b.get_content_type_display()}] {b.title}</a></li>'
            )

        total = obj.incoming_links.count()
        footer = ""
        if total > 15:
            footer = f'<li style="color: #888;">... y {total - 15} más</li>'

        return format_html(f'<ul style="margin:0; padding-left:20px;">{"".join(items)}{footer}</ul>')

    backlinks_display.short_description = "Backlinks (items que enlazan aquí)"

    def outlinks_display(self, obj):
        """Display items this item links TO"""
        outlinks = list(obj.outgoing_links.select_related("target")[:15])
        if not outlinks:
            return format_html(
                '<span style="color: #888;">Sin enlaces salientes</span>'
            )

        items = []
        for link in outlinks:
            target = link.target
            url = reverse("admin:content_hub_contentitem_change", args=[target.id])
            items.append(
                f'<li><a href="{url}">[{target.get_content_type_display()}] {target.title}</a> '
                f'<em style="color:#666;">({link.get_link_type_display()})</em></li>'
            )

        total = obj.outgoing_links.count()
        footer = ""
        if total > 15:
            footer = f'<li style="color: #888;">... y {total - 15} más</li>'

        return format_html(f'<ul style="margin:0; padding-left:20px;">{"".join(items)}{footer}</ul>')

    outlinks_display.short_description = "Enlaces salientes"

    def related_by_tags_display(self, obj):
        """Display items that share tags"""
        related = obj.get_related_by_tags(limit=10)
        if not related:
            return format_html(
                '<span style="color: #888;">Sin contenido relacionado por tags</span>'
            )

        items = []
        for r in related:
            url = reverse("admin:content_hub_contentitem_change", args=[r.id])
            shared_tags = set(obj.tags.names()) & set(r.tags.names())
            tags_str = ", ".join(list(shared_tags)[:3])
            items.append(
                f'<li><a href="{url}">{r.title}</a> '
                f'<em style="color:#666;">({tags_str})</em></li>'
            )

        return format_html(f'<ul style="margin:0; padding-left:20px;">{"".join(items)}</ul>')

    related_by_tags_display.short_description = "Relacionados por tags"

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("tags", "outgoing_links", "incoming_links")
        )


@admin.register(ContentLink)
class ContentLinkAdmin(admin.ModelAdmin):
    list_display = ["source", "link_type_display", "target", "created_at"]
    list_filter = ["link_type", "created_at"]
    autocomplete_fields = ["source", "target"]
    search_fields = ["source__title", "target__title", "notes"]
    date_hierarchy = "created_at"

    def link_type_display(self, obj):
        arrows = {
            "related": "↔",
            "part_of": "⊂",
            "derived": "←",
            "reference": "→",
            "created_by": "✎",
            "contains": "⊃",
            "prerequisite": "→|",
        }
        arrow = arrows.get(obj.link_type, "→")
        return f"{arrow} {obj.get_link_type_display()}"

    link_type_display.short_description = "Tipo"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "order", "content_count", "full_path_display"]
    list_filter = ["parent"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "description"]
    ordering = ["order", "name"]
    list_editable = ["order"]

    def content_count(self, obj):
        count = obj.contentcategoryorder_set.count()
        return count

    content_count.short_description = "# Items"

    def full_path_display(self, obj):
        return obj.get_full_path()

    full_path_display.short_description = "Ruta completa"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("parent")
            .annotate(item_count=models.Count("contentcategoryorder"))
        )
