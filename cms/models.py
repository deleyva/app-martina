from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.blocks import (
    CharBlock,
    TextBlock,
    RichTextBlock,
    PageChooserBlock,
    StructBlock,
)
from wagtail.images.blocks import ImageChooserBlock


class HomePage(Page):
    """Página de inicio del sitio web"""
    
    hero_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Título principal de la página de inicio"
    )
    hero_subtitle = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subtítulo de la página de inicio"
    )
    hero_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Imagen principal de la página de inicio"
    )
    body = RichTextField(
        blank=True,
        help_text="Contenido principal de la página"
    )
    
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('hero_title'),
            FieldPanel('hero_subtitle'),
            FieldPanel('hero_image'),
        ], heading="Sección Hero"),
        FieldPanel('body'),
    ]
    
    class Meta:
        verbose_name = "Página de Inicio"


class StandardPage(Page):
    """Página estándar con contenido flexible"""
    
    intro = models.TextField(
        blank=True,
        help_text="Introducción de la página"
    )
    body = RichTextField(
        blank=True,
        help_text="Contenido principal de la página"
    )
    
    content_panels = Page.content_panels + [
        FieldPanel('intro'),
        FieldPanel('body'),
    ]
    
    class Meta:
        verbose_name = "Página Estándar"


class BlogIndexPage(Page):
    """Página índice del blog"""
    
    intro = RichTextField(blank=True)
    
    content_panels = Page.content_panels + [
        FieldPanel('intro'),
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        # Obtener todas las páginas de blog que son hijas de esta página
        blogpages = self.get_children().live().order_by('-first_published_at')
        context['blogpages'] = blogpages
        return context
    
    class Meta:
        verbose_name = "Índice del Blog"


class BlogPage(Page):
    """Página individual de blog"""
    
    date = models.DateField("Fecha de publicación")
    intro = models.CharField(max_length=250, help_text="Resumen del artículo")
    body = RichTextField(blank=True)
    featured_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Imagen destacada del artículo"
    )
    
    content_panels = Page.content_panels + [
        FieldPanel('date'),
        FieldPanel('intro'),
        FieldPanel('featured_image'),
        FieldPanel('body'),
    ]
    
    class Meta:
        verbose_name = "Artículo de Blog"
