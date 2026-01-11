"""
AI Metadata Extractor Service

Uses Google Gemini to extract structured metadata from natural language descriptions
of musical content.
"""

import json
import logging
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class AIMetadataExtractor:
    """
    Extract structured metadata from natural language descriptions using Google Gemini.
    """

    PROMPT_TEMPLATE = """Eres un asistente experto en catalogación musical. El usuario ha subido archivos musicales y ha proporcionado la siguiente descripción:

DESCRIPCIÓN:
{description}

ARCHIVOS SUBIDOS:
{file_names}

Tu tarea es extraer la siguiente información estructurada en formato JSON:

{{
  "title": "Título de la obra musical",
  "composer": "Nombre del compositor o autor",
  "key_signature": "Tonalidad (ej: C mayor, F# menor, D menor)",
  "tempo": "Indicación de tempo (ej: Allegro, Andante, 120 BPM)",
  "time_signature": "Compás (ej: 4/4, 3/4, 6/8)",
  "difficulty": "Nivel de dificultad: beginner, easy, intermediate, advanced, o expert",
  "duration_minutes": Duración aproximada en minutos (número entero o null),
  "reference_catalog": "Número de catálogo, opus, BWV, etc.",
  "categories": ["Lista", "de", "categorías"],
  "tags": ["Lista", "de", "etiquetas"],
  "description": "Descripción mejorada y completa de la obra",
  "notes": "Notas adicionales sobre la interpretación, técnicas, etc."
}}

REGLAS:
- Si algún campo no se puede determinar, usa "" para strings, [] para arrays, o null para números
- Las categorías deben ser genéricas y en español (ej: "Jazz", "Clásica", "Pop", "Rock", "Folk", "Vocal", "Instrumental")
- Los tags deben ser descriptivos y en español (ej: "vocal", "piano", "guitarra", "ejercicio", "principiante", "avanzado")
- El título debe ser claro y conciso
- Difficulty debe ser una de estas opciones exactas: beginner, easy, intermediate, advanced, expert
- La descripción mejorada debe ser clara, informativa y en español
- Las notas deben incluir consejos prácticos para el intérprete

Responde SOLO con el JSON válido, sin texto adicional antes o después. No uses markdown code blocks.
"""

    DEFAULT_METADATA = {
        "title": "Sin título",
        "composer": "",
        "key_signature": "",
        "tempo": "",
        "time_signature": "",
        "difficulty": "",
        "duration_minutes": None,
        "reference_catalog": "",
        "categories": [],
        "tags": [],
        "description": "",
        "notes": "",
    }

    def __init__(self):
        """Initialize the AI metadata extractor with Gemini API."""
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not configured in settings. "
                "Please add it to your .env file."
            )

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = "gemini-2.0-flash-exp"  # Latest fast model

    def extract_metadata(
        self, description: str, file_names: list[str]
    ) -> dict[str, Any]:
        """
        Extract structured metadata from a natural language description.

        Args:
            description: Natural language description of the musical content
            file_names: List of uploaded file names (for context)

        Returns:
            Dictionary with extracted metadata fields

        Raises:
            ValueError: If description is empty
            RuntimeError: If API call fails after retries
        """
        if not description or not description.strip():
            raise ValueError("Description cannot be empty")

        # Format file names for the prompt
        formatted_files = "\n".join(f"- {name}" for name in file_names) if file_names else "- (ningún archivo especificado)"

        # Build the prompt
        prompt = self.PROMPT_TEMPLATE.format(
            description=description.strip(), file_names=formatted_files
        )

        logger.info(
            f"Extracting metadata with AI for description: {description[:100]}..."
        )

        try:
            # Call Gemini API with retry logic
            metadata = self._call_gemini_with_retry(prompt)
            logger.info(f"Successfully extracted metadata: {metadata.get('title', 'N/A')}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to extract metadata after retries: {e}")
            # Return default metadata with original description
            fallback = self.DEFAULT_METADATA.copy()
            fallback["description"] = description
            fallback["notes"] = "Metadata extraída automáticamente no disponible. Por favor, completa manualmente."
            return fallback

    def _call_gemini_with_retry(
        self, prompt: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Call Gemini API with exponential backoff retry logic.

        Args:
            prompt: The prompt to send to Gemini
            max_retries: Maximum number of retry attempts

        Returns:
            Extracted metadata dictionary

        Raises:
            RuntimeError: If all retries fail
        """
        import time

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # Low temperature for consistent output
                        max_output_tokens=2048,
                        response_mime_type="application/json",  # Request JSON response
                    ),
                )

                # Extract text from response
                response_text = response.text.strip()

                # Parse JSON
                metadata = self._parse_json_response(response_text)

                # Validate and normalize metadata
                metadata = self._validate_and_normalize(metadata)

                return metadata

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries}: JSON parsing failed: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries}: API call failed: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

        raise RuntimeError(
            f"Failed to extract metadata after {max_retries} attempts"
        )

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse JSON response, handling common formatting issues.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: If parsing fails
        """
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove trailing ```

        response_text = response_text.strip()

        return json.loads(response_text)

    def _validate_and_normalize(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and normalize extracted metadata.

        Args:
            metadata: Raw metadata dictionary from AI

        Returns:
            Validated and normalized metadata dictionary
        """
        # Start with defaults
        normalized = self.DEFAULT_METADATA.copy()

        # Validate difficulty
        valid_difficulties = {"beginner", "easy", "intermediate", "advanced", "expert"}
        difficulty = metadata.get("difficulty", "").lower()
        if difficulty in valid_difficulties:
            normalized["difficulty"] = difficulty
        else:
            normalized["difficulty"] = ""

        # Validate and normalize strings
        for field in [
            "title",
            "composer",
            "key_signature",
            "tempo",
            "time_signature",
            "reference_catalog",
            "description",
            "notes",
        ]:
            value = metadata.get(field, "")
            normalized[field] = str(value).strip() if value else ""

        # Validate duration_minutes (must be positive integer or null)
        duration = metadata.get("duration_minutes")
        if duration is not None:
            try:
                duration = int(duration)
                if duration > 0:
                    normalized["duration_minutes"] = duration
            except (ValueError, TypeError):
                pass

        # Validate lists
        for field in ["categories", "tags"]:
            value = metadata.get(field, [])
            if isinstance(value, list):
                # Filter out empty strings and deduplicate
                normalized[field] = list(
                    {item.strip() for item in value if item and str(item).strip()}
                )
            else:
                normalized[field] = []

        return normalized
