# Fase 98 — tres anillos en la banda. Añade `alumnos`, copia los `bloqueos`
# que hubiera a `alumnos[id].no` y quita la columna vieja.

from django.db import migrations, models


def copiar_bloqueos(apps, schema_editor):
    BandaDeGrupo = apps.get_model("clases", "BandaDeGrupo")
    for banda in BandaDeGrupo.objects.exclude(bloqueos={}):
        alumnos = {}
        for alumno, claves in (banda.bloqueos or {}).items():
            if str(alumno).isdigit() and claves:
                alumnos[str(alumno)] = {"anillo": "rota", "puestos": [], "no": list(claves)}
        banda.alumnos = alumnos
        banda.save(update_fields=["alumnos"])


def devolver_bloqueos(apps, schema_editor):
    BandaDeGrupo = apps.get_model("clases", "BandaDeGrupo")
    for banda in BandaDeGrupo.objects.exclude(alumnos={}):
        banda.bloqueos = {
            a: list(v.get("no", [])) for a, v in (banda.alumnos or {}).items() if v.get("no")
        }
        banda.save(update_fields=["bloqueos"])


class Migration(migrations.Migration):

    dependencies = [
        ("clases", "0029_escaleras_y_peldanos"),
    ]

    operations = [
        migrations.AddField(
            model_name="bandadegrupo",
            name="alumnos",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Anillo de cada alumno (rota, fijo en unos puestos, o fuera) y sus vetos",
            ),
        ),
        migrations.RunPython(copiar_bloqueos, devolver_bloqueos),
        migrations.RemoveField(model_name="bandadegrupo", name="bloqueos"),
    ]
