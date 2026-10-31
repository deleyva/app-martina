# Fase 89 (2026-10-31, decisión de Jesús: «Quita GroupLibraryItem»).
#
# Borra la tabla `evaluations_grouplibraryitem`: la biblioteca de grupo, que
# guardaba punteros a contenido (páginas, documentos, imágenes), no el
# contenido. Es destructiva e irreversible.
#
# Antes de borrarla, cualquier fila que guarde contenido por `(ContentType,
# object_id)` y apunte a una fila de la biblioteca pasa a apuntar a lo que
# apuntaba esa fila. Sin esto quedaría colgando de una tabla que ya no existe.
# En la copia local no había ninguna; producción no se pudo contar, y por eso
# el paso existe en vez de darlo por hecho.

from django.db import IntegrityError, migrations, transaction

# Los seis modelos con GenericForeignKey del proyecto (rg del 2026-10-31).
CON_CONTENIDO = [
    ("clases", "ClassSessionItem"),
    ("clases", "GroupBookItem"),
    ("my_library", "LibraryItem"),
    ("my_library", "SharedNote"),
    ("programacion", "PlanItem"),
    ("programacion", "ContentCoverage"),
]


def reapuntar_a_su_contenido(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    GroupLibraryItem = apps.get_model("clases", "GroupLibraryItem")

    # Dos tipos con el mismo nombre: el de `evaluations`, de antes del traslado,
    # y el de `clases`. Los dos leen la misma tabla, así que el pk vale igual.
    tipos = list(
        ContentType.objects.filter(model="grouplibraryitem").values_list("pk", flat=True)
    )
    if not tipos:
        return
    destinos = {
        pk: (ct, obj)
        for pk, ct, obj in GroupLibraryItem.objects.values_list(
            "pk", "content_type_id", "object_id"
        )
    }

    for app, nombre in CON_CONTENIDO:
        Modelo = apps.get_model(app, nombre)
        movidas = colgadas = chocan = 0
        for fila in Modelo.objects.filter(content_type_id__in=tipos):
            destino = destinos.get(int(fila.object_id))
            if destino is None:
                colgadas += 1  # ya apuntaba a una fila borrada: no se inventa nada
                continue
            fila.content_type_id, fila.object_id = destino
            try:
                with transaction.atomic():
                    fila.save(update_fields=["content_type", "object_id"])
                movidas += 1
            except IntegrityError:
                chocan += 1  # su dueño ya tiene ese contenido directamente
        if movidas or colgadas or chocan:
            print(
                f"\n  {app}.{nombre}: {movidas} reapuntadas, "
                f"{colgadas} ya colgaban, {chocan} duplicadas que se quedan como estaban"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("clases", "0026_tarjeta_de_respuesta"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("my_library", "0014_fuera_los_mazos"),
        ("programacion", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(reapuntar_a_su_contenido, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="GroupLibraryItem",
        ),
    ]
