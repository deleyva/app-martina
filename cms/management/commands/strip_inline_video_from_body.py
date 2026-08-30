"""Saca el <video> crudo del RichTextField `body` de las BlogPage.

`update_qlp_book` inyectaba en su dia un `<div><video><source ...></video></div>`
dentro del body. Wagtail lo guarda y lo pinta sin quejarse, pero el editor
Draftail no sabe cerrar `<source>` y la vista de edicion revienta:

    AssertionError: Unmatched tags: expected source, got video

El video ya existe como bloque `video` del StreamField de adjuntos, y la
plantilla lo pinta encima del body, asi que quitarlo del body no pierde nada.

Limpia tambien la ultima revision: la vista de edicion lee de ahi, no del body
publicado, y sin eso el 500 sigue.
"""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import BlogPage

# El div envoltorio tal cual lo escribia update_qlp_book, y por si acaso un
# <video> suelto sin el div.
VIDEO_PATTERNS = [
    re.compile(r'<div[^>]*>\s*<video\b.*?</video>\s*</div>\s*', re.DOTALL | re.IGNORECASE),
    re.compile(r'<video\b.*?</video>\s*', re.DOTALL | re.IGNORECASE),
]


def strip_video(body: str) -> str:
    for pattern in VIDEO_PATTERNS:
        body = pattern.sub("", body)
    return body.strip()


class Command(BaseCommand):
    help = "Quita el <video> en HTML crudo del body de las BlogPage (arregla el 500 al editar)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se guarda nada"))

        pages = BlogPage.objects.filter(body__contains="<video")
        self.stdout.write(f"Paginas afectadas: {pages.count()}")

        changed = 0
        for page in pages:
            cleaned = strip_video(page.body or "")
            if cleaned == (page.body or ""):
                continue

            self.stdout.write(f"  [{page.pk}] {page.title}")
            changed += 1
            if dry_run:
                continue

            with transaction.atomic():
                page.body = cleaned
                page.save(update_fields=["body"])

                # La vista de edicion lee de la ultima revision.
                revision = page.get_latest_revision()
                if revision:
                    revision.content = page.serializable_data()
                    revision.save(update_fields=["content"])

        verb = "Se limpiarian" if dry_run else "Limpiadas"
        self.stdout.write(self.style.SUCCESS(f"{verb} {changed} paginas."))
