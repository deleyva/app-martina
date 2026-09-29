"""Devuelve la página de origen a los elementos de las clases duplicadas.

Hasta el 2026-09-29 duplicar una clase no copiaba `source_page`, así que las
copias pintan la tablatura sin el botón de Songsterr y ningún elemento tiene el
de «ver la página entera». El dato no se perdió: sigue en la clase original.

Para cada elemento sin página se buscan sus gemelos —mismo contenido, mismo
grupo— que sí la tengan. Solo se asigna cuando todos apuntan a la MISMA página:
si un contenido llegó a clase desde dos páginas distintas no hay forma de saber
cuál era, y una página equivocada es peor que ninguna.

Uso:
  # Ensayo (por defecto): cuenta, no escribe
  python manage.py recuperar_origen_de_copias

  # Escribir
  python manage.py recuperar_origen_de_copias --aplicar

  # Solo una clase
  python manage.py recuperar_origen_de_copias --session 135
"""

from django.core.management.base import BaseCommand

from clases.models import ClassSessionItem


class Command(BaseCommand):
    help = "Recupera source_page en los elementos de clases duplicadas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribir los cambios. Sin esto solo se cuenta.",
        )
        parser.add_argument(
            "--session",
            type=int,
            help="Solo los elementos de esta clase",
        )

    def handle(self, *args, **options):
        aplicar = options["aplicar"]

        sin_pagina = ClassSessionItem.objects.filter(
            source_page__isnull=True,
        ).select_related("session")
        if options["session"]:
            sin_pagina = sin_pagina.filter(session_id=options["session"])

        recuperados = ambiguos = sin_gemelo = 0
        clases = set()
        for item in sin_pagina:
            paginas = set(
                ClassSessionItem.objects.filter(
                    session__group_id=item.session.group_id,
                    content_type_id=item.content_type_id,
                    object_id=item.object_id,
                    source_page__isnull=False,
                ).values_list("source_page_id", flat=True)
            )
            if not paginas:
                sin_gemelo += 1
                continue
            if len(paginas) > 1:
                ambiguos += 1
                continue

            recuperados += 1
            clases.add(item.session_id)
            if aplicar:
                item.source_page_id = paginas.pop()
                item.save(update_fields=["source_page_id"])

        verbo = "Recuperados" if aplicar else "Se recuperarían"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verbo}: {recuperados} elementos en {len(clases)} clases"
            )
        )
        self.stdout.write(f"Sin gemelo con página (se quedan como están): {sin_gemelo}")
        self.stdout.write(f"Ambiguos, con más de una página posible: {ambiguos}")
        if not aplicar and recuperados:
            self.stdout.write("Ensayo: no se ha escrito nada. Repite con --aplicar.")
