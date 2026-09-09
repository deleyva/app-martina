import uuid

from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.urls import reverse
from django.utils import timezone

# El orden de la clase, y es fijo: teoría, ritmo o melodía, dictado y
# reconocimiento, sensorialidad, instrumento, canciones.
#
# Vive aquí, a nivel de módulo, porque lo usan dos modelos que no pueden verse
# entre ellos: `ClassSessionItem` se define antes que `GroupBook`. Y vive en UN
# sitio porque el orden es una propiedad del sistema, no de cada asignación: si
# algún día cambia, cambia aquí y ya.
SECCIONES_CLASE = [
    ("teoria", "Teoría"),
    ("ritmo_melodia", "Ritmo o melodía"),
    ("dictado", "Dictado y reconocimiento"),
    ("sensorialidad", "Sensorialidad"),
    ("instrumento", "Instrumento"),
    ("cancion", "Canciones"),
]

# =============================================================================
# ASIGNATURAS Y GESTIÓN DE GRUPOS
# =============================================================================


class Subject(models.Model):
    """Asignatura (Música, Matemáticas, Historia, etc.)"""

    name = models.CharField(
        max_length=100,
        verbose_name="Nombre de la asignatura",
        help_text="Ej: Música, Matemáticas, Historia",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código",
        help_text="Código corto único (ej: MUS, MAT, HIS)",
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Icono",
        help_text="Emoji o clase de icono (ej: 🎵, 🔢, 📚)",
    )
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        verbose_name="Color",
        help_text="Color en formato hexadecimal (ej: #3B82F6)",
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está activa, se puede usar para crear nuevos grupos",
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

    name = models.CharField(max_length=50, verbose_name="Nombre del grupo")
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="groups",
        verbose_name="Asignatura",
        help_text="Asignatura que se imparte a este grupo",
    )
    academic_year = models.CharField(
        max_length=20,
        default="2024-2025",
        verbose_name="Curso académico",
        help_text="Ej: 2024-2025",
    )
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="teaching_groups",
        blank=True,
        verbose_name="Profesores",
        help_text="Profesores que imparten clase a este grupo",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Fuera del día a día, pero no borrado.
    #
    # **No se deduce del curso académico a propósito.** El caso que lo demuestra
    # es `familia-jesus`: es de 2024-2025 y se queda activo. Qué grupos estorban
    # hoy lo sabe el profesor, no el calendario.
    #
    # Las sesiones NO llevan su propio interruptor: una sesión pertenece a un
    # grupo, y no hay ningún caso en que quieras la sesión de un grupo archivado
    # en la lista diaria. Además cada curso es una fila distinta de `Group` —el
    # año forma parte de la clave única—, así que archivar por grupo ya separa
    # los años solo.
    archivado = models.BooleanField(
        default=False,
        verbose_name="Archivado",
        help_text="Fuera de las listas del día a día. No borra nada y se puede deshacer",
    )

    class Meta:
        db_table = "evaluations_group"  # Mantener tabla existente
        ordering = ["name", "subject"]
        unique_together = ["name", "subject", "academic_year"]
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"

    @property
    def active_enrollment_count(self):
        return self.enrollments.filter(is_active=True).count()

    @staticmethod
    def del_profesor(user, incluir_archivados=False):
        """Los grupos de un profesor para el día a día.

        **Un solo sitio que decide.** Cuatro pantallas preguntan por los grupos
        —la lista de sesiones, el desplegable de libros, el panel de avance y el
        formulario de crear sesión— y si cada una filtra por su cuenta, el
        filtro se olvida en la quinta que añadamos.
        """
        grupos = user.teaching_groups.all()
        return grupos if incluir_archivados else grupos.filter(archivado=False)

    @staticmethod
    def matriculados_de(user, incluir_archivados=False):
        """Igual, para el alumnado: un grupo archivado desaparece también para ellos."""
        grupos = Group.objects.filter(
            enrollments__user=user, enrollments__is_active=True
        ).distinct()
        return grupos if incluir_archivados else grupos.filter(archivado=False)

    def __str__(self):
        return f"{self.name} - {self.subject.name} ({self.academic_year})"


class Student(models.Model):
    """Estudiante pertenece a un grupo.

    DEPRECADO: Este modelo se mantiene por compatibilidad con datos existentes.
    Usa Enrollment para la relación User-Group many-to-many.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True,
        verbose_name="Usuario",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="students",
        verbose_name="Grupo",
        help_text="Grupo al que pertenece el estudiante (DEPRECADO: usar Enrollment)",
    )

    class Meta:
        db_table = "evaluations_student"  # Mantener tabla existente
        ordering = ["user__name"]
        verbose_name = "Estudiante (Legacy)"
        verbose_name_plural = "Estudiantes (Legacy)"

    def __str__(self):
        return f"{self.user.name}" if self.user else f"Student {self.id}"


class Enrollment(models.Model):
    """Matrícula de un usuario en un grupo (relación many-to-many User-Group)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Usuario",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Grupo",
    )
    enrolled_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de matrícula",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está desactivado, el usuario no verá este grupo",
    )

    class Meta:
        ordering = ["-enrolled_at"]
        unique_together = ["user", "group"]
        verbose_name = "Matrícula"
        verbose_name_plural = "Matrículas"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["group", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.name if hasattr(self.user, 'name') else self.user.email} → {self.group}"


class GroupInvitation(models.Model):
    """Enlace de invitación para que usuarios se unan a un grupo concreto."""

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name="Grupo",
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Token de invitación",
        help_text="Identificador único del enlace de invitación",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_group_invitations",
        verbose_name="Creado por",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está desactivada, el enlace deja de funcionar",
    )
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número máximo de usos",
        help_text="Déjalo vacío para usos ilimitados",
    )
    uses = models.PositiveIntegerField(
        default=0,
        verbose_name="Usos realizados",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expira el",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creada el",
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último uso",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Invitación a grupo"
        verbose_name_plural = "Invitaciones a grupos"

    def __str__(self):
        return f"Invitación a {self.group} ({self.token})"

    def is_valid(self):
        """Comprobar si la invitación sigue siendo válida."""
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True

    def get_join_path(self):
        """Path relativo que procesa esta invitación."""
        return reverse("clases:group_join_by_invitation", args=[str(self.token)])

    def accept_for_user(self, user):
        """Aceptar la invitación para un usuario autenticado.

        Retorna (enrollment, status) donde status es:
        - "joined": se ha creado el Enrollment y unido al grupo
        - "already_in_group": el usuario ya está matriculado en este grupo
        - "invalid": la invitación no es válida
        """

        if not self.is_valid():
            return None, "invalid"

        # Verificar si ya existe matrícula activa para este grupo
        existing = Enrollment.objects.filter(
            user=user, group=self.group, is_active=True
        ).first()

        if existing:
            return existing, "already_in_group"

        # Crear nueva matrícula
        enrollment = Enrollment.objects.create(user=user, group=self.group)

        self.uses += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["uses", "last_used_at"])

        return enrollment, "joined"


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
        verbose_name="Grupo",
    )

    # Referencia genérica al contenido (ScorePage, Document, Image, RecursoPage, etc.)
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
        help_text="Profesor que añadió este elemento",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas del profesor sobre este elemento para el grupo",
    )
    group_proficiency_level = models.PositiveSmallIntegerField(
        default=1,
        choices=[
            (1, "⭐ El grupo apenas lo conoce"),
            (2, "⭐⭐ Lo está aprendiendo"),
            (3, "⭐⭐⭐ Lo trabaja con soltura"),
            (4, "⭐⭐⭐⭐ Lo domina muy bien"),
        ],
        verbose_name="Nivel del grupo",
        help_text="Nivel de dominio de este contenido por el grupo (1-4)",
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
            if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                return "Audio"
            # Detectar PDFs
            elif filename.endswith(".pdf"):
                return "Documento PDF"
            else:
                return "Documento"

        # Mapping para otros tipos
        mapping = {
            "scorepage": "Partitura",
            "image": "Imagen",
            "recursopage": "Artículo de Blog",
            "dictadopage": "Dictado",
            "embed": "Contenido Incrustado",
            # Sin el nombre del proveedor se leería "Enlaceexterno". En clase
            # lo que hace falta saber es a dónde te manda, no de qué clase es.
            "enlaceexterno": "Enlace externo",
        }
        return mapping.get(model_name, model_name.title())

    def get_icon(self):
        """Icono según tipo de contenido"""
        model_name = self.content_type.model

        # Si es un Document, verificar si es audio o PDF
        if model_name == "document" and hasattr(self.content_object, "file"):
            filename = self.content_object.file.name.lower()
            if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                return "🎵"
            elif filename.endswith(".pdf"):
                return "📄"

        icons = {
            "scorepage": "🎼",
            "document": "📄",
            "image": "🖼️",
            "recursopage": "📝",
            "embed": "▶️",
            # Material con licencia que vive fuera (Blink Learning): el visor
            # lo abre en ventana con nombre, no lo incrusta.
            "enlaceexterno": "🔗",
        }
        return icons.get(model_name, "📁")

    def get_viewer_url(self):
        """URL para ver el elemento en fullscreen dentro de la biblioteca de grupo."""
        return reverse(
            "clases:group_library_item_viewer",
            args=[self.group.pk, self.pk],
        )

    def get_related_scorepage(self):
        """
        Obtener ScorePage relacionado si este item es un Document, Image individual.
        Similar a LibraryItem.get_related_scorepage()
        """
        # Si ya es una ScorePage completa, retornar ella misma
        if self.content_type.model == "scorepage":
            return self.content_object

        # Para documentos, imágenes, embeds, buscar en ScorePages
        if self.content_type.model in ["document", "image", "embed"]:
            from musica.models import ScorePage

            if not self.content_object or not hasattr(self.content_object, "pk"):
                return None

            def _get_block_value(block_value, key):
                value = getattr(block_value, key, None)
                if value:
                    return value
                try:
                    return block_value.get(key)
                except (AttributeError, TypeError):
                    return None

            # Importante: si el mismo Document/Image se reutiliza en varias ScorePages,
            # elegimos la ScorePage más reciente para evitar resultados no deterministas.
            scores = ScorePage.objects.live().order_by(
                "-last_published_at",
                "-first_published_at",
                "-pk",
            )
            for score in scores:
                for block in score.content:
                    try:
                        if block.block_type == "pdf_score":
                            pdf_file = _get_block_value(block.value, "pdf_file")
                            if (
                                pdf_file
                                and hasattr(pdf_file, "pk")
                                and pdf_file.pk == self.content_object.pk
                            ):
                                return score
                        elif block.block_type == "audio":
                            audio_file = _get_block_value(block.value, "audio_file")
                            if (
                                audio_file
                                and hasattr(audio_file, "pk")
                                and audio_file.pk == self.content_object.pk
                            ):
                                return score
                        elif block.block_type == "image":
                            image = _get_block_value(block.value, "image")
                            if (
                                image
                                and hasattr(image, "pk")
                                and image.pk == self.content_object.pk
                            ):
                                return score
                        elif block.block_type == "embed":
                            embed_val = _get_block_value(block.value, "url")
                            if (
                                embed_val
                                and hasattr(self.content_object, "url")
                                and embed_val == self.content_object.url
                            ):
                                return score
                    except (AttributeError, KeyError, TypeError):
                        continue

        return None

    def get_related_scorepage_media(self):
        """Obtener audios y embeds del contenido relacionado (ScorePage, RecursoPage, etc.)."""
        # Primero ver si el propio contenido tiene estos métodos
        if hasattr(self.content_object, "get_audios") or hasattr(self.content_object, "get_embeds"):
            return {
                "score": self.content_object,
                "audios": self.content_object.get_audios() if hasattr(self.content_object, "get_audios") else [],
                "embeds": self.content_object.get_embeds() if hasattr(self.content_object, "get_embeds") else [],
            }

        score = self.get_related_scorepage()
        if not score:
            return {
                "score": None,
                "audios": [],
                "embeds": [],
            }

        return {
            "score": score,
            "audios": score.get_audios() if hasattr(score, "get_audios") else [],
            "embeds": score.get_embeds() if hasattr(score, "get_embeds") else [],
        }

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
            },
        )
        return item, created

    @classmethod
    def is_in_library(cls, group, content_object):
        """Verificar si el contenido ya está en la biblioteca del grupo"""
        content_type = ContentType.objects.get_for_model(content_object)
        return cls.objects.filter(
            group=group, content_type=content_type, object_id=content_object.pk
        ).exists()

    def get_session_count(self):
        """
        Contar en cuántas sesiones de este grupo se ha usado este contenido.
        Cuenta sesiones únicas, no repeticiones del mismo ítem.
        """
        return (
            ClassSessionItem.objects.filter(
                session__group=self.group,
                content_type=self.content_type,
                object_id=self.object_id,
            )
            .values("session")
            .distinct()
            .count()
        )

    @staticmethod
    def get_session_count_for_object(group, content_object):
        """
        Contar en cuántas sesiones del grupo se ha usado un objeto específico.
        Útil para elementos dentro de ScorePage que no tienen GroupLibraryItem propio.
        """
        content_type = ContentType.objects.get_for_model(content_object)
        return (
            ClassSessionItem.objects.filter(
                session__group=group,
                content_type=content_type,
                object_id=content_object.pk,
            )
            .values("session")
            .distinct()
            .count()
        )

    def get_scorepage_total_session_count(self):
        """
        Para ScorePages: obtener el contador SUMATORIO de todos sus elementos.
        Retorna la suma de veces que cada elemento (PDF, audio, imagen, embed)
        ha sido añadido a sesiones de este grupo.
        Solo funciona si este GroupLibraryItem apunta a una ScorePage.
        """
        if self.content_type.model != "scorepage":
            return 0

        total_count = 0
        elements = self.get_scorepage_elements()

        for element in elements:
            count = self.get_session_count_for_object(self.group, element["object"])
            total_count += count

        return total_count

    def get_related_tags(self):
        """
        Obtener tags asociados al contenido.
        Prioridad:
        1. Tags del Document/Image si los tiene
        2. Tags de la ScorePage relacionada
        """
        # Si el contenido tiene tags directamente (Documents en Wagtail)
        if hasattr(self.content_object, "tags") and self.content_object.tags.exists():
            return self.content_object.tags.all()

        # Si es una ScorePage, sus etiquetas están en `faceted_tags`: las
        # páginas dejaron de tener `tags` cuando se retiró `MusicTag` (C37c).
        if self.content_type.model == "scorepage":
            return (
                self.content_object.faceted_tags.all()
                if hasattr(self.content_object, "faceted_tags")
                else []
            )

        # Buscar en ScorePage relacionada. Desde la fase 8 las páginas etiquetan
        # con `faceted_tags`; el `MusicTag` plano ya no lo lee nadie.
        related_score = self.get_related_scorepage()
        if related_score and hasattr(related_score, "faceted_tags"):
            return related_score.faceted_tags.all()

        return []

    def get_related_categories(self):
        """
        Obtener categorías musicales del contenido.
        Solo disponibles en ScorePages (MusicCategory snippets).
        """
        # Si es una ScorePage directamente
        if self.content_type.model == "scorepage":
            return (
                self.content_object.categories.all()
                if hasattr(self.content_object, "categories")
                else []
            )

        # Buscar en ScorePage relacionada
        related_score = self.get_related_scorepage()
        if related_score and hasattr(related_score, "categories"):
            return related_score.categories.all()

        return []

    def get_metadata_badges(self):
        """
        Obtener metadata musical para mostrar como badges.
        Retorna dict con compás, tonalidad, dificultad, etc.
        Solo disponible si hay ScorePage relacionada con MetadataBlock.
        """
        badges = {}

        # Si es ScorePage, buscar MetadataBlock
        score = None
        if self.content_type.model == "scorepage":
            score = self.content_object
        else:
            score = self.get_related_scorepage()

        if score and hasattr(score, "content"):
            # Buscar en StreamField
            for block in score.content:
                if block.block_type == "metadata":
                    metadata = block.value
                    # Extraer campos relevantes
                    if metadata.get("time_signature"):
                        badges["time_signature"] = metadata["time_signature"]
                    if metadata.get("key"):
                        badges["key"] = metadata["key"]
                    if metadata.get("difficulty"):
                        badges["difficulty"] = metadata["difficulty"]
                    break  # Solo el primer bloque de metadata

        return badges

    def get_scorepage_elements(self):
        """
        Obtener todos los elementos de una ScorePage (PDFs, audios, imágenes, embeds).
        Retorna lista de dicts con estructura:
        {
            'type': 'pdf'|'audio'|'image'|'embed',
            'title': str,
            'object': Document|Image object,
            'content_type_id': int,  # ID del ContentType para HTMX
            'tags': QuerySet de etiquetas facetadas (si existen),
            'block': el block del StreamField
        }
        Solo funciona si este GroupLibraryItem apunta a una ScorePage.
        """
        elements = []

        # Solo procesar si es ScorePage
        if self.content_type.model != "scorepage":
            return elements

        score = self.content_object
        if not score or not hasattr(score, "content"):
            return elements

        # Obtener ContentTypes una sola vez
        from wagtail.documents.models import Document
        from wagtail.images.models import Image

        document_ct = ContentType.objects.get_for_model(Document)
        image_ct = ContentType.objects.get_for_model(Image)

        # Iterar sobre el StreamField
        for block in score.content:
            element = None

            if block.block_type == "pdf_score":
                pdf_file = block.value.get("pdf_file")
                if pdf_file:
                    element = {
                        "type": "pdf",
                        "title": block.value.get("title", pdf_file.title),
                        "object": pdf_file,
                        "content_type_id": document_ct.id,
                        "tags": [],  # Documents no tienen tags directos en este modelo
                        "block": block,
                        "session_count": self.get_session_count_for_object(
                            self.group, pdf_file
                        ),
                    }

            elif block.block_type == "audio":
                audio_file = block.value.get("audio_file")
                if audio_file:
                    element = {
                        "type": "audio",
                        "title": block.value.get("title", audio_file.title),
                        "object": audio_file,
                        "content_type_id": document_ct.id,
                        "tags": [],
                        "block": block,
                        "session_count": self.get_session_count_for_object(
                            self.group, audio_file
                        ),
                    }

            elif block.block_type == "image":
                image = block.value.get("image")
                if image:
                    element = {
                        "type": "image",
                        "title": block.value.get("title", image.title),
                        "object": image,
                        "content_type_id": image_ct.id,
                        "tags": [],
                        "block": block,
                        "session_count": self.get_session_count_for_object(
                            self.group, image
                        ),
                    }

            elif block.block_type == "embed":
                embed_val = block.value
                if embed_val and hasattr(embed_val, "url"):
                    from wagtail.embeds.embeds import get_embed
                    from wagtail.embeds.exceptions import EmbedException
                    from wagtail.embeds.models import Embed
                    try:
                        embed_obj = get_embed(embed_val.url)
                        embed_ct = ContentType.objects.get_for_model(Embed)
                        element = {
                            "type": "embed",
                            "title": getattr(embed_obj, "title", "Video/Audio") or "Embed",
                            "object": embed_obj,
                            "content_type_id": embed_ct.id,
                            "tags": [],
                            "block": block,
                            "session_count": self.get_session_count_for_object(
                                self.group, embed_obj
                            ),
                        }
                    except EmbedException:
                        continue

            if element:
                elements.append(element)

        return elements

    def get_blogpage_elements(self):
        """
        Obtener todos los elementos importables de una RecursoPage.

        Incluye:
        1. PDFs, audios e imágenes del StreamField `attachments`
        2. Imágenes embebidas en el body (RichTextField, tags
           `<embed embedtype="image">`)
        3. Embeds de media (vídeos/audios) embebidos en el body
           (tags `<embed embedtype="media">`), resueltos a instancias
           reales del modelo `wagtail.embeds.Embed` vía `get_embed(url)`.

        Devuelve lista de dicts con la misma estructura que
        get_scorepage_elements(). Solo funciona si este GroupLibraryItem
        apunta a una RecursoPage.

        Usa caché por instancia (`_blogpage_elements_cache`) para que
        múltiples llamadas dentro del mismo render de plantilla no repitan
        el trabajo. Para los attachments usa además la caché de
        `RecursoPage._parse_attachments()`.
        """
        if hasattr(self, "_blogpage_elements_cache"):
            return self._blogpage_elements_cache

        elements = []

        # Solo procesar si es RecursoPage
        if self.content_type.model != "recursopage":
            self._blogpage_elements_cache = elements
            return elements

        blogpage = self.content_object
        if not blogpage or not hasattr(blogpage, "_parse_attachments"):
            self._blogpage_elements_cache = elements
            return elements

        # Obtener ContentTypes una sola vez
        from wagtail.documents.models import Document
        from wagtail.images.models import Image

        document_ct = ContentType.objects.get_for_model(Document)
        image_ct = ContentType.objects.get_for_model(Image)

        # --- 1) Attachments StreamField ---
        # Reutilizar la caché de RecursoPage._parse_attachments() que ya
        # deserializa el StreamField una sola vez por instancia.
        parsed = blogpage._parse_attachments()

        for pdf_val in parsed.get("pdfs", []):
            pdf_file = pdf_val.get("pdf_file")
            if pdf_file:
                elements.append({
                    "type": "pdf",
                    "title": pdf_val.get("title", pdf_file.title),
                    "object": pdf_file,
                    "content_type_id": document_ct.id,
                    "tags": [],
                    "session_count": self.get_session_count_for_object(
                        self.group, pdf_file
                    ),
                })

        for audio_val in parsed.get("audios", []):
            audio_file = audio_val.get("audio_file")
            if audio_file:
                elements.append({
                    "type": "audio",
                    "title": audio_val.get("title", audio_file.title),
                    "object": audio_file,
                    "content_type_id": document_ct.id,
                    "tags": [],
                    "session_count": self.get_session_count_for_object(
                        self.group, audio_file
                    ),
                })

        for img_val in parsed.get("images", []):
            image = img_val.get("image")
            if image:
                elements.append({
                    "type": "image",
                    "title": img_val.get("title", image.title),
                    "object": image,
                    "content_type_id": image_ct.id,
                    "tags": [],
                    "session_count": self.get_session_count_for_object(
                        self.group, image
                    ),
                })

        # --- 2) + 3) Body RichTextField (imágenes y embeds de media) ---
        body_html = getattr(blogpage, "body", None)
        if body_html:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(body_html, "html.parser")

            # 2) Imágenes embebidas en el body — son Image reales con PK.
            # Dedupe contra las imágenes ya añadidas desde attachments.
            existing_image_pks = {
                e["object"].pk for e in elements if e["type"] == "image"
            }
            image_id_attrs = [
                tag.get("id")
                for tag in soup.find_all("embed", embedtype="image")
                if tag.get("id")
            ]
            if image_id_attrs:
                # Una sola query para todas las imágenes del body
                try:
                    int_ids = [int(i) for i in image_id_attrs]
                except (TypeError, ValueError):
                    int_ids = []
                if int_ids:
                    db_images = Image.objects.filter(pk__in=int_ids)
                    for image in db_images:
                        if image.pk in existing_image_pks:
                            continue
                        elements.append({
                            "type": "image",
                            "title": image.title,
                            "object": image,
                            "content_type_id": image_ct.id,
                            "tags": [],
                            "session_count": self.get_session_count_for_object(
                                self.group, image
                            ),
                        })
                        existing_image_pks.add(image.pk)

            # 3) Embeds de media (vídeos/audios) embebidos en el body.
            # `get_embed(url)` resuelve y cachea en el modelo Embed.
            media_embed_tags = soup.find_all("embed", embedtype="media")
            if media_embed_tags:
                from wagtail.embeds.embeds import get_embed
                from wagtail.embeds.exceptions import EmbedException
                from wagtail.embeds.models import Embed

                embed_ct = ContentType.objects.get_for_model(Embed)
                seen_embed_pks = set()
                for tag in media_embed_tags:
                    url = tag.get("url")
                    if not url:
                        continue
                    try:
                        embed_obj = get_embed(url)
                    except EmbedException:
                        continue
                    if not embed_obj or embed_obj.pk in seen_embed_pks:
                        continue
                    seen_embed_pks.add(embed_obj.pk)
                    elements.append({
                        "type": "embed",
                        "title": getattr(embed_obj, "title", None) or "Embed",
                        "object": embed_obj,
                        "content_type_id": embed_ct.id,
                        "tags": [],
                        "session_count": self.get_session_count_for_object(
                            self.group, embed_obj
                        ),
                    })

        self._blogpage_elements_cache = elements
        return elements

    def get_blogpage_total_session_count(self):
        """
        Para BlogPages: obtener el contador SUMATORIO de todos sus elementos
        (PDFs, audios, imágenes en attachments). Mismo patrón que
        get_scorepage_total_session_count().

        Suma los `session_count` ya calculados en `get_blogpage_elements()`
        en vez de re-consultar la base de datos por cada elemento.
        """
        if self.content_type.model != "recursopage":
            return 0
        return sum(e["session_count"] for e in self.get_blogpage_elements())


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
        verbose_name="Profesor",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="class_sessions",
        verbose_name="Grupo",
    )
    date = models.DateField(verbose_name="Fecha de la sesión")
    title = models.CharField(max_length=200, verbose_name="Título")
    notes = models.TextField(
        blank=True, verbose_name="Notas", help_text="Notas generales sobre la sesión"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadatos",
        help_text="Información adicional específica de la asignatura (JSON)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # === Reflexión al cierre de la clase ===
    reflection = models.TextField(
        blank=True,
        verbose_name="Reflexión",
        help_text="Reflexión del profesor al finalizar la clase (cómo ha ido, qué quedó pendiente...)",
    )
    reflection_audio = models.FileField(
        upload_to="class_reflections/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="Reflexión (audio)",
        help_text="Nota de voz grabada al finalizar la clase",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Cerrada el",
        help_text="Momento en que el profesor dio la clase por finalizada",
    )

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

    # === Cierre / reflexión ===

    @property
    def is_closed(self):
        """La clase ha sido dada por finalizada por el profesor"""
        return self.closed_at is not None

    def close(self, reflection_text="", audio_file=None):
        """
        Cerrar la sesión guardando la reflexión del profesor.
        Idempotente: si ya estaba cerrada, actualiza la reflexión sin cambiar closed_at.
        """
        from django.utils import timezone

        if reflection_text:
            self.reflection = reflection_text
        if audio_file:
            self.reflection_audio = audio_file
        if not self.closed_at:
            self.closed_at = timezone.now()
        self.save(
            update_fields=["reflection", "reflection_audio", "closed_at", "updated_at"]
        )

    def reopen(self):
        """Reabrir una sesión cerrada (mantiene la reflexión)"""
        self.closed_at = None
        self.save(update_fields=["closed_at", "updated_at"])


class ClassSessionItem(models.Model):
    """
    Elemento individual de una sesión de clase.
    Usa GenericForeignKey para apuntar a cualquier tipo de contenido.
    """

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Sesión",
    )

    # Referencia genérica al contenido
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # Página de origen (ScorePage o RecursoPage desde la que se añadió el elemento)
    source_page = models.ForeignKey(
        "wagtailcore.Page",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_items_from",
        verbose_name="Página de origen",
        help_text="Página desde la que se añadió este elemento",
    )

    # Orden y metadatos
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas específicas para este elemento en la sesión",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    # De qué libro del grupo salió este elemento.
    #
    # **Que sea nullable es la pieza que hace todo lo demás posible.** Un
    # elemento que el profesor añade suelto para hoy lleva `group_book = None`:
    # entra en la clase, se ve, y no mueve la progresión de ningún libro. Es
    # justo lo que pidió el principal — "poder añadir algún ítem extra a una
    # clase sin tener que ensuciar los libros".
    group_book = models.ForeignKey(
        "clases.GroupBook",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_items",
        verbose_name="Libro del grupo",
    )

    # Se copia al preparar la sesión en vez de leerse de `group_book`, porque
    # los extras no tienen libro y aun así ocupan un sitio en el orden de la
    # clase. Vacío = extra suelto, va al final.
    seccion = models.CharField(
        max_length=20,
        blank=True,
        choices=SECCIONES_CLASE,
        verbose_name="Sección de la clase",
    )

    # Lo que pasó con este elemento EN ESTA CLASE.
    #
    # No duplica `GroupBookItem.estado`: responden a preguntas distintas. Este
    # dice "hoy llegamos a verlo"; aquel dice "el grupo ya no necesita que se lo
    # vuelvan a proponer". Un extra suelto solo puede tener el primero.
    visto = models.BooleanField(default=False, verbose_name="Visto en clase")

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
            if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                return "Audio"
            elif filename.endswith(".pdf"):
                return "Documento PDF"
            else:
                return "Documento"

        mapping = {
            "scorepage": "Partitura",
            "image": "Imagen",
            "recursopage": "Artículo de Blog",
            "grouplibraryitem": "Item de Biblioteca",
            "embed": "Contenido Incrustado",
            "enlaceexterno": "Enlace externo",
        }
        return mapping.get(model_name, model_name.title())

    def get_icon(self):
        """Icono según tipo de contenido"""
        model_name = self.content_type.model

        if model_name == "document" and hasattr(self.content_object, "file"):
            filename = self.content_object.file.name.lower()
            if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                return "🎵"
            elif filename.endswith(".pdf"):
                return "📄"

        icons = {
            "scorepage": "🎼",
            "document": "📄",
            "image": "🖼️",
            "recursopage": "📝",
            "embed": "▶️",
            # Material con licencia que vive fuera (Blink Learning): el visor
            # lo abre en ventana con nombre, no lo incrusta.
            "enlaceexterno": "🔗",
        }
        return icons.get(model_name, "📁")

    def get_content_url(self):
        """Obtener URL del contenido si existe"""
        try:
            if hasattr(self.content_object, "get_url"):
                return self.content_object.get_url()
            elif hasattr(self.content_object, "url"):
                return self.content_object.url
            elif hasattr(self.content_object, "file"):
                # Wagtail Document
                return self.content_object.file.url
        except (AttributeError, ValueError):
            pass
        return None

    def get_related_scorepage(self):
        """
        Obtener ScorePage relacionado si este item es un Document, Image individual.
        Similar a GroupLibraryItem.get_related_scorepage()
        """
        # Si ya es una ScorePage completa, retornar ella misma
        if self.content_type.model == "scorepage":
            return self.content_object

        # Si tenemos source_page guardada, usarla directamente
        if self.source_page_id:
            return self.source_page

        # Fallback: para documentos, imágenes, buscar en ScorePages
        if self.content_type.model in ["document", "image", "embed"]:
            from musica.models import ScorePage

            if not self.content_object or not hasattr(self.content_object, "pk"):
                return None

            def _get_block_value(block_value, key):
                value = getattr(block_value, key, None)
                if value:
                    return value
                try:
                    return block_value.get(key)
                except (AttributeError, TypeError):
                    return None

            # Importante: si el mismo Document/Image se reutiliza en varias ScorePages,
            # elegimos la ScorePage más reciente para evitar resultados no deterministas.
            scores = ScorePage.objects.live().order_by(
                "-last_published_at",
                "-first_published_at",
                "-pk",
            )
            for score in scores:
                for block in score.content:
                    try:
                        if block.block_type == "pdf_score":
                            pdf_file = _get_block_value(block.value, "pdf_file")
                            if (
                                pdf_file
                                and hasattr(pdf_file, "pk")
                                and pdf_file.pk == self.content_object.pk
                            ):
                                return score
                        elif block.block_type == "audio":
                            audio_file = _get_block_value(block.value, "audio_file")
                            if (
                                audio_file
                                and hasattr(audio_file, "pk")
                                and audio_file.pk == self.content_object.pk
                            ):
                                return score
                        elif block.block_type == "image":
                            image = _get_block_value(block.value, "image")
                            if (
                                image
                                and hasattr(image, "pk")
                                and image.pk == self.content_object.pk
                            ):
                                return score
                        elif block.block_type == "embed":
                            embed_val = _get_block_value(block.value, "url")
                            if (
                                embed_val
                                and hasattr(self.content_object, "url")
                                and embed_val == self.content_object.url
                            ):
                                return score
                    except (AttributeError, KeyError, TypeError):
                        continue

        return None

    def get_related_scorepage_media(self):
        """Obtener audios y embeds del contenido relacionado (ScorePage, RecursoPage, etc.)."""
        # Primero ver si el propio contenido tiene estos métodos
        if hasattr(self.content_object, "get_audios") or hasattr(self.content_object, "get_embeds"):
            return {
                "score": self.content_object,
                "audios": self.content_object.get_audios() if hasattr(self.content_object, "get_audios") else [],
                "embeds": self.content_object.get_embeds() if hasattr(self.content_object, "get_embeds") else [],
            }

        score = self.get_related_scorepage()
        if not score:
            return {
                "score": None,
                "audios": [],
                "embeds": [],
            }

        return {
            "score": score,
            "audios": score.get_audios() if hasattr(score, "get_audios") else [],
            "embeds": score.get_embeds() if hasattr(score, "get_embeds") else [],
        }

    @classmethod
    def add_to_session(cls, session, content_object, notes="", source_page_id=None):
        """Añadir elemento a la sesión.

        RESTRICCIÓN: No se permiten ScorePages completas en sesiones de clase.
        Solo se pueden añadir elementos individuales (PDFs, audios, imágenes) y BlogPages.
        """
        content_type = ContentType.objects.get_for_model(content_object)

        # Validación: rechazar ScorePages completas
        if content_type.model == "scorepage":
            raise ValueError(
                "No se pueden añadir ScorePages completas a sesiones de clase. "
                "Añade los elementos individuales (PDFs, audios, imágenes) en su lugar."
            )

        order = session.get_next_order()

        item = cls.objects.create(
            session=session,
            content_type=content_type,
            object_id=content_object.pk,
            order=order,
            notes=notes,
            source_page_id=source_page_id,
        )
        return item


# =============================================================================
# TARJETAS DE ESTUDIO
# =============================================================================


class StudyCardBatch(models.Model):
    """Un lote de tarjetas generado para impresión."""

    group = models.ForeignKey(
        "clases.Group",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="study_card_batches",
        verbose_name="Grupo",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_card_batches",
        verbose_name="Creado por",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, verbose_name="Título")
    notes = models.TextField(blank=True, verbose_name="Notas")
    pdf_file = models.FileField(
        upload_to="study_cards/batches/",
        null=True,
        blank=True,
        verbose_name="Archivo PDF",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lote de Tarjetas"
        verbose_name_plural = "Lotes de Tarjetas"

    def __str__(self):
        return f"{self.title} ({self.created_at:%Y-%m-%d})"

    def get_items_count(self):
        return self.items.count()


class StudyCardItem(models.Model):
    """Una tarjeta individual dentro de un batch."""

    batch = models.ForeignKey(
        StudyCardBatch,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Lote",
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        verbose_name="Imagen",
    )
    source_page = models.ForeignKey(
        "wagtailcore.Page",
        on_delete=models.CASCADE,
        verbose_name="Página de origen",
    )
    code = models.CharField(max_length=20, verbose_name="Código")
    position = models.PositiveIntegerField(verbose_name="Posición")

    class Meta:
        ordering = ["position"]
        unique_together = ["batch", "code"]
        verbose_name = "Tarjeta"
        verbose_name_plural = "Tarjetas"
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.image.title}"


class StudyCardPickup(models.Model):
    """Registro de que un alumno cogió una tarjeta."""

    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("photo_ocr", "Photo OCR"),
    ]

    card_item = models.ForeignKey(
        StudyCardItem,
        on_delete=models.CASCADE,
        related_name="pickups",
        verbose_name="Tarjeta",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_card_pickups",
        verbose_name="Alumno",
    )
    picked_up_at = models.DateField(verbose_name="Fecha de recogida")
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="manual",
        verbose_name="Origen",
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Confianza OCR",
        help_text="Confianza del reconocimiento OCR (0-1)",
    )

    class Meta:
        ordering = ["-picked_up_at"]
        unique_together = ["card_item", "student"]
        verbose_name = "Recogida de Tarjeta"
        verbose_name_plural = "Recogidas de Tarjetas"
        indexes = [
            models.Index(fields=["student", "-picked_up_at"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.card_item.code} ({self.picked_up_at})"


class StudyCardLabel(models.Model):
    """Etiqueta descriptiva corta para una imagen imprimible en un capítulo."""

    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        verbose_name="Imagen",
    )
    source_page = models.ForeignKey(
        "wagtailcore.Page",
        on_delete=models.CASCADE,
        verbose_name="Página de origen",
    )
    description = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Descripción",
        help_text="Texto corto que se imprime junto al código (máx. 60 car.)",
    )

    class Meta:
        unique_together = ["image", "source_page"]
        verbose_name = "Etiqueta de Tarjeta"
        verbose_name_plural = "Etiquetas de Tarjetas"

    def __str__(self):
        return f"{self.description} ({self.image.title})"


# =============================================================================
# LIBROS QUE DAN CLASE
#
# El motor de `my_library` (objetivo por libro + creación perezosa) aplicado a
# los grupos. `GroupBook` es a un grupo lo que `LibraryGoal` es a un usuario:
# guarda la INTENCIÓN de trabajar un libro, no su material.
# =============================================================================


class GroupBook(models.Model):
    """Un libro asignado a un grupo, con su sitio en el orden de la clase.

    **La sección va aquí y no en cada elemento** (decisión del principal,
    2026-09-08). El orden de la clase es fijo —teoría, ritmo, dictado,
    sensorialidad, instrumento, canciones—, así que montar una sesión no es
    elegir libros sino elegir qué secciones se tocan hoy: el orden sale solo y
    no hay que recolocarlo nunca.

    **Es por GRUPO, no por profesor.** `Group.teachers` es M2M; con la
    selección atada al profesor, dos profesores del mismo grupo llevarían
    progresos distintos sobre el mismo libro y el alumnado recibiría dos veces
    lo que baje a sus bibliotecas.

    Sirven los DOS tipos de libro, y no por casualidad: los capítulos se piden
    a `my_library.libros.capitulos_de`, que distingue por capacidad y no por
    tipo. Un `LibroPage` con páginas hijas se recorre por el árbol; un
    `LibroDeEstudioPage` se recorre por sus referencias. El segundo es el que
    hace falta para las canciones, porque en Wagtail una página tiene un solo
    padre: agrupar por árbol obligaría a que cada canción viviera en un único
    libro para siempre.
    """

    # El orden de la clase vive en `SECCIONES_CLASE`, arriba del módulo. Aquí
    # solo se expone con el nombre corto para que se lea bien en el modelo.
    SECCIONES = SECCIONES_CLASE

    # Modo de avance. La distinción existe porque un método y una canción no se
    # estudian igual: el ejercicio 14 de un método se hace y se pasa al 15, pero
    # una canción se trabaja durante semanas. Con un solo comportamiento, o las
    # canciones desaparecen en la segunda sesión, o se deja de marcar nada por
    # miedo y el motor no avanza.
    SECUENCIAL = "secuencial"
    EN_CURSO = "en_curso"
    MODOS = [
        (SECUENCIAL, "Secuencial — avanza y no vuelve"),
        (EN_CURSO, "En curso — sigue activo hasta que lo cierres"),
    ]

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="books",
        verbose_name="Grupo",
    )
    libro = models.ForeignKey(
        "wagtailcore.Page",
        on_delete=models.CASCADE,
        related_name="group_books",
        verbose_name="Libro",
    )
    seccion = models.CharField(
        max_length=20,
        choices=SECCIONES,
        verbose_name="Sección de la clase",
        help_text="En qué momento de la clase entra este libro",
    )
    modo = models.CharField(
        max_length=12,
        choices=MODOS,
        default=SECUENCIAL,
        verbose_name="Modo de avance",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Un libro inactivo deja de proponer elementos, sin perder el avance",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Asignado por",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["group", "seccion", "created_at"]
        unique_together = ["group", "libro"]
        verbose_name = "Libro del grupo"
        verbose_name_plural = "Libros del grupo"
        indexes = [
            models.Index(fields=["group", "activo"]),
        ]

    def __str__(self):
        return f"{self.group.name} · {self.libro.title} ({self.get_seccion_display()})"

    @property
    def orden_de_seccion(self):
        """Posición de su sección en el orden fijo de la clase.

        Se calcula sobre `SECCIONES` en vez de guardarse, porque el orden de la
        clase es una propiedad del sistema y no de cada asignación: si un día
        cambia, cambia en un sitio.
        """
        claves = [clave for clave, _ in self.SECCIONES]
        return claves.index(self.seccion) if self.seccion in claves else len(claves)


class GroupBookItem(models.Model):
    """Lo que el grupo ha hecho con UN elemento de un libro. Fila de excepción.

    **No es una copia del material, y esa es toda la idea.** Un libro recién
    asignado son CERO filas aquí: el material se enumera al vuelo desde la
    página con `my_library.libros.material_del_libro`, y el orden por defecto es
    el del libro. Solo nace fila cuando el profesor se sale de ese defecto:
    excluye un elemento, lo recoloca, lo da por visto o marca que baja a las
    bibliotecas del alumnado.

    El motivo está medido y es el mismo que llevó a la creación perezosa en
    `my_library`: *Ukulele Aerobics* tiene 283 medios practicables. Copiarlos
    por adelantado para cada grupo que estudie el libro llena la tabla de
    material que nadie ha mirado todavía, y obliga a resincronizar cada vez que
    se edita la página del libro.
    """

    PENDIENTE = "pendiente"
    VISTO = "visto"
    REPETIR = "repetir"
    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (VISTO, "Visto — no volver a proponerlo"),
        (REPETIR, "Visto, pero repetirlo"),
    ]

    group_book = models.ForeignKey(
        GroupBook,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Libro del grupo",
    )

    # Referencia genérica al medio: Image, Document, Embed…
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    source_page = models.ForeignKey(
        "wagtailcore.Page",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_book_items_from",
        verbose_name="Capítulo de origen",
    )

    # Posición dentro del libro PARA ESTE GRUPO. `None` significa "donde diga el
    # libro": así, reordenar unos pocos elementos no obliga a escribir una fila
    # por cada uno de los que no se han tocado.
    orden = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Orden en el grupo",
        help_text="Vacío = el orden del libro",
    )

    incluido = models.BooleanField(
        default=True,
        verbose_name="Incluido",
        help_text="Desmarcado: no se propone nunca a este grupo",
    )

    # Si baja a las bibliotecas personales del alumnado cuando se da por visto.
    #
    # Existe porque bañarlas con TODO lo visto en clase las convierte en un
    # vertedero: son unas 5.400 filas por grupo y curso, y la mitad son
    # ejercicios de un solo uso (dictado, sensorialidad) que nadie va a repasar
    # en casa. Lo lee la fase C; en la A solo se guarda.
    a_casa = models.BooleanField(
        default=False,
        verbose_name="Baja a las bibliotecas del alumnado",
    )

    estado = models.CharField(
        max_length=12,
        choices=ESTADOS,
        default=PENDIENTE,
        verbose_name="Estado",
    )
    visto_en = models.ForeignKey(
        "clases.ClassSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items_marcados",
        verbose_name="Visto en la sesión",
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group_book", "orden"]
        unique_together = ["group_book", "content_type", "object_id"]
        verbose_name = "Elemento de libro del grupo"
        verbose_name_plural = "Elementos de libros del grupo"
        indexes = [
            models.Index(fields=["group_book", "estado"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.group_book} · {self.content_type.model}#{self.object_id}"

    @property
    def propuesto(self):
        """Si el motor debe volver a ofrecer este elemento."""
        return self.incluido and self.estado != self.VISTO
