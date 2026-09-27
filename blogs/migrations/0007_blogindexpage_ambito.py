# Fase 52·1 — menú en dos niveles: cada departamento tiene un ámbito.
#
# El reparto inicial se hace por el nombre del departamento, sin acentos ni
# mayúsculas, para no depender del slug. Lo que no case queda en «centro», que
# es el valor por defecto, y todo es editable después desde el CMS.

import unicodedata

from django.db import migrations, models

REPARTO = {
    "ciencias": [
        "biologia y geologia",
        "fisica y quimica",
        "matematicas",
        "tecnologia",
    ],
    "humanidades": [
        "cultura clasica",
        "economia",
        "filosofia",
        "geografia e historia",
        "lengua y literatura",
    ],
    "lenguas": ["aleman", "frances", "ingles"],
    "artes": ["educacion fisica", "educacion plastica y visual", "musica"],
    "fp": ["cofotap", "instalaciones electrotecnicas"],
    "centro": ["actividades extraescolares", "orientacion"],
}


def _normaliza(texto):
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore")
    return " ".join(sin_acentos.decode().lower().split())


def repartir(apps, schema_editor):
    BlogIndexPage = apps.get_model("blogs", "BlogIndexPage")
    ambito_por_nombre = {
        nombre: clave for clave, nombres in REPARTO.items() for nombre in nombres
    }
    for pagina in BlogIndexPage.objects.all():
        clave = ambito_por_nombre.get(_normaliza(pagina.title))
        if clave and pagina.ambito != clave:
            pagina.ambito = clave
            pagina.save(update_fields=["ambito"])


class Migration(migrations.Migration):

    dependencies = [
        ("blogs", "0006_articulopage_adjuntos_sin_musica"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogindexpage",
            name="ambito",
            field=models.CharField(
                choices=[
                    ("ciencias", "Ciencias"),
                    ("humanidades", "Humanidades"),
                    ("lenguas", "Lenguas"),
                    ("artes", "Artes y deporte"),
                    ("fp", "Formación Profesional"),
                    ("centro", "Centro"),
                ],
                default="centro",
                help_text="Bajo qué ámbito aparece este departamento en el menú del sitio.",
                max_length=20,
                verbose_name="Ámbito",
            ),
        ),
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
