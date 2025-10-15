from django.core.management.base import BaseCommand
from music_cards.models import MusicItem
from martina_bescos_app.users.models import User


class Command(BaseCommand):
    help = 'Test del sistema de borrado lógico para MusicItem'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Iniciando test de borrado lógico...")
        
        # Crear un usuario de prueba si no existe
        user, created = User.objects.get_or_create(
            email='test_soft_delete@example.com', 
            defaults={'name': 'Test User', 'first_name': 'Test', 'last_name': 'User'}
        )
        self.stdout.write(f"👤 Usuario: {user} (creado: {created})")
        
        # Crear un MusicItem de prueba
        item = MusicItem.objects.create(
            title='Test Item para Borrado Lógico',
            created_by=user
        )
        self.stdout.write(f"🎵 Item creado: {item.id} - {item.title}")
        
        # Verificar que aparece en consultas normales
        normal_count = MusicItem.objects.count()
        all_count = MusicItem.all_objects.count()
        self.stdout.write(f"📊 Items normales: {normal_count}")
        self.stdout.write(f"📊 Items totales (incluyendo borrados): {all_count}")
        
        # Probar borrado lógico
        self.stdout.write(f"❓ ¿Está borrado antes?: {item.is_deleted}")
        item.delete()
        self.stdout.write(f"✅ ¿Está borrado después?: {item.is_deleted}")
        self.stdout.write(f"📅 Fecha de borrado: {item.deleted_at}")
        
        # Verificar que no aparece en consultas normales
        normal_count_after = MusicItem.objects.count()
        all_count_after = MusicItem.all_objects.count()
        self.stdout.write(f"📊 Items normales después del borrado: {normal_count_after}")
        self.stdout.write(f"📊 Items totales después del borrado: {all_count_after}")
        
        # Verificar que el conteo cambió correctamente
        if normal_count_after != normal_count - 1:
            self.stdout.write(self.style.ERROR("❌ El borrado lógico no funcionó"))
            return
        if all_count_after != all_count:
            self.stdout.write(self.style.ERROR("❌ Se perdió el registro físicamente"))
            return
        
        # Probar restauración
        item.restore()
        self.stdout.write(f"🔄 ¿Está borrado después de restaurar?: {item.is_deleted}")
        
        normal_count_restored = MusicItem.objects.count()
        self.stdout.write(f"📊 Items normales después de restaurar: {normal_count_restored}")
        
        # Verificar que la restauración funcionó
        if normal_count_restored != normal_count:
            self.stdout.write(self.style.ERROR("❌ La restauración no funcionó"))
            return
        
        # Limpiar: borrado físico del item de prueba
        item.hard_delete()
        self.stdout.write("🗑️  Item de prueba eliminado físicamente")
        
        self.stdout.write(self.style.SUCCESS("✅ ¡Test de borrado lógico completado exitosamente!"))
