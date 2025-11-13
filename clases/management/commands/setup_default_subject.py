"""
Comando para crear la asignatura por defecto (Música) y asociar todos los grupos existentes.
Ejecutar DESPUÉS de aplicar las migraciones de clases.
"""
from django.core.management.base import BaseCommand
from clases.models import Subject, Group


class Command(BaseCommand):
    help = 'Crea la asignatura por defecto (Música) y actualiza los grupos existentes'

    def handle(self, *args, **options):
        # Crear asignatura Música por defecto
        subject, created = Subject.objects.get_or_create(
            code="MUS",
            defaults={
                "name": "Música",
                "icon": "🎵",
                "color": "#8B5CF6",  # Purple
                "description": "Asignatura de Música",
                "is_active": True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Asignatura creada: {subject}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  La asignatura "{subject}" ya existe')
            )
        
        # Actualizar grupos que no tengan subject asignado
        # NOTA: Esto no debería pasar si las migraciones se ejecutan correctamente
        # pero lo dejamos por seguridad
        groups_without_subject = Group.objects.filter(subject__isnull=True)
        count = groups_without_subject.count()
        
        if count > 0:
            groups_without_subject.update(subject=subject)
            self.stdout.write(
                self.style.SUCCESS(f'✅ {count} grupos actualizados con asignatura "{subject}"')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Todos los grupos ya tienen asignatura asignada')
            )
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 Configuración completada correctamente')
        )
