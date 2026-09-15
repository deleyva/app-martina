"""En qué lengua está escrito cada recurso — medido, no supuesto.

El campo `RecursoPage.idioma` nace con `es` por defecto, y los artículos que ya
había estaban escritos en inglés. Rellenarlo en una migración habría sido
adivinar en silencio sobre 238 páginas; esto lo mide y enseña la lista antes de
escribir nada. Escribir es un segundo paso explícito: `--aplicar`.

La medida son palabras vacías. No hace falta nada más para separar castellano
de inglés en textos de varios párrafos: son las palabras más frecuentes de cada
lengua, no se traducen entre sí, y ninguna es término musical. Un texto corto o
mezclado sale como `duda` y se queda sin tocar.
"""

import re

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from musica.models import RecursoPage

# Palabras vacías que no comparten forma entre las dos lenguas. Fuera quedan a
# propósito las que existen en ambas ("no", "a", "me", "son", "un"): sumarían
# ruido a los dos lados y no desempatan nada.
VACIAS_ES = {
    "el", "la", "los", "las", "de", "del", "que", "y", "en", "es", "se", "con",
    "por", "para", "una", "uno", "como", "más", "pero", "su", "sus", "al", "lo",
    "esta", "este", "esto", "ese", "esa", "cuando", "donde", "porque", "también",
}
VACIAS_EN = {
    "the", "of", "and", "to", "in", "is", "it", "that", "for", "with", "as",
    "was", "but", "they", "this", "these", "from", "you", "your", "are", "were",
    "which", "there", "their", "what", "when", "how", "about",
}

# Por debajo de esto no hay texto suficiente para afirmar nada.
MINIMO_SENALES = 8
# Una lengua gana si dobla a la otra. Con menos, es `duda`.
VENTAJA = 2.0


def contar(texto):
    """Cuántas señales hay de cada lengua en un texto."""
    palabras = re.findall(r"[a-záéíóúüñ]+", strip_tags(texto or "").lower())
    es = sum(1 for p in palabras if p in VACIAS_ES)
    en = sum(1 for p in palabras if p in VACIAS_EN)
    return es, en


def clasificar(texto):
    """`("es"|"en"|"duda", señales_es, señales_en)`."""
    es, en = contar(texto)
    if es + en < MINIMO_SENALES:
        return "duda", es, en
    if es >= en * VENTAJA:
        return "es", es, en
    if en >= es * VENTAJA:
        return "en", es, en
    return "duda", es, en


class Command(BaseCommand):
    help = "Mide en qué lengua está cada RecursoPage. Con --aplicar, lo escribe."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe el campo `idioma` en las páginas donde la medida es clara",
        )

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        cambios, iguales, dudas = [], 0, []

        for page in RecursoPage.objects.all().order_by("path"):
            veredicto, señales_es, señales_en = clasificar(
                f"{page.intro} {page.body}"
            )
            if veredicto == "duda":
                dudas.append((page, señales_es, señales_en))
            elif veredicto == page.idioma:
                iguales += 1
            else:
                cambios.append((page, veredicto, señales_es, señales_en))

        self.stdout.write(f"Recursos analizados: {RecursoPage.objects.count()}")
        self.stdout.write(f"  Ya correctos: {iguales}")
        self.stdout.write(f"  Sin texto suficiente (no se tocan): {len(dudas)}")
        self.stdout.write(f"  Habría que cambiar: {len(cambios)}")

        for page, veredicto, señales_es, señales_en in cambios:
            self.stdout.write(
                f"  [{page.id}] {page.title[:60]}: "
                f"{page.idioma} → {veredicto}  (es={señales_es} en={señales_en})"
            )

        if not aplicar:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo se ha escrito nada. Repite con --aplicar cuando la "
                    "lista te cuadre."
                )
            )
            return

        con_borrador = []
        for page, veredicto, _, _ in cambios:
            page.idioma = veredicto
            # Se escribe la página viva, no una revisión: es un dato de
            # catalogación, no una edición del texto. El precio está abajo.
            page.save(update_fields=["idioma"])
            if page.has_unpublished_changes:
                con_borrador.append(page)

        self.stdout.write(
            self.style.SUCCESS(f"\nEscritas {len(cambios)} páginas.")
        )
        if con_borrador:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(con_borrador)} tienen un borrador sin publicar, y ese "
                    "borrador guarda la lengua antigua: al publicarlo volverá "
                    "atrás. Revísalas en Wagtail:"
                )
            )
            for page in con_borrador:
                self.stdout.write(f"  [{page.id}] {page.title[:60]}")
