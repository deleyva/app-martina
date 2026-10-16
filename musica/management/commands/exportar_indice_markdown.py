"""Vuelca el índice de recursos musicales a un solo fichero Markdown.

Para subirlo como Knowledge a un GPT de ChatGPT (fase 77): un GPT no vuelve a
leer una URL en cada conversación, así que se le da el índice entero.

**No escribe nada en la base de datos.** El resumen va por stderr para que la
salida se pueda redirigir a un fichero sin ensuciarla.

    just exportar-indice                      # local → exports/
    just exportar-indice-produccion           # producción → exports/
    python manage.py exportar_indice_markdown --salida /tmp/indice.md
"""

from django.core.management.base import BaseCommand, CommandError

from musica.exportacion import exportar_indice
from musica.models import MusicLibraryIndexPage


class Command(BaseCommand):
    help = "Vuelca el índice de recursos musicales a Markdown. Solo lectura."

    def add_arguments(self, parser):
        parser.add_argument(
            "--salida",
            default=None,
            help="Fichero de destino. Si no se da, el Markdown sale por stdout.",
        )
        parser.add_argument(
            "--indice",
            default=None,
            help="pk o slug del índice. Si solo hay uno, no hace falta.",
        )
        parser.add_argument(
            "--incluir-privadas",
            action="store_true",
            help="Incluir también las páginas marcadas como privadas.",
        )
        parser.add_argument(
            "--solo-canciones",
            action="store_true",
            help="Solo recursos con ficha musical o letra con acordes.",
        )

    def _indice(self, clave):
        indices = MusicLibraryIndexPage.objects.live()
        if clave:
            indice = (
                indices.filter(pk=clave).first() if str(clave).isdigit() else None
            ) or indices.filter(slug=clave).first()
            if indice is None:
                raise CommandError(f"No hay ningún índice publicado con pk o slug «{clave}».")
            return indice
        if indices.count() == 1:
            return indices.get()
        if not indices.exists():
            raise CommandError("No hay ningún índice de recursos musicales publicado.")
        opciones = ", ".join(f"{i.pk} ({i.slug})" for i in indices)
        raise CommandError(f"Hay varios índices; elige uno con --indice: {opciones}")

    def handle(self, *args, **options):
        indice = self._indice(options["indice"])
        markdown, recuentos = exportar_indice(
            indice,
            incluir_privadas=options["incluir_privadas"],
            solo_canciones=options["solo_canciones"],
        )

        if options["salida"]:
            with open(options["salida"], "w", encoding="utf-8") as fichero:
                fichero.write(markdown)
            destino = options["salida"]
        else:
            self.stdout.write(markdown, ending="")
            destino = "stdout"

        total = sum(recuentos.values())
        detalle = ", ".join(f"{n} {t}" for t, n in sorted(recuentos.items())) or "nada"
        self.stderr.write(
            f"{indice.title}: {total} páginas ({detalle}), "
            f"{len(markdown.encode('utf-8')) / 1024:.0f} KB → {destino}"
        )
