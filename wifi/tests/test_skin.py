"""La piel: que login y logout dejen de parecer la Music App.

El mecanismo ya existía para `incidencias` — `AppModeMiddleware` guarda un
`app_mode` en sesión y un context processor elige la plantilla base. Aquí solo
se comprueba que `wifi` entra en ese mismo carril, y que no se lleva por delante
los otros dos modos.
"""

import pytest
from django.urls import reverse

from martina_bescos_app.middleware import AppModeMiddleware
from martina_bescos_app.utils.context_processors import base_template_context

from .factories import PersonalFactory

BASE_WIFI = "wifi/base_wifi.html"


@pytest.fixture
def app_de_google(db):
    """La plantilla de login pinta `provider_login_url`, que exige un SocialApp.

    No es un detalle del test: sin esta fila allauth revienta con
    `SocialApp.DoesNotExist`. En producción la fila existe; aquí hay que ponerla.
    """
    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site

    app = SocialApp.objects.create(
        provider="google", name="Google", client_id="test", secret="test",
    )
    app.sites.add(Site.objects.get_current())
    return app


class TestModoPorRuta:
    """`mode_for_path` es pura: se puede comprobar sin base de datos."""

    def _middleware(self):
        return AppModeMiddleware(lambda request: None)

    @pytest.mark.parametrize(
        ("ruta", "esperado"),
        [
            ("/wifi/", "wifi"),
            ("/wifi/gestion/", "wifi"),
            ("/incidencias/", "incidencias"),
            ("/my-library/", "main"),
            ("/", "main"),
        ],
    )
    def test_la_ruta_decide_el_modo(self, ruta, esperado):
        assert self._middleware().mode_for_path(ruta) == esperado

    @pytest.mark.parametrize("ruta", ["/accounts/login/", "/accounts/logout/", "/users/1/"])
    def test_las_vistas_compartidas_conservan_el_modo(self, ruta):
        """Si `/accounts/` decidiera, el login siempre volvería a la piel de siempre."""
        assert self._middleware().mode_for_path(ruta) is None

    @pytest.mark.parametrize("ruta", ["/analytics/track/", "/static/css/output.css"])
    def test_lo_no_navegacional_no_decide(self, ruta):
        assert self._middleware().mode_for_path(ruta) is None


class TestPlantillaBase:
    def _peticion(self, rf, modo=None, host="testserver"):
        peticion = rf.get("/", HTTP_HOST=host)
        peticion.session = {"app_mode": modo} if modo else {}
        return peticion

    def test_en_modo_wifi_la_base_es_la_de_wifi(self, rf):
        assert base_template_context(self._peticion(rf, "wifi"))["base_template"] == BASE_WIFI

    def test_incidencias_sigue_con_la_suya(self, rf):
        contexto = base_template_context(self._peticion(rf, "incidencias"))
        assert contexto["base_template"] == "incidencias/base_incidencias.html"

    def test_sin_modo_manda_la_de_siempre(self, rf):
        assert base_template_context(self._peticion(rf))["base_template"] == "base.html"


@pytest.mark.django_db
class TestPantallasDeSesion:
    def test_el_logout_lleva_la_piel_de_wifi_tras_pasar_por_la_app(self, client):
        client.force_login(PersonalFactory())
        client.get("/wifi/")  # el middleware apunta el modo

        contenido = client.get(reverse("account_logout")).content.decode()

        assert "Vas a salir de las altas de WiFi" in contenido
        assert "Martina Bescós Music App" not in contenido

    def test_el_login_lleva_la_piel_de_wifi(self, client, app_de_google):
        client.get("/wifi/")  # anónimo: redirige al login, pero deja el modo puesto

        contenido = client.get(reverse("account_login")).content.decode()

        assert "Acceso a la WiFi del centro" in contenido
        assert "Martina Bescós Music App" not in contenido

    def test_sin_pasar_por_wifi_el_login_es_el_de_siempre(self, client, app_de_google):
        contenido = client.get(reverse("account_login")).content.decode()
        assert "Acceso a la WiFi del centro" not in contenido

    def test_venir_de_incidencias_no_contagia_la_piel_de_wifi(self, client, app_de_google):
        client.get("/incidencias/")
        contenido = client.get(reverse("account_login")).content.decode()
        assert "Acceso a la WiFi del centro" not in contenido


@pytest.mark.django_db
class TestRemitenteEnLaPagina:
    def test_la_pagina_dice_de_quien_viene_el_correo(self, client, settings):
        settings.DEFAULT_FROM_EMAIL = "Martina Bescós App <app.gestion.admin@iesmartinabescos.es>"
        user = PersonalFactory()
        client.force_login(user)

        contenido = client.get("/wifi/").content.decode()

        # La dirección, sin el nombre para mostrar.
        assert "app.gestion.admin@iesmartinabescos.es" in contenido
        assert "Martina Bescós App &lt;" not in contenido
        # Y a quién le llega.
        assert user.email in contenido
        assert "spam" in contenido
