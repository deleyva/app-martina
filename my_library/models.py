import json

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from taggit.managers import TaggableManager
from martina_bescos_app.users.models import User


class LibraryDeck(models.Model):
    """
    Mazo de práctica — filtro de tags guardado para estudio recurrente.
    Almacena un nombre y una lista de tags como JSON. Los items que coincidan
    con TODOS los tags (lógica AND) forman el contenido del mazo.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="library_decks"
    )
    name = models.CharField(max_length=100)
    tags_json = models.TextField(
        help_text="JSON array of tag names, e.g. [\"guitarra\", \"jazz\"]"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["user", "name"]
        verbose_name = "Mazo de Biblioteca"
        verbose_name_plural = "Mazos de Biblioteca"

    def __str__(self):
        # Este User no tiene `username` (USERNAME_FIELD = "email")
        return f"{self.user.email} - {self.name}"

    def get_tags(self):
        """Return list of tag names."""
        try:
            return json.loads(self.tags_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags(self, tag_list):
        """Set tags from a list of strings."""
        self.tags_json = json.dumps(tag_list)

    def get_matching_item_pks(self, tag_map):
        """Return PKs of library items matching ALL deck tags.

        Args:
            tag_map: dict mapping item PK to set of lowercase tag strings,
                     built once via LibraryDeck.build_tag_map() and shared across decks.
        """
        tags = [t.lower() for t in self.get_tags()]
        if not tags:
            return list(tag_map.keys())

        return [pk for pk, item_tags in tag_map.items() if all(t in item_tags for t in tags)]

    @staticmethod
    def precargar_etiquetas_de_pagina(items):
        """Carga en bloque las etiquetas facetadas de las páginas de origen.

        `get_content_tags` sube a `source_page.specific` para leerlas, y eso son
        unas 3 consultas por elemento: la página, su subclase concreta y sus
        etiquetas. Medido sobre la biblioteca real: 51 elementos pasaban de 107
        a 254 consultas y de 74 a 222 ms, y eso crece en línea recta — a 500
        elementos serían más de dos segundos en la página con la que se arranca
        cada sesión.

        Esto lo baja a dos consultas para toda la lista. Deja las etiquetas
        colgadas de cada elemento en `_etiquetas_de_pagina`; sin precarga,
        `get_content_tags` sigue funcionando igual, solo que consulta una a una.
        """
        from wagtail.models import Page

        pks = {item.source_page_id for item in items if item.source_page_id}
        por_pagina = {}
        if pks:
            for pagina in Page.objects.filter(pk__in=pks).specific():
                if hasattr(pagina, "faceted_tags"):
                    por_pagina[pagina.pk] = list(pagina.faceted_tags.all())
        for item in items:
            item._etiquetas_de_pagina = por_pagina.get(item.source_page_id, [])

    @staticmethod
    def build_tag_map(items_qs):
        """Build a {pk: set(lowercase_tags)} dict for all items in queryset.

        Call once, share across all decks to avoid per-deck N+1 queries.
        """
        items = list(items_qs)
        LibraryDeck.precargar_etiquetas_de_pagina(items)

        tag_map = {}
        for item in items:
            tags_set = set()
            # Item's own tags (prefetched)
            for tag in item.tags.all():
                tags_set.add(tag.name.lower())
            # Content object tags (GenericFK — unavoidable per-item query)
            obj = item.content_object
            if obj and hasattr(obj, "tags"):
                for tag in obj.tags.all():
                    tags_set.add(tag.name.lower())
            # Etiquetas de la página de origen. Desde la fase 8 se leen de
            # `faceted_tags` (taggit, vocabulario facetado) y NO de `tags`, que
            # es el `MusicTag` plano. Mientras se leían las dos, una etiqueta de
            # página no podía agrupar ni filtrar una sesión, porque `facets.parse`
            # no reconoce un nombre sin faceta. Ese era el motivo de la fase.
            #
            # `tags` sigue existiendo y sigue alimentando el filtrado del sitio;
            # lo que se decide en C37 es su destino, no el de esta lectura.
            for tag in getattr(item, "_etiquetas_de_pagina", []):
                tags_set.add(tag.name.lower())
            tag_map[item.pk] = tags_set
        return tag_map


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
        # Este User no tiene `username` (USERNAME_FIELD = "email")
        return f"{self.user.email} - {self.get_content_title()}"

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
            "externalresource": "Enlace Externo",
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
            "externalresource": "🔗",
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

        # Enlace externo
        if model_name == "externalresource":
            icon = getattr(obj, "icon", "🔗")
            return format_html(
                '<div class="flex items-center justify-center size-16 bg-gradient-to-br from-emerald-100 to-emerald-200 dark:from-emerald-900/30 dark:to-emerald-800/30 rounded-lg">'
                '<span class="text-2xl">{}</span></div>',
                icon,
            )

        # Fallback genérico
        return format_html(
            '<div class="flex items-center justify-center size-16 bg-gradient-to-br from-primary/20 to-secondary/20 rounded-lg">'
            '<span class="text-2xl">{}</span></div>',
            self.get_icon(),
        )

    def get_content_tags(self):
        """Las etiquetas de este elemento: las suyas MÁS las de su página.

        Las propias salen del contenido referenciado, con `self.tags` de reserva
        para los embeds y demás que no traen etiquetas propias. A eso se le suman
        las de `source_page`, que es de donde vienen las que describen el
        contenedor: los 23 capítulos del libro de Jens Larsen llevan
        `estilo:jazz-moderno` en la página del libro, no en cada PDF.

        **Por qué se suma aquí y no solo en `build_tag_map`** (decisión del
        principal, opción A, 2026-08-24): había dos definiciones de "las
        etiquetas de este elemento" conviviendo. `build_tag_map` miraba la
        página y esta no, así que la página contaba para emparejar un mazo y no
        para el selector de facetas ni para la agrupación temática. Ese
        desdoblamiento es lo que hizo que la fase 8 pareciera terminada sin
        entregar lo que decía. Ahora hay una sola respuesta, y la pinta también
        el visor: si un PDF es jazz moderno, ponerlo es información, no ruido.

        Solo se suman las de `faceted_tags`; el `MusicTag` plano no entra. Con
        el vocabulario viejo esto habría metido 169 etiquetas que ni agrupan ni
        filtran, que es justo lo que la fase 8 vino a quitar de en medio.
        """
        propias = []
        obj = self.content_object
        if obj and hasattr(obj, "tags"):
            propias = list(obj.tags.all())
        if not propias:
            # Reserva: etiquetas del propio LibraryItem (embeds y demás)
            propias = list(self.tags.all())

        de_pagina = getattr(self, "_etiquetas_de_pagina", None)
        if de_pagina is None:
            # Sin precarga: se sube a la página una por una. Correcto pero caro;
            # cualquier bucle sobre elementos debería llamar antes a
            # `precargar_etiquetas_de_pagina`.
            de_pagina = []
            if self.source_page_id and self.source_page:
                specific = self.source_page.specific
                if hasattr(specific, "faceted_tags"):
                    de_pagina = list(specific.faceted_tags.all())

        vistas = {etiqueta.name.lower() for etiqueta in propias}
        return propias + [
            etiqueta
            for etiqueta in de_pagina
            if etiqueta.name.lower() not in vistas
        ]

    def get_viewer_url(self):
        """URL para ver el elemento en fullscreen"""
        return reverse("my_library:view_item", args=[self.pk])

    def mark_as_viewed(self):
        """Actualizar contador de vistas"""
        self.times_viewed += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=["times_viewed", "last_viewed"])

    @property
    def clave_de_practica(self):
        return ("item", self.pk)

    @property
    def tiene_secciones(self):
        return self.sections.exists()

    @property
    def shared_note(self):
        """Nota docente de este contenido, o None. La ve todo el mundo."""
        return SharedNote.for_content(self.content_object)

    @property
    def last_review(self):
        """Último repaso del elemento ENTERO, o None.

        Deriva de ReviewLog, no de `last_viewed`: abrir el visor no es repasar.

        Excluye los repasos de secciones aunque lleven este `item_id`: si
        contaran, trocear una pieza haría que pareciera repasada entera cada
        vez que se toca un trozo.
        """
        return (
            self.reviews.filter(section__isnull=True).order_by("-reviewed_at").first()
        )

    @property
    def days_since_last_review(self):
        """Días desde el último repaso. None = nunca repasado.

        None significa máxima prioridad para un futuro planificador, no cero.
        """
        last = self.last_review
        if last is None:
            return None
        return (timezone.now() - last.reviewed_at).days

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
            # Verificar si es audio, GP o PDF
            if hasattr(self.content_object, "file"):
                filename = self.content_object.file.name.lower()
                if filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                    return {"audios": [self.content_object]}
                elif filename.endswith((".gp", ".gp5", ".gpx", ".gp4", ".gp3")):
                    return {"gp_files": [self.content_object]}
                else:
                    return {"pdfs": [self.content_object]}
            return {"pdfs": [self.content_object]}
        elif self.content_type.model == "image":
            return {"images": [self.content_object]}
        elif self.content_type.model == "embed":
            return {"embeds": [self.content_object]}
        elif self.content_type.model == "externalresource":
            return {"external_links": [self.content_object]}
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


class ItemSection(models.Model):
    """Un trozo practicable de un elemento largo.

    Una partitura de veinte páginas no es una unidad de práctica: nadie
    practica "la sonata entera", practica los compases 30-60. Mientras el PDF
    sea un solo elemento con una sola valoración, el sistema no puede saber que
    la primera parte te sale y la tercera no.

    El nombre lo pone el usuario y es lo que manda: la división útil en música
    es musical, no física — los compases difíciles no caen donde acaba la
    página. El localizador (páginas para un PDF, segundos para un vídeo) es
    opcional y solo sirve para que el visor salte solo.

    **Cuando un elemento tiene secciones, las secciones lo sustituyen como
    unidad de práctica**: el elemento entero deja de salir en la cola. Si
    siguiera saliendo, no se habría arreglado nada.

    El historial que el elemento tuviera antes de trocearse se queda en el
    elemento, sin usarse. No se puede repartir hacia atrás: nadie sabe a qué
    trozo correspondía cada repaso.
    """

    item = models.ForeignKey(
        LibraryItem, on_delete=models.CASCADE, related_name="sections"
    )
    orden = models.PositiveIntegerField(default=0)
    nombre = models.CharField(
        max_length=200,
        help_text='Cómo lo llamas: "compases 30-60", "el estribillo"',
    )

    # Localizador opcional — PDF
    pagina_desde = models.PositiveSmallIntegerField(null=True, blank=True)
    pagina_hasta = models.PositiveSmallIntegerField(null=True, blank=True)

    # Localizador opcional — vídeo o audio, en segundos
    segundo_desde = models.PositiveIntegerField(null=True, blank=True)
    segundo_hasta = models.PositiveIntegerField(null=True, blank=True)

    # Propios de la sección, no heredados del elemento: es el punto entero.
    proficiency_level = models.PositiveSmallIntegerField(
        default=1, help_text="Nivel de dominio de ESTA sección"
    )
    notes = models.TextField(blank=True, help_text="Notas de esta sección")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "pk"]
        indexes = [models.Index(fields=["item", "orden"])]
        verbose_name = "Sección"
        verbose_name_plural = "Secciones"

    def __str__(self):
        return f"{self.item_id} · {self.nombre}"

    # === Interfaz de unidad de práctica ===
    # LibraryItem e ItemSection se usan indistintamente al construir sesiones.
    # La clave lleva el tipo delante porque los pk de las dos tablas se pisan:
    # sin eso, el elemento 5 y la sección 5 serían el mismo en cualquier dict.

    @property
    def clave_de_practica(self):
        return ("seccion", self.pk)

    @property
    def user(self):
        return self.item.user

    def get_content_title(self):
        return f"{self.item.get_content_title()} · {self.nombre}"

    def get_content_tags(self):
        """Hereda las etiquetas del elemento: un trozo del blues sigue siendo
        blues, y obligar a re-etiquetar cada sección sería absurdo."""
        return self.item.get_content_tags()

    def get_icon(self):
        return self.item.get_icon()

    @property
    def last_review(self):
        return self.reviews.order_by("-reviewed_at").first()

    @property
    def days_since_last_review(self):
        ultimo = self.last_review
        if ultimo is None:
            return None
        return (timezone.now() - ultimo.reviewed_at).days

    @property
    def rango_paginas(self):
        """`(desde, hasta)` si hay localizador de páginas, si no None."""
        if self.pagina_desde is None:
            return None
        return (self.pagina_desde, self.pagina_hasta or self.pagina_desde)

    @property
    def rango_segundos(self):
        if self.segundo_desde is None:
            return None
        return (self.segundo_desde, self.segundo_hasta)


class SharedNote(models.Model):
    """Nota pública sobre un contenido, visible para todo el que lo estudie.

    Es la contraparte de `LibraryItem.notes`, que es privada de cada usuario.
    Las dos coexisten a propósito y resuelven cosas distintas:

    - `LibraryItem.notes` — mi apunte. Atado al par (usuario, contenido).
    - `SharedNote` — material docente. Atado SOLO al contenido, así que todo el
      que estudie ese vídeo la ve, tenga o no su propia nota.

    Cuelga del contenido vía GenericForeignKey en vez de ser un campo en cada
    modelo: el contenido puede ser Document, Image, Embed, ExternalResource o
    ScorePage, y añadir el campo a cada uno significaría tocar modelos de
    Wagtail que no son nuestros.

    La escribe el profesorado; el alumnado la lee.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    body = models.TextField(
        blank=True,
        verbose_name="Nota",
        help_text="Cómo estudiar este contenido. La ve todo el alumnado.",
    )

    # SET_NULL: que se borre una cuenta no debe llevarse el material docente.
    author = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shared_notes",
        verbose_name="Autor",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Una nota por contenido: es material docente, no un hilo de comentarios.
        unique_together = ["content_type", "object_id"]
        ordering = ["-updated_at"]
        verbose_name = "Nota compartida"
        verbose_name_plural = "Notas compartidas"

    def __str__(self):
        return f"Nota compartida sobre {self.content_type.model} #{self.object_id}"

    @classmethod
    def for_content(cls, content_object):
        """La nota de este contenido, o None. Nunca crea la fila."""
        if content_object is None:
            return None
        return cls.objects.filter(
            content_type=ContentType.objects.get_for_model(content_object),
            object_id=content_object.pk,
        ).first()


class ReviewLog(models.Model):
    """Registro de un repaso: una fila por evento de práctica.

    Es la única fuente de verdad histórica de la biblioteca. `times_viewed` y
    `last_viewed` en LibraryItem son agregados que no se pueden desagregar:
    de eventos se derivan contadores, de contadores no se deriva nada.

    Deliberadamente guarda hechos observados, no predicciones. Sin
    `next_review_date` ni `ease_factor`: cuando exista un planificador, se
    derivará de estas filas en vez de venir precocinado en ellas.

    Las filas se tratan como inmutables — se insertan, no se editan (el admin
    las expone en solo lectura).
    """

    SOURCE_STUDY = "study"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [
        (SOURCE_STUDY, "Sesión de estudio"),
        (SOURCE_MANUAL, "Valoración manual"),
    ]

    # Tope de duración por item. Sin esto, dejar la pestaña abierta toda la
    # noche mete un outlier de 8 horas que envenena cualquier media futura.
    MAX_DURATION_SECONDS = 3600

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="review_logs"
    )
    item = models.ForeignKey(
        LibraryItem, on_delete=models.CASCADE, related_name="reviews"
    )

    # Cuando el repaso fue de una sección concreta. El item se guarda igual,
    # para poder preguntar "¿cuánto he practicado esta pieza?" sumando trozos.
    section = models.ForeignKey(
        "ItemSection",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    reviewed_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Agrupa los repasos de una misma tanda sin necesidad de un modelo Session.
    # Lo genera el cliente al abrir el visor de estudio.
    session_uuid = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Agrupa los repasos de una misma sesión",
    )

    source = models.CharField(
        max_length=16, choices=SOURCE_CHOICES, default=SOURCE_STUDY,
        help_text="Dónde ocurrió el repaso — 'manual' no es práctica real",
    )

    proficiency_before = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Nivel antes de este repaso"
    )
    proficiency_after = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Nivel declarado en este repaso"
    )

    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True, help_text="Tiempo dedicado al item"
    )

    # SET_NULL: borrar un mazo no debe borrar la historia de lo practicado con él.
    deck = models.ForeignKey(
        LibraryDeck, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviews", verbose_name="Mazo de origen",
    )

    class Meta:
        ordering = ["-reviewed_at"]
        indexes = [
            models.Index(fields=["user", "-reviewed_at"]),  # "¿qué practiqué esta semana?"
            models.Index(fields=["item", "-reviewed_at"]),  # último repaso de un item
        ]
        verbose_name = "Repaso"
        verbose_name_plural = "Repasos"

    def __str__(self):
        # Este User no tiene `username` (USERNAME_FIELD = "email")
        return f"{self.user.email} - {self.item_id} @ {self.reviewed_at:%Y-%m-%d %H:%M}"

    @property
    def improved(self):
        """True si el nivel subió en este repaso. None si falta algún extremo."""
        if self.proficiency_before is None or self.proficiency_after is None:
            return None
        return self.proficiency_after > self.proficiency_before

    @classmethod
    def log(
        cls,
        item,
        *,
        section=None,
        source=SOURCE_STUDY,
        proficiency_before=None,
        proficiency_after=None,
        duration_seconds=None,
        session_uuid=None,
        deck=None,
    ):
        """Crea el registro. `user` se deriva del item, nunca se pasa a mano.

        Si se pasa una `section`, el repaso se atribuye a ella; el item se
        guarda igual, para poder sumar "cuánto he practicado esta pieza".
        """
        if duration_seconds is not None:
            duration_seconds = min(int(duration_seconds), cls.MAX_DURATION_SECONDS)

        return cls.objects.create(
            user=item.user,
            item=item,
            section=section,
            source=source,
            proficiency_before=proficiency_before,
            proficiency_after=proficiency_after,
            duration_seconds=duration_seconds,
            session_uuid=session_uuid,
            deck=deck,
        )
