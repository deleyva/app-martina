"""Mete el repertorio de Luciernaga en un indice propio y privado.

Las 31 canciones colgaban sueltas del Indice de recursos musicales, cada una con
su `is_private` marcado a mano. Eso funciona pero no se hereda: la cancion 32
nace publica salvo que alguien se acuerde de marcarla.

`LibroDeEstudioPage` no sirve de padre a proposito: guarda referencias, no
hijos, para que una cancion pueda estar en varios libros a la vez. Asi que el
sitio donde viven es un `BlogIndexPage` privado, y el libro las sigue
referenciando por pk para estudiarlas. Las dos cosas conviven.

Mover cambia la URL de las 31. Las redirecciones NO se crean aqui: Wagtail 7
las genera solas en `Page.move()` (WAGTAILREDIRECTS_AUTO_CREATE, por defecto
activo). Crearlas a mano ademas dejaba dos filas identicas por pagina.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Page

from cms.models import BlogIndexPage, BlogPage

SLUG_INDICE_MUSICAL = "indice-de-recursos-musicales"
SLUG_DESTINO = "repertorio-luciernaga"
TITULO_DESTINO = "Repertorio Luciérnaga"
MARCA = "uciérnaga"


class Command(BaseCommand):
    help = "Crea un indice privado 'Repertorio Luciérnaga' y mueve alli sus canciones."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se guarda nada"))

        indice = Page.objects.filter(slug=SLUG_INDICE_MUSICAL).first()
        if indice is None:
            self.stderr.write("No encuentro el Índice de recursos musicales.")
            return

        # La marca esta en la intro de las 31, y solo en ellas. Se comprueba
        # contra las hijas DIRECTAS: una vez movidas, dejan de estarlo, asi que
        # volver a lanzar el comando no arrastra nada.
        canciones = [
            p
            for p in indice.get_children().type(BlogPage).specific().order_by("title")
            if MARCA in (p.intro or "")
        ]
        self.stdout.write(f"Canciones a mover: {len(canciones)}")
        if not canciones:
            self.stdout.write(self.style.SUCCESS("Nada que hacer."))
            return

        destino = (
            BlogIndexPage.objects.child_of(indice).filter(slug=SLUG_DESTINO).first()
        )
        if destino is None:
            self.stdout.write(f"Creando índice destino '{TITULO_DESTINO}'")
            if not dry_run:
                # El owner importa: `_check_page_visibility` trata una pagina
                # privada SIN dueño como visible solo para superusuarios, asi
                # que se hereda el de las canciones.
                destino = BlogIndexPage(
                    title=TITULO_DESTINO,
                    slug=SLUG_DESTINO,
                    intro="Repertorio de El Grupo Luciérnaga.",
                    is_private=True,
                    owner=canciones[0].owner,
                )
                indice.add_child(instance=destino)
                destino.save_revision().publish()
        else:
            self.stdout.write(f"El índice destino ya existe (pk={destino.pk})")
            if not dry_run and not destino.is_private:
                destino.is_private = True
                destino.save()
                destino.save_revision().publish()
                self.stdout.write("  marcado como privado")

        for pagina in canciones:
            self.stdout.write(f"  [{pagina.pk}] {pagina.title}")
            if dry_run:
                continue
            with transaction.atomic():
                pagina.move(destino, pos="last-child")

        verbo = "Se moverían" if dry_run else "Movidas"
        self.stdout.write(self.style.SUCCESS(f"{verbo} {len(canciones)} páginas."))
