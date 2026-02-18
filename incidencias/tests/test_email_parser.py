# ruff: noqa: E501
"""Tests for EmailIncidenciaParser service."""

import json
from unittest.mock import MagicMock, patch

import pytest

from incidencias.services.email_parser import EmailIncidenciaParser


@pytest.fixture
def mock_gemini_response():
    """Factory fixture for creating mock Gemini responses."""
    def _make_response(data: dict):
        mock_response = MagicMock()
        mock_response.text = json.dumps(data)
        return mock_response
    return _make_response


@pytest.fixture
def parser():
    """Create a parser instance with mocked Gemini client."""
    with patch("incidencias.services.email_parser.genai"):
        with patch.object(EmailIncidenciaParser, "__init__", lambda self: None):
            p = EmailIncidenciaParser.__new__(EmailIncidenciaParser)
            p.client = MagicMock()
            p.rate_limiter = MagicMock()
            p.rate_limiter.can_call.return_value = True
            return p


@pytest.mark.django_db
class TestEmailParserForwardedEmail:
    """Test parsing of forwarded emails."""

    def test_parse_forwarded_email_extracts_original_sender(self, parser, mock_gemini_response):
        """Gemini should extract the original sender from forwarded email body."""
        gemini_data = {
            "titulo": "Impresora no funciona en Sala A",
            "descripcion": "La impresora HP del aula A no imprime. Sale un error de papel atascado.",
            "reportero_nombre": "Prof. García López",
            "urgencia": "media",
            "ubicacion_nombre": "Aula A",
            "etiquetas": ["hardware"],
            "etiquetas_nuevas": [],
            "es_privada": True,
        }
        parser.client.models.generate_content.return_value = mock_gemini_response(gemini_data)

        result = parser.parse_email(
            subject="Fwd: Impresora rota",
            body="---------- Forwarded message ----------\nDe: Prof. García López <garcia@iesmartinabescos.es>\n\nLa impresora HP del aula A no imprime.",
            sender="cofotap@iesmartinabescos.es",
        )

        assert result["reportero_nombre"] == "Prof. García López"
        assert result["titulo"] == "Impresora no funciona en Sala A"
        assert result["urgencia"] == "media"


@pytest.mark.django_db
class TestEmailParserDirectEmail:
    """Test parsing of direct (non-forwarded) emails."""

    def test_parse_direct_email(self, parser, mock_gemini_response):
        """Direct email should use 'From' as the reporter."""
        gemini_data = {
            "titulo": "Proyector sin imagen",
            "descripcion": "El proyector del aula 204 no enciende.",
            "reportero_nombre": "Ana Martínez",
            "urgencia": "alta",
            "ubicacion_nombre": None,
            "etiquetas": ["hardware"],
            "etiquetas_nuevas": ["proyector"],
            "es_privada": True,
        }
        parser.client.models.generate_content.return_value = mock_gemini_response(gemini_data)

        result = parser.parse_email(
            subject="Proyector sin imagen",
            body="El proyector del aula 204 no enciende desde esta mañana.",
            sender="ana.martinez@iesmartinabescos.es",
        )

        assert result["reportero_nombre"] == "Ana Martínez"
        assert result["urgencia"] == "alta"
        assert "proyector" in result["etiquetas_nuevas"]


@pytest.mark.django_db
class TestEmailParserFallback:
    """Test fallback parsing when Gemini fails."""

    def test_fallback_on_rate_limit(self, parser):
        """When rate limit is exceeded, fallback parsing should be used."""
        parser.rate_limiter.can_call.return_value = False

        result = parser.parse_email(
            subject="Fwd: Re: Wifi caído",
            body="---------- Forwarded ----------\nDe: Pedro Ruiz <pruiz@iesmartinabescos.es>\n\nEl wifi no funciona.",
            sender="cofotap@iesmartinabescos.es",
        )

        # Fallback should clean the subject
        assert result["titulo"] == "Wifi caído"
        assert result["urgencia"] == "media"
        assert result["es_privada"] is True

    def test_fallback_on_gemini_error(self, parser):
        """When Gemini raises an exception, fallback should be used."""
        parser.client.models.generate_content.side_effect = Exception("API Error")

        result = parser.parse_email(
            subject="Re: Problema con el ordenador",
            body="El ordenador del despacho no arranca.",
            sender="profesor@iesmartinabescos.es",
        )

        assert result["titulo"] == "Problema con el ordenador"
        assert result["urgencia"] == "media"
        assert result["descripcion"] != ""

    def test_fallback_cleans_multiple_prefixes(self, parser):
        """Fallback should clean multiple Re:/Fwd: prefixes."""
        parser.rate_limiter.can_call.return_value = False

        result = parser.parse_email(
            subject="Fwd: Re: Fwd: RV: Teclado roto",
            body="Un teclado está roto",
            sender="cofotap@iesmartinabescos.es",
        )

        assert result["titulo"] == "Teclado roto"


@pytest.mark.django_db
class TestEmailParserValidation:
    """Test result validation and normalization."""

    def test_invalid_urgencia_defaults_to_media(self, parser, mock_gemini_response):
        """Invalid urgency values should default to 'media'."""
        gemini_data = {
            "titulo": "Test",
            "descripcion": "Description",
            "reportero_nombre": "User",
            "urgencia": "super_urgente",  # invalid
            "ubicacion_nombre": None,
            "etiquetas": [],
            "etiquetas_nuevas": [],
            "es_privada": True,
        }
        parser.client.models.generate_content.return_value = mock_gemini_response(gemini_data)

        result = parser.parse_email(
            subject="Test",
            body="Test body",
            sender="user@test.com",
        )

        assert result["urgencia"] == "media"

    def test_empty_titulo_defaults_to_sin_titulo(self, parser, mock_gemini_response):
        """Empty title should default to 'Sin título'."""
        gemini_data = {
            "titulo": "",
            "descripcion": "Some desc",
            "reportero_nombre": "User",
            "urgencia": "media",
            "ubicacion_nombre": None,
            "etiquetas": [],
            "etiquetas_nuevas": [],
            "es_privada": True,
        }
        parser.client.models.generate_content.return_value = mock_gemini_response(gemini_data)

        result = parser.parse_email(
            subject="",
            body="Test",
            sender="user@test.com",
        )

        assert result["titulo"] == "Sin título"

    def test_es_privada_defaults_to_true(self, parser, mock_gemini_response):
        """es_privada should default to True."""
        gemini_data = {
            "titulo": "Test",
            "descripcion": "Desc",
            "reportero_nombre": "User",
            "urgencia": "baja",
            "ubicacion_nombre": None,
            "etiquetas": [],
            "etiquetas_nuevas": [],
            # es_privada missing
        }
        parser.client.models.generate_content.return_value = mock_gemini_response(gemini_data)

        result = parser.parse_email(
            subject="Test",
            body="Test",
            sender="user@test.com",
        )

        assert result["es_privada"] is True

    def test_json_in_code_block_is_parsed(self, parser):
        """Gemini sometimes wraps JSON in ```json ... ``` — parser should handle it."""
        mock_response = MagicMock()
        mock_response.text = '```json\n{"titulo": "Test", "descripcion": "Desc", "reportero_nombre": "User", "urgencia": "media", "ubicacion_nombre": null, "etiquetas": [], "etiquetas_nuevas": [], "es_privada": true}\n```'
        parser.client.models.generate_content.return_value = mock_response

        result = parser.parse_email(
            subject="Test",
            body="Test body",
            sender="user@test.com",
        )

        assert result["titulo"] == "Test"
