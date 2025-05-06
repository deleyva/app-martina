from django.core.management.base import BaseCommand
from martina_bescos_app.users.models import User


class Command(BaseCommand):
    help = 'Actualiza los campos first_name y last_name de los usuarios basados en su campo name'

    def handle(self, *args, **kwargs):
        users = User.objects.filter(name__isnull=False).exclude(name='')
        users_updated = 0
        
        for user in users:
            # Solo procesar usuarios que tienen name pero no tienen first_name o last_name
            if not user.first_name or not user.last_name:
                name_parts = user.name.split(' ', 1)
                
                # Asignar first_name si está vacío y hay al menos una parte del nombre
                if len(name_parts) > 0 and not user.first_name:
                    user.first_name = name_parts[0]
                    self.stdout.write(f"Asignando first_name '{name_parts[0]}' a usuario {user.email}")
                
                # Asignar last_name si está vacío y hay una segunda parte del nombre
                if len(name_parts) > 1 and not user.last_name:
                    user.last_name = name_parts[1]
                    self.stdout.write(f"Asignando last_name '{name_parts[1]}' a usuario {user.email}")
                
                # Guardar el usuario si se hizo algún cambio
                if len(name_parts) > 0:
                    user.save()
                    users_updated += 1
        
        self.stdout.write(self.style.SUCCESS(f'Se actualizaron correctamente {users_updated} usuarios.'))
