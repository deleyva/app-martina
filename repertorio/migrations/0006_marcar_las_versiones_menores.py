"""Marca `es_menor` en las versiones ya importadas.

Misma razón que la 0004: el importador solo escribe lo que cambia en origen, y
la tonalidad no cambia. Sin esto, el filtro de modo saldría a cero en
producción.
"""

from django.db import migrations

from repertorio import tonalidades


def marcar(apps, schema_editor):
    Version = apps.get_model("repertorio", "Version")
    menores = [
        v
        for v in Version.objects.exclude(tonalidad="").iterator()
        if tonalidades.es_menor(v.tonalidad) != v.es_menor
    ]
    for v in menores:
        v.es_menor = tonalidades.es_menor(v.tonalidad)
    Version.objects.bulk_update(menores, ["es_menor"], batch_size=200)


def desmarcar(apps, schema_editor):
    apps.get_model("repertorio", "Version").objects.update(es_menor=False)


class Migration(migrations.Migration):
    dependencies = [("repertorio", "0005_version_es_menor_alter_version_tonalidad")]

    operations = [migrations.RunPython(marcar, desmarcar)]
