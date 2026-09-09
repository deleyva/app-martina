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

from collections import Counter, defaultdict

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from my_library.libros import material_del_libro
from my_library.models import LibraryItem


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
            libro = self._libro_de(item)
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

    def _libro_de(self, item):
        """El libro al que pertenece un elemento, o `None` si es material suelto."""
        if item.libro_id:  # libro por referencia: lo lleva escrito
            return item.libro.specific
        if item.source_page_id:  # libro por árbol: es el padre del capítulo
            padre = item.source_page.get_parent()
            return padre.specific if padre else None
        return None

    def _recolocar(self, libro, items, aplicar):
        """Asigna a cada elemento su índice en el material actual del libro."""
        posiciones = {}
        for indice, (_capitulo, objeto) in enumerate(material_del_libro(libro)):
            tipo = ContentType.objects.get_for_model(objeto)
            posiciones[(tipo.pk, objeto.pk)] = indice

        antes = Counter(it.orden for it in items)
        repetidos_antes = sum(1 for n in antes.values() if n > 1)

        cambios = huerfanos = 0
        for item in items:
            nuevo = posiciones.get((item.content_type_id, item.object_id))
            if nuevo is None:
                # Estaba en el libro cuando se creó y ya no está. No se toca: su
                # historial de práctica sigue siendo válido y borrarlo o moverlo
                # sería peor que dejarlo donde está.
                huerfanos += 1
                continue
            if item.orden != nuevo:
                cambios += 1
                if aplicar:
                    LibraryItem.objects.filter(pk=item.pk).update(orden=nuevo)

        etiqueta = libro.title[:44]
        self.stdout.write(
            f"  {etiqueta:46} {len(items):3} items · "
            f"{repetidos_antes} ordinales repetidos antes · "
            f"{cambios} a cambiar · {huerfanos} fuera del libro"
        )
        return cambios, huerfanos
