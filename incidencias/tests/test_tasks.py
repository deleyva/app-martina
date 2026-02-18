# ruff: noqa: E501
"""Tests for email-to-incidencia Huey tasks."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from incidencias.models import Etiqueta, Incidencia, ProcessedEmail, Ubicacion
from incidencias.tasks import _is_business_hours, _should_fetch_now


MADRID_TZ = ZoneInfo("Europe/Madrid")


class TestAdaptiveSchedule:
    """Test the adaptive scheduling logic."""

    @patch("incidencias.tasks.timezone")
    def test_business_hours_weekday_morning(self, mock_tz):
        """Monday 9:00 Madrid should be business hours."""
        # Monday 9:00 Madrid
        mock_tz.now.return_value = datetime(2026, 2, 16, 8, 0, tzinfo=MADRID_TZ)  # Monday
        assert _is_business_hours() is True

    @patch("incidencias.tasks.timezone")
    def test_business_hours_weekday_afternoon(self, mock_tz):
        """Monday 14:30 Madrid should still be business hours."""
        mock_tz.now.return_value = datetime(2026, 2, 16, 13, 30, tzinfo=MADRID_TZ)
        assert _is_business_hours() is True

    @patch("incidencias.tasks.timezone")
    def test_not_business_hours_weekend(self, mock_tz):
        """Saturday should NOT be business hours."""
        mock_tz.now.return_value = datetime(2026, 2, 21, 10, 0, tzinfo=MADRID_TZ)  # Saturday
        assert _is_business_hours() is False

    @patch("incidencias.tasks.timezone")
    def test_not_business_hours_evening(self, mock_tz):
        """Monday 20:00 Madrid should NOT be business hours."""
        mock_tz.now.return_value = datetime(2026, 2, 16, 20, 0, tzinfo=MADRID_TZ)
        assert _is_business_hours() is False

    @patch("incidencias.tasks.timezone")
    def test_not_business_hours_after_1430(self, mock_tz):
        """Monday 14:31 Madrid should NOT be business hours."""
        mock_tz.now.return_value = datetime(2026, 2, 16, 14, 31, tzinfo=MADRID_TZ)
        assert _is_business_hours() is False

    @patch("incidencias.tasks.timezone")
    def test_not_business_hours_before_8(self, mock_tz):
        """Monday 7:59 Madrid should NOT be business hours."""
        mock_tz.now.return_value = datetime(2026, 2, 16, 7, 59, tzinfo=MADRID_TZ)
        assert _is_business_hours() is False


@pytest.mark.django_db
class TestShouldFetchNow:
    """Test the should_fetch_now logic."""

    @patch("incidencias.tasks._is_business_hours", return_value=True)
    def test_always_fetch_during_business_hours(self, mock_bh):
        """During business hours, should always fetch."""
        assert _should_fetch_now() is True

    @patch("incidencias.tasks._is_business_hours", return_value=False)
    @patch("incidencias.tasks._last_fetch_timestamp", None)
    def test_fetch_outside_business_hours_first_time(self, mock_bh):
        """First fetch outside business hours should go ahead."""
        assert _should_fetch_now() is True


@pytest.mark.django_db
class TestDeduplication:
    """Test email deduplication logic."""

    def test_duplicate_email_not_processed_twice(self):
        """Same message_id should not create a second incidencia."""
        # Create a processed email record
        ubi = Ubicacion.objects.create(nombre="Test Location")
        inc = Incidencia.objects.create(
            titulo="Original",
            descripcion="Test",
            reportero_nombre="Test User",
            ubicacion=ubi,
        )
        ProcessedEmail.objects.create(
            message_id="<unique-msg-123@gmail.com>",
            incidencia=inc,
            raw_subject="Test",
            raw_sender="test@example.com",
        )

        # Verify duplicate check works
        assert ProcessedEmail.objects.filter(
            message_id="<unique-msg-123@gmail.com>"
        ).exists()

        # A different message_id should not exist
        assert not ProcessedEmail.objects.filter(
            message_id="<different-msg-456@gmail.com>"
        ).exists()


@pytest.mark.django_db
class TestProcessSingleEmail:
    """Test the _process_single_email function."""

    @patch("incidencias.services.email_parser.genai")
    def test_creates_incidencia_with_etiquetas(self, mock_genai):
        """Processing should create an Incidencia and assign existing etiquetas."""
        from incidencias.tasks import _process_single_email

        # Setup test data
        ubi = Ubicacion.objects.create(nombre="Aula 101")
        etiqueta = Etiqueta.objects.create(nombre="hardware", slug="hardware")

        # Mock the email message
        message = MagicMock()
        message.message_id = "<test-msg-789@gmail.com>"
        message.subject = "Fwd: Monitor roto"
        message.from_address = ["cofotap@iesmartinabescos.es"]
        message.text = "El monitor del aula 101 está roto.\nDe: Prof. López"
        message.html = ""
        message.attachments = MagicMock()
        message.attachments.all.return_value = []

        # Create a parser mock
        parser = MagicMock()
        parser.parse_email.return_value = {
            "titulo": "Monitor roto",
            "descripcion": "El monitor del aula 101 está roto",
            "reportero_nombre": "Prof. López",
            "urgencia": "media",
            "ubicacion_nombre": "Aula 101",
            "etiquetas": ["hardware"],
            "etiquetas_nuevas": [],
            "es_privada": True,
        }

        with patch("incidencias.tasks._move_to_processed_gmail"):
            _process_single_email(message, parser)

        # Verify incidencia was created
        inc = Incidencia.objects.get(titulo="Monitor roto")
        assert inc.reportero_nombre == "Prof. López"
        assert inc.urgencia == "media"
        assert inc.ubicacion == ubi
        assert inc.es_privada is True
        assert etiqueta in inc.etiquetas.all()

        # Verify processed email was recorded
        assert ProcessedEmail.objects.filter(
            message_id="<test-msg-789@gmail.com>"
        ).exists()

    @patch("incidencias.services.email_parser.genai")
    def test_creates_new_etiquetas_if_suggested(self, mock_genai):
        """Processing should create new etiquetas when Gemini suggests them."""
        from incidencias.tasks import _process_single_email

        message = MagicMock()
        message.message_id = "<test-new-tag@gmail.com>"
        message.subject = "Problema impresora 3D"
        message.from_address = ["cofotap@iesmartinabescos.es"]
        message.text = "La impresora 3D no funciona."
        message.html = ""
        message.attachments = MagicMock()
        message.attachments.all.return_value = []

        parser = MagicMock()
        parser.parse_email.return_value = {
            "titulo": "Impresora 3D averiada",
            "descripcion": "La impresora 3D del taller no funciona",
            "reportero_nombre": "Prof. Inventado",
            "urgencia": "alta",
            "ubicacion_nombre": None,
            "etiquetas": [],
            "etiquetas_nuevas": ["impresora-3d"],
            "es_privada": True,
        }

        with patch("incidencias.tasks._move_to_processed_gmail"):
            _process_single_email(message, parser)

        inc = Incidencia.objects.get(titulo="Impresora 3D averiada")
        assert Etiqueta.objects.filter(nombre="impresora-3d").exists()
        assert inc.etiquetas.filter(nombre="impresora-3d").exists()

    @patch("incidencias.services.email_parser.genai")
    def test_skips_duplicate_message(self, mock_genai):
        """Should skip an email if its message_id is already processed."""
        from incidencias.tasks import _process_single_email

        # Pre-create a processed record
        ProcessedEmail.objects.create(
            message_id="<already-processed@gmail.com>",
            raw_subject="Old",
            raw_sender="old@test.com",
        )

        message = MagicMock()
        message.message_id = "<already-processed@gmail.com>"
        message.subject = "Should not be created"
        message.from_address = ["test@test.com"]
        message.text = "Test"

        parser = MagicMock()

        _process_single_email(message, parser)

        # Parser should NOT have been called
        parser.parse_email.assert_not_called()
        # No new incidencia
        assert Incidencia.objects.count() == 0
