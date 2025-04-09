from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import APIKey

# Create your views here.

@login_required
def api_key_list(request):
    """Vista para listar las claves API del usuario autenticado"""
    api_keys = APIKey.objects.filter(user=request.user)
    return render(request, 'api_keys/list.html', {
        'api_keys': api_keys,
    })

@login_required
def api_key_create(request):
    """Vista para crear una nueva clave API"""
    if request.method == 'POST':
        name = request.POST.get('name', '')
        if not name:
            messages.error(request, 'El nombre de la clave es obligatorio')
            return redirect('api_keys:list')
        
        # Crear la nueva clave API
        api_key = APIKey.objects.create(
            name=name,
            user=request.user,
            is_active=True
        )
        messages.success(request, f'Clave API "{name}" creada correctamente')
        return redirect('api_keys:list')
    
    return render(request, 'api_keys/create.html')

@login_required
@require_POST
def api_key_delete(request, pk):
    """Vista para eliminar una clave API"""
    api_key = get_object_or_404(APIKey, id=pk, user=request.user)
    name = api_key.name
    api_key.delete()
    
    messages.success(request, f'Clave API "{name}" eliminada correctamente')
    return redirect('api_keys:list')

@login_required
@require_POST
def api_key_toggle(request, pk):
    """Vista para activar/desactivar una clave API"""
    api_key = get_object_or_404(APIKey, id=pk, user=request.user)
    api_key.is_active = not api_key.is_active
    api_key.save(update_fields=['is_active'])
    
    status = "activada" if api_key.is_active else "desactivada"
    messages.success(request, f'Clave API "{api_key.name}" {status} correctamente')
    
    # Si es una petición AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_active': api_key.is_active,
            'message': f'Clave API "{api_key.name}" {status} correctamente'
        })
    
    return redirect('api_keys:list')
