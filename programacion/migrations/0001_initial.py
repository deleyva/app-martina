import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("clases", "0013_classsession_reflection"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CoursePlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Ej: 2º Trimestre 2025-26", max_length=200, verbose_name="Nombre")),
                ("start_date", models.DateField(blank=True, null=True, verbose_name="Inicio")),
                ("end_date", models.DateField(blank=True, null=True, verbose_name="Fin")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activa")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="course_plans", to="clases.group", verbose_name="Grupo")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="course_plans", to=settings.AUTH_USER_MODEL, verbose_name="Profesor")),
            ],
            options={
                "verbose_name": "Programación",
                "verbose_name_plural": "Programaciones",
                "ordering": ["-is_active", "-start_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PlanItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_id", models.PositiveIntegerField()),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                ("sessions_estimate", models.PositiveSmallIntegerField(default=1, help_text="Número de clases que estimas dedicar a este recurso", verbose_name="Sesiones estimadas")),
                ("status", models.CharField(choices=[("auto", "Automático (según cobertura)"), ("skipped", "Saltado"), ("done", "Completado (manual)")], default="auto", max_length=10, verbose_name="Estado")),
                ("notes", models.TextField(blank=True, verbose_name="Notas")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("parent", models.ForeignKey(blank=True, help_text="Para capítulos de un libro", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="programacion.planitem", verbose_name="Padre")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="programacion.courseplan", verbose_name="Programación")),
            ],
            options={
                "verbose_name": "Item de Programación",
                "verbose_name_plural": "Items de Programación",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="ContentCoverage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_id", models.PositiveIntegerField()),
                ("elements_total", models.PositiveIntegerField(default=0)),
                ("elements_seen", models.PositiveIntegerField(default=0)),
                ("seen_element_keys", models.JSONField(blank=True, default=list, help_text='Claves de elementos vistos, p.ej. ["document:12", "image:3"]')),
                ("page_presented", models.BooleanField(default=False, help_text="La página completa se ha mostrado en alguna sesión")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="content_coverage", to="clases.group", verbose_name="Grupo")),
                ("last_session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="clases.classsession")),
            ],
            options={
                "verbose_name": "Cobertura de Contenido",
                "verbose_name_plural": "Coberturas de Contenido",
            },
        ),
        migrations.AddIndex(
            model_name="courseplan",
            index=models.Index(fields=["teacher", "-created_at"], name="programacio_teacher_bddd02_idx"),
        ),
        migrations.AddIndex(
            model_name="courseplan",
            index=models.Index(fields=["group", "-created_at"], name="programacio_group_i_f81f49_idx"),
        ),
        migrations.AddIndex(
            model_name="planitem",
            index=models.Index(fields=["plan", "order"], name="programacio_plan_id_87c3d7_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="planitem",
            unique_together={("plan", "content_type", "object_id")},
        ),
        migrations.AddIndex(
            model_name="contentcoverage",
            index=models.Index(fields=["group", "content_type", "object_id"], name="programacio_group_i_5683d0_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="contentcoverage",
            unique_together={("group", "content_type", "object_id")},
        ),
    ]
