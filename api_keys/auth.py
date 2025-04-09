from ninja.security import APIKeyHeader
from django.utils import timezone
from .models import APIKey

class DatabaseApiKey(APIKeyHeader):
    """
    Clase de autenticación para Django Ninja que verifica las API keys almacenadas en la base de datos.
    Esta clase puede ser utilizada por cualquier API en el proyecto.
    
    Ejemplo de uso:
    ```python
    from api_keys.auth import DatabaseApiKey
    
    api = NinjaAPI(auth=DatabaseApiKey())
    
    @api.get("/endpoint", auth=DatabaseApiKey())
    def my_endpoint(request):
        # El usuario autenticado está disponible en request.user
        return {"message": f"Hola, {request.user.email}"}
    ```
    """
    param_name = "X-API-Key"
    
    def authenticate(self, request, key):
        try:
            # Buscar la clave en la base de datos
            api_key = APIKey.objects.get(key=key, is_active=True)
            
            # Actualizar la fecha de último uso
            api_key.mark_as_used()
            
            # Almacenar el usuario en la solicitud para posible uso posterior
            request.user = api_key.user
            
            return api_key.user
        except (APIKey.DoesNotExist, ValueError):
            return None
