from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clases", "0012_add_studycardlabel"),
    ]

    operations = [
        migrations.AddField(
            model_name="classsession",
            name="reflection",
            field=models.TextField(
                blank=True,
                help_text="Reflexión del profesor al finalizar la clase (cómo ha ido, qué quedó pendiente...)",
                verbose_name="Reflexión",
            ),
        ),
        migrations.AddField(
            model_name="classsession",
            name="reflection_audio",
            field=models.FileField(
                blank=True,
                help_text="Nota de voz grabada al finalizar la clase",
                null=True,
                upload_to="class_reflections/%Y/%m/",
                verbose_name="Reflexión (audio)",
            ),
        ),
        migrations.AddField(
            model_name="classsession",
            name="closed_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Momento en que el profesor dio la clase por finalizada",
                null=True,
                verbose_name="Cerrada el",
            ),
        ),
    ]
