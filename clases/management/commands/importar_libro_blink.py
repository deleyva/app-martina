"""Monta en la biblioteca los libros de Blink Learning como libros de ENLACES.

No importa material: crea un `LibroPage` por libro, un `RecursoPage` por unidad
y un `EnlaceExterno` por unidad apuntando a su enlace profundo en Blink. El
contenido se queda en Blink, bajo la licencia del centro.

    python manage.py importar_libro_blink
    python manage.py importar_libro_blink --dry-run
    python manage.py importar_libro_blink --datos otro_indice.json

Idempotente: se apoya en `get_or_create` por slug y en la unicidad de
(capítulo, url), así que volver a pasarlo actualiza títulos y no duplica nada.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from musica.models import (
    EnlaceExterno,
    LibroPage,
    MusicLibraryIndexPage,
    RecursoPage,
)

DATOS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "data" / "blink_awos_a.json"


class Command(BaseCommand):
    help = "Crea los libros de enlaces de Blink Learning en la biblioteca musical"

    def add_arguments(self, parser):
        parser.add_argument(
            "--datos",
            default=str(DATOS_POR_DEFECTO),
            help="JSON con el índice cosechado de Blink",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Dice lo que haría y no toca la base de datos",
        )

    def handle(self, *args, **opciones):
        ruta = Path(opciones["datos"])
        if not ruta.exists():
            raise CommandError(f"No encuentro el índice: {ruta}")
        indice = json.loads(ruta.read_text())

        raiz = MusicLibraryIndexPage.objects.live().first()
        if raiz is None:
            raise CommandError(
                "No hay MusicLibraryIndexPage: la biblioteca musical no existe todavía"
            )

        base = indice["base"]
        seco = opciones["dry_run"]

        with transaction.atomic():
            for datos_libro in indice["libros"]:
                self._un_libro(raiz, base, datos_libro, seco)
            if seco:
                self.stdout.write(self.style.WARNING("\n--dry-run: deshaciendo"))
                transaction.set_rollback(True)

    def _un_libro(self, raiz, base, datos, seco):
        slug = datos["clave"]
        libro = LibroPage.objects.child_of(raiz).filter(slug=slug).first()
        if libro is None:
            libro = LibroPage(
                title=datos["titulo"],
                slug=slug,
                intro=(
                    "Libro de enlaces. El material vive en Blink Learning bajo la "
                    "licencia del centro; aquí solo están los enlaces a cada unidad."
                ),
            )
            raiz.add_child(instance=libro)
            libro.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"📗 Libro creado: {libro.title}"))
        else:
            self.stdout.write(f"📗 Libro ya estaba: {libro.title}")

        creados = actualizados = 0
        for unidad in datos["unidades"]:
            url = f"{base}#activity/{datos['book_id']}/{unidad['unidad']}/{unidad['actividad']}"
            # El número va delante del slug para que el orden de árbol de
            # Wagtail (`path`) coincida con el orden del libro sin tener que
            # arrastrar nada a mano en el explorador.
            slug_cap = slugify(f"{unidad['n']:02d}-{unidad['titulo']}")[:255]
            capitulo = RecursoPage.objects.child_of(libro).filter(slug=slug_cap).first()
            if capitulo is None:
                capitulo = RecursoPage(
                    title=unidad["titulo"],
                    slug=slug_cap,
                    date=timezone.now().date(),
                    intro=f"Unidad {unidad['n']} — se abre en Blink Learning",
                )
                libro.add_child(instance=capitulo)
                capitulo.save_revision().publish()
                creados += 1
            else:
                actualizados += 1

            EnlaceExterno.objects.update_or_create(
                source_page=capitulo,
                url=url,
                defaults={
                    "titulo": unidad["titulo"],
                    "proveedor": EnlaceExterno.BLINK,
                    "orden": unidad["n"],
                },
            )

        self.stdout.write(
            f"   capítulos: {creados} creados, {actualizados} ya estaban "
            f"· {len(datos['unidades'])} enlaces al día"
        )
