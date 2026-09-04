"""Núcleo compartido del CMS.

Lo que queda de `cms` después de la fase 25. Antes esta app tenía 2.311 líneas y
quince modelos `Page`, y mezclaba el blog de los departamentos con la biblioteca
musical: la misma `BlogPage` servía de artículo de geografía y de canción, y
`get_template()` decidía cuál era mirando el `Host` de la petición. Eso está en
`blogs/` y en `musica/`.

Aquí se queda solo lo que de verdad usan las dos: la portada de `apps.`, la
página estándar, la ayuda y los enlaces externos reutilizables. La visibilidad
está en `cms/visibilidad.py` y los adjuntos en `cms/adjuntos.py`, que es lo único
que blog y música comparten de verdad.
"""

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from taggit.managers import TaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException
from wagtail.embeds.models import Embed
from wagtail.fields import RichTextField
from wagtail.models import Page, Site
from wagtail.snippets.models import register_snippet


class TaggedEmbedItem(TaggedItemBase):
    """Through model for tagging embeds via TaggableEmbed."""
    content_object = models.ForeignKey(
        'cms.TaggableEmbed',
        on_delete=models.CASCADE,
        related_name='tagged_items',
    )


class TaggableEmbed(models.Model):
    """Concrete model wrapping Wagtail Embed to add tag support."""
    embed = models.OneToOneField(
        Embed,
        on_delete=models.CASCADE,
        related_name='taggable',
    )
    tags = TaggableManager(through=TaggedEmbedItem, blank=True)

    @property
    def title(self):
        return self.embed.title

    @title.setter
    def title(self, value):
        self.embed.title = value
        self.embed.save(update_fields=['title'])

    def __str__(self):
        return self.embed.title or self.embed.url

    class Meta:
        verbose_name = "Embed etiquetable"
        verbose_name_plural = "Embeds etiquetables"


@register_snippet
class ExternalResource(models.Model):
    """Enlace externo reutilizable (e.g. Ultimate Guitar tabs, Musescore, etc.)"""

    url = models.URLField(max_length=500)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="🔗", help_text="Emoji o icono")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("url"),
        FieldPanel("description"),
        FieldPanel("icon"),
    ]

    @cached_property
    def domain(self):
        from urllib.parse import urlparse
        return urlparse(self.url).netloc

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Enlace Externo"
        verbose_name_plural = "Enlaces Externos"
        ordering = ["-created_at"]


class HomePage(Page):
    """Portada de `apps.iesmartinabescos.es`.

    Tenía 100 líneas más: todo el contexto de una portada editorial para el sitio
    de blogs, detrás de `if _is_blog_request(request)`. Nunca se ejecutó — la raíz
    del sitio de blogs es un `BlogIndexPage`, no una `HomePage`. Ese código y sus
    plantillas están conservados y desconectados en `blogs/portada_editorial.py`,
    con las instrucciones para encenderlo si Jesús quiere.
    """

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

    def get_template(self, request, *args, **kwargs):
        return "cms/home_page.html"

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

    def get_template(self, request, *args, **kwargs):
        return "cms/standard_page.html"

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
        "musica.MusicLibraryIndexPage",
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


class SavedResourceFilter(models.Model):
    """Filtros guardados por el usuario para la biblioteca unificada"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_resource_filters')
    name = models.CharField(max_length=100)
    query_params = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Filtro de Recurso Guardado"
        verbose_name_plural = "Filtros de Recursos Guardados"

    def __str__(self):
        return f"{self.user.username} - {self.name}"
