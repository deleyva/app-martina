from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.urls import reverse
from martina_bescos_app.users.models import User

# Create your models here.


class PresentationTemplate(models.Model):
    """Plantilla para presentaciones"""
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Configuración de la plantilla
    TEMPLATE_TYPES = [
        ('class_session', 'Sesión de Clase'),
        ('music_collection', 'Colección Musical'),
        ('student_portfolio', 'Portfolio de Estudiante'),
        ('custom', 'Personalizada'),
    ]
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    
    # Configuración de diseño
    theme = models.CharField(max_length=50, default='default', 
                           help_text="Tema visual de la presentación")
    
    # Configuración de página para impresión
    page_format = models.CharField(max_length=10, default='A4', 
                                 choices=[('A4', 'A4'), ('A3', 'A3'), ('Letter', 'Letter')])
    orientation = models.CharField(max_length=10, default='portrait',
                                 choices=[('portrait', 'Vertical'), ('landscape', 'Horizontal')])
    
    # CSS personalizado
    custom_css = models.TextField(blank=True, help_text="CSS adicional para personalizar la presentación")
    
    # Creador de la plantilla
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='presentation_templates')
    is_public = models.BooleanField(default=False, help_text="Disponible para otros usuarios")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class Presentation(models.Model):
    """Presentación generada"""
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Plantilla utilizada
    template = models.ForeignKey(PresentationTemplate, on_delete=models.CASCADE, 
                               related_name='presentations')
    
    # Contenido fuente (polimórfico)
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.PositiveIntegerField()
    source_content = GenericForeignKey('source_content_type', 'source_object_id')
    
    # Configuración específica de esta presentación
    custom_settings = models.JSONField(default=dict, blank=True,
                                     help_text="Configuraciones específicas en formato JSON")
    
    # Estado de la presentación
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('generating', 'Generando'),
        ('ready', 'Lista'),
        ('error', 'Error'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Archivos generados
    html_file = models.FileField(upload_to='presentations/html/', null=True, blank=True)
    pdf_file = models.FileField(upload_to='presentations/pdf/', null=True, blank=True)
    
    # Metadatos
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='presentations')
    generated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.template.name}"
    
    def get_absolute_url(self):
        return reverse('presentations:detail', kwargs={'pk': self.pk})
    
    def get_preview_url(self):
        return reverse('presentations:preview', kwargs={'pk': self.pk})
    
    def get_pdf_url(self):
        if self.pdf_file:
            return self.pdf_file.url
        return None


class PresentationSlide(models.Model):
    """Diapositiva individual de una presentación"""
    
    presentation = models.ForeignKey(Presentation, on_delete=models.CASCADE, 
                                   related_name='slides')
    
    # Orden y configuración
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200, blank=True)
    
    # Tipo de diapositiva
    SLIDE_TYPES = [
        ('title', 'Título'),
        ('content', 'Contenido'),
        ('music_item', 'Elemento Musical'),
        ('exercise', 'Ejercicio'),
        ('image', 'Imagen'),
        ('text', 'Texto'),
        ('break', 'Descanso'),
    ]
    slide_type = models.CharField(max_length=20, choices=SLIDE_TYPES)
    
    # Contenido de la diapositiva (polimórfico)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Contenido adicional
    text_content = models.TextField(blank=True)
    image = models.ImageField(upload_to='presentations/slides/', null=True, blank=True)
    
    # Configuración de la diapositiva
    duration = models.DurationField(null=True, blank=True, 
                                  help_text="Duración estimada de esta diapositiva")
    notes = models.TextField(blank=True, help_text="Notas del presentador")
    
    # Configuración de estilo específica
    custom_css_class = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Slide {self.order}: {self.title or self.get_slide_type_display()}"


class PresentationExport(models.Model):
    """Registro de exportaciones de presentaciones"""
    
    presentation = models.ForeignKey(Presentation, on_delete=models.CASCADE, 
                                   related_name='exports')
    
    # Tipo de exportación
    EXPORT_TYPES = [
        ('html', 'HTML'),
        ('pdf', 'PDF'),
        ('pptx', 'PowerPoint'),  # Para futuras implementaciones
    ]
    export_type = models.CharField(max_length=10, choices=EXPORT_TYPES)
    
    # Configuración de exportación
    export_settings = models.JSONField(default=dict, blank=True)
    
    # Archivo generado
    file = models.FileField(upload_to='presentations/exports/')
    file_size = models.PositiveIntegerField(default=0)
    
    # Estado de la exportación
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completada'),
        ('failed', 'Fallida'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    # Metadatos
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.presentation.title} - {self.get_export_type_display()}"


class PresentationShare(models.Model):
    """Compartir presentaciones con otros usuarios"""
    
    presentation = models.ForeignKey(Presentation, on_delete=models.CASCADE, 
                                   related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  related_name='shared_presentations')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                related_name='presentation_shares_given')
    
    # Permisos
    PERMISSION_LEVELS = [
        ('view', 'Solo visualización'),
        ('edit', 'Puede editar'),
        ('duplicate', 'Puede duplicar'),
    ]
    permission_level = models.CharField(max_length=20, choices=PERMISSION_LEVELS, 
                                      default='view')
    
    # Configuración del compartir
    expires_at = models.DateTimeField(null=True, blank=True, 
                                    help_text="Fecha de expiración del acceso")
    is_active = models.BooleanField(default=True)
    
    # Mensaje opcional
    message = models.TextField(blank=True, help_text="Mensaje para el usuario")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['presentation', 'shared_with']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.presentation.title} compartida con {self.shared_with}"
