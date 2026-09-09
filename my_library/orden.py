"""El ordinal de un elemento dentro de su libro.

`LibraryItem.orden` es el índice del material en la secuencia completa del libro,
y `siguiente_del_objetivo` lo guarda como **una foto del momento de crear**: es
barato y para el uso normal es correcto, porque montas el libro y luego lo
estudias.

El problema aparece cuando el libro cambia después. Los elementos viejos se
quedan con índices de un libro más corto y los nuevos reciben los del largo, así
que los ordinales chocan y el material deja de servirse en el orden del libro.
Medido en producción el 2026-09-09: cuatro grupos afectados, el peor CAGED con 10
ordinales repetidos sobre 45 elementos.

Aquí vive **la única implementación** del recálculo. La usan la tarea que
dispara la señal y el comando `recalcular_orden`, y eso es a propósito: dos
copias de esta lógica acabarían discrepando, y la discrepancia sería exactamente
el defecto que esto arregla.
"""

import logging
from collections import Counter

from django.contrib.contenttypes.models import ContentType

from my_library.libros import material_del_libro
from my_library.models import LibraryItem

logger = logging.getLogger(__name__)


def libro_de(item):
    """El libro al que pertenece un elemento, o `None` si es material suelto.

    Misma regla que `session._libro_de`: los libros por referencia lo llevan
    escrito en la FK, y los de árbol son el padre del capítulo.
    """
    if item.libro_id:
        return item.libro.specific
    if item.source_page_id:
        padre = item.source_page.get_parent()
        return padre.specific if padre else None
    return None


def recolocar(libro, items, aplicar=True):
    """Reasigna el ordinal de `items` según el material ACTUAL de `libro`.

    Devuelve `(cambios, huerfanos, repetidos_antes)`. Con `aplicar=False` cuenta
    lo que haría y no escribe, que es lo que permite mirar antes de decidir.

    Un elemento que ya no está en el libro **no se toca**: su historial de
    práctica sigue siendo válido, y moverlo o borrarlo sería peor que dejarlo
    donde está.
    """
    posiciones = {}
    for indice, (_capitulo, objeto) in enumerate(material_del_libro(libro)):
        tipo = ContentType.objects.get_for_model(objeto)
        posiciones[(tipo.pk, objeto.pk)] = indice

    cuenta = Counter(it.orden for it in items)
    repetidos_antes = sum(1 for n in cuenta.values() if n > 1)

    cambios = huerfanos = 0
    for item in items:
        nuevo = posiciones.get((item.content_type_id, item.object_id))
        if nuevo is None:
            huerfanos += 1
            continue
        if item.orden != nuevo:
            cambios += 1
            if aplicar:
                LibraryItem.objects.filter(pk=item.pk).update(orden=nuevo)

    return cambios, huerfanos, repetidos_antes


def recolocar_libro_para_todos(libro):
    """Recalcula ese libro para TODOS los usuarios que tengan material suyo.

    El orden es una propiedad del libro, no de quien lo estudia: si el libro
    cambia, cambia para todos. Se agrupa por usuario porque `LibraryItem` es de
    un usuario y la unicidad va por (usuario, tipo, objeto).

    Devuelve `{email: cambios}` de los usuarios a los que se les movió algo.
    """
    from collections import defaultdict

    por_usuario = defaultdict(list)
    for item in LibraryItem.objects.select_related(
        "user", "source_page", "libro", "content_type"
    ):
        suyo = libro_de(item)
        if suyo is not None and suyo.pk == libro.pk:
            por_usuario[item.user].append(item)

    if not por_usuario:
        return {}

    tocados = {}
    for usuario, items in por_usuario.items():
        cambios, _huerfanos, _antes = recolocar(libro, items, aplicar=True)
        if cambios:
            tocados[usuario.email] = cambios
    return tocados
