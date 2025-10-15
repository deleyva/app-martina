from django.core.management.base import BaseCommand
from django.db import transaction
from study_sessions.models import UniversalStudyItem


class Command(BaseCommand):
    help = 'Migra datos de GenericForeignKey a referencias específicas en UniversalStudyItem'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta en modo simulación sin hacer cambios reales'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Número de elementos a procesar por lote (default: 100)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        if dry_run:
            self.stdout.write("🔍 Ejecutando en modo DRY-RUN (sin cambios reales)")
        
        self.stdout.write("🔄 Iniciando migración de GenericForeignKey a referencias específicas...")
        
        # Obtener elementos que usan GenericForeignKey
        items_to_migrate = UniversalStudyItem.objects.filter(
            content_type__isnull=False,
            object_id__isnull=False,
            music_item__isnull=True,
            class_session_page__isnull=True,
            student_contribution__isnull=True
        )
        
        total_count = items_to_migrate.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ No hay elementos que migrar"))
            return
        
        self.stdout.write(f"📊 Encontrados {total_count} elementos para migrar")
        
        migrated_count = 0
        failed_count = 0
        
        # Procesar en lotes
        for i in range(0, total_count, batch_size):
            batch = items_to_migrate[i:i + batch_size]
            
            with transaction.atomic():
                for item in batch:
                    try:
                        if dry_run:
                            # Solo simular la migración
                            content_obj = item.content_object
                            if content_obj:
                                model_name = content_obj._meta.model_name
                                self.stdout.write(f"  [DRY-RUN] Migraría {item.id}: {model_name} -> {content_obj}")
                                migrated_count += 1
                        else:
                            # Migración real
                            if item.migrate_from_generic_fk():
                                migrated_count += 1
                                if migrated_count % 25 == 0:
                                    self.stdout.write(f"✅ Migrados {migrated_count}/{total_count} elementos...")
                            else:
                                failed_count += 1
                                self.stdout.write(
                                    self.style.WARNING(f"⚠️  No se pudo migrar elemento {item.id}")
                                )
                                
                    except Exception as e:
                        failed_count += 1
                        self.stdout.write(
                            self.style.ERROR(f"❌ Error migrando elemento {item.id}: {e}")
                        )
        
        # Resumen final
        self.stdout.write("\n" + "="*60)
        if dry_run:
            self.stdout.write(f"🔍 SIMULACIÓN COMPLETADA:")
            self.stdout.write(f"  - Elementos que se migrarían: {migrated_count}")
            self.stdout.write(f"  - Elementos que fallarían: {failed_count}")
            self.stdout.write(f"  - Total procesados: {migrated_count + failed_count}")
        else:
            self.stdout.write(f"🎉 MIGRACIÓN COMPLETADA:")
            self.stdout.write(f"  - Elementos migrados exitosamente: {migrated_count}")
            self.stdout.write(f"  - Elementos que fallaron: {failed_count}")
            self.stdout.write(f"  - Total procesados: {migrated_count + failed_count}")
        
        if migrated_count > 0:
            self.stdout.write("\n📈 BENEFICIOS OBTENIDOS:")
            self.stdout.write("  ✅ Consultas más rápidas (sin GenericForeignKey)")
            self.stdout.write("  ✅ Mejor uso de índices de base de datos")
            self.stdout.write("  ✅ Posibilidad de usar select_related optimizado")
            
        if not dry_run and migrated_count > 0:
            self.stdout.write(f"\n🔧 PRÓXIMO PASO:")
            self.stdout.write("  Ejecutar: python manage.py demo_phase4_performance")
            self.stdout.write("  Para ver las mejoras de rendimiento obtenidas")
        
        self.stdout.write(self.style.SUCCESS("✅ ¡Proceso completado!"))
