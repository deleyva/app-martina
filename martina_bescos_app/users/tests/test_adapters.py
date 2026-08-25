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
