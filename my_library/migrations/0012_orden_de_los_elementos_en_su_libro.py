"""Rellena `orden` en los elementos que ya existen.

Sin esto, todo lo anterior se queda a 0 y la sesion sigue ordenando por pk: los
elementos nuevos, con `orden` de verdad, se irian detras de TODOS los viejos y
el orden del libro saldria peor que antes. La migracion no es opcional.

El orden que se reconstruye es `(path del capitulo, pk)`, que dentro de un libro
por arbol es exactamente el orden del libro: el `path` de treebeard ordena los
capitulos como se ven en el explorador, y dentro de un capitulo el pk es el
orden en que se fue creando el material, que la creacion perezosa recorre en
orden. O sea que reproduce lo que ya habia, pero ahora escrito en un campo en
vez de deducido del pk.
"""

from django.db import migrations


def rellenar(apps, schema_editor):
    from wagtail.models import Page  # solo por `steplen`, no se consulta nada

    LibraryItem = apps.get_model("my_library", "LibraryItem")

    filas = (
        LibraryItem.objects.exclude(source_page__isnull=True)
        .values_list("pk", "user_id", "source_page__path")
        .order_by("source_page__path", "pk")
    )

    # El contador va por (usuario, libro): dos usuarios con el mismo libro
    # tienen cada uno su cola, y compartir contador les dejaria huecos.
    contador = {}
    for pk, user_id, path in filas:
        clave = (user_id, path[: -Page.steplen] or None)
        n = contador.get(clave, 0)
        contador[clave] = n + 1
        LibraryItem.objects.filter(pk=pk).update(orden=n)


def vaciar(apps, schema_editor):
    apps.get_model("my_library", "LibraryItem").objects.update(orden=0)


class Migration(migrations.Migration):

    dependencies = [
        ("my_library", "0011_libraryitem_libro_libraryitem_orden"),
    ]

    operations = [
        migrations.RunPython(rellenar, vaciar),
    ]
