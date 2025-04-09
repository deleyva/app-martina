from ninja import Router, Schema
from typing import List, Optional
from django.http import HttpRequest
from django.utils import timezone
from django.shortcuts import get_object_or_404
import uuid

from .models import APIKey
from .auth import DatabaseApiKey

# Crear un router en lugar de una instancia de NinjaAPI
router = Router(tags=["API Keys"], auth=DatabaseApiKey())

# Schemas para la API
class APIKeyOut(Schema):
    id: int
    name: str
    key: uuid.UUID
    created_at: str
    is_active: bool
    last_used: Optional[str] = None

class APIKeyIn(Schema):
    name: str
    is_active: bool = True

@router.get("/keys", response=List[APIKeyOut])
def list_api_keys(request: HttpRequest) -> List[APIKeyOut]:
    """Lista todas las claves de API del usuario autenticado"""
    return APIKey.objects.filter(user=request.user)

@router.post("/keys", response=APIKeyOut)
def create_api_key(request: HttpRequest, data: APIKeyIn):
    """Crea una nueva clave de API para el usuario autenticado"""
    api_key = APIKey.objects.create(
        name=data.name,
        is_active=data.is_active,
        user=request.user
    )
    return api_key

@router.get("/keys/{key_id}", response=APIKeyOut)
def get_api_key(request: HttpRequest, key_id: int):
    """Obtiene una clave de API específica del usuario autenticado"""
    return get_object_or_404(APIKey, id=key_id, user=request.user)

@router.put("/keys/{key_id}", response=APIKeyOut)
def update_api_key(request: HttpRequest, key_id: int, data: APIKeyIn):
    """Actualiza una clave de API específica del usuario autenticado"""
    api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
    api_key.name = data.name
    api_key.is_active = data.is_active
    api_key.save()
    return api_key

@router.delete("/keys/{key_id}", response={"success": bool})
def delete_api_key(request: HttpRequest, key_id: int):
    """Elimina una clave de API específica del usuario autenticado"""
    api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
    api_key.delete()
    return {"success": True}
