# Fase 97 (2026-11-02): NT+ = 8,5 en la escala del curso.
#
# Dos cosas: la letra del cuaderno pasa a caber tres caracteres, y los
# instrumentos que ya calificaban con SB · NT · BI · SU · IN reciben NT+ entre
# SB y NT. Las notas no se tocan: 8,5 es un valor nuevo que no choca con nada,
# y las de antes siguen leyéndose por su valor exacto.

from django.db import migrations, models

ANTIGUA = ["SB", "NT", "BI", "SU", "IN"]
NT_MAS = {"etiqueta": "NT+", "valor": 8.5}


def _etiquetas(instrumento):
    return [str(o.get("etiqueta", "")).strip().upper() for o in (instrumento.opciones or [])]


def anadir_nt_mas(apps, schema_editor):
    Instrumento = apps.get_model("calificaciones", "Instrumento")
    for instrumento in Instrumento.objects.filter(escala="opciones"):
        if _etiquetas(instrumento) == ANTIGUA:
            instrumento.opciones = [instrumento.opciones[0], dict(NT_MAS), *instrumento.opciones[1:]]
            instrumento.save(update_fields=["opciones"])


def quitar_nt_mas(apps, schema_editor):
    Instrumento = apps.get_model("calificaciones", "Instrumento")
    for instrumento in Instrumento.objects.filter(escala="opciones"):
        if _etiquetas(instrumento) == ["SB", "NT+", *ANTIGUA[1:]]:
            instrumento.opciones = [o for o in instrumento.opciones if str(o.get("etiqueta", "")).strip().upper() != "NT+"]
            instrumento.save(update_fields=["opciones"])


class Migration(migrations.Migration):

    dependencies = [
        ("calificaciones", "0007_revision_cuaderno"),
    ]

    operations = [
        migrations.AlterField(
            model_name="revisioncuaderno",
            name="letra",
            field=models.CharField(
                blank=True,
                choices=[("SB", "SB"), ("NT+", "NT+"), ("NT", "NT"), ("BI", "BI"), ("SU", "SU"), ("IN", "IN")],
                help_text="Vacía = sorteado y pendiente de mirar",
                max_length=3,
            ),
        ),
        migrations.RunPython(anadir_nt_mas, quitar_nt_mas),
    ]
