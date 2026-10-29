# Tramo 76·4: la vuelta de comprobación y las correcciones a mano. Tres campos
# con valor por defecto; no toca ninguna fila existente.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("preguntas", "0002_pase_en_vivo"),
    ]

    operations = [
        migrations.AddField(
            model_name="pase",
            name="revision",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="pasepregunta",
            name="correcciones",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="respuesta",
            name="corregida",
            field=models.BooleanField(default=False),
        ),
    ]
