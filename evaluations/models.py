from django.db import models
import uuid
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

# Create your models here.


# =============================================================================
# GESTIÓN DE GRUPOS Y ESTUDIANTES
# =============================================================================


class Group(models.Model):
    """Grupo de estudiantes (ej: 1º ESO A, 2º Bachillerato B)"""
    
    name = models.CharField(max_length=50, unique=True, verbose_name="Nombre del grupo")
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="teaching_groups",
        blank=True,
        verbose_name="Profesores",
        help_text="Profesores que imparten clase a este grupo"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["name"]
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
    
    def __str__(self):
        return self.name


# =============================================================================
# EVALUACIONES
# =============================================================================


class EvaluationItem(models.Model):
    name = models.CharField(max_length=100)
    TERM_CHOICES = [
        ("primera", "Primera evaluación"),
        ("segunda", "Segunda evaluación"),
        ("tercera", "Tercera evaluación"),
    ]
    term = models.CharField(choices=TERM_CHOICES, null=True, blank=True)
    description = models.TextField(blank=True)
    ai_prompt = models.TextField(
        blank=True, help_text="Prompt para Gemini que reescribirá la retroalimentación"
    )
    force_web_submission = models.BooleanField(
        default=False,
        verbose_name="Forzar entrega por web",
        help_text="Si está activado, todos los alumnos deberán entregar por la web y no en clase",
    )
    classroom_reduces_points = models.BooleanField(
        default=False, verbose_name="Entrega por classroom resta puntos"
    )
    info_url = models.URLField(
        blank=True, 
        verbose_name="URL de información",
        help_text="URL con información adicional sobre esta evaluación para los estudiantes"
    )

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="students",
        verbose_name="Grupo",
        help_text="Grupo al que pertenece el estudiante"
    )

    def __str__(self):
        return f"{self.user.name}" if self.user else f"Student {self.id}"

    class Meta:
        ordering = ["user__name"]
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"


class RubricCategory(models.Model):
    """Categoría de la rúbrica (ej: Plasticidad, Velocidad, Compás, etc.)"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_points = models.DecimalField(max_digits=3, decimal_places=1, default=2.0)
    order = models.PositiveSmallIntegerField(default=0)
    evaluation_item = models.ForeignKey(
        EvaluationItem,
        on_delete=models.CASCADE,
        related_name="rubric_categories",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Categoría de rúbrica"
        verbose_name_plural = "Categorías de rúbrica"

    def __str__(self):
        return self.name


class Evaluation(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="evaluations"
    )
    evaluation_item = models.ForeignKey(
        EvaluationItem, on_delete=models.CASCADE, related_name="evaluations"
    )
    score = models.DecimalField(max_digits=4, decimal_places=2)
    date_evaluated = models.DateTimeField(auto_now_add=True)
    classroom_submission = models.BooleanField(
        default=False, verbose_name="Entrega por classroom"
    )
    max_score = models.DecimalField(
        max_digits=3, decimal_places=1, default=10.0, verbose_name="Nota máxima"
    )
    feedback = models.TextField(blank=True)
    sent_by_mail = models.BooleanField(default=False, verbose_name="Enviada por correo")

    class Meta:
        unique_together = ["student", "evaluation_item"]
        ordering = ["-date_evaluated"]

    def __str__(self):
        return f"{self.student} - {self.evaluation_item}: {self.score}"

    def calculate_score(self):
        """Calcula la puntuación total basada en las puntuaciones de la rúbrica"""
        rubric_scores = self.rubric_scores.all()
        if not rubric_scores:
            return 0

        total_points = sum(score.points for score in rubric_scores)
        max_possible = sum(score.category.max_points for score in rubric_scores)

        return (total_points / max_possible) * 10 if max_possible > 0 else 0


class RubricScore(models.Model):
    """Puntuación de un estudiante en una categoría específica de la rúbrica"""

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="rubric_scores"
    )
    category = models.ForeignKey(
        RubricCategory, on_delete=models.CASCADE, related_name="scores"
    )
    points = models.DecimalField(max_digits=3, decimal_places=1)

    class Meta:
        unique_together = ["evaluation", "category"]

    def __str__(self):
        return f"{self.evaluation.student} - {self.category.name}: {self.points} puntos"


class PendingEvaluationStatus(models.Model):
    """Modelo para almacenar el estado de las evaluaciones pendientes"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="pending_statuses"
    )
    evaluation_item = models.ForeignKey(
        EvaluationItem, on_delete=models.CASCADE, related_name="pending_statuses"
    )
    classroom_submission = models.BooleanField(
        default=False, verbose_name="Entrega por classroom"
    )
    feedback = models.TextField(blank=True, verbose_name="Retroalimentación")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["student", "evaluation_item"]
        verbose_name = "Estado de evaluación pendiente"
        verbose_name_plural = "Estados de evaluaciones pendientes"
        indexes = [
            models.Index(fields=["student", "evaluation_item"]),
            models.Index(fields=["evaluation_item"]),
            models.Index(fields=["classroom_submission"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.evaluation_item} - {'Classroom' if self.classroom_submission else 'En clase'}"

    @classmethod
    def get_pending_students(
        cls, evaluation_item=None, group=None, include_classroom=False
    ):
        """Obtiene los estudiantes con evaluaciones pendientes"""
        query = cls.objects.select_related(
            "student", "student__user", "evaluation_item"
        )

        if evaluation_item:
            query = query.filter(evaluation_item=evaluation_item)

        if group:
            query = query.filter(student__group=group)

        if not include_classroom:
            query = query.filter(classroom_submission=False)

        return query


# =============================================================================
# BIBLIOTECA DE GRUPO
# =============================================================================


class GroupLibraryItem(models.Model):
    """
    Biblioteca compartida de un grupo - puede contener cualquier tipo de contenido.
    Similar a my_library.LibraryItem pero para grupos en lugar de usuarios individuales.
    Usa GenericForeignKey para apuntar a ScorePages, Documents, Images, BlogPages, etc.
    """
    
    # Grupo al que pertenece este item
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="library_items",
        verbose_name="Grupo"
    )
    
    # Referencia genérica al contenido (ScorePage, Document, Image, BlogPage, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    
    # Metadatos
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Añadido por",
        help_text="Profesor que añadió este elemento"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas del profesor sobre este elemento para el grupo"
    )
    
    class Meta:
        ordering = ["-added_at"]
        unique_together = ["group", "content_type", "object_id"]
        indexes = [
            models.Index(fields=["group", "-added_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "Item de Biblioteca de Grupo"
        verbose_name_plural = "Items de Biblioteca de Grupo"
    
    def __str__(self):
        return f"{self.group.name} - {self.get_content_title()}"
    
    # === MÉTODOS FAT MODEL (toda la lógica de negocio aquí) ===
    
    def get_content_title(self):
        """Obtener título del contenido referenciado"""
        if hasattr(self.content_object, "title"):
            return self.content_object.title
        elif hasattr(self.content_object, "name"):
            return self.content_object.name
        return str(self.content_object)
    
    def get_content_type_name(self):
        """Tipo de contenido legible"""
        model_name = self.content_type.model
        
        # Si es un Document de Wagtail, verificar el tipo de archivo
        if model_name == "document" and hasattr(self.content_object, "file"):
            filename = self.content_object.file.name.lower()
            # Detectar audios
            if filename.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac')):
                return "Audio"
            # Detectar PDFs
            elif filename.endswith('.pdf'):
                return "Documento PDF"
            else:
                return "Documento"
        
        # Mapping para otros tipos
        mapping = {
            "scorepage": "Partitura",
            "image": "Imagen",
            "blogpage": "Artículo de Blog",
        }
        return mapping.get(model_name, model_name.title())
    
    def get_icon(self):
        """Icono según tipo de contenido"""
        model_name = self.content_type.model
        
        # Si es un Document, verificar si es audio o PDF
        if model_name == "document" and hasattr(self.content_object, "file"):
            filename = self.content_object.file.name.lower()
            if filename.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac')):
                return "🎵"
            elif filename.endswith('.pdf'):
                return "📄"
        
        icons = {
            "scorepage": "🎼",
            "document": "📄",
            "image": "🖼️",
            "blogpage": "📝",
        }
        return icons.get(model_name, "📁")
    
    def get_related_scorepage(self):
        """
        Obtener ScorePage relacionado si este item es un Document, Image individual.
        Similar a LibraryItem.get_related_scorepage()
        """
        # Si ya es una ScorePage completa, retornar ella misma
        if self.content_type.model == "scorepage":
            return self.content_object
        
        # Para documentos, imágenes, buscar en ScorePages
        if self.content_type.model in ["document", "image"]:
            from cms.models import ScorePage
            
            # Buscar en todas las ScorePages
            for score in ScorePage.objects.live():
                # Revisar el StreamField content
                for block in score.content:
                    try:
                        # Para PDFs
                        if block.block_type == "pdf_score":
                            if block.value.get('pdf_file') == self.content_object:
                                return score
                        # Para Audios
                        elif block.block_type == "audio":
                            if block.value.get('audio_file') == self.content_object:
                                return score
                        # Para Imágenes
                        elif block.block_type == "image":
                            if block.value.get('image') == self.content_object:
                                return score
                    except (AttributeError, KeyError):
                        continue
        
        return None
    
    @classmethod
    def add_to_library(cls, group, content_object, added_by=None, notes=""):
        """Añadir elemento a la biblioteca del grupo (evita duplicados)"""
        content_type = ContentType.objects.get_for_model(content_object)
        item, created = cls.objects.get_or_create(
            group=group,
            content_type=content_type,
            object_id=content_object.pk,
            defaults={
                "added_by": added_by,
                "notes": notes,
            }
        )
        return item, created
    
    @classmethod
    def is_in_library(cls, group, content_object):
        """Verificar si el contenido ya está en la biblioteca del grupo"""
        content_type = ContentType.objects.get_for_model(content_object)
        return cls.objects.filter(
            group=group,
            content_type=content_type,
            object_id=content_object.pk
        ).exists()


# =============================================================================
# SESIONES DE CLASE
# =============================================================================


class ClassSession(models.Model):
    """
    Sesión de clase para un grupo específico.
    Permite organizar contenido ordenable para una clase.
    """
    
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="class_sessions",
        verbose_name="Profesor"
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="class_sessions",
        verbose_name="Grupo"
    )
    date = models.DateField(verbose_name="Fecha de la sesión")
    title = models.CharField(max_length=200, verbose_name="Título")
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas generales sobre la sesión"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Sesión de Clase"
        verbose_name_plural = "Sesiones de Clase"
        indexes = [
            models.Index(fields=["teacher", "-date"]),
            models.Index(fields=["group", "-date"]),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.group.name} ({self.date})"
    
    # === MÉTODOS FAT MODEL ===
    
    def get_items_ordered(self):
        """Obtener items de la sesión ordenados por order"""
        return self.items.all().order_by("order")
    
    def get_next_order(self):
        """Obtener el siguiente número de orden disponible"""
        last_item = self.items.order_by("-order").first()
        return (last_item.order + 1) if last_item else 0
    
    def reorder_items(self, item_ids):
        """
        Reordenar items según lista de IDs.
        item_ids: lista de IDs en el orden deseado
        """
        for index, item_id in enumerate(item_ids):
            self.items.filter(pk=item_id).update(order=index)


class ClassSessionItem(models.Model):
    """
    Elemento individual de una sesión de clase.
    Usa GenericForeignKey para apuntar a cualquier tipo de contenido.
    """
    
    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Sesión"
    )
    
    # Referencia genérica al contenido
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    
    # Orden y metadatos
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas específicas para este elemento en la sesión"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["order"]
        verbose_name = "Item de Sesión"
        verbose_name_plural = "Items de Sesión"
        indexes = [
            models.Index(fields=["session", "order"]),
        ]
    
    def __str__(self):
        return f"{self.get_content_title()} (orden {self.order})"
    
    # === MÉTODOS FAT MODEL ===
    
    def get_content_title(self):
        """Obtener título del contenido referenciado"""
        if hasattr(self.content_object, "title"):
            return self.content_object.title
        elif hasattr(self.content_object, "name"):
            return self.content_object.name
        return str(self.content_object)
    
    def get_content_type_name(self):
        """Tipo de contenido legible"""
        model_name = self.content_type.model
        
        if model_name == "document" and hasattr(self.content_object, "file"):
            filename = self.content_object.file.name.lower()
            if filename.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac')):
                return "Audio"
            elif filename.endswith('.pdf'):
                return "Documento PDF"
            else:
                return "Documento"
        
        mapping = {
            "scorepage": "Partitura",
            "image": "Imagen",
            "blogpage": "Artículo de Blog",
            "grouplibraryitem": "Item de Biblioteca",
        }
        return mapping.get(model_name, model_name.title())
    
    def get_icon(self):
        """Icono según tipo de contenido"""
        model_name = self.content_type.model
        
        if model_name == "document" and hasattr(self.content_object, "file"):
            filename = self.content_object.file.name.lower()
            if filename.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac')):
                return "🎵"
            elif filename.endswith('.pdf'):
                return "📄"
        
        icons = {
            "scorepage": "🎼",
            "document": "📄",
            "image": "🖼️",
            "blogpage": "📝",
        }
        return icons.get(model_name, "📁")
    
    def get_content_url(self):
        """Obtener URL del contenido si existe"""
        if hasattr(self.content_object, "get_url"):
            return self.content_object.get_url()
        elif hasattr(self.content_object, "url"):
            return self.content_object.url
        return None
    
    @classmethod
    def add_to_session(cls, session, content_object, notes=""):
        """Añadir elemento a la sesión"""
        content_type = ContentType.objects.get_for_model(content_object)
        order = session.get_next_order()
        
        item = cls.objects.create(
            session=session,
            content_type=content_type,
            object_id=content_object.pk,
            order=order,
            notes=notes
        )
        return item
