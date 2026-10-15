"""Pone a cada alumno la foto de los listados con foto de secretaría.

    python manage.py importar_fotos_alumnado <carpeta>            # solo informa
    python manage.py importar_fotos_alumnado <carpeta> --aplicar  # guarda

`<carpeta>` es lo que deja `scripts/extraer_fotos_alumnado.ts` a partir de los
PDF: un JPEG por foto y un `manifest.json` con el nombre que iba debajo de
cada una. Este comando no lee PDF; solo empareja nombres.

**Cómo se empareja.** El PDF escribe «MARÍA BALAGUER CEBRIÁN» y la app puede
tener «María Balaguer Cebrián» o «Balaguer Cebrián, María». Se comparan las
palabras sin acentos, sin mayúsculas y sin orden. Si no hay coincidencia
exacta, vale una aproximada (todas las palabras de uno están en el otro, con
al menos dos en común) **solo si es única**. Lo dudoso no se guarda: sale en
el informe para ponerlo a mano en el admin.

Solo se miran alumnos matriculados en algún grupo; el profesorado no entra.
"""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from calificaciones.models import FotoAlumno


def palabras(nombre: str) -> frozenset[str]:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", nombre) if not unicodedata.combining(c)
    )
    limpio = "".join(c if c.isalnum() else " " for c in sin_acentos.lower())
    return frozenset(limpio.split())


def emparejar(nombre_pdf: str, alumnos: list) -> tuple[object | None, str]:
    """El alumno de ese nombre y cómo se ha encontrado: «exacta», «aproximada», «ambigua» o «ninguna»."""
    buscadas = palabras(nombre_pdf)
    exactas = [a for a in alumnos if palabras(a.name) == buscadas]
    if len(exactas) == 1:
        return exactas[0], "exacta"
    if len(exactas) > 1:
        return None, "ambigua"
    parecidas = [
        a
        for a in alumnos
        if len(palabras(a.name) & buscadas) >= 2
        and (palabras(a.name) <= buscadas or buscadas <= palabras(a.name))
    ]
    if len(parecidas) == 1:
        return parecidas[0], "aproximada"
    return None, "ambigua" if parecidas else "ninguna"


class Command(BaseCommand):
    help = "Empareja las fotos extraídas de los listados de secretaría con el alumnado y las guarda."

    def add_arguments(self, parser):
        parser.add_argument("carpeta")
        parser.add_argument("--aplicar", action="store_true", help="Guardar; sin esto solo informa.")
        parser.add_argument(
            "--reemplazar", action="store_true", help="Cambiar también las fotos que ya existen."
        )

    def handle(self, carpeta, aplicar, reemplazar, **opciones):
        carpeta = Path(carpeta)
        try:
            manifest = json.loads((carpeta / "manifest.json").read_text())
        except FileNotFoundError as e:
            raise CommandError(f"No hay manifest.json en {carpeta}") from e

        alumnos = list(
            get_user_model()
            .objects.filter(enrollments__is_active=True)
            .exclude(name="")
            .distinct()
        )
        con_foto = set(FotoAlumno.objects.values_list("alumno_id", flat=True))

        # Un alumno sale dos veces si está en un subgrupo (1º E FRAN, 4º DIVER):
        # es la misma foto, se queda la primera.
        vistos: set[str] = set()
        resultado = defaultdict(list)
        elegidas: dict[int, dict] = {}
        for entrada in manifest:
            clave = " ".join(sorted(palabras(entrada["nombre"])))
            if clave in vistos:
                continue
            vistos.add(clave)
            alumno, como = emparejar(entrada["nombre"], alumnos)
            if alumno is not None and alumno.pk in elegidas:
                como, alumno = "ambigua", None  # dos nombres del PDF caen en el mismo alumno
            resultado[como].append((entrada, alumno))
            if alumno is not None:
                elegidas[alumno.pk] = entrada

        self.stdout.write(f"Fotos distintas en el PDF: {len(vistos)}")
        for como in ("exacta", "aproximada", "ambigua", "ninguna"):
            self.stdout.write(f"  {como}: {len(resultado[como])}")
        for entrada, alumno in resultado["aproximada"]:
            self.stdout.write(f"  ~ {entrada['grupo']} «{entrada['nombre']}» → «{alumno.name}» ({alumno.pk})")
        for como in ("ambigua", "ninguna"):
            for entrada, _ in resultado[como]:
                self.stdout.write(f"  ✗ {como}: {entrada['grupo']} «{entrada['nombre']}»")

        guardables = [
            (e, a) for e, a in resultado["exacta"] + resultado["aproximada"] if reemplazar or a.pk not in con_foto
        ]
        if not aplicar:
            self.stdout.write(f"Se guardarían {len(guardables)}. Repite con --aplicar.")
            return

        with transaction.atomic():
            for entrada, alumno in guardables:
                anterior = FotoAlumno.objects.filter(alumno=alumno).first()
                if anterior:
                    anterior.delete()
                foto = FotoAlumno(alumno=alumno, origen=f"{entrada['pdf']}, p. {entrada['pagina']}")
                with open(carpeta / entrada["fichero"], "rb") as f:
                    foto.imagen.save(entrada["fichero"], File(f), save=False)
                foto.save()
        self.stdout.write(self.style.SUCCESS(f"Guardadas {len(guardables)} fotos."))
