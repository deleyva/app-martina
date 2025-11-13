from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

# =============================================================================
# ASIGNATURAS Y GESTIÓN DE GRUPOS
# =============================================================================


class Subject(models.Model):
    """Asignatura (Música, Matemáticas, Historia, etc.)"""
    
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre de la asignatura",
        help_text="Ej: Música, Matemáticas, Historia"
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código",
        help_text="Código corto único (ej: MUS, MAT, HIS)"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Icono",
        help_text="Emoji o clase de icono (ej: 🎵, 🔢, 📚)"
    )
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        verbose_name="Color",
        help_text="Color en formato hexadecimal (ej: #3B82F6)"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está activa, se puede usar para crear nuevos grupos"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["name"]
        verbose_name = "Asignatura"
        verbose_name_plural = "Asignaturas"
    
    def __str__(self):
        if self.icon:
            return f"{self.icon} {self.name}"
        return self.name


class Group(models.Model):
    """Grupo de estudiantes (ej: 1º ESO A, 2º Bachillerato B)"""
    
    name = models.CharField(
        max_length=50,
        verbose_name="Nombre del grupo"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="groups",
        verbose_name="Asignatura",
        help_text="Asignatura que se imparte a este grupo"
    )
    academic_year = models.CharField(
        max_length=20,
        default="2024-2025",
        verbose_name="Curso académico",
        help_text="Ej: 2024-2025"
    )
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="teaching_groups",
        blank=True,
        verbose_name="Profesores",
        help_text="Profesores que imparten clase a este grupo"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "evaluations_group"  # Mantener tabla existente
        ordering = ["name", "subject"]
        unique_together = ["name", "subject", "academic_year"]
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
    
    def __str__(self):
        return f"{self.name} - {self.subject.name} ({self.academic_year})"


class Student(models.Model):
    """Estudiante pertenece a un grupo"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True,
        verbose_name="Usuario"
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="students",
        verbose_name="Grupo",
        help_text="Grupo al que pertenece el estudiante"
    )
    
    class Meta:
        db_table = "evaluations_student"  # Mantener tabla existente
        ordering = ["user__name"]
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"
    
    def __str__(self):
        return f"{self.user.name}" if self.user else f"Student {self.id}"


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
        db_table = "evaluations_grouplibraryitem"  # Mantener tabla existente
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
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadatos",
        help_text="Información adicional específica de la asignatura (JSON)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "evaluations_classsession"  # Mantener tabla existente
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
        db_table = "evaluations_classsessionitem"  # Mantener tabla existente
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
