import pytest
from django.core import mail

from ..models import DispositivoWifi
from ..tasks import enviar_avisos_alta
from .factories import DispositivoWifiFactory


@pytest.mark.django_db
class TestAvisoDeAlta:
    def test_el_cuerpo_es_el_texto_acordado_con_el_ssid_y_la_clave(self, settings):
        settings.WIFI_SSID = "MARTINABESCOS"
        settings.WIFI_PASSWORD = "clave-de-prueba"
        dispositivo = DispositivoWifiFactory()
        dispositivo.marcar_anadida()

        enviar_avisos_alta([dispositivo.pk])

        assert len(mail.outbox) == 1
        correo = mail.outbox[0]
        assert correo.to == [dispositivo.usuario.email]
        assert "MARTINABESCOS" in correo.subject

        cuerpo = correo.body
        assert "Tu dispositivo ha sido dado de alta en la red." in cuerpo
        assert "Puedes acceder a la red MARTINABESCOS con la contraseña clave-de-prueba" in cuerpo
        assert "no sabes quitar la MAC Aleatoria" in cuerpo
        assert "Un saludo." in cuerpo

    def test_sella_notificado_at(self, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        dispositivo = DispositivoWifiFactory()
        dispositivo.marcar_anadida()

        enviar_avisos_alta([dispositivo.pk])

        dispositivo.refresh_from_db()
        assert dispositivo.notificado_at is not None

    def test_no_reenvia_a_quien_ya_fue_avisado(self, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        dispositivo = DispositivoWifiFactory()
        dispositivo.marcar_anadida()

        enviar_avisos_alta([dispositivo.pk])
        enviar_avisos_alta([dispositivo.pk])

        assert len(mail.outbox) == 1

    def test_no_escribe_a_quien_no_esta_dado_de_alta(self, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        pendiente = DispositivoWifiFactory()

        enviar_avisos_alta([pendiente.pk])

        assert len(mail.outbox) == 0
        pendiente.refresh_from_db()
        assert pendiente.estado == DispositivoWifi.Estado.PENDIENTE

    def test_sin_clave_configurada_no_manda_nada_y_no_sella(self, settings):
        """La clave vive en el entorno. Si falta, mejor callar que mandar un correo vacío."""
        settings.WIFI_PASSWORD = ""
        dispositivo = DispositivoWifiFactory()
        dispositivo.marcar_anadida()

        # Con huey en modo inmediato la llamada devuelve un Result, no el entero:
        # lo que importa aquí son los efectos, no el valor de retorno.
        enviar_avisos_alta([dispositivo.pk])
        assert len(mail.outbox) == 0
        dispositivo.refresh_from_db()
        assert dispositivo.notificado_at is None
