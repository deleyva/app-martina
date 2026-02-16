"""
Content Hub Models - Knowledge Graph for Musical Content

Philosophy: Everything is a ContentItem (like an Obsidian note).
Relationships are ContentLinks (like [[wikilinks]] with semantics).
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from taggit.managers import TaggableManager

User = get_user_model()


class ContentItem(models.Model):
    """
    Atomic unit of content - equivalent to an Obsidian note.
    EVERYTHING is a ContentItem: songs, authors, PDFs, embeds, images, audio, text.
    """

    class ContentType(models.TextChoices):
        # Semantic entities
        SONG = "song", "Canción"
        AUTHOR = "author", "Autor/Compositor"
        ALBUM = "album", "Álbum/Colección"

        # Multimedia content
        PDF = "pdf", "PDF/Partitura"
        AUDIO = "audio", "Audio"
        IMAGE = "image", "Imagen"
        VIDEO = "video", "Vídeo"

        # External references
        EMBED = "embed", "Embed (Hooktheory, YouTube, etc.)"
        URL = "url", "URL/Enlace"

        # Text
        NOTE = "note", "Nota/Texto libre"
        EXERCISE = "exercise", "Ejercicio"

    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        db_index=True,
        verbose_name="Tipo de contenido",
    )
    title = models.CharField(max_length=255, verbose_name="Título")
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    # Content storage (mutually exclusive based on content_type)
    file = models.FileField(
        upload_to="content_hub/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="Archivo",
    )
    url = models.URLField(blank=True, max_length=500, verbose_name="URL")
    text_content = models.TextField(
        blank=True,
        verbose_name="Contenido de texto",
        help_text="Para notas, ejercicios, HTML de embeds",
    )

    # Flexible metadata (JSONB in PostgreSQL)
    # Examples by type:
    # - song: {key: "C", tempo: 120, time_signature: "4/4", difficulty: 3}
    # - author: {birth_year: 1685, death_year: 1750, nationality: "German"}
    # - embed: {provider: "hooktheory", embed_code: "...", width: 800, height: 400}
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadatos",
        help_text="Datos estructurados según el tipo de contenido",
    )

    # Tagging (django-taggit with global tags)
    tags = TaggableManager(blank=True, verbose_name="Etiquetas")

    # Categories (orderable for sequential material)
    categories = models.ManyToManyField(
        "Category",
        through="ContentCategoryOrder",
        blank=True,
        verbose_name="Categorías",
    )

    # Knowledge graph (links to other ContentItems)
    # Access: item.outgoing_links.all(), item.incoming_links.all()
    linked_to = models.ManyToManyField(
        "self",
        through="ContentLink",
        through_fields=("source", "target"),
        symmetrical=False,
        blank=True,
    )

    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_content",
        verbose_name="Creado por",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    # Soft delete
    is_archived = models.BooleanField(
        default=False,
        verbose_name="Archivado",
        help_text="Contenido archivado no aparece en búsquedas",
    )

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Elemento de contenido"
        verbose_name_plural = "Elementos de contenido"
        indexes = [
            models.Index(fields=["content_type", "is_archived"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        return f"[{self.get_content_type_display()}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = "item"
            self.slug = base_slug
            # Handle uniqueness
            counter = 1
            while ContentItem.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    # Convenience methods
    def get_backlinks(self):
        """Get all items that link TO this item (Obsidian-style backlinks)"""
        return ContentItem.objects.filter(outgoing_links__target=self).distinct()

    def get_outlinks(self):
        """Get all items this item links TO"""
        return ContentItem.objects.filter(incoming_links__source=self).distinct()

    def get_songs_by_author(self):
        """If this is an author, return their songs"""
        if self.content_type != self.ContentType.AUTHOR:
            return ContentItem.objects.none()
        return ContentItem.objects.filter(
            outgoing_links__target=self,
            outgoing_links__link_type=ContentLink.LinkType.CREATED_BY,
            content_type=self.ContentType.SONG,
        )

    def get_related_by_tags(self, limit=10):
        """Get items that share tags with this item"""
        if not self.tags.exists():
            return ContentItem.objects.none()

        tag_names = list(self.tags.names())
        return (
            ContentItem.objects.filter(tags__name__in=tag_names)
            .exclude(pk=self.pk)
            .exclude(is_archived=True)
            .distinct()[:limit]
        )


class ContentLink(models.Model):
    """
    Typed directional link between ContentItems.
    Equivalent to [[wikilinks]] in Obsidian but with semantics.
    """

    class LinkType(models.TextChoices):
        RELATED = "related", "Relacionado con"
        PART_OF = "part_of", "Es parte de"
        DERIVED = "derived", "Derivado de"
        REFERENCE = "reference", "Hace referencia a"
        CREATED_BY = "created_by", "Creado por"  # Song → Author
        CONTAINS = "contains", "Contiene"  # Album → Songs
        PREREQUISITE = "prerequisite", "Requiere conocer"  # For sequential material

    source = models.ForeignKey(
        ContentItem,
        on_delete=models.CASCADE,
        related_name="outgoing_links",
        verbose_name="Origen",
    )
    target = models.ForeignKey(
        ContentItem,
        on_delete=models.CASCADE,
        related_name="incoming_links",
        verbose_name="Destino",
    )
    link_type = models.CharField(
        max_length=20,
        choices=LinkType.choices,
        default=LinkType.RELATED,
        verbose_name="Tipo de enlace",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Contexto adicional del enlace",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")

    class Meta:
        unique_together = ["source", "target", "link_type"]
        verbose_name = "Enlace de contenido"
        verbose_name_plural = "Enlaces de contenido"
        indexes = [
            models.Index(fields=["link_type"]),
        ]

    def __str__(self):
        return f"{self.source.title} --[{self.get_link_type_display()}]--> {self.target.title}"


class Category(models.Model):
    """
    Hierarchical categories for organizing sequential content.
    E.g.: "Curso de Armonía" > "Módulo 1: Intervalos" > "Lección 1.1"
    """

    name = models.CharField(max_length=100, verbose_name="Nombre")
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Categoría padre",
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Icono",
        help_text="Emoji o clase de icono CSS",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["order", "name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            if not base_slug:
                base_slug = "category"
            self.slug = base_slug
            counter = 1
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_ancestors(self):
        """Return list of ancestors (for breadcrumbs)"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_full_path(self):
        """Return full path as string"""
        ancestors = self.get_ancestors()
        path_parts = [a.name for a in ancestors] + [self.name]
        return " > ".join(path_parts)


class ContentCategoryOrder(models.Model):
    """
    Through model for ordering content within categories.
    Allows a ContentItem to appear in multiple categories with different order.
    """

    content = models.ForeignKey(
        ContentItem,
        on_delete=models.CASCADE,
        verbose_name="Contenido",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        verbose_name="Categoría",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        ordering = ["order"]
        unique_together = ["content", "category"]
        verbose_name = "Orden de contenido en categoría"
        verbose_name_plural = "Órdenes de contenido en categorías"

    def __str__(self):
        return f"{self.content.title} en {self.category.name} (#{self.order})"
