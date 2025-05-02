import json
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings

from .spotify_client import SpotifyClient


class SpotifyDebugView(LoginRequiredMixin, View):
    """View for debugging Spotify API connection issues"""
    
    def get(self, request):
        # Verificar configuración
        config_info = {
            'spotify_client_id_configured': bool(settings.SPOTIFY_CLIENT_ID),
            'spotify_client_secret_configured': bool(settings.SPOTIFY_CLIENT_SECRET),
            # Mostrar los primeros 5 caracteres para verificar que están cargados (pero no mostrar todo por seguridad)
            'client_id_prefix': settings.SPOTIFY_CLIENT_ID[:5] + '...' if settings.SPOTIFY_CLIENT_ID else None,
            'client_secret_prefix': settings.SPOTIFY_CLIENT_SECRET[:5] + '...' if settings.SPOTIFY_CLIENT_SECRET else None,
        }
        
        # Probar la autenticación
        client = SpotifyClient()
        token = client.get_auth_token()
        
        auth_info = {
            'token_obtained': bool(token),
            'token_prefix': token[:10] + '...' if token else None
        }
        
        # Probar una búsqueda simple
        test_query = request.GET.get('q', 'love')
        search_results = client.search_songs(test_query, limit=3)
        
        search_info = {
            'query': test_query,
            'results_count': len(search_results),
            'results_preview': search_results[:1] if search_results else []
        }
        
        # Devolver toda la información para depuración
        return JsonResponse({
            'config': config_info,
            'auth': auth_info,
            'search': search_info
        }, json_dumps_params={'indent': 2})
