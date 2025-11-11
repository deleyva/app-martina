from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.urls import reverse
from martina_bescos_app.users.models import User


class LibraryItem(models.Model):
    """
    Biblioteca personal del usuario - puede contener cualquier tipo de contenido.
    Usa GenericForeignKey para apuntar a ScorePages, Documents, Images de Wagtail, etc.
    """

    # Usuario propietario
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="library_items"
    )

    # Referencia genérica al contenido (ScorePage, Document, Image, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # Metadatos
    added_at = models.DateTimeField(auto_now_add=True)
    times_viewed = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    
    # Nivel de conocimiento (1=apenas lo conozco, 4=me lo sé muy bien)
    proficiency_level = models.PositiveSmallIntegerField(
        default=1,
        choices=[
            (1, "⭐ Apenas lo conozco"),
            (2, "⭐⭐ Lo estoy aprendiendo"),
            (3, "⭐⭐⭐ Lo conozco bien"),
            (4, "⭐⭐⭐⭐ Me lo sé muy bien"),
        ],
        help_text="Nivel de dominio de este contenido (1-4)",
    )
    notes = models.TextField(
        blank=True, help_text="Notas personales sobre este elemento"
    )

    # Organización (futuro)
    favorite = models.BooleanField(default=False)

    class Meta:
        ordering = ["proficiency_level", "times_viewed", "-added_at"]
        unique_together = ["user", "content_type", "object_id"]
        indexes = [
            models.Index(fields=["user", "-added_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "Item de Biblioteca"
        verbose_name_plural = "Items de Biblioteca"

    def __str__(self):
        return f"{self.user.username} - {self.get_content_title()}"

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
        }
        return mapping.get(model_name, model_name.title())

    def get_icon(self):
        """Icono según tipo de contenido"""
        model_name = self.content_type.model
        
        # Si es un Document, verificar si es audio
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
        }
        return icons.get(model_name, "📁")

    def get_viewer_url(self):
        """URL para ver el elemento en fullscreen"""
        return reverse("my_library:view_item", args=[self.pk])

    def mark_as_viewed(self):
        """Actualizar contador de vistas"""
        self.times_viewed += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=["times_viewed", "last_viewed"])

    def get_related_scorepage(self):
        """
        Obtener ScorePage relacionado si este item es un Document o Image individual.
        Busca en todas las ScorePages para ver cuál contiene este documento/imagen.
        """
        if self.content_type.model in ["document", "image"]:
            from cms.models import ScorePage
            
            # Buscar en todas las ScorePages
            for score in ScorePage.objects.live():
                # Revisar el StreamField content
                for block in score.content:
                    # Para PDFs/Audios
                    if block.block_type in ["pdf_score", "audio"] and hasattr(block.value, "file"):
                        if block.value.file == self.content_object:
                            return score
                    # Para imágenes
                    elif block.block_type == "image" and hasattr(block.value, "image"):
                        if block.value.image == self.content_object:
                            return score
        return None
    
    def get_documents(self):
        """
        Obtener documentos/archivos del contenido.
        Para ScorePage extrae PDFs, audios, imágenes del StreamField de Wagtail.
        """
        if self.content_type.model == "scorepage":
            score = self.content_object
            return {
                "pdfs": (
                    score.get_pdf_blocks() if hasattr(score, "get_pdf_blocks") else []
                ),
                "audios": score.get_audios() if hasattr(score, "get_audios") else [],
                "images": score.get_images() if hasattr(score, "get_images") else [],
            }
        elif self.content_type.model == "document":
            # Verificar si es audio o PDF
            if hasattr(self.content_object, "file"):
                filename = self.content_object.file.name.lower()
                if filename.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac')):
                    return {"audios": [self.content_object]}
                else:
                    return {"pdfs": [self.content_object]}
            return {"pdfs": [self.content_object]}
        elif self.content_type.model == "image":
            return {"images": [self.content_object]}
        return {}

    @classmethod
    def add_to_library(cls, user, content_object):
        """Añadir elemento a la biblioteca (evita duplicados)"""
        content_type = ContentType.objects.get_for_model(content_object)
        item, created = cls.objects.get_or_create(
            user=user, content_type=content_type, object_id=content_object.pk
        )
        return item, created

    @classmethod
    def is_in_library(cls, user, content_object):
        """Verificar si el contenido ya está en la biblioteca"""
        if not user.is_authenticated:
            return False
        content_type = ContentType.objects.get_for_model(content_object)
        return cls.objects.filter(
            user=user, content_type=content_type, object_id=content_object.pk
        ).exists()
