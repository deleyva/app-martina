"""
Content Hub Views - Quick Add, Detail, and Search Views
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
    DeleteView,
    TemplateView,
)

from .forms import (
    QuickContentForm,
    AuthorContentForm,
    SongContentForm,
    ContentSearchForm,
)
from .models import ContentItem, ContentLink, Category


class ContentHubIndexView(LoginRequiredMixin, TemplateView):
    """Dashboard view for Content Hub"""

    template_name = "content_hub/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Recent content
        context["recent_items"] = ContentItem.objects.filter(
            is_archived=False
        ).select_related("created_by").prefetch_related("tags")[:10]

        # Stats
        context["stats"] = {
            "total_items": ContentItem.objects.filter(is_archived=False).count(),
            "total_songs": ContentItem.objects.filter(
                content_type=ContentItem.ContentType.SONG, is_archived=False
            ).count(),
            "total_authors": ContentItem.objects.filter(
                content_type=ContentItem.ContentType.AUTHOR, is_archived=False
            ).count(),
            "total_links": ContentLink.objects.count(),
            "total_categories": Category.objects.count(),
        }

        # Content by type
        context["content_by_type"] = (
            ContentItem.objects.filter(is_archived=False)
            .values("content_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Categories
        context["categories"] = Category.objects.filter(parent__isnull=True).prefetch_related(
            "children"
        )[:10]

        return context


class QuickAddView(LoginRequiredMixin, CreateView):
    """
    Quick form for adding content.
    Auto-detects type from input (URL → embed/url, File → pdf/audio/image).
    """

    model = ContentItem
    form_class = QuickContentForm
    template_name = "content_hub/quick_add.html"
    success_url = reverse_lazy("content_hub:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        # Auto-detect content_type from input
        if form.cleaned_data.get("url"):
            form.instance.content_type = self._detect_url_type(form.cleaned_data["url"])
        elif form.cleaned_data.get("file"):
            form.instance.content_type = self._detect_file_type(form.cleaned_data["file"])
        else:
            form.instance.content_type = ContentItem.ContentType.NOTE

        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Contenido "{self.object.title}" creado correctamente.',
        )
        return response

    def _detect_url_type(self, url: str) -> str:
        """Detect content type from URL"""
        embed_domains = [
            "hooktheory.com",
            "youtube.com",
            "youtu.be",
            "soundcloud.com",
            "spotify.com",
            "vimeo.com",
        ]
        url_lower = url.lower()
        if any(d in url_lower for d in embed_domains):
            return ContentItem.ContentType.EMBED
        return ContentItem.ContentType.URL

    def _detect_file_type(self, file) -> str:
        """Detect content type from uploaded file"""
        ext = file.name.lower().split(".")[-1] if "." in file.name else ""
        type_map = {
            "pdf": ContentItem.ContentType.PDF,
            "mp3": ContentItem.ContentType.AUDIO,
            "wav": ContentItem.ContentType.AUDIO,
            "ogg": ContentItem.ContentType.AUDIO,
            "flac": ContentItem.ContentType.AUDIO,
            "m4a": ContentItem.ContentType.AUDIO,
            "jpg": ContentItem.ContentType.IMAGE,
            "jpeg": ContentItem.ContentType.IMAGE,
            "png": ContentItem.ContentType.IMAGE,
            "gif": ContentItem.ContentType.IMAGE,
            "webp": ContentItem.ContentType.IMAGE,
            "mp4": ContentItem.ContentType.VIDEO,
            "webm": ContentItem.ContentType.VIDEO,
            "mov": ContentItem.ContentType.VIDEO,
        }
        return type_map.get(ext, ContentItem.ContentType.NOTE)


class QuickAddAuthorView(LoginRequiredMixin, CreateView):
    """Quick form for adding Authors"""

    model = ContentItem
    form_class = AuthorContentForm
    template_name = "content_hub/quick_add_author.html"
    success_url = reverse_lazy("content_hub:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Autor "{self.object.title}" creado correctamente.',
        )
        return response


class QuickAddSongView(LoginRequiredMixin, CreateView):
    """Quick form for adding Songs with author linking"""

    model = ContentItem
    form_class = SongContentForm
    template_name = "content_hub/quick_add_song.html"
    success_url = reverse_lazy("content_hub:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Canción "{self.object.title}" creada correctamente.',
        )
        return response


class ContentDetailView(LoginRequiredMixin, DetailView):
    """Detail view showing content and its knowledge graph connections"""

    model = ContentItem
    template_name = "content_hub/detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return ContentItem.objects.prefetch_related(
            "tags",
            "categories",
            "outgoing_links__target",
            "incoming_links__source",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object

        # Backlinks (items that link to this)
        context["backlinks"] = obj.get_backlinks()[:20]

        # Outlinks (items this links to)
        context["outlinks"] = obj.outgoing_links.select_related("target")[:20]

        # Related by tags
        context["related_by_tags"] = obj.get_related_by_tags(limit=10)

        # If author, show their songs
        if obj.content_type == ContentItem.ContentType.AUTHOR:
            context["author_songs"] = ContentItem.objects.filter(
                outgoing_links__target=obj,
                outgoing_links__link_type=ContentLink.LinkType.CREATED_BY,
            ).distinct()[:20]

        # If song, show author
        if obj.content_type == ContentItem.ContentType.SONG:
            author_link = obj.outgoing_links.filter(
                link_type=ContentLink.LinkType.CREATED_BY
            ).first()
            context["song_author"] = author_link.target if author_link else None

        return context


class ContentListView(LoginRequiredMixin, ListView):
    """List view with search and filtering"""

    model = ContentItem
    template_name = "content_hub/list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        queryset = ContentItem.objects.filter(is_archived=False).prefetch_related(
            "tags", "categories"
        ).select_related("created_by")

        # Search query
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(text_content__icontains=q)
                | Q(tags__name__icontains=q)
            ).distinct()

        # Filter by content type
        content_type = self.request.GET.get("content_type")
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        # Filter by tags
        tags_str = self.request.GET.get("tags", "").strip()
        if tags_str:
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            for tag in tags:
                queryset = queryset.filter(tags__name__iexact=tag)

        # Filter by category
        category_id = self.request.GET.get("category")
        if category_id:
            queryset = queryset.filter(categories__id=category_id)

        return queryset.order_by("-updated_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = ContentSearchForm(self.request.GET)
        context["content_types"] = ContentItem.ContentType.choices
        context["categories"] = Category.objects.all()
        return context


class ContentUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for content items"""

    model = ContentItem
    form_class = QuickContentForm
    template_name = "content_hub/edit.html"
    context_object_name = "item"

    def get_success_url(self):
        return reverse("content_hub:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Contenido "{self.object.title}" actualizado.')
        return response


class ContentDeleteView(LoginRequiredMixin, DeleteView):
    """Delete view (soft delete - archives the item)"""

    model = ContentItem
    template_name = "content_hub/confirm_delete.html"
    success_url = reverse_lazy("content_hub:list")

    def form_valid(self, form):
        # Soft delete
        self.object.is_archived = True
        self.object.save()
        messages.success(self.request, f'Contenido "{self.object.title}" archivado.')
        return redirect(self.success_url)


class CategoryDetailView(LoginRequiredMixin, DetailView):
    """View content within a category"""

    model = Category
    template_name = "content_hub/category_detail.html"
    context_object_name = "category"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get content in this category, ordered
        context["items"] = (
            ContentItem.objects.filter(
                categories=self.object,
                is_archived=False,
            )
            .prefetch_related("tags")
            .order_by("contentcategoryorder__order")
        )

        # Subcategories
        context["subcategories"] = self.object.children.all()

        # Breadcrumbs
        context["breadcrumbs"] = self.object.get_ancestors()

        return context


class GraphView(LoginRequiredMixin, TemplateView):
    """Knowledge graph visualization (basic)"""

    template_name = "content_hub/graph.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all links for visualization
        links = ContentLink.objects.select_related("source", "target")[:500]

        # Build graph data for JavaScript
        nodes = {}
        edges = []

        for link in links:
            # Add source node
            if link.source.id not in nodes:
                nodes[link.source.id] = {
                    "id": link.source.id,
                    "label": link.source.title[:30],
                    "type": link.source.content_type,
                }
            # Add target node
            if link.target.id not in nodes:
                nodes[link.target.id] = {
                    "id": link.target.id,
                    "label": link.target.title[:30],
                    "type": link.target.content_type,
                }
            # Add edge
            edges.append({
                "source": link.source.id,
                "target": link.target.id,
                "type": link.link_type,
            })

        context["nodes"] = list(nodes.values())
        context["edges"] = edges

        return context


def create_link(request, source_pk, target_pk):
    """AJAX/POST endpoint to create a link between items"""
    if request.method != "POST":
        return redirect("content_hub:index")

    source = get_object_or_404(ContentItem, pk=source_pk)
    target = get_object_or_404(ContentItem, pk=target_pk)
    link_type = request.POST.get("link_type", ContentLink.LinkType.RELATED)

    ContentLink.objects.get_or_create(
        source=source,
        target=target,
        link_type=link_type,
        defaults={"notes": request.POST.get("notes", "")},
    )

    messages.success(request, f"Enlace creado: {source.title} → {target.title}")

    next_url = request.POST.get("next", reverse("content_hub:detail", kwargs={"pk": source_pk}))
    return redirect(next_url)
