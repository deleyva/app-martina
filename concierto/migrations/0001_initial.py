from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Acto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(verbose_name="Orden")),
                ("artistas", models.CharField(max_length=500, verbose_name="Artistas")),
                ("canciones", models.TextField(help_text="Una cancion por linea", verbose_name="Canciones")),
                ("autores", models.CharField(blank=True, default="", max_length=500, verbose_name="Autores")),
                ("material", models.TextField(blank=True, default="", verbose_name="Material necesario")),
                ("duracion_minutos", models.PositiveIntegerField(default=5, verbose_name="Duracion (min)")),
            ],
            options={
                "verbose_name": "Acto",
                "verbose_name_plural": "Actos",
                "ordering": ["orden"],
            },
        ),
        migrations.CreateModel(
            name="Tarea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=200, verbose_name="Nombre")),
                ("descripcion", models.TextField(blank=True, default="", verbose_name="Descripcion")),
                ("max_voluntarios", models.PositiveIntegerField(default=3, verbose_name="Max voluntarios")),
                ("acto", models.ForeignKey(blank=True, help_text="Solo para tareas de grabacion vinculadas a un acto", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tareas_grabacion", to="concierto.acto")),
            ],
            options={
                "verbose_name": "Tarea",
                "verbose_name_plural": "Tareas",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="Voluntario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(help_text="Tu usuario sin @iesmartinabescos.es (ej: jlopez)", max_length=100, verbose_name="Usuario IES")),
                ("fecha_registro", models.DateTimeField(auto_now_add=True)),
                ("tarea", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="voluntarios", to="concierto.tarea")),
            ],
            options={
                "verbose_name": "Voluntario",
                "verbose_name_plural": "Voluntarios",
                "unique_together": {("username", "tarea")},
            },
        ),
    ]
