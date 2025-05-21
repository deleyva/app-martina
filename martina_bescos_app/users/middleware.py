from django.shortcuts import redirect
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.functional import SimpleLazyObject
from django.contrib.auth.models import AnonymousUser


class GoogleLoginRedirectMiddleware:
    """
    Middleware que redirige a los usuarios no administradores a la página de inicio de sesión de Google
    cuando intentan acceder a la página de inicio de sesión normal (con email/password)
    o a la página de registro manual.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lista de rutas que siempre deben estar permitidas para el proceso social
        social_allowed_paths = [
            '/accounts/google/', 
            '/accounts/social/',
            '/accounts/facebook/',
            '/accounts/twitter/'
        ]
        
        # No interferir con los callbacks y procesos de las cuentas sociales
        for allowed_path in social_allowed_paths:
            if request.path.startswith(allowed_path):
                return self.get_response(request)
        
        # Comprobar si es parte de un proceso social a través de los parámetros de URL
        is_social_process = 'process' in request.GET or request.path.endswith('/callback/')
        if is_social_process:
            return self.get_response(request)
        
        # Comprobar si request.user está disponible y si el usuario es staff
        is_staff = False
        if hasattr(request, 'user') and not isinstance(request.user, SimpleLazyObject):
            # Si el usuario está autenticado y es staff, permitimos continuar
            if hasattr(request.user, 'is_staff') and request.user.is_staff:
                is_staff = True
        
        # Bloquear acceso a la página de inicio de sesión tradicional
        if request.path == reverse('account_login') and not request.path.startswith('/admin/'):
            # Si no es admin, redirigir
            if not is_staff:
                try:
                    # Intentar redirigir al inicio de sesión de Google
                    return redirect('socialaccount_signin_google')
                except NoReverseMatch:
                    # Si no existe la URL para Google, usar la URL genérica
                    return redirect('/accounts/google/login/?process=login')
        
        # Bloquear acceso a la página de registro manual
        try:
            signup_url = reverse('account_signup')
            if request.path == signup_url and not is_staff:
                try:
                    # Intentar redirigir al registro con Google
                    return redirect('socialaccount_signup')
                except NoReverseMatch:
                    # Si no existe la URL para Google, usar la URL genérica
                    return redirect('/accounts/google/login/?process=signup')
        except NoReverseMatch:
            # Si la URL de registro no existe, ignorar esta parte
            pass
        
        response = self.get_response(request)
        return response
