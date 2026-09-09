"""Reasigna `LibraryItem.orden` desde el orden ACTUAL del libro.

**Por qué hace falta.** `siguiente_del_objetivo` guarda el ordinal como una foto
del momento de crear: es barato y para el uso normal es correcto, porque montas
el libro y luego lo estudias. Pero si el libro crece entre creaciones, los
elementos viejos se quedan con índices de un libro más corto y los nuevos
reciben índices del largo. Resultado: ordinales repetidos, y el material deja de
servirse en el orden del libro.

Medido en producción el 2026-09-09: cuatro grupos con ordinales pisados, el peor
CAGED con 10 repetidos sobre 45 elementos. Y algunos a 0, que son los anteriores
a que el campo existiera (fase 21) y se van todos al principio.

**Este comando es la contrapartida de esa decisión**, no su enmienda: la foto
sigue siendo lo correcto al crear, y esto se pasa cuando un libro ha cambiado.

    just production-command recalcular_orden --email <correo>
    just production-command recalcular_orden --email <correo> --aplicar

Sin `--aplicar` no escribe nada: enseña qué cambiaría y se va.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand

from my_library.models import LibraryItem
from my_library.orden import libro_de, recolocar


class Command(BaseCommand):
    help = "Reasigna el orden de los elementos según el orden actual de su libro"

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Solo este usuario; si falta, todos")
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe los cambios. Sin esto solo informa.",
        )

    def handle(self, *args, **opciones):
        items = LibraryItem.objects.select_related(
            "user", "source_page", "libro", "content_type"
        )
        if opciones["email"]:
            items = items.filter(user__email=opciones["email"])

        # Agrupar por (usuario, libro). El libro se saca del padre en el árbol o
        # de la FK en los libros por referencia, que es la misma regla que usa
        # `session._libro_de` para decidir de qué libro es un elemento.
        grupos = defaultdict(list)
        for item in items:
            libro = libro_de(item)
            if libro is not None:
                grupos[(item.user_id, libro.pk)].append((libro, item))

        total_cambios = total_huerfanos = 0
        for (user_id, _pk), pares in sorted(grupos.items()):
            libro = pares[0][0]
            del_grupo = [it for _lb, it in pares]
            cambios, huerfanos = self._recolocar(
                libro, del_grupo, aplicar=opciones["aplicar"]
            )
            total_cambios += cambios
            total_huerfanos += huerfanos

        verbo = "cambiados" if opciones["aplicar"] else "se cambiarían"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{total_cambios} ordinales {verbo} · "
                f"{total_huerfanos} elemento(s) ya no están en su libro"
            )
        )
        if not opciones["aplicar"] and total_cambios:
            self.stdout.write("Vuelve a lanzarlo con --aplicar para escribirlo.")

    def _recolocar(self, libro, items, aplicar):
        """Delega en `my_library.orden`, que es donde vive la única versión."""
        cambios, huerfanos, repetidos_antes = recolocar(libro, items, aplicar=aplicar)
        self.stdout.write(
            f"  {libro.title[:44]:46} {len(items):3} items · "
            f"{repetidos_antes} ordinales repetidos antes · "
            f"{cambios} a cambiar · {huerfanos} fuera del libro"
        )
        return cambios, huerfanos
