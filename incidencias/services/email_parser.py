# ruff: noqa: ERA001, E501
"""
Email-to-Incidencia Parser using Gemini AI.

Parses incoming emails (forwarded or direct) and extracts structured data
for creating Incidencia objects using Google Gemini.
"""

import json
import logging
import re
from typing import Any

from django.conf import settings
from google import genai

from incidencias.services.gemini_rate_limiter import GeminiRateLimiter

logger = logging.getLogger(__name__)


class EmailIncidenciaParser:
    """
    Parses email content using Gemini AI and extracts structured data
    to create Incidencia objects.

    Handles both:
    - Direct emails (From = actual sender)
    - Forwarded emails (From = cofotap, real sender in body)
    """

    MODEL_ID = "gemini-2.0-flash"
    CALLER_NAME = "email_parser"

    PROMPT_TEMPLATE = """Eres un asistente que extrae datos estructurados de emails para crear incidencias
en un sistema de gestión de incidencias informáticas de un centro educativo (IES Martina Bescós).

El email puede ser:
1. Un email REENVIADO: el remitente real está en el cuerpo del email (busca "From:", "De:", "Enviado por:", etc.)
2. Un email DIRECTO: el remitente es el campo "From" del email.

Analiza el siguiente email y extrae los datos en formato JSON.

=== EMAIL ===
Asunto: {subject}
De: {sender}
Cuerpo:
{body}
=== FIN EMAIL ===

=== UBICACIONES DISPONIBLES ===
{ubicaciones}
=== FIN UBICACIONES ===

=== ETIQUETAS EXISTENTES ===
{etiquetas}
=== FIN ETIQUETAS ===

Responde SOLO con un JSON válido con estos campos:
{{
    "titulo": "Título conciso de la incidencia (limpiando Re:, Fwd:, etc.)",
    "descripcion": "Descripción detallada del problema reportado",
    "reportero_nombre": "Nombre completo de la persona que reporta el problema (el remitente original, NO cofotap)",
    "urgencia": "baja|media|alta|critica (infiere del contenido; por defecto 'media')",
    "ubicacion_nombre": "Nombre exacto de la ubicación más probable de la lista proporcionada, o null si no se puede determinar",
    "etiquetas": ["lista de nombres de etiquetas existentes que apliquen"],
    "etiquetas_nuevas": ["lista de etiquetas nuevas sugeridas si ninguna existente es adecuada"],
    "es_privada": true
}}

REGLAS:
- titulo: Limpia prefijos como "Re:", "Fwd:", "RV:", "Reenviar:", etc.
- reportero_nombre: Si es un email reenviado, extrae el nombre del remitente original del cuerpo.
  Si no puedes determinarlo, usa el nombre del campo "De" del email.
- urgencia: "critica" solo si hay peligro o servicio crítico caído. "alta" si afecta a varios usuarios.
  "baja" para solicitudes menores. Por defecto "media".
- ubicacion_nombre: Escoge la ubicación existente que mejor coincida. Si no hay match, devuelve null.
- etiquetas: Usa SOLO nombres de la lista proporcionada.
- etiquetas_nuevas: Solo si ninguna etiqueta existente describe el problema.
- es_privada: true por defecto. false solo si el contenido solicita explícitamente la publicación.
- descripcion: Resume el problema claramente, incluyendo detalles técnicos relevantes.
"""

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not configured. Add it to .env file."
            )
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.rate_limiter = GeminiRateLimiter()

    def parse_email(
        self,
        subject: str,
        body: str,
        sender: str,
    ) -> dict[str, Any]:
        """
        Parse an email and extract structured data for creating an Incidencia.

        Returns a dict with keys:
            titulo, descripcion, reportero_nombre, urgencia,
            ubicacion_nombre, etiquetas, etiquetas_nuevas, es_privada
        """
        # Check rate limit before calling Gemini
        if not self.rate_limiter.can_call():
            logger.warning("Gemini rate limit exceeded, using fallback parsing")
            return self._fallback_parse(subject, body, sender)

        try:
            prompt = self._build_prompt(subject, body, sender)
            result = self._call_gemini(prompt)
            self.rate_limiter.register_call(
                caller=self.CALLER_NAME,
                success=True,
            )
            return self._validate_result(result)
        except Exception:
            logger.exception("Gemini parsing failed, using fallback")
            self.rate_limiter.register_call(
                caller=self.CALLER_NAME,
                success=False,
                error_message="Gemini parsing failed",
            )
            return self._fallback_parse(subject, body, sender)

    def _build_prompt(self, subject: str, body: str, sender: str) -> str:
        """Build the Gemini prompt with context from existing data."""
        from incidencias.models import Etiqueta, Ubicacion

        ubicaciones = list(
            Ubicacion.objects.values_list("nombre", flat=True).order_by("nombre")
        )
        etiquetas = list(
            Etiqueta.objects.values_list("nombre", flat=True).order_by("nombre")
        )

        return self.PROMPT_TEMPLATE.format(
            subject=subject,
            body=body[:3000],  # Limit body to avoid token overflow
            sender=sender,
            ubicaciones="\n".join(f"- {u}" for u in ubicaciones) if ubicaciones else "(ninguna definida)",
            etiquetas="\n".join(f"- {e}" for e in etiquetas) if etiquetas else "(ninguna definida)",
        )

    def _call_gemini(self, prompt: str) -> dict[str, Any]:
        """Call Gemini API with retry logic."""
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.MODEL_ID,
                    contents=prompt,
                )
                return self._parse_json_response(response.text)
            except json.JSONDecodeError:
                last_error = ValueError(f"Invalid JSON in Gemini response: {response.text[:200]}")
                logger.warning(
                    "Gemini returned invalid JSON (attempt %d/%d)",
                    attempt + 1,
                    max_retries,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Gemini API error (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    str(e),
                )

        raise last_error  # type: ignore[misc]

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Extract JSON from Gemini response, handling markdown code blocks."""
        # Strip markdown code block if present
        text = text.strip()
        if text.startswith("```"):
            # Remove ```json ... ``` wrapper
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    def _validate_result(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize the parsed result."""
        valid_urgencias = {"baja", "media", "alta", "critica"}

        return {
            "titulo": str(data.get("titulo", "")).strip() or "Sin título",
            "descripcion": str(data.get("descripcion", "")).strip() or "Sin descripción",
            "reportero_nombre": str(data.get("reportero_nombre", "")).strip() or "Desconocido",
            "urgencia": data.get("urgencia", "media") if data.get("urgencia") in valid_urgencias else "media",
            "ubicacion_nombre": data.get("ubicacion_nombre"),
            "etiquetas": data.get("etiquetas", []) or [],
            "etiquetas_nuevas": data.get("etiquetas_nuevas", []) or [],
            "es_privada": data.get("es_privada", True),
        }

    def _fallback_parse(
        self,
        subject: str,
        body: str,
        sender: str,
    ) -> dict[str, Any]:
        """Fallback parsing without Gemini — uses basic heuristics."""
        # Clean subject
        titulo = re.sub(
            r"^(Re:\s*|Fwd:\s*|RV:\s*|Reenviar:\s*)+",
            "",
            subject,
            flags=re.IGNORECASE,
        ).strip() or "Sin título"

        # Try to extract original sender from forwarded email body
        reportero = sender
        fwd_patterns = [
            r"(?:De|From|Enviado por)[:\s]+([^\n<]+)",
            r"(?:De|From)[:\s]*(?:<)?([^>\n]+)",
        ]
        for pattern in fwd_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                reportero = match.group(1).strip()
                break

        return {
            "titulo": titulo,
            "descripcion": body[:500].strip() if body else "Sin descripción",
            "reportero_nombre": reportero,
            "urgencia": "media",
            "ubicacion_nombre": None,
            "etiquetas": [],
            "etiquetas_nuevas": [],
            "es_privada": True,
        }
