from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from datetime import timedelta
from martina_bescos_app.users.models import User

# Create your models here.


class StudyContext(models.Model):
    """Contexto donde se estudia el contenido"""
    CONTEXT_TYPES = [
        ('individual', 'Estudio Individual'),
        ('class', 'Clase Grupal'),
        ('homework', 'Tarea Asignada'),
        ('practice', 'Práctica Libre'),
    ]
    
    context_type = models.CharField(max_length=20, choices=CONTEXT_TYPES)
    name = models.CharField(max_length=200, help_text="Nombre descriptivo del contexto")
    description = models.TextField(blank=True)
    
    # Relación opcional con curso (para contextos de clase)
    course = models.ForeignKey('classroom.Course', null=True, blank=True, on_delete=models.CASCADE)
    
    # Creador del contexto
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_study_contexts')
    
    # Configuración del algoritmo de repetición espaciada
    initial_interval = models.DurationField(default=timedelta(days=1), 
                                          help_text="Intervalo inicial entre repasos")
    max_interval = models.DurationField(default=timedelta(days=365), 
                                      help_text="Intervalo máximo entre repasos")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_context_type_display()})"


class UniversalStudyItem(models.Model):
    """Item de estudio que puede venir de cualquier fuente"""
    
    # Referencia polimórfica al contenido
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadatos de estudio
    title = models.CharField(max_length=200, help_text="Título descriptivo del item")
    difficulty_level = models.IntegerField(default=1, choices=[(i, f"Nivel {i}") for i in range(1, 6)])
    estimated_practice_time = models.DurationField(null=True, blank=True)
    
    # Tags para categorización
    tags = models.ManyToManyField('music_cards.Tag', blank=True, related_name='study_items')
    
    # Creador del item
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_study_items')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['content_type', 'object_id', 'created_by']
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.title
    
    @classmethod
    def get_or_create_from_music_item(cls, music_item, user):
        """Crea o obtiene un UniversalStudyItem desde un MusicItem"""
        content_type = ContentType.objects.get_for_model(music_item)
        item, created = cls.objects.get_or_create(
            content_type=content_type,
            object_id=music_item.id,
            created_by=user,
            defaults={
                'title': music_item.title,
                'difficulty_level': 1,
            }
        )
        return item, created


class StudySession(models.Model):
    """Sesión de estudio (individual o grupal)"""
    
    context = models.ForeignKey(StudyContext, on_delete=models.CASCADE, related_name='study_sessions')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Participantes
    participants = models.ManyToManyField(User, through='StudyParticipation', related_name='study_sessions')
    
    # Items de estudio
    study_items = models.ManyToManyField(UniversalStudyItem, through='SessionItem', related_name='study_sessions')
    
    # Estado de la sesión
    STATUS_CHOICES = [
        ('planned', 'Planificada'),
        ('active', 'Activa'),
        ('paused', 'Pausada'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    
    # Fechas
    scheduled_start = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_start', '-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.context.name}"
    
    def start_session(self):
        """Inicia la sesión de estudio"""
        self.status = 'active'
        self.actual_start = timezone.now()
        self.save()
    
    def complete_session(self):
        """Completa la sesión de estudio"""
        self.status = 'completed'
        self.actual_end = timezone.now()
        self.save()
    
    def generate_review_schedule(self):
        """Genera horario de repaso basado en el rendimiento previo"""
        # Implementar algoritmo de repetición espaciada
        pass


class StudyParticipation(models.Model):
    """Participación en sesión de estudio"""
    
    session = models.ForeignKey(StudySession, on_delete=models.CASCADE)
    participant = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Rol en la sesión
    ROLE_CHOICES = [
        ('student', 'Estudiante'),
        ('teacher', 'Profesor'),
        ('observer', 'Observador'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    
    # Métricas de rendimiento
    items_completed = models.PositiveIntegerField(default=0)
    total_practice_time = models.DurationField(default=timedelta(0))
    
    # Fechas de participación
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['session', 'participant']
    
    def __str__(self):
        return f"{self.participant} en {self.session.title} ({self.role})"


class SessionItem(models.Model):
    """Item específico dentro de una sesión de estudio"""
    
    session = models.ForeignKey(StudySession, on_delete=models.CASCADE)
    study_item = models.ForeignKey(UniversalStudyItem, on_delete=models.CASCADE)
    
    order = models.PositiveIntegerField(default=0)
    
    # Estado del item en la sesión
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En progreso'),
        ('completed', 'Completado'),
        ('skipped', 'Omitido'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Tiempo dedicado a este item
    time_spent = models.DurationField(default=timedelta(0))
    
    # Notas específicas para esta sesión
    session_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['session', 'study_item']
    
    def __str__(self):
        return f"{self.study_item.title} en {self.session.title}"


class StudyProgress(models.Model):
    """Progreso de un participante con un item específico"""
    
    participant = models.ForeignKey(User, on_delete=models.CASCADE)
    study_item = models.ForeignKey(UniversalStudyItem, on_delete=models.CASCADE)
    context = models.ForeignKey(StudyContext, on_delete=models.CASCADE)
    
    # Nivel de dominio (similar a las cajas de Anki)
    mastery_level = models.IntegerField(default=1, choices=[(i, f"Nivel {i}") for i in range(1, 6)])
    
    # Estadísticas de práctica
    practice_count = models.PositiveIntegerField(default=0)
    total_practice_time = models.DurationField(default=timedelta(0))
    
    # Fechas de seguimiento
    last_practiced = models.DateTimeField(auto_now=True)
    next_review_date = models.DateTimeField(null=True, blank=True)
    
    # Intervalo actual entre repasos
    current_interval = models.DurationField(default=timedelta(days=1))
    
    # Factor de facilidad (algoritmo SM-2)
    ease_factor = models.FloatField(default=2.5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['participant', 'study_item', 'context']
        ordering = ['next_review_date', '-last_practiced']
    
    def __str__(self):
        return f"{self.participant} - {self.study_item.title} (Nivel {self.mastery_level})"
    
    def update_progress(self, performance_rating):
        """
        Actualiza el progreso basado en el rendimiento
        performance_rating: 1-5 (1=muy difícil, 5=muy fácil)
        """
        self.practice_count += 1
        
        # Algoritmo simplificado de repetición espaciada
        if performance_rating >= 3:
            # Respuesta correcta
            if self.mastery_level < 5:
                self.mastery_level += 1
            
            # Aumentar intervalo
            self.current_interval = timedelta(
                days=max(1, int(self.current_interval.days * self.ease_factor))
            )
        else:
            # Respuesta incorrecta
            if self.mastery_level > 1:
                self.mastery_level -= 1
            
            # Resetear intervalo
            self.current_interval = timedelta(days=1)
        
        # Actualizar ease_factor
        self.ease_factor = max(1.3, self.ease_factor + (0.1 - (5 - performance_rating) * (0.08 + (5 - performance_rating) * 0.02)))
        
        # Calcular próxima fecha de repaso
        self.next_review_date = timezone.now() + self.current_interval
        
        self.save()
    
    def is_due_for_review(self):
        """Verifica si el item necesita repaso"""
        if not self.next_review_date:
            return True
        return timezone.now() >= self.next_review_date
