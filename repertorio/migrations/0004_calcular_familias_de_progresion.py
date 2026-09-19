"""Rellena `progresion_familia` en lo que ya estaba importado.

Hace falta una migración de datos y no basta con reimportar: el importador solo
escribe las canciones cuyos valores hayan cambiado en origen, y
`progresion_romana` no cambia. Sin esto, el filtro nuevo saldría vacío en
producción hasta que JamZone tocara algo.
"""

from django.db import migrations

from repertorio import progresiones


def calcular(apps, schema_editor):
    Cancion = apps.get_model("repertorio", "Cancion")
    por_guardar = []
    for cancion in Cancion.objects.exclude(progresion_romana="").iterator():
        familia = progresiones.familia(cancion.progresion_romana)[:120]
        if familia != cancion.progresion_familia:
            cancion.progresion_familia = familia
            por_guardar.append(cancion)
    Cancion.objects.bulk_update(por_guardar, ["progresion_familia"], batch_size=200)


def vaciar(apps, schema_editor):
    apps.get_model("repertorio", "Cancion").objects.update(progresion_familia="")


class Migration(migrations.Migration):
    dependencies = [("repertorio", "0003_cancion_progresion_familia")]

    operations = [migrations.RunPython(calcular, vaciar)]
