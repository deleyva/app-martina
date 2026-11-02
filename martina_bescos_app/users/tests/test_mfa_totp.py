"""La activación del 2FA por TOTP necesita `qrcode` en la imagen.

El 2026-11-01 producción devolvió un 500 en /accounts/2fa/totp/activate/ con
`ModuleNotFoundError: No module named 'qrcode'`: allauth lo importa de forma
perezosa en `DefaultMFAAdapter.build_totp_svg`, así que ni el arranque ni los
tests existentes lo echaban en falta. Este test pide la página como lo haría
un usuario recién autenticado y exige el QR en la respuesta.
"""

import time
from http import HTTPStatus

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_activar_totp_muestra_el_qr(client, user):
    user.set_password("una-contraseña-cualquiera")
    user.save()
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    client.force_login(user)
    # allauth exige reautenticación reciente para tocar el 2FA; esto es lo que
    # deja en sesión un login por contraseña.
    session = client.session
    session["account_authentication_methods"] = [{"method": "password", "at": time.time()}]
    session.save()

    response = client.get(reverse("mfa_activate_totp"))

    assert response.status_code == HTTPStatus.OK
    assert "data:image/svg+xml;base64," in response.content.decode()
