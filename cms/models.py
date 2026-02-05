from django.db import models
from django import forms
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.safestring import mark_safe
from wagtail.models import Page, Orderable, Site
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException
from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    TextBlock,
    RichTextBlock,
    URLBlock,
    PageChooserBlock,
    StructBlock,
    ListBlock,
)
from wagtail.images.blocks import ImageChooserBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.snippets.models import register_snippet
from modelcluster.fields import ParentalKey, ParentalManyToManyField


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


class HelpIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    parent_page_types = [
        "cms.HomePage",
        "cms.StandardPage",
        "cms.MusicLibraryIndexPage",
    ]
    subpage_types = ["cms.HelpVideoPage"]

    class Meta:
        verbose_name = "Ayuda (Índice)"
        verbose_name_plural = "Ayuda"

    @classmethod
    def for_request(cls, request):
        qs = cls.objects.live()
        site = Site.find_for_request(request)
        if site:
            qs = qs.descendant_of(site.root_page, inclusive=True)
        return qs.order_by("path").first()

    def get_videos(self):
        return HelpVideoPage.objects.child_of(self).live().order_by("title").specific()


class HelpVideoPage(Page):
    intro = models.CharField(
        max_length=250,
        blank=True,
        help_text="Resumen corto del videotutorial",
    )
    video_url = models.URLField(
        help_text="Enlace del vídeo (YouTube, Vimeo, etc.)",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("video_url"),
    ]

    parent_page_types = ["cms.HelpIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Videotutorial"
        verbose_name_plural = "Videotutoriales"

    @classmethod
    def for_request_and_slug(cls, request, slug):
        index = HelpIndexPage.for_request(request)
        qs = cls.objects.live().filter(slug=slug)
        if index:
            qs = qs.descendant_of(index)
        return qs.order_by("path").first()

    def get_embed(self):
        try:
            return get_embed(self.video_url)
        except (EmbedException, ValueError):
            return None

    def get_thumbnail_url(self):
        embed = self.get_embed()
        if not embed:
            return ""
        return getattr(embed, "thumbnail_url", "") or ""

    def get_embed_html(self):
        embed = self.get_embed()
        if not embed:
            return ""
        return mark_safe(embed.html)


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


# =============================================================================
# DICTADO PAGE - StreamField Blocks
# =============================================================================


class AudioBlock(StructBlock):
    """Bloque de audio para reproductores WaveSurfer.js"""

    title = CharBlock(
        max_length=255,
        help_text="Título del audio (ej: 'Dictado 1', 'Ejercicio rítmico')",
    )
    audio_file = DocumentChooserBlock(
        help_text="Archivo de audio (MP3, WAV, OGG, etc.)"
    )
    description = TextBlock(
        required=False, help_text="Descripción o instrucciones opcionales"
    )

    class Meta:
        icon = "media"
        label = "Audio"
        template = "cms/blocks/audio_block.html"


class AnswerImageBlock(StructBlock):
    """Bloque de imagen como respuesta (colapsable)"""

    title = CharBlock(
        max_length=255,
        default="Ver respuesta",
        help_text="Título del widget colapsable",
    )
    image = ImageChooserBlock(help_text="Imagen de la respuesta")
    caption = TextBlock(required=False, help_text="Pie de imagen opcional")
    is_collapsed = BooleanBlock(
        default=True,
        required=False,
        help_text="Si está marcado, la respuesta estará oculta por defecto",
    )

    class Meta:
        icon = "image"
        label = "Respuesta (Imagen)"
        template = "cms/blocks/answer_image_block.html"


class AnswerPDFBlock(StructBlock):
    """Bloque de PDF como respuesta (colapsable)"""

    title = CharBlock(
        max_length=255,
        default="Ver partitura",
        help_text="Título del widget colapsable",
    )
    pdf = DocumentChooserBlock(help_text="PDF de la respuesta")
    description = TextBlock(required=False, help_text="Descripción opcional")
    is_collapsed = BooleanBlock(
        default=True,
        required=False,
        help_text="Si está marcado, la respuesta estará oculta por defecto",
    )

    class Meta:
        icon = "doc-full"
        label = "Respuesta (PDF)"
        template = "cms/blocks/answer_pdf_block.html"


class DictadoPage(Page):
    """Página de dictado musical con audio y respuestas ocultas"""

    date = models.DateField("Fecha de publicación", default=timezone.now)
    intro = RichTextField(
        blank=True,
        help_text="Instrucciones del dictado o contexto para el estudiante",
    )

    # StreamField para contenido flexible: audios + respuestas
    content = StreamField(
        [
            ("audio", AudioBlock()),
            ("answer_image", AnswerImageBlock()),
            ("answer_pdf", AnswerPDFBlock()),
        ],
        blank=True,
        help_text="Añade audios y respuestas (imágenes o PDFs). Los audios se reproducen con WaveSurfer.js",
    )

    # Categorías y tags para organización
    categories = ParentalManyToManyField("MusicCategory", blank=True)
    tags = ParentalManyToManyField("MusicTag", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("content"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("tags", widget=forms.CheckboxSelectMultiple),
    ]

    parent_page_types = ["cms.MusicLibraryIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Dictado"
        verbose_name_plural = "Dictados"


class AnswerOptionBlock(StructBlock):
    """Opción de respuesta para preguntas tipo test"""

    text = CharBlock(max_length=255, help_text="Texto de la respuesta")
    image = ImageChooserBlock(required=False, help_text="Imagen opcional")
    is_correct = BooleanBlock(
        required=False, help_text="Marca esta casilla si la respuesta es correcta"
    )

    class Meta:
        icon = "tick"
        label = "Opción"


class QuestionBlock(StructBlock):
    """Pregunta con 4 opciones"""

    prompt = CharBlock(max_length=255, help_text="Enunciado principal de la pregunta")
    description = TextBlock(required=False, help_text="Contexto o aclaraciones")
    illustration = ImageChooserBlock(required=False, help_text="Imagen opcional")
    options = ListBlock(
        AnswerOptionBlock(),
        min_num=4,
        max_num=4,
        help_text="Cada pregunta debe tener exactamente 4 opciones",
    )
    explanation = TextBlock(
        required=False,
        help_text="Explicación que se mostrará al revelar la respuesta",
    )

    class Meta:
        icon = "help"
        label = "Pregunta de Test"


class TestPage(Page):
    """Página con preguntas tipo test"""

    date = models.DateField("Fecha de publicación", default=timezone.now)
    intro = models.CharField(
        max_length=250,
        blank=True,
        help_text="Breve descripción del test",
    )
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Imagen destacada para la tarjeta del test",
    )
    questions = StreamField(
        [
            ("question", QuestionBlock()),
        ],
        use_json_field=True,
    )
    categories = ParentalManyToManyField("MusicCategory", blank=True)
    tags = ParentalManyToManyField("MusicTag", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("questions"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("tags", widget=forms.CheckboxSelectMultiple),
    ]

    parent_page_types = ["cms.MusicLibraryIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Test Musical"
        verbose_name_plural = "Tests Musicales"

    def clean(self):
        super().clean()
        errors = []
        for block in self.questions:
            if block.block_type != "question":
                continue
            correct_count = sum(
                1 for option in block.value["options"] if option["is_correct"]
            )
            if correct_count != 1:
                prompt = block.value["prompt"]
                errors.append(
                    ValidationError(
                        f"La pregunta '{prompt}' debe tener exactamente una respuesta correcta."
                    )
                )
        if errors:
            raise ValidationError({"questions": errors})


# Modelos para sesiones de clase musicales
# ------------------------------------------------------------------------------
# NOTA: ClassSessionPage y SessionMusicItem removidas temporalmente
# Requieren refactorización para usar clases.Group en lugar de classroom.Course
# y actualizar referencias a music_cards

# class ClassSessionPage(Page):
#     """Página de Wagtail para una sesión de clase musical"""
#     session_date = models.DateField(help_text="Fecha de la sesión de clase")
#     course = models.ForeignKey("clases.Group", on_delete=models.PROTECT, ...)
#     ...
#
# class SessionMusicItem(Orderable):
#     """Relación entre sesión de clase y elementos musicales"""
#     page = ParentalKey(ClassSessionPage, ...)
#     ...

# class MusicExercisePage(Page):
#     """Página para ejercicios musicales individuales"""
#     # También requiere refactorización - tiene referencia a music_cards.MusicItem
#     ...


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
    """Block para PDF - MUSIC PILLS"""

    title = CharBlock(max_length=200, help_text="Título del PDF")
    pdf_file = DocumentChooserBlock(help_text="Seleccionar archivo PDF")
    description = TextBlock(required=False, help_text="Descripción opcional")
    page_count = CharBlock(max_length=10, required=False, help_text="Número de páginas")

    class Meta:
        icon = "doc-full-inverse"
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


class ImageBlock(StructBlock):
    """Block para imágenes - MUSIC PILLS"""

    title = CharBlock(max_length=200, help_text="Título de la imagen")
    image = ImageChooserBlock(help_text="Seleccionar imagen")
    caption = TextBlock(
        required=False, help_text="Texto alternativo para accesibilidad"
    )

    class Meta:
        icon = "image"
        label = "Image"


class URLCardBlock(StructBlock):
    title = CharBlock(max_length=200, help_text="Título del enlace")
    url = URLBlock(help_text="URL")

    class Meta:
        icon = "link"
        label = "URL"


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

    # Permitir ScorePage, SetlistPage, BlogPage, TestPage y DictadoPage como hijos
    subpage_types = [
        "cms.ScorePage",
        "cms.SetlistPage",
        "cms.BlogPage",
        "cms.TestPage",
        "cms.DictadoPage",
    ]

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
        except (ProgrammingError, OperationalError):
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
        except (ProgrammingError, OperationalError):
            # Si la tabla BlogPage no existe aún, devolver lista vacía
            context["blog_posts"] = []
            context["blog_posts_count"] = 0

        # Obtener todas las páginas de test que son hijas de esta página
        try:
            test_pages = (
                TestPage.objects.child_of(self).live().order_by("-first_published_at")
            )
            context["test_pages"] = test_pages
            context["test_pages_count"] = test_pages.count()
        except (ProgrammingError, OperationalError):
            context["test_pages"] = []
            context["test_pages_count"] = 0

        # Obtener todas las páginas de dictado que son hijas de esta página
        try:
            dictado_pages = (
                DictadoPage.objects.child_of(self).live().order_by("-first_published_at")
            )
            context["dictado_pages"] = dictado_pages
            context["dictado_pages_count"] = dictado_pages.count()
        except (ProgrammingError, OperationalError):
            # Si la tabla DictadoPage no existe aún, devolver lista vacía
            context["dictado_pages"] = []
            context["dictado_pages_count"] = 0

        # Combinar scores y dictados en una sola lista de contenido musical
        music_content = []
        for score in context["scores"]:
            music_content.append({"type": "score", "page": score})
        for dictado in context["dictado_pages"]:
            music_content.append({"type": "dictado", "page": dictado})
        
        # Ordenar por fecha de publicación
        music_content.sort(
            key=lambda item: (
                item["page"].first_published_at
                or item["page"].latest_revision_created_at
            ),
            reverse=True,
        )
        context["music_content"] = music_content
        context["music_content_count"] = len(music_content)

        # Combinar entradas tipo blog/test para la sección de artículos
        combined_entries = []
        for post in context["blog_posts"]:
            combined_entries.append({"type": "blog", "page": post})
        for test in context["test_pages"]:
            combined_entries.append({"type": "test", "page": test})
        combined_entries.sort(
            key=lambda item: (
                item["page"].first_published_at
                or item["page"].latest_revision_created_at
            ),
            reverse=True,
        )
        context["blog_entries"] = combined_entries
        context["blog_entries_count"] = len(combined_entries)

        return context


class ScorePageCategory(Orderable):
    """
    Through model para ordenar ScorePages dentro de cada categoría.
    Hereda 'sort_order' de Orderable automáticamente.
    """

    score_page = ParentalKey(
        "ScorePage",
        on_delete=models.CASCADE,
        related_name="score_categories",
    )
    category = models.ForeignKey(
        "MusicCategory",
        on_delete=models.CASCADE,
        related_name="category_scores",
    )

    class Meta:
        unique_together = ["score_page", "category"]
        ordering = ["sort_order"]  # Campo heredado de Orderable
        verbose_name = "Partitura"
        verbose_name_plural = "Partituras"

    panels = [
        FieldPanel("score_page"),
    ]

    def save(self, *args, **kwargs):
        """Asegurar que sort_order tenga un valor válido al crear"""
        if self.sort_order is None:
            # Obtener el máximo sort_order actual para esta categoría
            max_order = (
                ScorePageCategory.objects.filter(category=self.category)
                .aggregate(models.Max("sort_order"))["sort_order__max"]
            )
            self.sort_order = (max_order + 1) if max_order is not None else 0
        super().save(*args, **kwargs)


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
    categories = ParentalManyToManyField(
        "MusicCategory",
        through="ScorePageCategory",
        blank=True,
    )
    tags = ParentalManyToManyField("MusicTag", blank=True)

    # StreamField para contenido flexible
    content = StreamField(
        [
            ("pdf_score", PDFBlock()),
            ("metadata", MetadataBlock()),
            ("bookmarks", ListBlock(BookmarkBlock())),
            ("notes", RichTextBlock()),
            ("audio", AudioBlock()),
            ("image", ImageBlock()),
            ("url", URLCardBlock()),
            ("embed", EmbedBlock()),
        ],
        blank=True,
        use_json_field=True,
    )

    # Campos difficulty_level y rating eliminados - usar tags para clasificación de dificultad

    content_panels = Page.content_panels + [
        FieldPanel("composer"),
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

    def get_images(self):
        """Obtener todos los bloques de imagen del StreamField de contenido"""
        images = []
        for block in self.content:
            if block.block_type == "image":
                images.append(block.value)
        return images

    def get_embeds(self):
        """Obtener todos los embeds del StreamField de contenido"""
        embeds = []
        for block in self.content:
            if block.block_type == "embed":
                embeds.append(block.value)
        return embeds

    def get_embed_html_for_url(self, embed_url):
        if not embed_url:
            return ""

        if embed_url not in self.get_embeds():
            return ""

        try:
            embed = get_embed(embed_url)
        except (EmbedException, ValueError):
            return ""

        return getattr(embed, "html", "") or ""

    def get_all_tags(self):
        """
        Obtener unión de todas las tags de:
        1. Tags directas de ScorePage (MusicTag)
        2. Tags de PDFs en el StreamField
        3. Tags de audios en el StreamField
        4. Tags de imágenes en el StreamField

        Returns: Lista de objetos tag únicos (sin duplicados)
        """
        all_tags = []

        # 1. Tags directas (MusicTag)
        all_tags.extend(self.tags.all())

        # 2. Tags de PDFs
        for pdf_block in self.get_pdf_blocks():
            if pdf_block.get("pdf_file") and hasattr(pdf_block["pdf_file"], "tags"):
                all_tags.extend(pdf_block["pdf_file"].tags.all())

        # 3. Tags de audios
        for audio_block in self.get_audios():
            if audio_block.get("audio_file") and hasattr(
                audio_block["audio_file"], "tags"
            ):
                all_tags.extend(audio_block["audio_file"].tags.all())

        # 4. Tags de imágenes
        for image_block in self.get_images():
            if image_block.get("image") and hasattr(image_block["image"], "tags"):
                all_tags.extend(image_block["image"].tags.all())

        # Deduplicar por nombre (case-insensitive)
        seen_names = set()
        unique_tags = []
        for tag in all_tags:
            tag_name_lower = tag.name.lower()
            if tag_name_lower not in seen_names:
                seen_names.add(tag_name_lower)
                unique_tags.append(tag)

        return unique_tags

    @property
    def all_tags(self):
        """Property para acceso desde templates: {{ page.all_tags }}"""
        return self.get_all_tags()


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
