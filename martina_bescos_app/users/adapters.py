from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.helpers import ImmediateHttpResponse
from django.conf import settings
from django.forms import ValidationError
import re

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from martina_bescos_app.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        # Rely on the global setting, as the template only shows social signup.
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)
    
    def is_social_login_request(self, request):
        """Determina de manera robusta si una solicitud es parte de un proceso de inicio de sesión social."""
        # 1. Verificar si hay un proveedor social en la sesión
        if request.session.get('sociallogin_provider') is not None:
            return True
            
        # 2. Verificar si hay un parámetro de proceso en la URL
        if 'process' in request.GET:
            return True
            
        # 3. Verificar si estamos en un callback o en una ruta de autenticación social
        social_paths = ['accounts/google/', 'accounts/social/', 'socialaccount/']
        for path in social_paths:
            if path in request.path:
                return True
                
        # 4. Verificar si hay un header específico de solicitud AJAX relacionado con allauth
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 'allauth' in request.path:
            return True
            
        return False
    
    def login(self, request, user):
        # Permitir inicio de sesión en estos casos:
        # 1. El usuario es staff (administrador)
        # 2. Es un inicio de sesión social (Google)
        # 3. El usuario tiene cuentas sociales vinculadas
        # 4. Es parte del proceso de impersonación
        
        # Verificar si es parte del proceso de impersonación
        is_impersonating = request.session.get('_impersonate', None) is not None
        
        # Verificar si el usuario es administrador
        is_staff = getattr(user, 'is_staff', False)
        
        # Verificar si es un inicio de sesión social
        is_social_login = self.is_social_login_request(request)
        
        # Verificar si el usuario tiene cuentas sociales vinculadas
        has_social_account = False
        if hasattr(user, 'socialaccount_set'):
            has_social_account = user.socialaccount_set.exists()
        
        # Permitir el login si se cumple alguna de las condiciones
        if is_staff or is_social_login or has_social_account or is_impersonating:
            return super().login(request, user)
        
        # Si no cumple ninguna condición, rechazar el login
        raise ValidationError(
            "El inicio de sesión con email/contraseña está deshabilitado. "
            "Por favor, usa tu cuenta de Google para iniciar sesión."
        )
    
    def pre_login(self, request, user, **kwargs):
        # Verificar si es parte del proceso de impersonación
        is_impersonating = request.session.get('_impersonate', None) is not None
        
        # Verificar si el usuario es administrador
        is_staff = getattr(user, 'is_staff', False)
        
        # Verificar si es un inicio de sesión social
        is_social_login = self.is_social_login_request(request)
        
        # Verificar si el usuario tiene cuentas sociales vinculadas
        has_social_account = False
        if hasattr(user, 'socialaccount_set'):
            has_social_account = user.socialaccount_set.exists()
        
        # Permitir el login si se cumple alguna de las condiciones
        if is_staff or is_social_login or has_social_account or is_impersonating:
            return super().pre_login(request, user, **kwargs)
        
        # Si llega aquí, es un intento de login normal y no es administrador
        raise ValidationError(
            "El inicio de sesión con email/contraseña está deshabilitado. "
            "Por favor, usa tu cuenta de Google para iniciar sesión."
        )
        
    def get_signup_form_class(self, request=None):
        if request and request.session.get('sociallogin_provider'):
            # Si es un registro social, permitir el formulario normal
            return super().get_signup_form_class(request)
        # En caso contrario, retornar None para deshabilitar el registro manual
        return None

    def get_logout_redirect_url(self, request):
        """
        Retorna la URL de redirección después del logout.
        Si el usuario está en el modo 'incidencias', redirige a la landing de incidencias.
        """
        if request.session.get('app_mode') == 'incidencias':
            from django.urls import reverse
            return reverse('incidencias:landing')
        return super().get_logout_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        # Permitir el registro con cuentas sociales si está habilitado globalmente
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)
    
    def get_callback_url(self, request, app):
        """
        Genera dinámicamente la URL de callback basada en el host y puerto actual.
        Esto permite que funcione tanto con localhost:8000 como con el proxy de Windsurf.
        """
        # Obtener el host y puerto actual de la request
        host = request.get_host()
        scheme = 'https' if request.is_secure() else 'http'
        
        # Construir la URL de callback dinámicamente
        callback_url = f"{scheme}://{host}/accounts/google/login/callback/"
        
        return callback_url
        
    def pre_social_login(self, request, sociallogin):
        """
        Este método se llama justo antes de que un usuario se autentique con una cuenta social.
        Aquí intentamos vincular la cuenta social con un usuario existente si el correo electrónico coincide.
        """
        # Verificar si ya existe un usuario con el mismo correo electrónico
        if sociallogin.is_existing:
            return  # Si la cuenta ya está vinculada, no hacemos nada
        
        # Obtener el email de la cuenta social
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return  # Si no hay email, no podemos buscar un usuario existente
        
        # Tratar de encontrar un usuario existente con ese email
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(email=email)
            
            # Vincular la cuenta existente con la cuenta social
            sociallogin.connect(request, user)
            
        except User.DoesNotExist:
            # No existe un usuario con ese email, se creará uno nuevo
            pass
        except Exception as e:
            # Log del error para debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en pre_social_login: {e}")
            pass

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        return user
