"""Adjuntos de una página de contenido: PDF/Guitar Pro, audio, imagen, vídeo, enlace.

Lo comparten `blogs.ArticuloPage` y `musica.RecursoPage`. Es lo único que las dos
tenían realmente en común de la antigua `BlogPage`: un artículo de departamento y
una canción de la biblioteca adjuntan archivos de la misma manera. Todo lo demás
—la ficha musical— se quedó en el lado de música, que es de lo que iba la fase 25.

Un gesto por elemento: el editor elige el tipo de bloque y suelta el archivo.
"""

from wagtail.blocks import CharBlock, StructBlock, TextBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock


def adjuntos_field():
    """El StreamField de adjuntos. Función y no constante porque cada modelo
    necesita su propia instancia del campo."""
    return StreamField(
        [
            ("pdf_score", StructBlock([
                ("pdf_file", DocumentChooserBlock(
                    help_text="Seleccionar un PDF o un archivo Guitar Pro (.gp, .gp3, .gp4, .gp5, .gpx)"
                )),
            ], icon="doc-full-inverse", label="PDF / Guitar Pro")),
            ("audio", StructBlock([
                ("audio_file", DocumentChooserBlock(help_text="Seleccionar archivo audio")),
            ], icon="media", label="Audio")),
            ("image", StructBlock([
                ("image", ImageChooserBlock(help_text="Seleccionar imagen")),
                ("caption", TextBlock(required=False, help_text="Descripción opcional")),
            ], icon="image", label="Imagen")),
            ("video", StructBlock([
                ("video_file", DocumentChooserBlock(help_text="Seleccionar vídeo (máx. 10 MB)")),
            ], icon="media", label="Vídeo")),
            ("external_link", StructBlock([
                ("resource", SnippetChooserBlock("cms.ExternalResource")),
                ("override_title", CharBlock(required=False, help_text="Título alternativo (opcional)")),
            ], icon="link", label="Enlace")),
        ],
        blank=True,
        use_json_field=True,
        verbose_name="Archivos adjuntos",
        help_text="Archivos que se muestran como cards con descarga, visor y botón de librería",
    )


class AdjuntosMixin:
    """Lectura de `attachments` por tipo de bloque, cacheada por instancia.

    El StreamField se deserializa una vez: en un listado de 200 capítulos, hacerlo
    por cada acceso se nota.
    """

    def _parse_attachments(self):
        if not hasattr(self, "_attachments_cache"):
            pdfs, audios, images, videos, external_links = [], [], [], [], []
            for block in self.attachments:
                if block.block_type == "pdf_score":
                    pdfs.append(block.value)
                elif block.block_type == "audio":
                    audios.append(block.value)
                elif block.block_type == "image":
                    images.append(block.value)
                elif block.block_type == "video":
                    videos.append(block.value)
                elif block.block_type == "external_link":
                    external_links.append(block.value)
            self._attachments_cache = {
                "pdfs": pdfs, "audios": audios, "images": images,
                "videos": videos, "external_links": external_links,
            }
        return self._attachments_cache

    def get_pdf_blocks(self):
        return self._parse_attachments()["pdfs"]

    def get_audios(self):
        return self._parse_attachments()["audios"]

    def get_videos(self):
        return self._parse_attachments()["videos"]

    def get_external_links(self):
        return self._parse_attachments()["external_links"]

    def get_images(self):
        """Imágenes de los adjuntos más las incrustadas en el cuerpo."""
        images = [
            sv["image"] for sv in self._parse_attachments()["images"] if sv.get("image")
        ]

        if self.body and '<embed embedtype="image"' in self.body:
            from bs4 import BeautifulSoup
            from wagtail.images import get_image_model

            Image = get_image_model()
            soup = BeautifulSoup(self.body, "html.parser")
            image_ids = [
                tag.get("id")
                for tag in soup.find_all("embed", embedtype="image")
                if tag.get("id")
            ]
            if image_ids:
                db_images = {
                    str(img.pk): img for img in Image.objects.filter(pk__in=image_ids)
                }
                images.extend(
                    db_images.get(i) for i in image_ids if db_images.get(i)
                )
        return images

    def get_embeds(self):
        """URLs de embeds incrustados en el cuerpo."""
        from bs4 import BeautifulSoup

        if not self.body:
            return []

        soup = BeautifulSoup(self.body, "html.parser")

        class DummyEmbedValue:
            def __init__(self, url):
                self.url = url

        return [
            DummyEmbedValue(tag.get("url"))
            for tag in soup.find_all("embed", embedtype="media")
            if tag.get("url")
        ]
