# ruff: noqa: ERA001, E501
"""Initial migration for the incidencias app."""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models

import incidencias.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Etiqueta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, verbose_name="Nombre")),
                ("slug", models.SlugField(max_length=100, unique=True, verbose_name="Slug")),
            ],
            options={
                "verbose_name": "Etiqueta",
                "verbose_name_plural": "Etiquetas",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="Ubicacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, verbose_name="Aula")),
                ("grupo", models.CharField(blank=True, default="", max_length=100, verbose_name="Grupo")),
                ("planta", models.CharField(choices=[("PB", "Planta Baja"), ("P1", "Primera Planta"), ("P2", "Segunda Planta")], max_length=2, verbose_name="Planta")),
            ],
            options={
                "verbose_name": "Ubicación",
                "verbose_name_plural": "Ubicaciones",
                "ordering": ["planta", "nombre"],
                "unique_together": {("nombre", "planta")},
            },
        ),
        migrations.CreateModel(
            name="Tecnico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre_display", models.CharField(blank=True, default="", max_length=200, verbose_name="Nombre a mostrar")),
                ("activo", models.BooleanField(default=True, verbose_name="Activo")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="perfil_tecnico", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Técnico",
                "verbose_name_plural": "Técnicos",
            },
        ),
        migrations.CreateModel(
            name="Incidencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=255, verbose_name="Título")),
                ("descripcion", models.TextField(blank=True, default="", verbose_name="Descripción")),
                ("urgencia", models.CharField(choices=[("baja", "Baja"), ("media", "Media"), ("alta", "Alta"), ("critica", "Crítica")], default="media", max_length=10, verbose_name="Urgencia")),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("en_progreso", "En progreso"), ("resuelta", "Resuelta")], default="pendiente", max_length=12, verbose_name="Estado")),
                ("es_privada", models.BooleanField(default=False, verbose_name="Es privada")),
                ("reportero_nombre", models.CharField(help_text="Usuario de Google Workspace (sin @iesmartinabescos)", max_length=150, verbose_name="Reportado por")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Última actualización")),
                ("asignado_a", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incidencias_asignadas", to="incidencias.tecnico", verbose_name="Asignado a")),
                ("etiquetas", models.ManyToManyField(blank=True, related_name="incidencias", to="incidencias.etiqueta", verbose_name="Etiquetas")),
                ("ubicacion", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incidencias", to="incidencias.ubicacion", verbose_name="Ubicación")),
            ],
            options={
                "verbose_name": "Incidencia",
                "verbose_name_plural": "Incidencias",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Comentario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("autor_nombre", models.CharField(help_text="Usuario de Google Workspace (sin @iesmartinabescos)", max_length=150, verbose_name="Autor")),
                ("texto", models.TextField(verbose_name="Comentario")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Fecha")),
                ("incidencia", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comentarios", to="incidencias.incidencia", verbose_name="Incidencia")),
            ],
            options={
                "verbose_name": "Comentario",
                "verbose_name_plural": "Comentarios",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="Adjunto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("archivo", models.FileField(upload_to=incidencias.models.adjunto_upload_path, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "mp4", "mov", "avi", "webm"])], verbose_name="Archivo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Fecha")),
                ("incidencia", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="adjuntos", to="incidencias.incidencia", verbose_name="Incidencia")),
            ],
            options={
                "verbose_name": "Adjunto",
                "verbose_name_plural": "Adjuntos",
            },
        ),
    ]
