from django.db import models
from wagtail.models import Page, Orderable
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel
from wagtail.blocks import (
    CharBlock,
    TextBlock,
    RichTextBlock,
    PageChooserBlock,
    StructBlock,
)
from wagtail.images.blocks import ImageChooserBlock
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel


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


# Modelos para sesiones de clase musicales
# ------------------------------------------------------------------------------


class ClassSessionPage(Page):
    """Página de Wagtail para una sesión de clase musical"""
    
    # Información básica de la sesión
    session_date = models.DateField(
        help_text="Fecha de la sesión de clase"
    )
    start_time = models.TimeField(
        null=True, 
        blank=True,
        help_text="Hora de inicio de la sesión"
    )
    end_time = models.TimeField(
        null=True, 
        blank=True,
        help_text="Hora de finalización de la sesión"
    )
    
    # Relación con el modelo Course de la app classroom
    course = models.ForeignKey(
        'classroom.Course',
        on_delete=models.PROTECT,
        related_name='wagtail_sessions',
        help_text="Curso al que pertenece esta sesión"
    )
    
    # Descripción y objetivos de la sesión
    description = RichTextField(
        blank=True,
        help_text="Descripción detallada de la sesión"
    )
    objectives = RichTextField(
        blank=True,
        help_text="Objetivos de aprendizaje de la sesión"
    )
    
    # Notas del profesor
    teacher_notes = RichTextField(
        blank=True,
        help_text="Notas privadas del profesor para la sesión"
    )
    
    # Estado de la sesión
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('planned', 'Planificada'),
        ('in_progress', 'En progreso'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Estado actual de la sesión"
    )
    
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('course'),
            FieldPanel('session_date'),
            FieldPanel('start_time'),
            FieldPanel('end_time'),
            FieldPanel('status'),
        ], heading="Información de la Sesión"),
        FieldPanel('description'),
        FieldPanel('objectives'),
        InlinePanel('session_music_items', label="Contenido Musical"),
        FieldPanel('teacher_notes'),
    ]
    
    # Configuración de páginas padre permitidas
    parent_page_types = ['cms.HomePage', 'cms.StandardPage']
    subpage_types = []  # No permitir subpáginas
    
    class Meta:
        verbose_name = "Sesión de Clase"
        verbose_name_plural = "Sesiones de Clase"
    
    def __str__(self):
        return f"{self.title} - {self.session_date}"
    
    def get_context(self, request):
        context = super().get_context(request)
        # Añadir contenido musical ordenado
        context['music_items'] = self.session_music_items.all().order_by('sort_order')
        return context


class SessionMusicItem(Orderable):
    """Relación entre sesión de clase y elementos musicales"""
    
    page = ParentalKey(
        ClassSessionPage,
        on_delete=models.CASCADE,
        related_name='session_music_items'
    )
    
    # Referencia al MusicItem de la app music_cards
    music_item = models.ForeignKey(
        'music_cards.MusicItem',
        on_delete=models.CASCADE,
        help_text="Elemento musical a incluir en la sesión"
    )
    
    # Notas específicas para esta sesión
    session_notes = RichTextField(
        blank=True,
        help_text="Notas específicas sobre cómo usar este elemento en la sesión"
    )
    
    # Tiempo estimado para trabajar este elemento
    estimated_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Tiempo estimado para este elemento (ej: 00:15:00 para 15 minutos)"
    )
    
    # Tipo de actividad
    ACTIVITY_TYPES = [
        ('warm_up', 'Calentamiento'),
        ('technique', 'Técnica'),
        ('repertoire', 'Repertorio'),
        ('theory', 'Teoría'),
        ('improvisation', 'Improvisación'),
        ('listening', 'Audición'),
        ('composition', 'Composición'),
        ('review', 'Repaso'),
    ]
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES,
        blank=True,
        help_text="Tipo de actividad musical"
    )
    
    panels = [
        FieldPanel('music_item'),
        FieldPanel('activity_type'),
        FieldPanel('estimated_duration'),
        FieldPanel('session_notes'),
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
        help_text="Nivel de dificultad del ejercicio (1-5)"
    )
    
    # Duración estimada
    estimated_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Duración estimada del ejercicio"
    )
    
    # Contenido del ejercicio
    instructions = RichTextField(
        help_text="Instrucciones detalladas del ejercicio"
    )
    
    # Objetivos pedagógicos
    learning_objectives = RichTextField(
        blank=True,
        help_text="Objetivos de aprendizaje del ejercicio"
    )
    
    # Referencia a MusicItem relacionado
    related_music_item = models.ForeignKey(
        'music_cards.MusicItem',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Elemento musical relacionado (opcional)"
    )
    
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('difficulty_level'),
            FieldPanel('estimated_duration'),
            FieldPanel('related_music_item'),
        ], heading="Información del Ejercicio"),
        FieldPanel('instructions'),
        FieldPanel('learning_objectives'),
    ]
    
    parent_page_types = ['cms.HomePage', 'cms.StandardPage', 'cms.ClassSessionPage']
    
    class Meta:
        verbose_name = "Ejercicio Musical"
        verbose_name_plural = "Ejercicios Musicales"
