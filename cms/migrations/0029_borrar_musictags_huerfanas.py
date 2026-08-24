"""Borra las `MusicTag` que no etiquetan ninguna página.

Son 15 en producción, medidas el 2026-08-24. Restos de etiquetas que en algún
momento se usaron y ya no, o que se crearon y nunca se llegaron a poner.

Va aparte del re-etiquetado a propósito: `migrar_musictags` **no borra nada**,
para que la comprobación de paridad de C35 tuviera una red. Con esa paridad ya
verificada en producción, limpiar lo que no cuelga de nada es seguro.

No toca las que sí etiquetan páginas: el destino del modelo entero es C37b, y
mezclarlo aquí quitaría la red otra vez.
"""

from django.db import migrations


def borrar_huerfanas(apps, schema_editor):
    MusicTag = apps.get_model("cms", "MusicTag")
    BlogPage = apps.get_model("cms", "BlogPage")
    ScorePage = apps.get_model("cms", "ScorePage")
    DictadoPage = apps.get_model("cms", "DictadoPage")
    TestPage = apps.get_model("cms", "TestPage")

    en_uso = set()
    for modelo in (BlogPage, ScorePage, DictadoPage, TestPage):
        en_uso |= set(
            modelo.tags.through.objects.values_list("musictag_id", flat=True)
        )

    MusicTag.objects.exclude(pk__in=en_uso).delete()


def sin_vuelta_atras(apps, schema_editor):
    """No se puede resucitar lo que no colgaba de nada: no queda de dónde
    reconstruir los nombres. La vuelta atrás es la copia del día."""


class Migration(migrations.Migration):
    dependencies = [("cms", "0028_blogpagetag_blogpage_faceted_tags_dictadopagetag_and_more")]

    operations = [migrations.RunPython(borrar_huerfanas, sin_vuelta_atras)]
