"""Asigna a un grupo los mismos libros que tiene otro, con su configuración.

    manage.py copiar_libros_de_grupo --de 18 --a 17            # ensayo, no escribe
    manage.py copiar_libros_de_grupo --de 18 --a 17 --aplicar

Copia de cada libro la sección de la clase, el modo de avance y si está activo,
y de sus elementos lo que el profesor eligió: si está incluido, su orden y la
casita. NO copia el avance (visto, visto en, notas): eso es del otro grupo.

Un libro que el destino ya tiene se deja como está, para no pisar su avance.
Nació para dar a Raúl los libros de Carmen (2026-09-26).
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clases.models import Group, GroupBook, GroupBookItem


class Command(BaseCommand):
    help = "Asigna a un grupo los libros de otro (sin su avance). Ensayo salvo --aplicar."

    def add_arguments(self, parser):
        parser.add_argument("--de", type=int, required=True, help="pk del grupo origen")
        parser.add_argument("--a", type=int, required=True, help="pk del grupo destino")
        parser.add_argument("--aplicar", action="store_true", help="escribir de verdad")

    def handle(self, *args, **opciones):
        try:
            origen = Group.objects.get(pk=opciones["de"])
            destino = Group.objects.get(pk=opciones["a"])
        except Group.DoesNotExist as e:
            raise CommandError(str(e))
        if origen.pk == destino.pk:
            raise CommandError("Origen y destino son el mismo grupo.")

        aplicar = opciones["aplicar"]
        self.stdout.write(f"{'APLICANDO' if aplicar else 'ENSAYO'}: «{origen.name}» → «{destino.name}»")

        ya = set(destino.books.values_list("libro_id", flat=True))
        copiados = saltados = elementos = 0
        with transaction.atomic():
            for gb in origen.books.select_related("libro").order_by("seccion", "created_at"):
                if gb.libro_id in ya:
                    saltados += 1
                    self.stdout.write(f"  = ya lo tiene: {gb.libro.title}")
                    continue
                filas = list(gb.items.all())
                self.stdout.write(
                    f"  + {gb.libro.title} · {gb.get_seccion_display()} · {gb.get_modo_display()}"
                    f"{'' if gb.activo else ' · inactivo'} · {len(filas)} elementos personalizados"
                )
                copiados += 1
                elementos += len(filas)
                if not aplicar:
                    continue
                nuevo = GroupBook.objects.create(
                    group=destino, libro=gb.libro, seccion=gb.seccion, modo=gb.modo,
                    activo=gb.activo, added_by=gb.added_by,
                )
                GroupBookItem.objects.bulk_create([
                    GroupBookItem(
                        group_book=nuevo, content_type_id=f.content_type_id, object_id=f.object_id,
                        source_page_id=f.source_page_id, orden=f.orden, incluido=f.incluido,
                        a_casa=f.a_casa,
                    )
                    for f in filas
                ])

        self.stdout.write(
            f"{'Copiados' if aplicar else 'Se copiarían'} {copiados} libros "
            f"({elementos} elementos personalizados); {saltados} ya estaban."
        )
