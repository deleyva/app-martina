import pytest
from django.conf import settings

from incidencias.services.notification_service import (
    IncidenciaNotificationService,
    _username_to_email,
)
from incidencias.tests.factories import ComentarioFactory, IncidenciaFactory, TecnicoFactory


@pytest.mark.django_db
class TestNotificationService:
    def test_username_to_email_with_domain(self):
        """Si el username ya tiene @, se devuelve tal cual."""
        assert _username_to_email("pepe@gmail.com") == "pepe@gmail.com"

    def test_username_to_email_without_domain(self):
        """Si el username no tiene @, se le añade el dominio configurado."""
        assert _username_to_email("pepe") == f"pepe@{settings.DEFAULT_USER_EMAIL_DOMAIN}"

    def test_username_to_email_empty(self):
        """Si el username está vacío, se devuelve None."""
        assert _username_to_email("") is None
        assert _username_to_email("   ") is None

    def test_get_participant_emails_includes_reporter(self):
        incidencia = IncidenciaFactory(reportero_nombre="reportero_test")
        emails = IncidenciaNotificationService.get_participant_emails(incidencia)
        
        expected_email = f"reportero_test@{settings.DEFAULT_USER_EMAIL_DOMAIN}"
        assert expected_email in emails

    def test_get_participant_emails_includes_tecnico(self):
        tecnico = TecnicoFactory(user__email="tecnico@iesmartinabescos.es")
        incidencia = IncidenciaFactory(asignado_a=tecnico)
        emails = IncidenciaNotificationService.get_participant_emails(incidencia)
        assert "tecnico@iesmartinabescos.es" in emails

    def test_get_participant_emails_includes_commenters(self):
        incidencia = IncidenciaFactory()
        ComentarioFactory(incidencia=incidencia, autor_nombre="comentarista1")
        ComentarioFactory(incidencia=incidencia, autor_nombre="comentarista2@gmail.com")
        
        emails = IncidenciaNotificationService.get_participant_emails(incidencia)
        
        expected_email1 = f"comentarista1@{settings.DEFAULT_USER_EMAIL_DOMAIN}"
        assert expected_email1 in emails
        assert "comentarista2@gmail.com" in emails

    def test_get_participant_emails_deduplicates(self):
        tecnico = TecnicoFactory(user__email="tecnico@iesmartinabescos.es")
        incidencia = IncidenciaFactory(
            reportero_nombre="tecnico", # Same username as tech's email start 
            asignado_a=tecnico
        )
        
        ComentarioFactory(incidencia=incidencia, autor_nombre="tecnico")
        ComentarioFactory(incidencia=incidencia, autor_nombre="tecnico@iesmartinabescos.es")

        # Set default domain to match the tehcnico for this test
        settings.DEFAULT_USER_EMAIL_DOMAIN = "iesmartinabescos.es"
        
        emails = IncidenciaNotificationService.get_participant_emails(incidencia)
        
        assert len(emails) == 1
        assert "tecnico@iesmartinabescos.es" in emails

    def test_get_participant_emails_ignores_empty_fields(self):
        incidencia = IncidenciaFactory(reportero_nombre="", asignado_a=None)
        ComentarioFactory(incidencia=incidencia, autor_nombre="")
        
        emails = IncidenciaNotificationService.get_participant_emails(incidencia)
        assert len(emails) == 0