"""Sube ficheros .gp de una carpeta y los engancha a su cancion.

El emparejamiento es por titulo normalizado: Songsterr nombra los ficheros con
el patron "Artista-Titulo-fecha.gp", asi que se busca el titulo de la pagina
dentro del nombre del fichero. Lo que no case con una sola pagina se informa y
no se toca: adjuntar una tablatura a la cancion equivocada es peor que dejarla
sin subir.

Idempotente: si la pagina ya tiene un adjunto con ese mismo fichero, se salta.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from wagtail.documents.models import Document

from cms.models import BlogIndexPage, BlogPage

EXTENSIONES = (".gp", ".gp3", ".gp4", ".gp5", ".gpx")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


class Command(BaseCommand):
    help = "Sube los .gp de una carpeta y los adjunta a su canción por título."

    def add_arguments(self, parser):
        parser.add_argument("carpeta", help="Directorio con los ficheros .gp")
        parser.add_argument("--indice", default="repertorio-luciernaga",
                            help="Slug del índice cuyas páginas se emparejan")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se sube nada"))

        carpeta = Path(options["carpeta"]).expanduser()
        if not carpeta.is_dir():
            self.stderr.write(f"No existe la carpeta {carpeta}")
            return

        indice = BlogIndexPage.objects.filter(slug=options["indice"]).first()
        if indice is None:
            self.stderr.write(f"No encuentro el índice '{options['indice']}'")
            return

        paginas = list(indice.get_children().type(BlogPage).specific())
        ficheros = sorted(f for f in carpeta.iterdir()
                          if f.suffix.lower() in EXTENSIONES)
        self.stdout.write(f"Ficheros: {len(ficheros)} | Canciones: {len(paginas)}")

        sin_pareja, ambiguos, subidos, ya_estaban = [], [], 0, 0

        for fichero in ficheros:
            nombre = normalizar(fichero.stem)
            # El titulo de la pagina tiene que aparecer entero en el nombre del
            # fichero. Asi "Miedo" no se lleva el fichero de "Tengo miedo".
            candidatas = [p for p in paginas if normalizar(p.title) in nombre]
            if not candidatas:
                sin_pareja.append(fichero.name)
                continue
            if len(candidatas) > 1:
                # Con varias, gana el titulo mas largo: "Salir, Beber" antes que
                # "Salir". Si aun asi empatan, no se adivina.
                candidatas.sort(key=lambda p: len(p.title), reverse=True)
                if len(normalizar(candidatas[0].title)) == len(normalizar(candidatas[1].title)):
                    ambiguos.append((fichero.name, [p.title for p in candidatas]))
                    continue

            pagina = candidatas[0]
            # Comparar por nombre de fichero no vale: Wagtail le anade un sufijo
            # al guardarlo si ya existe, asi que la segunda pasada no lo
            # reconocia y duplicaba la tablatura. Lo que se quiere evitar es que
            # una cancion acabe con dos, asi que basta con mirar si ya tiene una.
            ya = any(
                b.block_type == "pdf_score"
                and b.value.get("pdf_file")
                and b.value["pdf_file"].file.name.lower().endswith(EXTENSIONES)
                for b in pagina.attachments
            )
            if ya:
                ya_estaban += 1
                self.stdout.write(f"  = {pagina.title} (ya lo tenía)")
                continue

            self.stdout.write(f"  + {pagina.title}  <-  {fichero.name}")
            if dry_run:
                subidos += 1
                continue

            documento = Document(title=f"{pagina.title} — Guitar Pro")
            with fichero.open("rb") as f:
                documento.file.save(fichero.name, File(f), save=True)

            bloques = list(pagina.attachments.raw_data)
            bloques.append({"type": "pdf_score",
                            "value": {"pdf_file": documento.pk}})
            pagina.attachments = bloques
            pagina.save()
            pagina.save_revision().publish()
            subidos += 1

        verbo = "Se subirían" if dry_run else "Subidos"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verbo} {subidos} | ya estaban {ya_estaban} | sin pareja {len(sin_pareja)} | ambiguos {len(ambiguos)}"
        ))
        for nombre in sin_pareja:
            self.stdout.write(self.style.WARNING(f"  sin pareja: {nombre}"))
        for nombre, titulos in ambiguos:
            self.stdout.write(self.style.WARNING(f"  ambiguo: {nombre} -> {titulos}"))
