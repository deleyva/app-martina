from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from taggit.managers import TaggableManager
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

    # Página de origen (ScorePage o BlogPage desde la que se añadió el elemento)
    source_page = models.ForeignKey(
        "wagtailcore.Page",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_items_from",
        verbose_name="Página de origen",
        help_text="Página desde la que se añadió este elemento",
    )

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

    # Tags para items sin tags propios (embeds)
    tags = TaggableManager(blank=True, help_text="Tags para items sin tags propios (embeds)")

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
            "embed": "Contenido Incrustado",
        }
        return mapping.get(model_name, model_name.title())

    def get_icon(self):
        """Icono según tipo de contenido"""
        model_name = self.content_type.model

        # Si es un Document, verificar si es audio
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
            "embed": "▶️",
        }
        return icons.get(model_name, "📁")

    def get_preview_html(self):
        """Generar HTML de previsualización según tipo de contenido."""
        model_name = self.content_type.model
        obj = self.content_object

        if not obj:
            return format_html(
                '<div class="flex items-center justify-center size-16 bg-base-200 rounded-lg">'
                '<span class="text-2xl">❓</span></div>'
            )

        # Imagen de Wagtail: rendición real
        if model_name == "image" and hasattr(obj, "get_rendition"):
            try:
                rendition = obj.get_rendition("fill-64x64")
                return format_html(
                    '<img src="{}" alt="{}" class="size-16 rounded-lg object-cover" loading="lazy">',
                    rendition.url,
                    obj.title,
                )
            except Exception:
                pass

        # Document de Wagtail (PDF o Audio)
        if model_name == "document" and hasattr(obj, "file"):
            filename = obj.file.name.lower()
            if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                return format_html(
                    '<div class="flex items-center justify-center size-16 bg-gradient-to-br from-purple-100 to-purple-200 dark:from-purple-900/30 dark:to-purple-800/30 rounded-lg">'
                    '<svg class="w-8 h-8 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>'
                    '</svg></div>'
                )
            elif filename.endswith(".pdf"):
                return format_html(
                    '<div class="flex items-center justify-center size-16 bg-gradient-to-br from-red-100 to-red-200 dark:from-red-900/30 dark:to-red-800/30 rounded-lg">'
                    '<svg class="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>'
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-6 3h4"></path>'
                    '</svg></div>'
                )

        # Embed: intentar thumbnail del oembed
        if model_name == "embed" and hasattr(obj, "thumbnail_url"):
            thumb = obj.thumbnail_url
            if thumb:
                return format_html(
                    '<div class="relative size-16 rounded-lg overflow-hidden">'
                    '<img src="{}" alt="{}" class="size-16 object-cover" loading="lazy">'
                    '<div class="absolute inset-0 flex items-center justify-center bg-black/30">'
                    '<svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">'
                    '<path d="M8 5v14l11-7z"></path>'
                    '</svg></div></div>',
                    thumb,
                    getattr(obj, "title", "embed"),
                )
            # Embed sin thumbnail (ej: Hooktheory)
            return format_html(
                '<div class="flex items-center justify-center size-16 bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900/30 dark:to-blue-800/30 rounded-lg">'
                '<svg class="w-8 h-8 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 24 24">'
                '<path d="M8 5v14l11-7z"></path>'
                '</svg></div>'
            )

        # Fallback genérico
        return format_html(
            '<div class="flex items-center justify-center size-16 bg-gradient-to-br from-primary/20 to-secondary/20 rounded-lg">'
            '<span class="text-2xl">{}</span></div>',
            self.get_icon(),
        )

    def get_content_tags(self):
        """Obtener tags del contenido referenciado. Fallback a self.tags para embeds."""
        obj = self.content_object
        if obj and hasattr(obj, "tags"):
            content_tags = obj.tags.all()
            if content_tags.exists():
                return content_tags
        # Fallback: tags en el LibraryItem (para embeds u otros sin tags propios)
        return self.tags.all()

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
        Obtener ScorePage relacionado si este item es un Document, Image o Embed individual.
        Usa source_page FK si está disponible, si no busca en ScorePages.
        """
        # Si ya es una ScorePage completa, retornar ella misma
        if self.content_type.model == "scorepage":
            return self.content_object

        # Usar source_page guardada si existe (fuente fiable)
        if self.source_page_id:
            return self.source_page.specific

        # Fallback: buscar en ScorePages (para items legacy sin source_page)
        if self.content_type.model in ["document", "image", "embed"]:
            return self._search_scorepage_in_streamfields()

        return None

    def _search_scorepage_in_streamfields(self):
        """Buscar en StreamFields de ScorePages (fallback lento para items legacy)."""
        from cms.models import ScorePage

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
        """Obtener audios y embeds del contenido relacionado (ScorePage, BlogPage, etc.)."""
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
                if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                    return {"audios": [self.content_object]}
                else:
                    return {"pdfs": [self.content_object]}
            return {"pdfs": [self.content_object]}
        elif self.content_type.model == "image":
            return {"images": [self.content_object]}
        elif self.content_type.model == "embed":
            return {"embeds": [self.content_object]}
        return {}

    @classmethod
    def add_to_library(cls, user, content_object, source_page_id=None):
        """Añadir elemento a la biblioteca (evita duplicados).

        RESTRICCIÓN: No se permiten ScorePages completas en bibliotecas personales.
        Solo se pueden añadir elementos individuales (PDFs, audios, imágenes).
        """
        content_type = ContentType.objects.get_for_model(content_object)

        # Validación: rechazar ScorePages completas
        if content_type.model == "scorepage":
            raise ValueError(
                "No se pueden añadir ScorePages completas a la biblioteca personal. "
                "Añade los elementos individuales (PDFs, audios, imágenes) en su lugar."
            )

        item, created = cls.objects.get_or_create(
            user=user, content_type=content_type, object_id=content_object.pk
        )
        # Actualizar source_page si se proporciona y no tenía
        if source_page_id and not item.source_page_id:
            item.source_page_id = source_page_id
            item.save(update_fields=["source_page_id"])
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
