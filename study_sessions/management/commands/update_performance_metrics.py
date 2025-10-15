from django.core.management.base import BaseCommand
from study_sessions.models import StudyParticipation


class Command(BaseCommand):
    help = 'Actualiza las métricas de rendimiento desnormalizadas para todas las participaciones existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Número de participaciones a procesar por lote (default: 100)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        
        self.stdout.write("🔄 Iniciando actualización de métricas de rendimiento...")
        
        # Obtener todas las participaciones
        participations = StudyParticipation.objects.all()
        total_count = participations.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING("⚠️  No se encontraron participaciones para actualizar"))
            return
        
        self.stdout.write(f"📊 Encontradas {total_count} participaciones para actualizar")
        
        # Procesar en lotes para evitar problemas de memoria
        updated_count = 0
        for i in range(0, total_count, batch_size):
            batch = participations[i:i + batch_size]
            
            for participation in batch:
                try:
                    participation.update_metrics()
                    updated_count += 1
                    
                    if updated_count % 50 == 0:
                        self.stdout.write(f"✅ Procesadas {updated_count}/{total_count} participaciones...")
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error actualizando participación {participation.id}: {e}")
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f"🎉 ¡Actualización completada! {updated_count}/{total_count} participaciones actualizadas")
        )
