"""Matricula al alumnado de una lista del centro en los grupos de la app.

La lista viene de la gestión del centro (SIGAD cruzado con Google Workspace) con
las columnas `Nombre;Apellidos;Curso;Grupo;mail`. Los grupos del centro («3º E»)
no se llaman como los de la app («3-EG-BIL»), y a menudo dos del centro caen en
uno de la app; por eso el mapa va en la línea de comandos y no se adivina.

A cada alumno se le precrea el usuario si no existe —sin contraseña, con el
correo verificado— para que el día que entre con Google caiga en su cuenta y
vea su grupo. Quien no tiene correo del centro no entra con Google, así que se
salta y se cuenta, no se inventa nada.

Sin `--aplicar` solo enseña lo que haría. **No imprime nombres ni correos**:
la salida acaba en terminales, logs y transcripciones, y la lista es de
menores. Con `--nombres` los enseña, para depurar una fila concreta.

    python manage.py matricular_alumnado lista.csv \\
        --grupo "1º G=1-G-BIL" --grupo "3º E=3-EG-BIL" --grupo "3º G=3-EG-BIL" \\
        --curso 2026-2027 --aplicar

Con `-` como fichero lee de la entrada estándar, que es como se le pasa la
lista a producción sin dejarla en el servidor:

    ssh servidor "docker compose ... run --rm -T django python manage.py \\
        matricular_alumnado - --grupo ... --aplicar" < lista.csv
"""

import csv
import io
import sys
from collections import Counter
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clases.models import Group

COLUMNAS = ("Nombre", "Apellidos", "Grupo", "mail")


def curso_academico_actual(hoy=None):
    """«2026-2027» de septiembre a agosto: el curso empieza en septiembre."""
    hoy = hoy or date.today()
    inicio = hoy.year if hoy.month >= 9 else hoy.year - 1
    return f"{inicio}-{inicio + 1}"


def dominios_del_centro():
    return {
        d.strip().lower().lstrip("@")
        for d in getattr(settings, "SOCIAL_LOGIN_DOMAINS", [])
        if d.strip()
    }


class Command(BaseCommand):
    help = "Matricula alumnado de un CSV del centro en grupos de la app. Sin --aplicar, solo cuenta."

    def add_arguments(self, parser):
        parser.add_argument("csv", help="Ruta del CSV, o - para leer de la entrada estándar")
        parser.add_argument(
            "--grupo",
            action="append",
            default=[],
            metavar="CENTRO=APP",
            help='Mapa de grupo del centro a grupo de la app, ej: "3º E=3-EG-BIL". Repetible',
        )
        parser.add_argument(
            "--curso",
            default=curso_academico_actual(),
            help="Curso académico de los grupos de la app. Por defecto, el actual",
        )
        parser.add_argument(
            "--asignatura",
            default="MUS",
            help="Código de la asignatura de los grupos. Por defecto MUS",
        )
        parser.add_argument("--separador", default=";", help="Separador del CSV. Por defecto ;")
        parser.add_argument(
            "--aplicar", action="store_true", help="Escribe. Sin esto solo cuenta"
        )
        parser.add_argument(
            "--nombres",
            action="store_true",
            help="Imprime nombre y correo de cada fila. Por defecto no, que son menores",
        )

    def handle(self, *args, **options):
        mapa = self._mapa(options["grupo"])
        grupos = self._grupos(mapa, options["curso"], options["asignatura"])
        filas = self._filas(options["csv"], options["separador"])

        dominios = dominios_del_centro()
        User = get_user_model()

        resultado = Counter()
        por_grupo = {nombre: Counter() for nombre in mapa.values()}
        sin_mapa = Counter()

        with transaction.atomic():
            for fila in filas:
                grupo_centro = fila["Grupo"].strip()
                if grupo_centro not in mapa:
                    sin_mapa[grupo_centro] += 1
                    continue
                correo = fila["mail"].strip().lower()
                if correo.rsplit("@", 1)[-1] not in dominios:
                    resultado["sin correo del centro"] += 1
                    if options["nombres"]:
                        self.stdout.write(f"  · sin correo del centro: {fila['Nombre']} {fila['Apellidos']}")
                    continue

                grupo = grupos[mapa[grupo_centro]]
                if options["nombres"]:
                    self.stdout.write(f"  · {fila['Nombre']} {fila['Apellidos']} <{correo}> → {grupo.name}")
                if not options["aplicar"]:
                    existe = User.objects.filter(email__iexact=correo).exists()
                    resultado["usuarios ya existentes" if existe else "usuarios a crear"] += 1
                    por_grupo[grupo.name]["filas"] += 1
                    continue

                usuario, creado = User.objects.precrear_del_centro(
                    correo, fila["Nombre"], fila["Apellidos"]
                )
                resultado["usuarios creados" if creado else "usuarios ya existentes"] += 1
                por_grupo[grupo.name][grupo.matricular(usuario)] += 1

            if not options["aplicar"]:
                transaction.set_rollback(True)

        self._informe(options["aplicar"], resultado, por_grupo, sin_mapa)

    # -------------------------------------------------------------------------

    def _mapa(self, pares):
        if not pares:
            raise CommandError('Falta el mapa de grupos: --grupo "3º E=3-EG-BIL" (repetible)')
        mapa = {}
        for par in pares:
            if "=" not in par:
                raise CommandError(f"--grupo espera CENTRO=APP, no «{par}»")
            centro, app = (p.strip() for p in par.split("=", 1))
            if not centro or not app:
                raise CommandError(f"--grupo espera CENTRO=APP, no «{par}»")
            mapa[centro] = app
        return mapa

    def _grupos(self, mapa, curso, asignatura):
        nombres = sorted(set(mapa.values()))
        encontrados = {
            g.name: g
            for g in Group.objects.filter(
                name__in=nombres, academic_year=curso, subject__code=asignatura
            )
        }
        faltan = [n for n in nombres if n not in encontrados]
        if faltan:
            raise CommandError(
                f"No existen en la app ({asignatura}, {curso}): {', '.join(faltan)}. "
                "Créalos antes, o revisa --curso y --asignatura"
            )
        return encontrados

    def _filas(self, ruta, separador):
        if ruta == "-":
            texto = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8-sig").read()
        else:
            try:
                with open(ruta, encoding="utf-8-sig") as f:
                    texto = f.read()
            except OSError as e:
                raise CommandError(f"No puedo leer {ruta}: {e}") from e
        lector = csv.DictReader(io.StringIO(texto), delimiter=separador)
        faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
        if faltan:
            raise CommandError(f"Al CSV le faltan columnas: {', '.join(faltan)}")
        return [f for f in lector if any((v or "").strip() for v in f.values())]

    def _informe(self, aplicado, resultado, por_grupo, sin_mapa):
        self.stdout.write("Por grupo de la app:")
        for nombre in sorted(por_grupo):
            cuentas = por_grupo[nombre]
            detalle = ", ".join(f"{k} {v}" for k, v in sorted(cuentas.items())) or "nada"
            self.stdout.write(f"  {nombre}: {detalle}")
        for clave, n in sorted(resultado.items()):
            self.stdout.write(f"{clave}: {n}")
        if sin_mapa:
            self.stdout.write(
                self.style.WARNING(
                    "Filas saltadas por grupo sin mapa: "
                    + ", ".join(f"«{g}» {n}" for g, n in sorted(sin_mapa.items()))
                )
            )
        if aplicado:
            self.stdout.write(self.style.SUCCESS("Hecho."))
        else:
            self.stdout.write(
                self.style.WARNING("No se ha escrito nada. Repite con --aplicar si los números cuadran.")
            )
