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


class UniversalStudyItemManager(models.Manager):
    """Manager optimizado para UniversalStudyItem con nueva arquitectura"""
    
    def with_content(self):
        """Optimiza consultas incluyendo contenido relacionado"""
        return self.select_related(
            'music_item', 
            'class_session_page', 
            'student_contribution',
            'created_by'
        ).prefetch_related(
            'tags',
            'music_item__texts',
            'music_item__files',
            'music_item__embeds'
        )
    
    def by_content_type(self, content_type_name):
        """Filtra por tipo de contenido usando referencias específicas"""
        if content_type_name.lower() == 'musicitem':
            return self.filter(music_item__isnull=False)
        elif content_type_name.lower() == 'classsessionpage':
            return self.filter(class_session_page__isnull=False)
        elif content_type_name.lower() == 'studentcontribution':
            return self.filter(student_contribution__isnull=False)
        else:
            # Fallback para tipos legacy
            return self.filter(content_type__model=content_type_name.lower())
    
    def create_from_music_item(self, music_item, user, **kwargs):
        """Crea un UniversalStudyItem desde un MusicItem usando nueva arquitectura"""
        defaults = {
            'title': music_item.title,
            'difficulty_level': 1,
            'created_by': user,
        }
        defaults.update(kwargs)
        
        return self.create(music_item=music_item, **defaults)


class UniversalStudyItem(models.Model):
    """Item de estudio que puede venir de cualquier fuente"""
    
    # NUEVA ARQUITECTURA: Referencias específicas (más eficientes)
    # En lugar de GenericForeignKey, usamos ForeignKeys específicos
    music_item = models.ForeignKey(
        'music_cards.MusicItem', 
        null=True, blank=True, 
        on_delete=models.CASCADE,
        help_text="Referencia a elemento musical"
    )
    class_session_page = models.ForeignKey(
        'cms.ClassSessionPage', 
        null=True, blank=True, 
        on_delete=models.CASCADE,
        help_text="Referencia a página de sesión de clase"
    )
    student_contribution = models.ForeignKey(
        'classroom.StudentContribution', 
        null=True, blank=True, 
        on_delete=models.CASCADE,
        help_text="Referencia a contribución estudiantil"
    )
    
    # MANTENER GenericForeignKey como fallback para compatibilidad
    # Será eliminado gradualmente
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
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
    
    # Manager optimizado
    objects = UniversalStudyItemManager()
    
    class Meta:
        unique_together = ['content_type', 'object_id', 'created_by']
        ordering = ['-updated_at']
        # TODO: Añadir constraints para asegurar una sola referencia activa después de la migración
    
    def __str__(self):
        return f"{self.title} ({self.get_content_source()})"
    
    @property
    def content_source(self):
        """Obtiene el objeto de contenido usando la nueva arquitectura primero"""
        # Priorizar referencias específicas (más eficientes)
        if self.music_item:
            return self.music_item
        elif self.class_session_page:
            return self.class_session_page
        elif self.student_contribution:
            return self.student_contribution
        # Fallback al GenericForeignKey para compatibilidad
        elif self.content_object:
            return self.content_object
        return None
    
    def get_content_source(self):
        """Método helper para obtener descripción del contenido"""
        source = self.content_source
        if source:
            return f"{source.__class__.__name__}: {source}"
        return "Sin contenido"
    
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
        return f"{self.title} ({self.get_content_source()})"
    
    @property
    def content_source(self):
        """Obtiene el objeto de contenido usando la nueva arquitectura primero"""
        # Priorizar referencias específicas (más eficientes)
        if self.music_item:
            return self.music_item
        elif self.class_session_page:
            return self.class_session_page
        elif self.student_contribution:
            return self.student_contribution
        # Fallback al GenericForeignKey para compatibilidad
        elif self.content_object:
            return self.content_object
        return None
    
    def get_content_source(self):
        """Método helper para obtener descripción del contenido"""
        source = self.content_source
        if source:
            return f"{source.__class__.__name__}: {source}"
        return "Sin contenido"
    
    @property
    def content_type_name(self):
        """Obtiene el nombre del tipo de contenido de forma eficiente"""
        if self.music_item:
            return "MusicItem"
        elif self.class_session_page:
            return "ClassSessionPage"
        elif self.student_contribution:
            return "StudentContribution"
        elif self.content_type:
            return self.content_type.model
        return "Unknown"
    
    def migrate_from_generic_fk(self):
        """Migra datos del GenericForeignKey a referencias específicas"""
        if not self.content_object or self.has_specific_reference():
            return False  # Ya migrado o no hay nada que migrar
        
        # Migrar según el tipo de contenido
        if hasattr(self.content_object, '_meta'):
            model_name = self.content_object._meta.model_name
            
            if model_name == 'musicitem':
                self.music_item = self.content_object
                self.content_type = None
                self.object_id = None
                self.save()
                return True
            elif model_name == 'classsessionpage':
                self.class_session_page = self.content_object
                self.content_type = None
                self.object_id = None
                self.save()
                return True
            elif model_name == 'studentcontribution':
                self.student_contribution = self.content_object
                self.content_type = None
                self.object_id = None
                self.save()
                return True
        
        return False
    
    def has_specific_reference(self):
        """Verifica si ya tiene una referencia específica"""
        return bool(self.music_item or self.class_session_page or self.student_contribution)
    
    class Meta:
        ordering = ['-scheduled_start', '-created_at']
    
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
    
    # Métricas de rendimiento (desnormalizadas para performance)
    items_completed = models.PositiveIntegerField(default=0)
    total_practice_time = models.DurationField(default=timedelta(0))
    
    # Métricas adicionales calculadas
    average_mastery_level = models.FloatField(default=0.0, help_text="Nivel promedio de dominio")
    items_mastered = models.PositiveIntegerField(default=0, help_text="Items con nivel 4-5")
    total_reviews = models.PositiveIntegerField(default=0, help_text="Total de repasos realizados")
    streak_days = models.PositiveIntegerField(default=0, help_text="Días consecutivos de práctica")
    
    # Fechas de participación
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['session', 'participant']
        indexes = [
            models.Index(fields=['participant', 'role']),  # Consultas por usuario y rol
            models.Index(fields=['session', 'joined_at']),  # Participantes por sesión
            models.Index(fields=['participant', 'joined_at']),  # Historial de participación
        ]
    
    def __str__(self):
        return f"{self.participant} en {self.session.title} ({self.role})"
    
    def update_metrics(self):
        """Actualiza las métricas desnormalizadas basándose en StudyProgress"""
        from django.db.models import Avg, Count, Q
        
        # Obtener progreso del participante en este contexto
        progress_qs = StudyProgress.objects.filter(
            participant=self.participant,
            context=self.session.context
        )
        
        # Calcular métricas
        metrics = progress_qs.aggregate(
            avg_mastery=Avg('mastery_level'),
            total_reviews=Count('id'),
            mastered_count=Count('id', filter=Q(mastery_level__gte=4))
        )
        
        # Actualizar campos desnormalizados
        self.average_mastery_level = metrics['avg_mastery'] or 0.0
        self.total_reviews = metrics['total_reviews'] or 0
        self.items_mastered = metrics['mastered_count'] or 0
        
        # Calcular racha de días (simplificado por ahora)
        # TODO: Implementar cálculo real de streak basado en fechas
        self.streak_days = min(self.total_reviews // 5, 30)  # Aproximación
        
        self.save(update_fields=[
            'average_mastery_level', 'total_reviews', 
            'items_mastered', 'streak_days'
        ])


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


class StudyProgressManager(models.Manager):
    """Manager optimizado para StudyProgress que evita consultas N+1"""
    
    def with_related(self):
        """Optimiza consultas incluyendo relaciones frecuentemente usadas"""
        return self.select_related(
            'participant', 'study_item', 'context'
        ).prefetch_related(
            'study_item__tags',
            'context__course'
        )
    
    def due_for_review(self):
        """Items que necesitan repaso, optimizado"""
        return self.with_related().filter(
            next_review_date__lte=timezone.now()
        ).order_by('next_review_date')
    
    def by_participant_and_context(self, participant, context):
        """Progreso de un participante en un contexto específico"""
        return self.with_related().filter(
            participant=participant,
            context=context
        ).order_by('-mastery_level', 'next_review_date')


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
    
    # Manager optimizado
    objects = StudyProgressManager()
    
    class Meta:
        unique_together = ['participant', 'study_item', 'context']
        ordering = ['next_review_date', '-last_practiced']
        indexes = [
            models.Index(fields=['participant', 'study_item', 'context']),  # Consulta principal
            models.Index(fields=['participant', 'next_review_date']),  # Items pendientes por usuario
            models.Index(fields=['next_review_date']),  # Items que necesitan repaso
            models.Index(fields=['participant', 'mastery_level']),  # Progreso por usuario
            models.Index(fields=['context', 'next_review_date']),  # Items por contexto
        ]
    
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
        
        # Actualizar métricas desnormalizadas en StudyParticipation
        self._update_participation_metrics()
    
    def is_due_for_review(self):
        """Verifica si el item necesita repaso"""
        if not self.next_review_date:
            return True
        return timezone.now() >= self.next_review_date
    
    def _update_participation_metrics(self):
        """Actualiza métricas desnormalizadas en StudyParticipation relacionadas"""
        # Buscar participaciones activas del usuario en este contexto
        participations = StudyParticipation.objects.filter(
            participant=self.participant,
            session__context=self.context,
            left_at__isnull=True  # Solo participaciones activas
        )
        
        # Actualizar métricas para cada participación
        for participation in participations:
            participation.update_metrics()
