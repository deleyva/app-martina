"""Rellena la huella (`file_hash`) de las imágenes y documentos que no la tienen.

    just manage rellenar_huellas              # solo cuenta lo que falta
    just manage rellenar_huellas --ejecutar   # la calcula y la guarda

**Por qué hace falta (fase 104).** La creación perezosa se salta las copias
exactas de lo que ya tienes, y eso lo decide la huella. Wagtail solo la
calcula al subir por su admin; las imágenes creadas por código
(`import_book_chapter`, los publicadores) la dejaban vacía: el 2026-11-07, las
302 del libro de CAGED. La sesión la calcula sola cuando le falta, así que esto
no cambia ningún resultado: adelanta el trabajo para que la primera sesión no
tenga que leer cientos de ficheros de golpe.

Solo escribe la columna `file_hash`. La clave de caché de las renditions lleva
la huella, así que cada imagen tocada estrena entrada de caché una vez; la
rendition guardada en la base sigue sirviendo.
"""

from django.core.management.base import BaseCommand
from wagtail.documents import get_document_model
from wagtail.images import get_image_model


class Command(BaseCommand):
    help = "Calcula y guarda file_hash en imágenes y documentos que no lo tienen"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Sin esto solo cuenta; con esto calcula y guarda la huella",
        )

    def handle(self, *args, **opciones):
        ejecutar = opciones["ejecutar"]
        for modelo in (get_image_model(), get_document_model()):
            pendientes = modelo.objects.filter(file_hash="")
            total = pendientes.count()
            nombre = modelo._meta.verbose_name_plural
            if not ejecutar:
                self.stdout.write(f"{nombre}: {total} sin huella")
                continue
            hechas = fallidas = 0
            for objeto in pendientes.iterator():
                try:
                    objeto.get_file_hash()
                    hechas += 1
                except (OSError, ValueError) as error:
                    fallidas += 1
                    self.stderr.write(f"  {modelo.__name__} {objeto.pk}: {error}")
            self.stdout.write(
                f"{nombre}: {hechas} con huella nueva, {fallidas} sin fichero legible"
            )
