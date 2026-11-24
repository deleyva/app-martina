# Fase 116 (2026-11-24): SB+ = 10 en la escala del curso.
#
# Como la 0008 con NT+: la letra entra en las opciones del cuaderno y los
# instrumentos que califican con SB · NT+ · NT · BI · SU · IN reciben SB+ por
# delante. Las notas no se tocan: 10 es un valor nuevo que no choca con nada.

from django.db import migrations, models

ANTERIOR = ["SB", "NT+", "NT", "BI", "SU", "IN"]
SB_MAS = {"etiqueta": "SB+", "valor": 10}


def _etiquetas(instrumento):
    return [str(o.get("etiqueta", "")).strip().upper() for o in (instrumento.opciones or [])]


def anadir_sb_mas(apps, schema_editor):
    Instrumento = apps.get_model("calificaciones", "Instrumento")
    for instrumento in Instrumento.objects.filter(escala="opciones"):
        if _etiquetas(instrumento) == ANTERIOR:
            instrumento.opciones = [dict(SB_MAS), *instrumento.opciones]
            instrumento.save(update_fields=["opciones"])


def quitar_sb_mas(apps, schema_editor):
    Instrumento = apps.get_model("calificaciones", "Instrumento")
    for instrumento in Instrumento.objects.filter(escala="opciones"):
        if _etiquetas(instrumento) == ["SB+", *ANTERIOR]:
            instrumento.opciones = instrumento.opciones[1:]
            instrumento.save(update_fields=["opciones"])


class Migration(migrations.Migration):

    dependencies = [
        ("calificaciones", "0008_nt_mas"),
    ]

    operations = [
        migrations.AlterField(
            model_name="revisioncuaderno",
            name="letra",
            field=models.CharField(
                blank=True,
                choices=[("SB+", "SB+"), ("SB", "SB"), ("NT+", "NT+"), ("NT", "NT"), ("BI", "BI"), ("SU", "SU"), ("IN", "IN")],
                help_text="Vacía = sorteado y pendiente de mirar",
                max_length=3,
            ),
        ),
        migrations.RunPython(anadir_sb_mas, quitar_sb_mas),
    ]
