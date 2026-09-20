"""La puerta nominal del login por contraseña.

El sitio obliga a Google: `AccountAdapter.pre_login` rechaza el login por
email/contraseña salvo para staff, cuentas con social vinculada e
impersonación. Eso deja sin entrada a las cuentas de pruebas o de servicio, y
la única salida era darles `is_staff` — o sea, el admin entero.

`PASSWORD_LOGIN_EMAILS` abre esa puerta por correo y nada más. Estos tests
existen para que no se convierta sin querer en "contraseña para todo el mundo".
"""

import pytest
from django.test import override_settings

from martina_bescos_app.users.adapters import AccountAdapter
from martina_bescos_app.users.adapters import es_correo_del_centro
from martina_bescos_app.users.tests.factories import UserFactory

# Un correo de ejemplo a proposito: la cuenta real vive solo en la variable de
# entorno, que no esta versionada. Este repo es publico, y publicar el nombre
# de una cuenta que puede entrar con contrasena es regalar la mitad del par.
PERMITIDO = "cuenta-de-servicio@ejemplo.test"


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=[PERMITIDO])
def test_el_correo_de_la_lista_puede_entrar_con_contrasena():
    user = UserFactory(email=PERMITIDO, is_staff=False, is_superuser=False)

    assert AccountAdapter()._password_login_permitido(user) is True


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=[PERMITIDO])
def test_cualquier_otro_correo_sigue_sin_poder():
    """El falsador de todo esto: si esto pasa a True, se ha abierto la puerta
    al alumnado entero y la obligacion de Google deja de existir."""
    user = UserFactory(email="alumno@ejemplo.test", is_staff=False)

    assert AccountAdapter()._password_login_permitido(user) is False


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=[])
def test_sin_configurar_no_cambia_nada_para_nadie():
    user = UserFactory(email=PERMITIDO, is_staff=False)

    assert AccountAdapter()._password_login_permitido(user) is False


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=["  Cuenta-DE-Servicio@Ejemplo.Test  "])
def test_el_correo_se_compara_normalizado():
    """Mayusculas y espacios en la variable de entorno no pueden dejar fuera a
    la cuenta: el correo se compara en minusculas y sin espacios."""
    user = UserFactory(email=PERMITIDO, is_staff=False)

    assert AccountAdapter()._password_login_permitido(user) is True


CONTRASENA = "unaContrasenaLarga123"


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=[])
def test_a_quien_se_le_niega_la_entrada_se_le_responde_una_pagina(client):
    """El falsador del 500: negar la entrada tiene que ser una respuesta.

    `pre_login` lanzaba `ValidationError` y nadie la recoge entre
    `LoginView.form_valid` y `perform_password_login`, asi que la negativa
    salia como error 500. Si esto vuelve a ser 500, ha vuelto el fallo.
    """
    from allauth.account.models import EmailAddress
    from django.urls import reverse

    user = UserFactory(email="alumna@ejemplo.test", is_staff=False, password=CONTRASENA)
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )

    respuesta = client.post(
        reverse("account_login"),
        {"login": user.email, "password": CONTRASENA},
        raise_request_exception=False,
    )

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("account_login")
    assert not respuesta.wsgi_request.user.is_authenticated


# ── La política del sitio ────────────────────────────────────────────────
# Quien tiene correo del centro entra con Google. Quien no, solo entra si el
# administrador le ha marcado «Puede entrar con contraseña» en su ficha. Estos
# tests son el falsador de esas dos frases.

DEL_CENTRO = "profe@iesmartinabescos.es"
DE_FUERA = "madre@gmail.com"


def _peticion_con_mensajes():
    """Una request de mentira que aguanta `messages.error`."""
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore
    from django.test import RequestFactory

    peticion = RequestFactory().get("/accounts/login/")
    peticion.session = SessionStore()
    peticion._messages = FallbackStorage(peticion)
    return peticion


def _login_social(email):
    from allauth.socialaccount.models import SocialAccount, SocialLogin

    from martina_bescos_app.users.models import User

    return SocialLogin(
        user=User(email=email),
        account=SocialAccount(provider="google", uid="uid-1", extra_data={"email": email}),
    )


def test_el_dominio_del_centro_se_reconoce():
    assert es_correo_del_centro(DEL_CENTRO) is True
    assert es_correo_del_centro("PROFE@IESMartinaBescos.ES") is True
    assert es_correo_del_centro(DE_FUERA) is False
    assert es_correo_del_centro("alguien@apps.iesmartinabescos.es") is False
    assert es_correo_del_centro("") is False


@pytest.mark.django_db
def test_con_el_alta_del_admin_se_entra_con_contrasena(client):
    """Lo que Jesús pidió: el admin marca la casilla y esa cuenta entra."""
    from allauth.account.models import EmailAddress
    from django.urls import reverse

    user = UserFactory(email=DE_FUERA, is_staff=False, password=CONTRASENA)
    user.acceso_con_contrasena = True
    user.save()
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

    respuesta = client.post(
        reverse("account_login"),
        {"login": user.email, "password": CONTRASENA},
        raise_request_exception=False,
    )

    assert respuesta.status_code == 302
    assert respuesta["Location"] != reverse("account_login")
    assert respuesta.wsgi_request.user.is_authenticated


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=[])
def test_sin_alta_no_se_entra_con_contrasena():
    """El falsador del alta: si esto pasa a True, la casilla no pinta nada."""
    user = UserFactory(email=DE_FUERA, is_staff=False)
    assert user.acceso_con_contrasena is False

    assert AccountAdapter()._login_permitido(_peticion_con_mensajes(), user) is False


@pytest.mark.django_db
@override_settings(PASSWORD_LOGIN_EMAILS=[])
def test_el_centro_entra_con_contrasena_sin_necesitar_alta():
    """La regla del sitio: el del centro entra como quiera, Google o contraseña."""
    user = UserFactory(email=DEL_CENTRO, is_staff=False)
    assert user.acceso_con_contrasena is False

    assert AccountAdapter()._login_permitido(_peticion_con_mensajes(), user) is True


@pytest.mark.django_db
def test_google_no_deja_entrar_a_un_correo_de_fuera():
    """El agujero que hace inútil el alta: si Google admite cualquier cuenta,
    cualquiera se registra solo y el administrador no pinta nada."""
    from allauth.core.exceptions import ImmediateHttpResponse

    from martina_bescos_app.users.adapters import SocialAccountAdapter
    from martina_bescos_app.users.models import User

    adaptador = SocialAccountAdapter()
    peticion = _peticion_con_mensajes()

    with pytest.raises(ImmediateHttpResponse):
        adaptador.pre_social_login(peticion, _login_social(DE_FUERA))

    assert not User.objects.filter(email=DE_FUERA).exists()
    assert adaptador.is_open_for_signup(peticion, _login_social(DE_FUERA)) is False


@pytest.mark.django_db
def test_google_sigue_abierto_para_el_centro():
    from martina_bescos_app.users.adapters import SocialAccountAdapter

    adaptador = SocialAccountAdapter()
    peticion = _peticion_con_mensajes()

    adaptador.pre_social_login(peticion, _login_social(DEL_CENTRO))  # no levanta nada

    assert adaptador.is_open_for_signup(peticion, _login_social(DEL_CENTRO)) is True
