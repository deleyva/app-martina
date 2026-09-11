"""Un comentario de plantilla partido en dos líneas se PINTA en pantalla.

En Django los `{# #}` son de UNA sola línea. Partidos, dejan de ser comentario y
salen como texto, a tamaño completo, en mitad de la interfaz.

**Este repo ha tropezado cuatro veces** con lo mismo: fases 16 y 23, el
2026-09-08 en la lista de sesiones, y el 2026-09-11 en la pantalla de elementos.
Escribirlo en el ISA no bastó para evitar la cuarta, así que ahora lo comprueba
la suite: es la diferencia entre una nota y un guarda.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EXCLUIDOS = ("node_modules", ".venv", "staticfiles", "site-packages")


def _plantillas():
    for fichero in RAIZ.rglob("*.html"):
        if any(x in str(fichero) for x in EXCLUIDOS):
            continue
        yield fichero


def test_ningun_comentario_de_plantilla_ocupa_mas_de_una_linea():
    culpables = []
    for fichero in _plantillas():
        texto = fichero.read_text(encoding="utf-8", errors="ignore")
        for encontrado in re.finditer(r"\{#(.*?)#\}", texto, re.S):
            if "\n" in encontrado.group(1):
                linea = texto[: encontrado.start()].count("\n") + 1
                culpables.append(f"{fichero.relative_to(RAIZ)}:{linea}")

    assert not culpables, (
        "Estos comentarios se van a PINTAR en pantalla; usa {% comment %}:\n  "
        + "\n  ".join(culpables)
    )
