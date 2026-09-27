# Fase 51 — artículos fijados en la cabecera de su departamento.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blogs", "0004_alter_articulopage_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="articulopage",
            name="is_pinned",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Siempre visible en la cabecera del departamento, por encima "
                    "de la cronología. Para la programación, los criterios de "
                    "calificación y lo que no debe quedarse atrás."
                ),
                verbose_name="Fijado en el departamento",
            ),
        ),
    ]
