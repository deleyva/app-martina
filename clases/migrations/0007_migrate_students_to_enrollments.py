# Generated manually for data migration

from django.db import migrations


def migrate_students_to_enrollments(apps, schema_editor):
    """Copia todos los Student existentes a Enrollment."""
    Student = apps.get_model("clases", "Student")
    Enrollment = apps.get_model("clases", "Enrollment")

    for student in Student.objects.all():
        if student.user and student.group:
            # Crear Enrollment solo si no existe ya (evitar duplicados si se ejecuta varias veces)
            Enrollment.objects.get_or_create(
                user=student.user,
                group=student.group,
                defaults={
                    "is_active": True,
                },
            )


def reverse_migration(apps, schema_editor):
    """Elimina todos los Enrollments creados por la migración."""
    Enrollment = apps.get_model("clases", "Enrollment")
    Enrollment.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("clases", "0006_alter_student_options_alter_student_group_enrollment"),
    ]

    operations = [
        migrations.RunPython(migrate_students_to_enrollments, reverse_migration),
    ]
