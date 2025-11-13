# Migration to add default Subject (Música) and link existing groups
from django.db import migrations


def create_default_subject(apps, schema_editor):
    """Crear asignatura Música por defecto y asociarla a todos los grupos existentes"""
    Subject = apps.get_model('clases', 'Subject')
    Group = apps.get_model('clases', 'Group')
    
    # Crear asignatura Música
    subject = Subject.objects.create(
        name="Música",
        code="MUS",
        icon="🎵",
        color="#8B5CF6",
        description="Asignatura de Música",
        is_active=True,
    )
    
    # Actualizar todos los grupos existentes
    Group.objects.all().update(subject=subject)
    
    print(f"✅ Asignatura '{subject.name}' creada y asignada a {Group.objects.count()} grupos")


def reverse_default_subject(apps, schema_editor):
    """Revertir: eliminar la asignatura Música"""
    Subject = apps.get_model('clases', 'Subject')
    Subject.objects.filter(code="MUS").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clases', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_subject, reverse_default_subject),
    ]
