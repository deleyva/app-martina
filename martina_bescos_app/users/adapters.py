from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
import re

def es_correo_del_centro(correo: str) -> bool:
    """¿Este correo pertenece a un dominio del centro?

    La lista vive en `SOCIAL_LOGIN_DOMAINS` para poder ampliarla sin tocar
    código: es la frontera entre «entra con Google» y «lo da de alta el
    administrador».
    """
    correo = (correo or "").strip().lower()
    if "@" not in correo:
        return False
    dominio = correo.rsplit("@", 1)[-1]
    permitidos = {
        d.strip().lower().lstrip("@")
        for d in getattr(settings, "SOCIAL_LOGIN_DOMAINS", [])
        if d.strip()
    }
    return dominio in permitidos


MENSAJE_DE_FUERA_SIN_ALTA = (
    "Esta cuenta no tiene permitido entrar con contraseña. Si eres de fuera "
    "del centro, pide al administrador que te dé de alta."
)

MENSAJE_GOOGLE_SOLO_DEL_CENTRO = (
    "Con Google solo se entra con una cuenta del centro. Si el administrador "
    "te ha dado de alta con otro correo, entra con tu correo y contraseña."
)

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from martina_bescos_app.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def _password_login_permitido(self, user) -> bool:
        """¿Puede ESTE correo entrar con contraseña?

        La regla del sitio es Google para todo el mundo. `PASSWORD_LOGIN_EMAILS`
        abre una puerta nominal para cuentas de pruebas o de servicio, que si no
        habría que meter en `is_staff` — o sea, darles el admin entero — solo
        para que puedan entrar.
        """
        correo = (getattr(user, "email", "") or "").strip().lower()
        if not correo:
            return False
        permitidos = {
            c.strip().lower()
            for c in getattr(settings, "PASSWORD_LOGIN_EMAILS", [])
            if c.strip()
        }
        return correo in permitidos

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
    
    def _login_permitido(self, request, user) -> bool:
        """Quién puede entrar con correo y contraseña.

        El centro, sí: quien tiene correo del centro entra como quiera, con
        Google o con la contraseña que se haya puesto él. Los de fuera solo si
        el administrador les ha marcado la casilla en su ficha — esa casilla
        ES el alta. Y al margen de todo, staff, impersonación y la lista de la
        variable de entorno, que son la salida de emergencia si Google falla.
        """
        if request.session.get("_impersonate") is not None:
            return True
        if getattr(user, "is_staff", False):
            return True
        if self.is_social_login_request(request):
            return True
        if es_correo_del_centro(getattr(user, "email", "")):
            return True
        if getattr(user, "acceso_con_contrasena", False):
            return True
        return self._password_login_permitido(user)

    def _rechazo(self, request, user) -> HttpResponseRedirect:
        """Devolver una respuesta es lo que allauth entiende por «corta aquí».

        Esto antes lanzaba `ValidationError`, y nadie la recoge en el camino
        `LoginView.form_valid` → `perform_password_login` → `pre_login`: la
        excepción salía del request como un 500 en la cara de quien se
        equivocaba de puerta. Salió a la luz el 2026-09-20, con una cuenta
        de fuera del centro intentando entrar con su contraseña.

        Aquí solo llega gente de fuera sin alta: al del centro no se le niega
        nunca, y quien se equivoca de contraseña recibe el error del propio
        formulario, no este.
        """
        del user  # el mensaje es el mismo para todo el que llega hasta aquí
        messages.error(request, MENSAJE_DE_FUERA_SIN_ALTA)
        return HttpResponseRedirect(reverse("account_login"))

    def login(self, request, user):
        if not self._login_permitido(request, user):
            # Aquí sí hay quien la recoja: `resume_login` envuelve
            # `adapter.login()` en un `except ImmediateHttpResponse`.
            raise ImmediateHttpResponse(self._rechazo(request, user))
        return super().login(request, user)

    def pre_login(self, request, user, **kwargs):
        if not self._login_permitido(request, user):
            return self._rechazo(request, user)
        return super().pre_login(request, user, **kwargs)

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
        modo = request.session.get('app_mode')
        destinos = {
            'incidencias': 'incidencias:landing',
            'wifi': 'wifi:solicitar',
        }
        if modo in destinos:
            from django.urls import reverse
            return reverse(destinos[modo])
        return super().get_logout_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"OAuth authentication error: provider={provider}, error={error}, "
            f"exception={exception}, exception_type={type(exception).__name__ if exception else None}"
        )
        if exception:
            import traceback
            logger.error(f"OAuth traceback: {traceback.format_exception(exception)}")

    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        """Con Google se registra quien tiene correo del centro, y nadie más.

        Sin esto, el alta por el administrador no vale de nada: cualquiera con
        una cuenta de Google se crea la suya sola y entra.
        """
        if not getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True):
            return False
        return es_correo_del_centro(self._correo_de(sociallogin))
    
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
        
    @staticmethod
    def _correo_de(sociallogin) -> str:
        """El correo del login social, venga del usuario o de los datos crudos."""
        del_usuario = getattr(getattr(sociallogin, "user", None), "email", "") or ""
        if del_usuario:
            return del_usuario
        return (sociallogin.account.extra_data or {}).get("email", "") or ""

    def pre_social_login(self, request, sociallogin):
        """
        Este método se llama justo antes de que un usuario se autentique con una cuenta social.
        Aquí intentamos vincular la cuenta social con un usuario existente si el correo electrónico coincide.
        """
        correo = self._correo_de(sociallogin)
        if not es_correo_del_centro(correo):
            # Los de fuera entran con correo y contraseña, y solo si el
            # administrador les ha dado de alta. Cortar aquí, antes de
            # `connect()`, es lo que impide que Google sea una puerta de atrás.
            messages.error(request, MENSAJE_GOOGLE_SOLO_DEL_CENTRO)
            raise ImmediateHttpResponse(
                HttpResponseRedirect(reverse("account_login"))
            )

        # Verificar si ya existe un usuario con el mismo correo electrónico
        if sociallogin.is_existing:
            self._nombre_de_google(sociallogin)
            return
        
        # Obtener el email de la cuenta social
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return  # Si no hay email, no podemos buscar un usuario existente
        
        # Tratar de encontrar un usuario existente con ese email
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(email__iexact=email)
            
            # Vincular la cuenta existente con la cuenta social
            sociallogin.connect(request, user)
            self._nombre_de_google(sociallogin)
            
        except User.DoesNotExist:
            # No existe un usuario con ese email, se creará uno nuevo
            pass
        except Exception as e:
            # Log del error para debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Error en pre_social_login: %r", e)
            pass

    def _nombre_de_google(self, sociallogin):
        """El nombre y los apellidos de Google mandan sobre los de la base.

        Al profesorado se le precrea el usuario desde las listas del centro
        (`cargar_equipos_blogs`), y ahí los nombres vienen como los escribió
        la gestión: «M. ROSA LOPEZ» donde Google dice «María Rosa López»
        (ejemplo inventado). Decisión de Jesús (2026-09-16): en cada
        entrada con Google se sobrescriben con los de Google. La identidad es
        el correo; el nombre es solo lo que se ve.

        Solo pisa lo que Google trae: un campo vacío en Google no borra nada.
        """
        user = sociallogin.user
        if not user or not user.pk:
            return
        datos = sociallogin.account.extra_data or {}
        nombre = (datos.get("given_name") or "").strip()
        apellidos = (datos.get("family_name") or "").strip()
        completo = (datos.get("name") or "").strip() or f"{nombre} {apellidos}".strip()

        cambios = {}
        for campo, valor in (
            ("first_name", nombre),
            ("last_name", apellidos),
            ("name", completo),
        ):
            if valor and getattr(user, campo) != valor:
                cambios[campo] = valor
        if cambios:
            for campo, valor in cambios.items():
                setattr(user, campo, valor)
            user.save(update_fields=list(cambios))

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
