"""Biblioteca musical — `apps.iesmartinabescos.es`.

Sale de partir `cms` en la fase 25. Aquí vive todo lo que es música: el índice de
recursos, los libros que agrupan capítulos, las canciones, las partituras, los
dictados, los tests y los libros de estudio.

Dos cosas cambiaron de nombre al salir de `cms`, y son las que arreglan el lío:

- `BlogIndexPage` cuando colgaba de la biblioteca era «un libro». Ahora es
  `LibroPage`, un modelo propio, y ya no comparte formulario ni plantilla con el
  blog de un departamento.
- `BlogPage` cuando colgaba de la biblioteca era «una canción o un capítulo».
  Ahora es `RecursoPage`, y es la única que lleva ficha musical.

También desaparece `_is_blog_request()`: esta app solo se sirve en un host, así
que `get_template()` ya no decide nada por el `Host` de la petición.
"""

from functools import lru_cache

from django import forms
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models
from django.db.utils import OperationalError, ProgrammingError
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from taggit.models import Tag, TaggedItemBase
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    DecimalBlock,
    ListBlock,
    PageChooserBlock,
    RichTextBlock,
    StructBlock,
    TextBlock,
    URLBlock,
)
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Orderable, Page
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.snippets.models import register_snippet

from cms.adjuntos import AdjuntosMixin, adjuntos_field
from cms.visibilidad import filter_visible_pages


class ScorePageTag(TaggedItemBase):
    content_object = ParentalKey(
        "musica.ScorePage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class DictadoPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "musica.DictadoPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class TestPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "musica.TestPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class RecursoPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "musica.RecursoPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class AudioDictadoBlock(StructBlock):
    # Renombrado al partir la app: se llamaba `AudioBlock` igual que el de
    # partituras (mas abajo), que lo pisaba. Funcionaba solo porque DictadoPage
    # se define antes de la redefinicion. Dos bloques distintos, dos nombres.
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


class SlideBlock(StructBlock):
    """Slide: foto + audio con trim opcional"""
    image = ImageChooserBlock(help_text="Foto de la actuacion")
    caption = TextBlock(required=False, help_text="Pie de foto opcional")
    audio_file = DocumentChooserBlock(help_text="Grabacion de audio (MP3, WAV, OGG)")
    audio_title = CharBlock(max_length=255, required=False, help_text="Titulo del audio")
    start_time = DecimalBlock(required=False, help_text="Segundo de inicio (vacio = desde el principio)", min_value=0)
    end_time = DecimalBlock(required=False, help_text="Segundo de fin (vacio = hasta el final)", min_value=0)

    class Meta:
        icon = "image"
        label = "Slide (Foto + Audio)"


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
            ("audio", AudioDictadoBlock()),
            ("answer_image", AnswerImageBlock()),
            ("answer_pdf", AnswerPDFBlock()),
        ],
        blank=True,
        help_text="Añade audios y respuestas (imágenes o PDFs). Los audios se reproducen con WaveSurfer.js",
    )

    # Categorías y tags para organización
    categories = ParentalManyToManyField("MusicCategory", blank=True)
    faceted_tags = ClusterTaggableManager(
        through="musica.DictadoPageTag",
        blank=True,
        verbose_name="Etiquetas facetadas",
        help_text="Vocabulario facetado (faceta:valor). Convive con las etiquetas de arriba mientras dura la migración.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("content"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("faceted_tags", heading="Etiquetas facetadas"),
    ]

    parent_page_types = ["musica.MusicLibraryIndexPage"]
    subpage_types = []

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from_session = request.GET.get("from_session")
        if from_session:
            from_edit = request.GET.get("from") == "edit"
            if from_edit:
                context["back_url"] = reverse(
                    "clases:class_session_edit", args=[from_session]
                )
            else:
                context["back_url"] = reverse(
                    "clases:class_session_view", args=[from_session]
                )
        return context

    def get_template(self, request, *args, **kwargs):
        return "musica/dictado_page.html"

    class Meta:
        verbose_name = "Dictado"
        verbose_name_plural = "Dictados"


class SlidesConAudioPage(Page):
    """Presentacion de slides con foto + audio"""
    date = models.DateField("Fecha", default=timezone.now)
    intro = RichTextField(blank=True, help_text="Descripcion breve")
    slides = StreamField([("slide", SlideBlock())], blank=True, help_text="Anade slides: cada uno con una foto y un audio")

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("slides"),
    ]

    parent_page_types = ["musica.LibroPage"]
    subpage_types = []

    def get_template(self, request, *args, **kwargs):
        return "musica/slides_con_audio_page.html"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        import json
        slides_data = []
        for block in self.slides:
            slide = block.value
            slides_data.append({
                "image_url": slide["image"].get_rendition("fill-1200x800").url,
                "image_alt": slide.get("caption") or "",
                "audio_url": slide["audio_file"].url,
                "audio_title": slide.get("audio_title") or "",
                "start_time": float(slide["start_time"]) if slide.get("start_time") else None,
                "end_time": float(slide["end_time"]) if slide.get("end_time") else None,
            })
        context["slides_json"] = json.dumps(slides_data)
        return context

    class Meta:
        verbose_name = "Slides con Audio"
        verbose_name_plural = "Slides con Audio"


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
    faceted_tags = ClusterTaggableManager(
        through="musica.TestPageTag",
        blank=True,
        verbose_name="Etiquetas facetadas",
        help_text="Vocabulario facetado (faceta:valor). Convive con las etiquetas de arriba mientras dura la migración.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("questions"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("faceted_tags", heading="Etiquetas facetadas"),
    ]

    parent_page_types = ["musica.MusicLibraryIndexPage"]
    subpage_types = []

    def get_template(self, request, *args, **kwargs):
        return "musica/test_page.html"

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


@lru_cache(maxsize=1)
def _hay_unaccent():
    """¿Está disponible la extensión `unaccent` en esta base de datos?

    Crearla (migración `cms/0035`) exige superusuario de base de datos. Si un
    despliegue no lo tiene, el buscador del índice musical vuelve a distinguir
    tildes en vez de reventar la portada con un `FieldError`. Se cachea por
    proceso: habilitar la extensión más tarde pide reiniciar los contenedores.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'")
            return cursor.fetchone() is not None
    except Exception:
        return False


def q_texto(campo, texto):
    """`Q` que ignora mayúsculas y —si la base lo permite— también tildes.

    Sin `unaccent`, buscar "armonia" no encontraba "Armonía": `icontains` en
    Postgres respeta los acentos, así que media biblioteca era invisible salvo
    que se escribiera el acento exacto.
    """
    lookup = "unaccent__icontains" if _hay_unaccent() else "icontains"
    return models.Q(**{f"{campo}__{lookup}": texto})


# Vocabulario del filtro por tipo de contenido del índice musical. El `slug` es
# lo que viaja en `?types=`, así que es API pública: no se renombra sin romper
# los enlaces que la gente haya guardado.
TIPOS_DE_CONTENIDO = [
    {"slug": "partitura", "label": "Partituras", "icon": "🎼"},
    {"slug": "dictado", "label": "Dictados", "icon": "🎧"},
    {"slug": "articulo", "label": "Artículos", "icon": "📝"},
    {"slug": "libro", "label": "Libros", "icon": "📖"},
    {"slug": "test", "label": "Tests", "icon": "🧠"},
]


@register_snippet
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

    # Permitir ScorePage, SetlistPage, RecursoPage, LibroPage, TestPage y DictadoPage como hijos
    subpage_types = [
        "musica.LibroPage",
        "musica.ScorePage",
        "musica.SetlistPage",
        "musica.RecursoPage",
        "musica.TestPage",
        "musica.DictadoPage",
        "musica.LibroDeEstudioPage",
    ]

    def get_template(self, request, *args, **kwargs):
        return "musica/music_library_index_page.html"

    class Meta:
        verbose_name = "Biblioteca Musical"
        verbose_name_plural = "Bibliotecas Musicales"

    def get_context(self, request):
        context = super().get_context(request)
        # Obtener todas las páginas de partituras que son hijas de esta página
        # Obtener parámetros de filtrado
        tag_names = (
            request.GET.get("tags", "").split(",") if request.GET.get("tags") else []
        )
        category_names = (
            request.GET.get("categories", "").split(",")
            if request.GET.get("categories")
            else []
        )
        search_query = request.GET.get("q", "").strip()

        # Filtro por tipo de contenido. Se aceptan las dos formas: `?types=a&types=b`
        # (lo que envían las casillas del formulario) y `?types=a,b` (enlaces
        # compartidos a mano). Los valores desconocidos se descartan en silencio.
        tipos_pedidos = []
        for valor in request.GET.getlist("types"):
            tipos_pedidos.extend(t.strip().lower() for t in valor.split(","))
        tipos_validos = {t["slug"] for t in TIPOS_DE_CONTENIDO}
        # `dict.fromkeys` deduplica conservando el orden: htmx puede mandar el
        # mismo valor dos veces (el elemento que dispara + el `hx-include`).
        selected_types = [
            t for t in dict.fromkeys(tipos_pedidos) if t in tipos_validos
        ]

        # Los contadores de cada pastilla se calculan ANTES de filtrar por tipo:
        # así "Artículos · 3" sigue diciendo cuántos artículos casan con el texto
        # aunque ahora mismo solo estén visibles los dictados.
        type_counts = {}

        def aplicar_tipo(qs, slug):
            type_counts[slug] = type_counts.get(slug, 0) + qs.count()
            if selected_types and slug not in selected_types:
                return qs.none()
            return qs

        # Limpiar nombres
        tag_names = [name.strip() for name in tag_names if name.strip()]
        category_names = [name.strip() for name in category_names if name.strip()]

        # Función auxiliar para filtrar por tags y categorías
        def filter_queryset(qs):
            # Filtrar por texto si existe — busca en título, intro, compositor
            # (solo ScorePage) y también en nombres de tags, de modo que
            # escribir "jazz" encuentre elementos etiquetados como "jazz".
            if search_query:
                search_filters = q_texto("title", search_query)

                if hasattr(qs.model, 'intro'):
                    search_filters |= q_texto("intro", search_query)

                if qs.model.__name__ == 'ScorePage':
                    search_filters |= q_texto("composer__name", search_query)

                # Buscar por nombre de etiqueta. Desde C37b el vocabulario es
                # `faceted_tags` (taggit); `MusicTag` ya no existe.
                if hasattr(qs.model, 'faceted_tags'):
                    search_filters |= q_texto("faceted_tags__name", search_query)

                qs = qs.filter(search_filters)

            for tag in tag_names:
                qs = qs.filter(faceted_tags__name__iexact=tag)
            for category in category_names:
                qs = qs.filter(categories__name__iexact=category)
            return qs.distinct()

        # Obtener todas las páginas de partituras que son hijas de esta página
        try:
            scores = (
                ScorePage.objects.child_of(self).live()
                .select_related("composer")
                .prefetch_related("faceted_tags", "categories")
                .order_by("-first_published_at")
            )
            scores = aplicar_tipo(filter_queryset(scores), "partitura")
            context["scores"] = scores
            # Forzar evaluación del queryset para capturar errores de DB aquí
            context["scores_count"] = scores.count()
        except (ProgrammingError, OperationalError):
            # Si la tabla ScorePage no existe aún, devolver lista vacía
            type_counts.setdefault("partitura", 0)
            context["scores"] = []
            context["scores_count"] = 0

        # Obtener todas las páginas de blog que son hijas de esta página
        try:
            blog_posts = (
                RecursoPage.objects.child_of(self).live()
                .prefetch_related("faceted_tags", "categories")
                .order_by("-first_published_at")
            )
            blog_posts = filter_visible_pages(blog_posts, request)
            blog_posts = aplicar_tipo(filter_queryset(blog_posts), "articulo")
            context["blog_posts"] = blog_posts
            context["blog_posts_count"] = blog_posts.count()
        except (ProgrammingError, OperationalError):
            # Si la tabla RecursoPage no existe aún, devolver lista vacía
            type_counts.setdefault("articulo", 0)
            context["blog_posts"] = []
            context["blog_posts_count"] = 0

        # Obtener los libros (LibroPage hijos) — actúan como contenedores
        # de capítulos dentro de la biblioteca musical. No tienen tags propios
        # así que solo se filtran por título / intro.
        try:
            book_indexes = (
                LibroPage.objects.child_of(self).live()
                .order_by("-first_published_at")
            )
            book_indexes = filter_visible_pages(book_indexes, request)
            if search_query:
                book_indexes = book_indexes.filter(
                    q_texto("title", search_query)
                    | q_texto("intro", search_query)
                )
            book_indexes = aplicar_tipo(book_indexes.distinct(), "libro")
            context["book_indexes"] = book_indexes
        except (ProgrammingError, OperationalError):
            type_counts.setdefault("libro", 0)
            context["book_indexes"] = []

        # Obtener todas las páginas de test que son hijas de esta página
        try:
            test_pages = (
                TestPage.objects.child_of(self).live()
                .prefetch_related("faceted_tags", "categories")
                .order_by("-first_published_at")
            )
            test_pages = aplicar_tipo(filter_queryset(test_pages), "test")
            context["test_pages"] = test_pages
            context["test_pages_count"] = test_pages.count()
        except (ProgrammingError, OperationalError):
            type_counts.setdefault("test", 0)
            context["test_pages"] = []
            context["test_pages_count"] = 0

        # Obtener todas las páginas de dictado que son hijas de esta página
        try:
            dictado_pages = (
                DictadoPage.objects.child_of(self).live()
                .prefetch_related("faceted_tags", "categories")
                .order_by("-first_published_at")
            )
            dictado_pages = aplicar_tipo(filter_queryset(dictado_pages), "dictado")
            context["dictado_pages"] = dictado_pages
            context["dictado_pages_count"] = dictado_pages.count()
        except (ProgrammingError, OperationalError):
            # Si la tabla DictadoPage no existe aún, devolver lista vacía
            type_counts.setdefault("dictado", 0)
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
        # Server-side pagination: limit to 6 unless filtered or show_all
        is_filtered = tag_names or category_names or search_query or selected_types
        show_all_music = is_filtered or request.GET.get("show_all_music")
        if not show_all_music and len(music_content) > 6:
            context["has_more_music"] = True
            context["music_content_total"] = len(music_content)
            music_content = music_content[:6]
        context["music_content"] = music_content
        context["music_content_count"] = len(music_content)

        # Añadir todos los tags y categorías para los filtros
        # Solo las etiquetas que de verdad cuelgan de alguna de estas páginas:
        # `MusicTag.objects.all()` listaba también las que no usaba nadie.
        context["all_tags"] = (
            Tag.objects.filter(
                # El prefijo de la relacion inversa lleva el app_label, asi que
                # partir `cms` los renombro todos: `cms_blogpagetag_items` paso a
                # ser `musica_recursopagetag_items`. Falla en tiempo de consulta,
                # no de importacion: lo destaparon los tests del filtrado.
                models.Q(musica_recursopagetag_items__isnull=False)
                | models.Q(musica_scorepagetag_items__isnull=False)
                | models.Q(musica_dictadopagetag_items__isnull=False)
                | models.Q(musica_testpagetag_items__isnull=False)
            )
            .distinct()
            .order_by("name")
        )
        context["all_categories"] = MusicCategory.objects.all().order_by("name")
        context["search_query"] = search_query
        context["selected_types"] = selected_types

        # Libros de estudio (LibroDeEstudioPage). Estaban permitidos como hijos
        # desde que se creo el tipo, pero nunca se anadieron aqui, asi que no
        # salian en el indice ni en su buscador (destapado 2026-08-29 buscando
        # "Luciernaga"). Mismo filtro de visibilidad que el resto.
        try:
            libros_estudio = (
                LibroDeEstudioPage.objects.child_of(self).live()
                .order_by("-first_published_at")
            )
            libros_estudio = filter_visible_pages(libros_estudio, request)
            if search_query:
                libros_estudio = libros_estudio.filter(
                    q_texto("title", search_query)
                    | q_texto("intro", search_query)
                )
            libros_estudio = aplicar_tipo(libros_estudio.distinct(), "libro")
            context["libros_estudio"] = libros_estudio
        except (ProgrammingError, OperationalError):
            type_counts.setdefault("libro", 0)
            context["libros_estudio"] = []

        # Combinar entradas tipo libro/blog/test para la sección editorial.
        # Los libros (LibroPage) van primero dentro de la sección.
        combined_entries = []
        for book in context["book_indexes"]:
            combined_entries.append({"type": "book", "page": book})
        for libro in context["libros_estudio"]:
            combined_entries.append({"type": "book", "page": libro})
        for post in context["blog_posts"]:
            combined_entries.append({"type": "blog", "page": post})
        for test in context["test_pages"]:
            combined_entries.append({"type": "test", "page": test})
        # All entries sorted by date (most recent first)
        combined_entries.sort(
            key=lambda item: (
                item["page"].first_published_at
                or item["page"].latest_revision_created_at
                or item["page"].last_published_at
            ),
            reverse=True,
        )
        # Server-side pagination for blog entries
        show_all_blog = is_filtered or request.GET.get("show_all_blog")
        if not show_all_blog and len(combined_entries) > 6:
            context["has_more_blog"] = True
            context["blog_entries_total"] = len(combined_entries)
            combined_entries = combined_entries[:6]
        context["blog_entries"] = combined_entries
        context["blog_entries_count"] = len(combined_entries)

        # Pastillas de tipo. Se montan aquí, al final, porque `libros_estudio`
        # sigue sumando al contador de "libro" después de la sección de música.
        # `types_query` es la forma con comas, para los enlaces normales
        # ("mostrar todo") que no pasan por el formulario.
        context["types_query"] = ",".join(selected_types)
        context["type_facets"] = [
            {
                "slug": tipo["slug"],
                "label": tipo["label"],
                "icon": tipo["icon"],
                "count": type_counts.get(tipo["slug"], 0),
                "selected": tipo["slug"] in selected_types,
            }
            for tipo in TIPOS_DE_CONTENIDO
        ]
        context["total_matches"] = sum(type_counts.values())

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
    faceted_tags = ClusterTaggableManager(
        through="musica.ScorePageTag",
        blank=True,
        verbose_name="Etiquetas facetadas",
        help_text="Vocabulario facetado (faceta:valor). Convive con las etiquetas de arriba mientras dura la migración.",
    )

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
        FieldPanel("faceted_tags", heading="Etiquetas facetadas"),
    ]

    # Solo permitir este tipo de página bajo MusicLibraryIndexPage
    parent_page_types = ["musica.MusicLibraryIndexPage", "musica.SetlistPage"]
    subpage_types = []  # No permitir hijos

    def get_template(self, request, *args, **kwargs):
        return "musica/score_page.html"

    class Meta:
        verbose_name = "Partitura"
        verbose_name_plural = "Partituras"

    def _parse_content(self):
        """Parse content StreamField once and cache by block type."""
        if not hasattr(self, '_content_cache'):
            cache = {'pdfs': [], 'bookmarks': [], 'metadata': None,
                     'audios': [], 'images': [], 'embeds': []}
            for block in self.content:
                if block.block_type == "pdf_score":
                    cache['pdfs'].append(block.value)
                elif block.block_type == "bookmarks":
                    cache['bookmarks'].extend(block.value)
                elif block.block_type == "metadata":
                    cache['metadata'] = block.value
                elif block.block_type == "audio":
                    cache['audios'].append(block.value)
                elif block.block_type == "image":
                    cache['images'].append(block.value)
                elif block.block_type == "embed":
                    cache['embeds'].append(block.value)
            self._content_cache = cache
        return self._content_cache

    def get_pdf_blocks(self):
        return self._parse_content()['pdfs']

    def get_bookmarks(self):
        return self._parse_content()['bookmarks']

    def get_metadata(self):
        return self._parse_content()['metadata']

    def get_audios(self):
        return self._parse_content()['audios']

    def get_images(self):
        return self._parse_content()['images']

    def get_embeds(self):
        return self._parse_content()['embeds']

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
        1. Tags directas de la ScorePage (taggit facetado)
        2. Tags de PDFs en el StreamField
        3. Tags de audios en el StreamField
        4. Tags de imágenes en el StreamField

        Returns: Lista de objetos tag únicos (sin duplicados)
        """
        all_tags = []

        # 1. Tags directas de la página. Desde C37b son las facetadas; el
        # `MusicTag` plano ya no existe. Los PDFs, audios e imágenes de abajo
        # llevan taggit desde siempre y no cambian.
        all_tags.extend(self.faceted_tags.all())

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
                    page_type="musica.ScorePage",
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
    parent_page_types = ["musica.MusicLibraryIndexPage"]
    subpage_types = ["musica.ScorePage"]

    def get_template(self, request, *args, **kwargs):
        return "musica/setlist_page.html"

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


class LibroDeEstudioPage(Page):
    """Un libro que agrupa paginas que YA EXISTEN, sin moverlas del arbol.

    El problema que resuelve, y por que no vale un `LibroPage`: en Wagtail
    una pagina tiene UN padre, y su URL sale de ahi. Para juntar cuatro
    canciones de los 70 en un libro habria que moverlas, lo que les cambia la
    URL y, sobre todo, **las deja sin poder estar en ningun otro libro**. Una
    cancion pertenece a varios sitios a la vez ("los 70", "3 ESO", "acordes
    abiertos"), y el arbol no sabe expresar eso.

    Aqui el libro guarda REFERENCIAS. La pagina se queda donde vive, con su
    URL, y N libros la apuntan. Es el mismo patron que `SetlistPage` usa con
    las partituras, ampliado a cualquier pagina con material practicable.

    **El orden de los bloques ES el orden de estudio.** Arrastrar un capitulo
    en el editor cambia el orden en que su material sale en las sesiones, sin
    tocar nada mas.
    """

    intro = RichTextField(blank=True, help_text="De que va este libro")

    cover_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Portada",
    )

    @property
    def n_capitulos(self):
        """Los capitulos viven en el StreamField, no como paginas hijas, asi que
        `get_children` da 0 y la tarjeta del indice mentiria."""
        return len(self.capitulos)

    capitulos = StreamField(
        [
            (
                "pagina",
                PageChooserBlock(
                    page_type=["musica.RecursoPage", "musica.ScorePage", "musica.DictadoPage"],
                    help_text="Una pagina que ya existe. El orden manda.",
                ),
            ),
        ],
        blank=True,
        use_json_field=True,
        verbose_name="Capitulos",
        help_text="Arrastra para ordenar: este es el orden en que saldra a estudiar.",
    )

    is_protected = models.BooleanField(
        default=False,
        verbose_name="Protegida",
        help_text="Requiere iniciar sesión para ver esta página.",
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name="Privada",
        help_text="Solo el creador de la página puede verla.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("cover_image"),
        FieldPanel("capitulos"),
    ]

    settings_panels = Page.settings_panels + [
        MultiFieldPanel(
            [
                FieldPanel("is_protected"),
                FieldPanel("is_private"),
            ],
            heading="Visibilidad",
        ),
    ]

    subpage_types = []

    class Meta:
        verbose_name = "Libro de estudio"
        verbose_name_plural = "Libros de estudio"

    def get_template(self, request, *args, **kwargs):
        # Dos pieles, como el resto del sitio: blogs.iesmartinabescos lleva la
        # del blog, apps.iesmartinabescos la de la aplicacion. Sin esto se
        # servia siempre la del blog, que es la que hereda la plantilla base.
        return "musica/libro_de_estudio_page.html"

    def get_context(self, request, *args, **kwargs):
        contexto = super().get_context(request, *args, **kwargs)
        contexto["capitulos"] = self.paginas_referenciadas()
        return contexto

    def paginas_referenciadas(self):
        """Las paginas del libro, en el orden de los bloques.

        Se saltan las que ya no existen o no estan publicadas: un libro con una
        referencia rota tiene que seguir funcionando, no reventar la sesion.
        Se saltan tambien los duplicados, porque referenciar dos veces la misma
        pagina no anade material y si romperia el conteo de progreso.
        """
        paginas, vistas = [], set()
        for bloque in self.capitulos:
            if bloque.block_type != "pagina":
                continue
            pagina = bloque.value
            if pagina is None or not pagina.live or pagina.pk in vistas:
                continue
            vistas.add(pagina.pk)
            paginas.append(pagina.specific)
        return paginas


class LibroPage(Page):
    """Un libro de la biblioteca musical: agrupa capítulos en orden de árbol.

    Antes era `BlogIndexPage` colgando de `MusicLibraryIndexPage`, y compartía
    modelo, formulario y espacio de plantillas con el blog de un departamento.
    `get_template()` miraba los ancestros para decidir si devolver la plantilla
    editorial o la de libro; `get_context()` miraba lo mismo para decidir si los
    hijos van por fecha o por orden de árbol. Las dos ramas se han ido con el
    modelo: aquí un libro es un libro.

    No lleva `moderator` ni `subject`: un libro no tiene departamento que lo
    apruebe. Dos de los doce libros los tenían puestos al migrar (los dos con
    Jesús de moderador y «Música» de asignatura, herencia de compartir modelo);
    se descartan a propósito, y queda dicho en el ISA.
    """

    intro = RichTextField(blank=True)
    cover_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Portada",
        help_text="Imagen de portada del libro.",
    )
    is_protected = models.BooleanField(
        default=False,
        verbose_name="Protegida",
        help_text="Requiere iniciar sesión para ver este libro y sus capítulos.",
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name="Privada",
        help_text="Solo el creador puede verlo. Los capítulos heredan la restricción.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("cover_image"),
    ]

    settings_panels = Page.settings_panels + [
        MultiFieldPanel(
            [
                FieldPanel("is_protected"),
                FieldPanel("is_private"),
            ],
            heading="Visibilidad",
        ),
    ]

    parent_page_types = ["musica.MusicLibraryIndexPage", "musica.LibroPage"]
    subpage_types = [
        "musica.LibroPage",
        "musica.RecursoPage",
        "musica.SlidesConAudioPage",
        "musica.LibroDeEstudioPage",
    ]

    def get_template(self, request, *args, **kwargs):
        return "musica/libro.html"

    def get_context(self, request):
        context = super().get_context(request)
        # Orden de árbol: un libro se lee del capítulo 1 al 12, no del más
        # reciente al más viejo. Antes esto era una rama dentro del modelo
        # compartido; ahora es simplemente cómo funciona un libro.
        capitulos = list(
            filter_visible_pages(
                RecursoPage.objects.child_of(self).live(), request
            )
            .specific()
            .prefetch_related("categories")
            .order_by("path")
        )
        context["capitulos"] = capitulos
        context["blogpages"] = capitulos  # nombre heredado por las plantillas
        context["sublibros"] = list(
            filter_visible_pages(
                LibroPage.objects.child_of(self).live(), request
            ).specific()
        )
        return context

    class Meta:
        verbose_name = "Libro de la biblioteca"
        verbose_name_plural = "Libros de la biblioteca"


class RecursoPage(AdjuntosMixin, Page):
    """Una canción, un capítulo de libro o un recurso suelto de la biblioteca.

    Es la única página con ficha musical del sistema. Antes era `BlogPage`, la
    misma clase que usaba un profesor de geografía para contar una salida al
    Moncayo, y por eso aquel formulario pedía tonalidad y BPM. Ahora los ocho
    campos musicales viven aquí y solo aquí.
    """

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
    is_featured = models.BooleanField(
        default=False,
        verbose_name="Destacado",
        help_text="Marcar para mostrar en la portada del blog",
    )
    is_protected = models.BooleanField(
        default=False,
        verbose_name="Protegida",
        help_text="Requiere iniciar sesión para ver esta página.",
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name="Privada",
        help_text="Solo el creador de la página puede verla.",
    )

    attachments = adjuntos_field()

    # --- Metadatos musicales (2026-08-28) ---
    # BlogPage sustituye a ScorePage como único tipo de página de contenido.
    # Espejo de MetadataBlock, salvo `difficulty`: ese se clasifica con la
    # faceta de etiqueta `dificultad`, según la decisión ya tomada en ScorePage
    # ("Campos difficulty_level y rating eliminados - usar tags").
    # Todos opcionales: las BlogPage que no son canciones quedan intactas.
    artist = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Artista / compositor",
        help_text="Quién la firma. ej: Fito & Fitipaldis",
    )
    # Tonalidad como la guardan MusicXML 4.0 y el MIDI estándar: el número de
    # alteraciones en el círculo de quintas (negativo bemoles, positivo
    # sostenidos) más el modo por separado. MusicXML lo llama `fifths`; el SMF
    # lo llama `sf`/`mi` en el meta-evento FF 59. Es el mismo dato.
    # Guardarlo como texto ("Bm") impide ordenar, filtrar por armadura,
    # transportar o exportar a partitura sin volver a interpretar la cadena.
    key_fifths = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Armadura (quintas)",
        validators=[MinValueValidator(-7), MaxValueValidator(7)],
        help_text="-7 a 7. Negativo bemoles, positivo sostenidos. 0 = Do mayor / La menor.",
    )
    key_mode = models.CharField(
        max_length=12,
        blank=True,
        choices=[
            ("major", "Mayor"),
            ("minor", "Menor"),
            ("dorian", "Dórico"),
            ("phrygian", "Frigio"),
            ("lydian", "Lidio"),
            ("mixolydian", "Mixolidio"),
            ("aeolian", "Eólico"),
            ("locrian", "Locrio"),
        ],
        verbose_name="Modo",
        help_text="Valores de MusicXML. Los modales importan para el trabajo de improvisación.",
    )
    # Compás: dos enteros, como `beats` y `beat-type` en MusicXML y `nn`/`dd`
    # en el meta-evento FF 58. Nunca la cadena "4/4".
    time_signature_beats = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Compás — numerador",
        validators=[MinValueValidator(1), MaxValueValidator(64)],
        help_text="El número de arriba. ej: 4 en 4/4, 6 en 6/8",
    )
    time_signature_beat_type = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Compás — denominador",
        choices=[(1, "1"), (2, "2"), (4, "4"), (8, "8"), (16, "16"), (32, "32")],
        help_text="El número de abajo. Potencia de dos, como exige el estándar.",
    )
    # Tempo en pulsos por minuto, entero. MusicXML lo lleva en `<sound tempo>`
    # y el MIDI en microsegundos por negra: en los dos es un número, no texto.
    tempo_bpm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo (BPM)",
        validators=[MinValueValidator(20), MaxValueValidator(400)],
        help_text="Pulsos por minuto. ej: 151",
    )
    # Duración en segundos, no "3:24". ID3 la guarda en milisegundos (TLEN).
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duración (segundos)",
        help_text="En segundos. La plantilla la pinta como m:ss.",
    )
    reference = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Referencia",
        help_text="Número de catálogo, opus, o versión de referencia. ej: vers. Halestorm",
    )
    # El id de Songsterr no viene dentro del .gp, asi que hay que guardarlo. Si
    # se deja vacio, la plantilla cae en una busqueda por artista y titulo.
    songsterr_url = models.URLField(
        blank=True,
        max_length=500,
        verbose_name="Tablatura en Songsterr",
        help_text=(
            "URL de la canción en Songsterr, para el botón sobre la tablatura. "
            "Si se deja vacío, el botón busca por artista y título."
        ),
    )
    # Letra con acordes en formato ChordPro: [Am]texto y directivas {start_of_verse}.
    # La transposición la hace ChordSheetJS en el navegador, no se guarda transpuesta.
    chordpro = models.TextField(
        blank=True,
        verbose_name="Letra con acordes (ChordPro)",
        help_text=(
            "Formato ChordPro: los acordes entre corchetes justo antes de la sílaba "
            "en la que caen, p. ej. [Am]On the street where you [F]live. "
            "Directivas admitidas: {start_of_verse}, {end_of_verse}, {start_of_chorus}, "
            "{end_of_chorus}, {comment: ...}. No hace falta poner {title} ni {artist}: "
            "esos ya salen de la ficha."
        ),
    )

    categories = ParentalManyToManyField("musica.MusicCategory", blank=True)
    faceted_tags = ClusterTaggableManager(
        through="musica.RecursoPageTag",
        blank=True,
        verbose_name="Etiquetas facetadas",
        help_text="Vocabulario facetado (faceta:valor).",
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("is_featured"),
        FieldPanel("body"),
        FieldPanel("chordpro", heading="Letra con acordes (ChordPro)"),
        MultiFieldPanel(
            [
                FieldPanel("artist"),
                FieldPanel("key_fifths"),
                FieldPanel("key_mode"),
                FieldPanel("time_signature_beats"),
                FieldPanel("time_signature_beat_type"),
                FieldPanel("tempo_bpm"),
                FieldPanel("duration_seconds"),
                FieldPanel("reference"),
                FieldPanel("songsterr_url"),
            ],
            heading="Metadatos musicales",
            classname="collapsed",
        ),
        FieldPanel("attachments", heading="Adjuntos"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
        FieldPanel("faceted_tags", heading="Etiquetas facetadas"),
    ]

    settings_panels = Page.settings_panels + [
        MultiFieldPanel(
            [
                FieldPanel("is_protected"),
                FieldPanel("is_private"),
            ],
            heading="Visibilidad",
        ),
    ]

    parent_page_types = ["musica.MusicLibraryIndexPage", "musica.LibroPage", "musica.SetlistPage"]
    subpage_types = []

    # El dato se guarda como manda el estándar; estas propiedades lo devuelven
    # a la forma en que un músico lo lee. La plantilla nunca calcula nada.

    # Círculo de quintas. El índice 7 es 0 alteraciones.
    _TONICAS_MAYOR = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C",
                      "G", "D", "A", "E", "B", "F#", "C#"]
    _TONICAS_MENOR = ["Ab", "Eb", "Bb", "F", "C", "G", "D", "A",
                      "E", "B", "F#", "C#", "G#", "D#", "A#"]

    @property
    def key_display(self):
        """ej: Bm, D, G (mixolidio). Cadena vacía si no hay armadura."""
        if self.key_fifths is None:
            return ""
        i = self.key_fifths + 7
        if self.key_mode == "minor":
            return f"{self._TONICAS_MENOR[i]}m"
        if self.key_mode in ("", "major"):
            return self._TONICAS_MAYOR[i]
        # Modal: la tónica depende del modo, así que damos la armadura y el
        # nombre del modo en vez de inventar una tónica que podría no ser.
        return f"{self._TONICAS_MAYOR[i]} ({self.get_key_mode_display().lower()})"

    @property
    def time_signature_display(self):
        """ej: 4/4. Vacío si falta cualquiera de los dos números."""
        if not self.time_signature_beats or not self.time_signature_beat_type:
            return ""
        return f"{self.time_signature_beats}/{self.time_signature_beat_type}"

    @property
    def duration_display(self):
        """ej: 3:24."""
        if not self.duration_seconds:
            return ""
        minutos, segundos = divmod(self.duration_seconds, 60)
        return f"{minutos}:{segundos:02d}"

    @property
    def tiene_ficha_musical(self):
        return any([
            self.artist, self.key_display, self.time_signature_display,
            self.tempo_bpm, self.duration_display, self.reference,
        ])

    @property
    def songsterr_link(self):
        """URL para el botón que se superpone a la tablatura.

        El .gp no lleva dentro el id de Songsterr, asi que sin `songsterr_url`
        lo unico honesto es abrir su buscador con lo que si sabemos.
        Devuelve None cuando no hay ni URL ni titulo con el que buscar.
        """
        if self.songsterr_url:
            return {"url": self.songsterr_url, "exacto": True}

        from urllib.parse import urlencode

        patron = " ".join(p for p in [self.artist, self.title] if p).strip()
        if not patron:
            return None
        return {
            "url": "https://www.songsterr.com/?" + urlencode({"pattern": patron}),
            "exacto": False,
        }

    def get_template(self, request, *args, **kwargs):
        return "musica/recurso.html"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from_session = request.GET.get("from_session")
        if from_session:
            from_edit = request.GET.get("from") == "edit"
            if from_edit:
                context["back_url"] = reverse(
                    "clases:class_session_edit", args=[from_session]
                )
            else:
                context["back_url"] = reverse(
                    "clases:class_session_view", args=[from_session]
                )
        return context

    class Meta:
        verbose_name = "Recurso musical"
        verbose_name_plural = "Recursos musicales"
