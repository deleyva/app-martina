from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from martina_bescos_app.users.models import User

# Create your models here.


class Course(models.Model):
    """Curso o clase musical"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught')
    students = models.ManyToManyField(User, through='Enrollment', related_name='courses_enrolled')
    academic_year = models.CharField(max_length=20, help_text="Ej: 2024-2025")
    
    # Configuración del curso
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year', 'name']
        unique_together = ['teacher', 'name', 'academic_year']
    
    def __str__(self):
        return f"{self.name} ({self.academic_year}) - {self.teacher}"
    
    def get_active_students(self):
        """Retorna estudiantes activos en el curso"""
        return self.students.filter(enrollment__is_active=True)


class Enrollment(models.Model):
    """Inscripción de estudiante en un curso"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Estado de la inscripción
    is_active = models.BooleanField(default=True)
    enrollment_date = models.DateField(auto_now_add=True)
    completion_date = models.DateField(null=True, blank=True)
    
    # Notas del profesor sobre el estudiante
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['course', 'student']
    
    def __str__(self):
        return f"{self.student} en {self.course.name}"


class ClassSession(models.Model):
    """Sesión individual de clase"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='class_sessions')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    # Contenido de la sesión - referencia polimórfica a cualquier tipo de contenido
    content_items = models.ManyToManyField('music_cards.MusicItem', 
                                         through='SessionContent', 
                                         related_name='class_sessions')
    
    # Estado de la sesión
    STATUS_CHOICES = [
        ('planned', 'Planificada'),
        ('in_progress', 'En progreso'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-start_time']
    
    def __str__(self):
        return f"{self.course.name} - {self.title} ({self.date})"


class SessionContent(models.Model):
    """Contenido específico de una sesión de clase"""
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    music_item = models.ForeignKey('music_cards.MusicItem', on_delete=models.CASCADE)
    
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, help_text="Notas específicas para esta sesión")
    
    # Tiempo estimado para este contenido en la sesión
    estimated_duration = models.DurationField(null=True, blank=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['class_session', 'music_item']
    
    def __str__(self):
        return f"{self.music_item.title} en {self.class_session.title}"


class Assignment(models.Model):
    """Tarea asignada a estudiantes"""
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Contenido de la tarea
    music_items = models.ManyToManyField('music_cards.MusicItem', 
                                       through='AssignmentItem',
                                       related_name='assignments')
    
    # Estudiantes asignados
    students = models.ManyToManyField(User, through='StudentAssignment', related_name='assignments')
    
    # Fechas importantes
    assigned_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    
    # Configuración
    is_mandatory = models.BooleanField(default=True)
    allow_late_submission = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date', '-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.class_session.course.name}"


class AssignmentItem(models.Model):
    """Item específico dentro de una tarea"""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    music_item = models.ForeignKey('music_cards.MusicItem', on_delete=models.CASCADE)
    
    order = models.PositiveIntegerField(default=0)
    instructions = models.TextField(blank=True, help_text="Instrucciones específicas para este item")
    
    class Meta:
        ordering = ['order']
        unique_together = ['assignment', 'music_item']
    
    def __str__(self):
        return f"{self.music_item.title} en {self.assignment.title}"


class StudentAssignment(models.Model):
    """Relación entre estudiante y tarea asignada"""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Estado de la entrega
    STATUS_CHOICES = [
        ('assigned', 'Asignada'),
        ('in_progress', 'En progreso'),
        ('submitted', 'Entregada'),
        ('reviewed', 'Revisada'),
        ('completed', 'Completada'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    # Fechas de seguimiento
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Feedback del profesor
    teacher_feedback = models.TextField(blank=True)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Notas del estudiante
    student_notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['assignment', 'student']
    
    def __str__(self):
        return f"{self.student} - {self.assignment.title} ({self.status})"


class StudentContribution(models.Model):
    """Contenido creado por estudiantes"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contributions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='student_contributions')
    
    # Referencia al contenido creado (polimórfica)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadatos de la contribución
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Estado de moderación
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('submitted', 'Enviado para revisión'),
        ('approved', 'Aprobado'),
        ('needs_revision', 'Necesita revisión'),
        ('rejected', 'Rechazado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Feedback del profesor
    teacher_feedback = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, 
                                  related_name='approved_contributions')
    
    # El profesor puede marcar para añadir a biblioteca compartida
    approved_for_library = models.BooleanField(default=False)
    
    # Fechas de seguimiento
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} por {self.student} ({self.status})"
