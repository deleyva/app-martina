# Generated migration for clases app
# This migration uses existing tables from evaluations app via db_table

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # Subject es una tabla NUEVA
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Ej: Música, Matemáticas, Historia', max_length=100, verbose_name='Nombre de la asignatura')),
                ('code', models.CharField(help_text='Código corto único (ej: MUS, MAT, HIS)', max_length=20, unique=True, verbose_name='Código')),
                ('icon', models.CharField(blank=True, help_text='Emoji o clase de icono (ej: 🎵, 🔢, 📚)', max_length=50, verbose_name='Icono')),
                ('color', models.CharField(default='#3B82F6', help_text='Color en formato hexadecimal (ej: #3B82F6)', max_length=7, verbose_name='Color')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('is_active', models.BooleanField(default=True, help_text='Si está activa, se puede usar para crear nuevos grupos', verbose_name='Activa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Asignatura',
                'verbose_name_plural': 'Asignaturas',
                'ordering': ['name'],
            },
        ),
        
        # Group usa tabla EXISTENTE evaluations_group
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='Nombre del grupo')),
                ('academic_year', models.CharField(default='2024-2025', help_text='Ej: 2024-2025', max_length=20, verbose_name='Curso académico')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('subject', models.ForeignKey(help_text='Asignatura que se imparte a este grupo', on_delete=django.db.models.deletion.PROTECT, related_name='groups', to='clases.subject', verbose_name='Asignatura')),
                ('teachers', models.ManyToManyField(blank=True, help_text='Profesores que imparten clase a este grupo', related_name='teaching_groups', to=settings.AUTH_USER_MODEL, verbose_name='Profesores')),
            ],
            options={
                'verbose_name': 'Grupo',
                'verbose_name_plural': 'Grupos',
                'ordering': ['name', 'subject'],
                'unique_together': {('name', 'subject', 'academic_year')},
                'db_table': 'evaluations_group',
            },
        ),
        
        # Student usa tabla EXISTENTE evaluations_student
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(help_text='Grupo al que pertenece el estudiante', on_delete=django.db.models.deletion.PROTECT, related_name='students', to='clases.group', verbose_name='Grupo')),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='student_profile', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Estudiante',
                'verbose_name_plural': 'Estudiantes',
                'ordering': ['user__name'],
                'db_table': 'evaluations_student',
            },
        ),
        
        # GroupLibraryItem usa tabla EXISTENTE evaluations_grouplibraryitem
        migrations.CreateModel(
            name='GroupLibraryItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, help_text='Notas del profesor sobre este elemento para el grupo', verbose_name='Notas')),
                ('added_by', models.ForeignKey(blank=True, help_text='Profesor que añadió este elemento', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Añadido por')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='library_items', to='clases.group', verbose_name='Grupo')),
            ],
            options={
                'verbose_name': 'Item de Biblioteca de Grupo',
                'verbose_name_plural': 'Items de Biblioteca de Grupo',
                'ordering': ['-added_at'],
                'unique_together': {('group', 'content_type', 'object_id')},
                'db_table': 'evaluations_grouplibraryitem',
            },
        ),
        
        # ClassSession usa tabla EXISTENTE evaluations_classsession
        migrations.CreateModel(
            name='ClassSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Fecha de la sesión')),
                ('title', models.CharField(max_length=200, verbose_name='Título')),
                ('notes', models.TextField(blank=True, help_text='Notas generales sobre la sesión', verbose_name='Notas')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Información adicional específica de la asignatura (JSON)', verbose_name='Metadatos')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_sessions', to='clases.group', verbose_name='Grupo')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_sessions', to=settings.AUTH_USER_MODEL, verbose_name='Profesor')),
            ],
            options={
                'verbose_name': 'Sesión de Clase',
                'verbose_name_plural': 'Sesiones de Clase',
                'ordering': ['-date', '-created_at'],
                'db_table': 'evaluations_classsession',
            },
        ),
        
        # ClassSessionItem usa tabla EXISTENTE evaluations_classsessionitem
        migrations.CreateModel(
            name='ClassSessionItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Orden')),
                ('notes', models.TextField(blank=True, help_text='Notas específicas para este elemento en la sesión', verbose_name='Notas')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='clases.classsession', verbose_name='Sesión')),
            ],
            options={
                'verbose_name': 'Item de Sesión',
                'verbose_name_plural': 'Items de Sesión',
                'ordering': ['order'],
                'db_table': 'evaluations_classsessionitem',
            },
        ),
        
        # Índices para GroupLibraryItem
        migrations.AddIndex(
            model_name='grouplibraryitem',
            index=models.Index(fields=['group', '-added_at'], name='evaluations_group_i_group_id_64e65f_idx'),
        ),
        migrations.AddIndex(
            model_name='grouplibraryitem',
            index=models.Index(fields=['content_type', 'object_id'], name='evaluations_group_i_content_6a12b6_idx'),
        ),
        
        # Índices para ClassSession
        migrations.AddIndex(
            model_name='classsession',
            index=models.Index(fields=['teacher', '-date'], name='evaluations_class_s_teacher_5d3e0a_idx'),
        ),
        migrations.AddIndex(
            model_name='classsession',
            index=models.Index(fields=['group', '-date'], name='evaluations_class_s_group_i_7f42c1_idx'),
        ),
        
        # Índice para ClassSessionItem
        migrations.AddIndex(
            model_name='classsessionitem',
            index=models.Index(fields=['session', 'order'], name='evaluations_class_s_session_892a3c_idx'),
        ),
    ]
