#!/usr/bin/env python
"""
Test del sistema de borrado lógico para MusicItem
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from music_cards.models import MusicItem
from martina_bescos_app.users.models import User

def test_soft_delete():
    print("🧪 Iniciando test de borrado lógico...")
    
    # Crear un usuario de prueba si no existe
    user, created = User.objects.get_or_create(
        email='test_soft_delete@example.com', 
        defaults={'name': 'Test User', 'first_name': 'Test', 'last_name': 'User'}
    )
    print(f"👤 Usuario: {user} (creado: {created})")
    
    # Crear un MusicItem de prueba
    item = MusicItem.objects.create(
        title='Test Item para Borrado Lógico',
        created_by=user
    )
    print(f"🎵 Item creado: {item.id} - {item.title}")
    
    # Verificar que aparece en consultas normales
    normal_count = MusicItem.objects.count()
    all_count = MusicItem.all_objects.count()
    print(f"📊 Items normales: {normal_count}")
    print(f"📊 Items totales (incluyendo borrados): {all_count}")
    
    # Probar borrado lógico
    print(f"❓ ¿Está borrado antes?: {item.is_deleted}")
    item.delete()
    print(f"✅ ¿Está borrado después?: {item.is_deleted}")
    print(f"📅 Fecha de borrado: {item.deleted_at}")
    
    # Verificar que no aparece en consultas normales
    normal_count_after = MusicItem.objects.count()
    all_count_after = MusicItem.all_objects.count()
    print(f"📊 Items normales después del borrado: {normal_count_after}")
    print(f"📊 Items totales después del borrado: {all_count_after}")
    
    # Verificar que el conteo cambió correctamente
    assert normal_count_after == normal_count - 1, "El borrado lógico no funcionó"
    assert all_count_after == all_count, "Se perdió el registro físicamente"
    
    # Probar restauración
    item.restore()
    print(f"🔄 ¿Está borrado después de restaurar?: {item.is_deleted}")
    
    normal_count_restored = MusicItem.objects.count()
    print(f"📊 Items normales después de restaurar: {normal_count_restored}")
    
    # Verificar que la restauración funcionó
    assert normal_count_restored == normal_count, "La restauración no funcionó"
    
    # Limpiar: borrado físico del item de prueba
    item.hard_delete()
    print(f"🗑️  Item de prueba eliminado físicamente")
    
    print("✅ ¡Test de borrado lógico completado exitosamente!")
    return True

if __name__ == "__main__":
    try:
        test_soft_delete()
    except Exception as e:
        print(f"❌ Error en el test: {e}")
        sys.exit(1)
