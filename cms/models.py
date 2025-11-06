from django.db import models
from django import forms
from wagtail.models import Page, Orderable
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel
from wagtail.blocks import (
    CharBlock,
    TextBlock,
    RichTextBlock,
    PageChooserBlock,
    StructBlock,
    ListBlock,
)
from wagtail.images.blocks import ImageChooserBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.snippets.models import register_snippet
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.models import ClusterableModel


class HomePage(Page):
    """Página de inicio del sitio web"""

    hero_title = models.CharField(
        max_length=255, blank=True, help_text="Título principal de la página de inicio"
    )
    hero_subtitle = models.CharField(
        max_length=255, blank=True, help_text="Subtítulo de la página de inicio"
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Imagen principal de la página de inicio",
    )
    body = RichTextField(blank=True, help_text="Contenido principal de la página")

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title"),
                FieldPanel("hero_subtitle"),
                FieldPanel("hero_image"),
            ],
            heading="Sección Hero",
        ),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Página de Inicio"


class StandardPage(Page):
    """Página estándar con contenido flexible"""

    intro = models.TextField(blank=True, help_text="Introducción de la página")
    body = RichTextField(blank=True, help_text="Contenido principal de la página")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Página Estándar"


class BlogIndexPage(Page):
    """Página índice del blog"""

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    def get_context(self, request):
        context = super().get_context(request)
        # Obtener todas las páginas de blog que son hijas de esta página
        blogpages = self.get_children().live().order_by("-first_published_at")
        context["blogpages"] = blogpages
        return context

    class Meta:
        verbose_name = "Índice del Blog"


class BlogPage(Page):
    """Página individual de blog"""

    date = models.DateField("Fecha de publicación")
    intro = models.CharField(max_length=250, help_text="Resumen del artículo")
    body = RichTextField(blank=True)
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Imagen destacada del artículo",
    )
    
    # Categorías y tags
    categories = ParentalManyToManyField("MusicCategory", blank=True)
    tags = ParentalManyToManyField("MusicTag", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("body"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("tags", widget=forms.CheckboxSelectMultiple),
    ]

    # Permitir BlogPage como hijo de BlogIndexPage y MusicLibraryIndexPage
    parent_page_types = ["cms.BlogIndexPage", "cms.MusicLibraryIndexPage"]

    class Meta:
        verbose_name = "Artículo de Blog"


# Modelos para sesiones de clase musicales
# ------------------------------------------------------------------------------


class ClassSessionPage(Page):
    """Página de Wagtail para una sesión de clase musical"""

    # Información básica de la sesión
    session_date = models.DateField(help_text="Fecha de la sesión de clase")
    start_time = models.TimeField(
        null=True, blank=True, help_text="Hora de inicio de la sesión"
    )
    end_time = models.TimeField(
        null=True, blank=True, help_text="Hora de finalización de la sesión"
    )

    # Relación con el modelo Course de la app classroom
    course = models.ForeignKey(
        "classroom.Course",
        on_delete=models.PROTECT,
        related_name="wagtail_sessions",
        help_text="Curso al que pertenece esta sesión",
    )

    # Descripción y objetivos de la sesión
    description = RichTextField(
        blank=True, help_text="Descripción detallada de la sesión"
    )
    objectives = RichTextField(
        blank=True, help_text="Objetivos de aprendizaje de la sesión"
    )

    # Notas del profesor
    teacher_notes = RichTextField(
        blank=True, help_text="Notas privadas del profesor para la sesión"
    )

    # Estado de la sesión
    STATUS_CHOICES = [
        ("draft", "Borrador"),
        ("planned", "Planificada"),
        ("in_progress", "En progreso"),
        ("completed", "Completada"),
        ("cancelled", "Cancelada"),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Estado actual de la sesión",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("course"),
                FieldPanel("session_date"),
                FieldPanel("start_time"),
                FieldPanel("end_time"),
                FieldPanel("status"),
            ],
            heading="Información de la Sesión",
        ),
        FieldPanel("description"),
        FieldPanel("objectives"),
        InlinePanel("session_music_items", label="Contenido Musical"),
        FieldPanel("teacher_notes"),
    ]

    # Configuración de páginas padre permitidas
    parent_page_types = ["cms.HomePage", "cms.StandardPage"]
    subpage_types = []  # No permitir subpáginas

    class Meta:
        verbose_name = "Sesión de Clase"
        verbose_name_plural = "Sesiones de Clase"

    def __str__(self):
        return f"{self.title} - {self.session_date}"

    def get_context(self, request):
        context = super().get_context(request)
        # Añadir contenido musical ordenado
        context["music_items"] = self.session_music_items.all().order_by("sort_order")
        return context


class SessionMusicItem(Orderable):
    """Relación entre sesión de clase y elementos musicales"""

    page = ParentalKey(
        ClassSessionPage, on_delete=models.CASCADE, related_name="session_music_items"
    )

    # Referencia al MusicItem de la app music_cards
    music_item = models.ForeignKey(
        "music_cards.MusicItem",
        on_delete=models.CASCADE,
        help_text="Elemento musical a incluir en la sesión",
    )

    # Notas específicas para esta sesión
    session_notes = RichTextField(
        blank=True,
        help_text="Notas específicas sobre cómo usar este elemento en la sesión",
    )

    # Tiempo estimado para trabajar este elemento
    estimated_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Tiempo estimado para este elemento (ej: 00:15:00 para 15 minutos)",
    )

    # Tipo de actividad
    ACTIVITY_TYPES = [
        ("warm_up", "Calentamiento"),
        ("technique", "Técnica"),
        ("repertoire", "Repertorio"),
        ("theory", "Teoría"),
        ("improvisation", "Improvisación"),
        ("listening", "Audición"),
        ("composition", "Composición"),
        ("review", "Repaso"),
    ]
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES,
        blank=True,
        help_text="Tipo de actividad musical",
    )

    panels = [
        FieldPanel("music_item"),
        FieldPanel("activity_type"),
        FieldPanel("estimated_duration"),
        FieldPanel("session_notes"),
    ]

    class Meta:
        verbose_name = "Elemento Musical de Sesión"
        verbose_name_plural = "Elementos Musicales de Sesión"

    def __str__(self):
        return f"{self.music_item.title} en {self.page.title}"


class MusicExercisePage(Page):
    """Página para ejercicios musicales individuales"""

    # Información del ejercicio
    difficulty_level = models.IntegerField(
        choices=[(i, f"Nivel {i}") for i in range(1, 6)],
        default=1,
        help_text="Nivel de dificultad del ejercicio (1-5)",
    )

    # Duración estimada
    estimated_duration = models.DurationField(
        null=True, blank=True, help_text="Duración estimada del ejercicio"
    )

    # Contenido del ejercicio
    instructions = RichTextField(help_text="Instrucciones detalladas del ejercicio")

    # Objetivos pedagógicos
    learning_objectives = RichTextField(
        blank=True, help_text="Objetivos de aprendizaje del ejercicio"
    )

    # Referencia a MusicItem relacionado
    related_music_item = models.ForeignKey(
        "music_cards.MusicItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Elemento musical relacionado (opcional)",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("difficulty_level"),
                FieldPanel("estimated_duration"),
                FieldPanel("related_music_item"),
            ],
            heading="Información del Ejercicio",
        ),
        FieldPanel("instructions"),
        FieldPanel("learning_objectives"),
    ]

    parent_page_types = ["cms.HomePage", "cms.StandardPage", "cms.ClassSessionPage"]

    class Meta:
        verbose_name = "Ejercicio Musical"
        verbose_name_plural = "Ejercicios Musicales"


# =============================================================================
# MUSIC PILLS - forScore Clone Models
# =============================================================================
# Esta sección contiene todos los modelos para Music Pills, una réplica de
# forScore enfocada en PDFs musicales. Estos modelos pueden ser extraídos
# fácilmente para usar en otra instalación de Wagtail.
# =============================================================================


# StreamField Blocks para contenido musical
# -----------------------------------------------------------------------------


class PDFBlock(StructBlock):
    """Block para documentos PDF - MUSIC PILLS"""

    title = CharBlock(max_length=200, help_text="Título del PDF")
    pdf_file = DocumentChooserBlock(help_text="Seleccionar archivo PDF")
    description = TextBlock(required=False, help_text="Descripción opcional")
    page_count = CharBlock(max_length=10, required=False, help_text="Número de páginas")

    class Meta:
        icon = "doc-full"
        label = "PDF Score"


class BookmarkBlock(StructBlock):
    """Block para bookmarks dentro de PDFs - MUSIC PILLS"""

    title = CharBlock(max_length=200)
    page_number = CharBlock(
        max_length=10, help_text="Número de página o rango (ej: '5' o '5-8')"
    )
    bookmark_type = CharBlock(
        max_length=10,
        help_text="Tipo: 'page' para página única, 'item' para rango de páginas",
    )
    notes = TextBlock(required=False)

    class Meta:
        icon = "bookmark"
        label = "Bookmark"


class MetadataBlock(StructBlock):
    """Block para metadatos musicales - MUSIC PILLS"""

    composer = CharBlock(max_length=200, required=False)
    key_signature = CharBlock(
        max_length=20, required=False, help_text="ej: C mayor, F# menor"
    )
    tempo = CharBlock(
        max_length=20, required=False, help_text="BPM o indicación de tempo"
    )
    difficulty = CharBlock(
        max_length=20,
        required=False,
        help_text="Principiante, Fácil, Intermedio, Avanzado, Experto",
    )
    duration_minutes = CharBlock(max_length=10, required=False)
    rating = CharBlock(max_length=5, required=False, help_text="1-5 estrellas")
    reference = CharBlock(
        max_length=200, required=False, help_text="Número de catálogo, opus, etc."
    )

    class Meta:
        icon = "tag"
        label = "Musical Metadata"


class AudioBlock(StructBlock):
    """Block para audio - MUSIC PILLS"""

    title = CharBlock(max_length=200, help_text="Título del audio")
    audio_file = DocumentChooserBlock(help_text="Seleccionar archivo audio")
    description = TextBlock(required=False, help_text="Descripción opcional")

    class Meta:
        icon = "media"
        label = "Audio"


# Snippets para Music Pills
# -----------------------------------------------------------------------------


@register_snippet
class MusicComposer(models.Model):
    """Compositor/Autor snippet - MUSIC PILLS"""

    name = models.CharField(max_length=200, unique=True)
    birth_year = models.PositiveIntegerField(null=True, blank=True)
    death_year = models.PositiveIntegerField(null=True, blank=True)
    bio = RichTextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("name"),
        MultiFieldPanel(
            [
                FieldPanel("birth_year"),
                FieldPanel("death_year"),
            ],
            heading="Fechas",
        ),
        FieldPanel("bio"),
    ]

    class Meta:
        ordering = ["name"]
        verbose_name = "Compositor Musical"
        verbose_name_plural = "Compositores Musicales"

    def __str__(self):
        return self.name


@register_snippet
class MusicCategory(models.Model):
    """Categorías jerárquicas - MUSIC PILLS"""

    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    description = RichTextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Clase CSS del icono")
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("parent"),
        FieldPanel("icon"),
        FieldPanel("description"),
    ]

    class Meta:
        verbose_name_plural = "Categorías Musicales"
        ordering = ["name"]
        unique_together = ["name", "parent"]
        verbose_name = "Categoría Musical"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    @property
    def full_path(self):
        """Obtener ruta completa de la categoría"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)


@register_snippet
class MusicTag(models.Model):
    """Etiquetas libres - MUSIC PILLS"""

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(
        max_length=7, default="#3B82F6", help_text="Código de color hex"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("color"),
    ]

    class Meta:
        ordering = ["name"]
        verbose_name = "Etiqueta Musical"
        verbose_name_plural = "Etiquetas Musicales"

    def __str__(self):
        return self.name


# Pages de Music Pills
# -----------------------------------------------------------------------------


class MusicLibraryIndexPage(Page):
    """Página principal de la biblioteca musical - MUSIC PILLS"""

    intro = RichTextField(
        blank=True, help_text="Texto de introducción para la biblioteca musical"
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    # Permitir ScorePage, SetlistPage y BlogPage como hijos
    subpage_types = ["cms.ScorePage", "cms.SetlistPage", "cms.BlogPage"]

    class Meta:
        verbose_name = "Biblioteca Musical"
        verbose_name_plural = "Bibliotecas Musicales"

    def get_context(self, request):
        context = super().get_context(request)
        # Obtener todas las páginas de partituras que son hijas de esta página
        try:
            scores = (
                ScorePage.objects.child_of(self).live().order_by("-first_published_at")
            )
            context["scores"] = scores
            # Forzar evaluación del queryset para capturar errores de DB aquí
            context["scores_count"] = scores.count()
        except:
            # Si la tabla ScorePage no existe aún, devolver lista vacía
            context["scores"] = []
            context["scores_count"] = 0
        
        # Obtener todas las páginas de blog que son hijas de esta página
        try:
            blog_posts = (
                BlogPage.objects.child_of(self).live().order_by("-first_published_at")
            )
            context["blog_posts"] = blog_posts
            context["blog_posts_count"] = blog_posts.count()
        except:
            # Si la tabla BlogPage no existe aún, devolver lista vacía
            context["blog_posts"] = []
            context["blog_posts_count"] = 0
        
        return context


class ScorePage(Page):
    """Página individual de partitura con PDF y metadatos - MUSIC PILLS"""

    # Metadatos básicos
    composer = models.ForeignKey(
        "MusicComposer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Seleccionar o añadir un compositor",
    )
    categories = ParentalManyToManyField("MusicCategory", blank=True)
    tags = ParentalManyToManyField("MusicTag", blank=True)

    # StreamField para contenido flexible
    content = StreamField(
        [
            ("pdf_score", PDFBlock()),
            ("metadata", MetadataBlock()),
            ("bookmarks", ListBlock(BookmarkBlock())),
            ("notes", RichTextBlock()),
            ("audio", AudioBlock()),
        ],
        blank=True,
        use_json_field=True,
    )

    # Campos adicionales
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ("beginner", "Principiante"),
            ("easy", "Fácil"),
            ("intermediate", "Intermedio"),
            ("advanced", "Avanzado"),
            ("expert", "Experto"),
        ],
        blank=True,
    )
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1-5 estrellas"
    )

    content_panels = Page.content_panels + [
        FieldPanel("composer"),
        FieldPanel("difficulty_level"),
        FieldPanel("rating"),
        FieldPanel("content"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("tags", widget=forms.CheckboxSelectMultiple),
    ]

    # Solo permitir este tipo de página bajo MusicLibraryIndexPage
    parent_page_types = ["cms.MusicLibraryIndexPage", "cms.SetlistPage"]
    subpage_types = []  # No permitir hijos

    class Meta:
        verbose_name = "Partitura"
        verbose_name_plural = "Partituras"

    def get_pdf_blocks(self):
        """Obtener todos los bloques PDF del StreamField de contenido"""
        pdf_blocks = []
        for block in self.content:
            if block.block_type == "pdf_score":
                pdf_blocks.append(block.value)
        return pdf_blocks

    def get_bookmarks(self):
        """Obtener todos los bloques de bookmarks del StreamField de contenido"""
        bookmarks = []
        for block in self.content:
            if block.block_type == "bookmarks":
                bookmarks.extend(block.value)
        return bookmarks

    def get_metadata(self):
        """Obtener bloque de metadatos del StreamField de contenido"""
        for block in self.content:
            if block.block_type == "metadata":
                return block.value
        return None

    def get_audios(self):
        """Obtener todos los bloques de audio del StreamField de contenido"""
        audios = []
        for block in self.content:
            if block.block_type == "audio":
                audios.append(block.value)
        return audios


class SetlistPage(Page):
    """Página para organizar partituras en setlists - MUSIC PILLS"""

    description = RichTextField(blank=True, help_text="Descripción de este setlist")

    # StreamField para elementos del setlist
    setlist_items = StreamField(
        [
            (
                "score_reference",
                PageChooserBlock(
                    page_type="cms.ScorePage",
                    help_text="Seleccionar una partitura de tu biblioteca",
                ),
            ),
            ("notes", RichTextBlock(help_text="Notas para este elemento del setlist")),
            (
                "separator",
                StructBlock(
                    [
                        (
                            "title",
                            CharBlock(
                                max_length=100,
                                help_text="Título de sección (ej: 'Intermedio')",
                            ),
                        ),
                    ],
                    icon="horizontalrule",
                ),
            ),
        ],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("setlist_items"),
    ]

    # Puede ser hijo de MusicLibraryIndexPage y puede contener ScorePages
    parent_page_types = ["cms.MusicLibraryIndexPage"]
    subpage_types = ["cms.ScorePage"]

    class Meta:
        verbose_name = "Lista de Reproducción"
        verbose_name_plural = "Listas de Reproducción"

    def get_scores(self):
        """Obtener todas las referencias de partituras del setlist"""
        scores = []
        for block in self.setlist_items:
            if block.block_type == "score_reference":
                score_page = block.value
                if score_page and score_page.live:
                    scores.append(score_page)
        return scores


# =============================================================================
# FIN DE MUSIC PILLS MODELS
# =============================================================================
