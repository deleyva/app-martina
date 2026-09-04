"""Blogs de departamento — `blogs.iesmartinabescos.es`.

Un sitio, un propósito: cada departamento publica sus artículos, con moderación
de Wagtail (grupo que escribe, grupo que aprueba, workflow por departamento).

Esta app sale de partir `cms` en la fase 25. Lo que había antes era una sola
`BlogPage` que servía a la vez de artículo de departamento y de canción de la
biblioteca musical, con `get_template()` decidiendo por el `Host` de la petición
y ocho campos musicales —artista, armadura, modo, compás, tempo, duración,
referencia, Songsterr, ChordPro— visibles en el formulario del profesor de
geografía. Ninguna de las 255 páginas tenía ni uno de esos campos relleno.

Aquí no existe ninguno de ellos. No están ocultos ni colapsados: no existen.
"""

from django.conf import settings
from django.db import models
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from cms.adjuntos import AdjuntosMixin, adjuntos_field
from cms.visibilidad import filter_visible_pages


class ArticuloPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "blogs.ArticuloPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class BlogIndexPage(Page):
    """La portada de blogs y cada departamento.

    Es el mismo modelo para los dos porque la diferencia es la posición en el
    árbol, no la naturaleza: la portada es el que tiene departamentos colgando y
    el departamento es el que tiene artículos. Esa rama (`is_hub`) es interna al
    sitio de blogs y no cruza dominios, que era el problema de verdad.

    Lo que sí desapareció: este modelo servía también de contenedor de libros de
    la biblioteca musical, y `get_template()` miraba si colgaba de
    `MusicLibraryIndexPage` para devolver `blog_index_page_book.html`. Eso ahora
    es `musica.LibroPage`, un modelo aparte con su plantilla.
    """

    intro = RichTextField(blank=True)
    cover_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Portada",
        help_text="Imagen de portada del departamento.",
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_blogs",
        verbose_name="Encargado/a",
        help_text="Moderador del departamento que aprueba artículos",
    )
    subject = models.ForeignKey(
        "clases.Subject",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blog_indexes",
        verbose_name="Asignatura",
        help_text="Vincula este blog con una asignatura (hereda icono y color)",
    )
    is_protected = models.BooleanField(
        default=False,
        verbose_name="Protegida",
        help_text="Requiere iniciar sesión para ver esta página y sus hijas.",
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name="Privada",
        help_text="Solo el creador de la página puede verla. Las hijas heredan esta restricción.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("cover_image"),
        MultiFieldPanel(
            [
                FieldPanel("moderator"),
                FieldPanel("subject"),
            ],
            heading="Departamento",
        ),
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

    parent_page_types = ["blogs.BlogIndexPage", "wagtailcore.Page"]
    subpage_types = ["blogs.BlogIndexPage", "blogs.ArticuloPage"]

    def get_template(self, request, *args, **kwargs):
        # La portada (tiene departamentos colgando) y un departamento (tiene
        # artículos) se pintan distinto. Es lo único que queda de aquel
        # `get_template` que decidía por el hostname.
        if BlogIndexPage.objects.child_of(self).exists():
            return "blogs/portada.html"
        return "blogs/departamento.html"

    def get_context(self, request):
        context = super().get_context(request)

        department_pages = list(
            filter_visible_pages(
                BlogIndexPage.objects.child_of(self).live(), request
            ).specific()
        )
        articulos = list(
            filter_visible_pages(
                ArticuloPage.objects.child_of(self).live(), request
            )
            .specific()
            .order_by("-first_published_at")
        )

        is_hub = len(department_pages) > 0
        context["is_hub"] = is_hub
        context["department_pages"] = department_pages
        # `blogpages` se mantiene como nombre de contexto porque lo usan las
        # plantillas heredadas; `articulos` es el nombre nuevo. Los dos apuntan
        # a la misma lista mientras dure la transición de plantillas.
        context["blogpages"] = articulos
        context["articulos"] = articulos

        if is_hub:
            destacados = (
                ArticuloPage.objects.descendant_of(self)
                .live()
                .filter(is_featured=True)
                .order_by("-first_published_at")
            )
            context["featured_posts"] = filter_visible_pages(destacados, request)[:6]

        return context

    class Meta:
        verbose_name = "Blog de departamento"
        verbose_name_plural = "Blogs de departamento"


class ArticuloPage(AdjuntosMixin, Page):
    """Un artículo de departamento.

    Sin ficha musical. Un profesor de filosofía abre este formulario y ve lo que
    necesita para escribir un artículo, y nada más.
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

    # Sin `categories`: era un ParentalManyToManyField a `MusicCategory`, o sea
    # categorías musicales en un artículo de departamento. En toda la base había
    # UNA fila usándolo, y era justo el síntoma que motivó partir la app.
    faceted_tags = ClusterTaggableManager(
        through="blogs.ArticuloPageTag",
        blank=True,
        verbose_name="Etiquetas",
        help_text="Vocabulario facetado (faceta:valor).",
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("is_featured"),
        FieldPanel("body"),
        FieldPanel("attachments", heading="Adjuntos"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("faceted_tags", heading="Etiquetas"),
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

    parent_page_types = ["blogs.BlogIndexPage"]
    subpage_types = []

    def get_template(self, request, *args, **kwargs):
        return "blogs/articulo.html"

    class Meta:
        verbose_name = "Artículo de departamento"
        verbose_name_plural = "Artículos de departamento"
