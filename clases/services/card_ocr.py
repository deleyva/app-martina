"""
Study Card registration sheet OCR using Gemini Vision.

Reads a photo of a handwritten registration sheet and extracts
student names and card codes.
"""

import json
import logging

from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MODEL_ID = "gemini-2.0-flash"

PROMPT_TEMPLATE = """Analiza esta foto de una hoja de registro de tarjetas de estudio musical.

La hoja tiene una tabla con:
- Columna izquierda: nombres de alumnos (pre-impresos)
- Columnas de la derecha: códigos de tarjetas escritos A MANO por los alumnos

Los códigos tienen formato: LETRAS-NÚMERO-NÚMERO (ejemplos: MJG-1-03, LM-2-15, GD-1-07).
Las letras son abreviaturas de libros, seguidas de número de capítulo y número de imagen.

ALUMNOS MATRICULADOS en este grupo:
{student_names}

Para cada alumno que tenga códigos escritos, extrae los códigos.
Si un código es ilegible, intenta tu mejor lectura pero marca confidence bajo.

Responde SOLO con un JSON válido (sin markdown, sin ```):
[
  {{
    "student_name": "Nombre completo del alumno (usa el nombre de la lista de matriculados)",
    "codes": ["MJG-1-03", "LM-2-15"],
    "confidence": 0.9
  }}
]

Si no puedes leer ningún código, responde: []
Solo incluye alumnos que tengan al menos un código escrito.
"""


def ocr_registration_sheet(image_bytes, mime_type, student_names):
    """
    OCR a registration sheet photo using Gemini Vision.

    Args:
        image_bytes: Raw image bytes
        mime_type: Image MIME type (image/jpeg, image/png)
        student_names: List of student name strings for context

    Returns:
        tuple: (results_list, error_string_or_none)
        results_list: [{student_name: str, codes: [str], confidence: float}]
    """
    if not settings.GEMINI_API_KEY:
        return [], "GEMINI_API_KEY no configurada"

    prompt = PROMPT_TEMPLATE.format(
        student_names="\n".join(f"- {name}" for name in student_names)
    )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
        )

        text = response.text.strip()
        # Clean markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        results = json.loads(text)
        if not isinstance(results, list):
            return [], "Respuesta inesperada de Gemini"

        # Validate structure
        validated = []
        for entry in results:
            if isinstance(entry, dict) and "student_name" in entry and "codes" in entry:
                validated.append({
                    "student_name": entry["student_name"],
                    "codes": [c.strip().upper() for c in entry["codes"] if isinstance(c, str)],
                    "confidence": float(entry.get("confidence", 0.5)),
                })
        return validated, None

    except json.JSONDecodeError:
        logger.exception("Gemini OCR returned invalid JSON")
        return [], "No se pudo interpretar la respuesta de Gemini"
    except Exception as e:
        logger.exception("Gemini OCR failed")
        return [], f"Error en OCR: {e}"
