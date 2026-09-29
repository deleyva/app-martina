"""Plantillas de plan: los instrumentos ya puestos y el reparto ya cuadrado.

**Por qué existen.** En la SPA del curso pasado (`~/Documents/notas`) los
instrumentos de cada evaluación venían escritos en `TERM_CONFIGS`: se abría y se
calificaba. Aquí un plan hay que montarlo en una rejilla criterio × instrumento,
que es la verdad legal pero no es por donde se empieza un lunes a primera hora.
Una plantilla es ese plan ya montado.

**Por qué en código y no en la base.** Son pocas, cambian una vez al año con la
programación, y así un test recorre todas y exige que cuadren con los pesos
legales de su marco. La siembra (`cargar_marcos_musica`) lee de aquí: no hay dos
tablas de reparto que mantener iguales.

**Empezar por plantilla crea siempre un plan nuevo y propio del grupo.** Nunca
se comparte: un plan compartido comparte también sus pruebas, y eso solo se
quiere cuando se elige a propósito.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from .models import Instrumento, MarcoEvaluacion, Plan, Reparto

# La escala del curso 26-27 (decisión de Jesús, 2026-09-29): se califica con
# letra. El valor es la nota 0-10 con la que entra en el cálculo.
ESCALA_AD = [
    {"etiqueta": "A", "valor": 10},
    {"etiqueta": "B", "valor": 8},
    {"etiqueta": "C", "valor": 6},
    {"etiqueta": "D", "valor": 4},
]

# Los nueve instrumentos. (nombre, abreviatura, escala, opciones)
INSTRUMENTOS = [
    ("Teoría", "Teoría", "opciones", ESCALA_AD),
    ("Sensorialidad", "Sensor.", "opciones", ESCALA_AD),
    ("Dictado rítmico", "D. rít.", "opciones", ESCALA_AD),
    ("Dictado melódico", "D. mel.", "opciones", ESCALA_AD),
    ("Lectura rítmica", "L. rít.", "opciones", ESCALA_AD),
    ("Lectura melódica", "L. mel.", "opciones", ESCALA_AD),
    ("Interpretación instrumental", "Interp.", "opciones", ESCALA_AD),
    ("Composición / trabajo", "Compos.", "opciones", ESCALA_AD),
    ("Cuaderno", "Cuad.", "opciones", ESCALA_AD),
]

# Reparto de partida. Cada instrumento: {criterio: porcentaje}. Cada
# marco tiene el suyo porque los pesos legales por criterio cambian.
REPARTO_3ESO = {
    "Teoría": {"1.2": 10, "1.3": 5},
    "Sensorialidad": {"1.1": 5, "1.3": 5},
    "Dictado rítmico": {"1.1": 5, "3.1": 5},
    "Dictado melódico": {"3.1": 5, "2.2": 5},
    "Lectura rítmica": {"3.2": 5, "3.3": 5},
    "Lectura melódica": {"3.2": 5, "3.3": 5},
    "Interpretación instrumental": {"2.1": 5, "2.2": 5},
    "Composición / trabajo": {"4.1": 10, "2.1": 5},
    "Cuaderno": {"4.2": 10},
}
# 1º: 1.1 15 · 1.2 15 · 1.3 10 · 2.1 5 · 2.2 5 · 3.1 15 · 3.2 15 · 3.3 10 · 4.1 5 · 4.2 5
REPARTO_1ESO = {
    "Teoría": {"1.2": 15, "1.3": 5},
    "Sensorialidad": {"1.1": 5, "1.3": 5},
    "Dictado rítmico": {"1.1": 5, "3.1": 5},
    "Dictado melódico": {"1.1": 5, "3.1": 5},
    "Lectura rítmica": {"3.1": 5, "3.2": 5},
    "Lectura melódica": {"3.2": 5, "3.3": 5},
    "Interpretación instrumental": {"3.2": 5, "3.3": 5},
    "Composición / trabajo": {"2.1": 5, "2.2": 5, "4.1": 5},
    "Cuaderno": {"4.2": 5},
}
# 4º: 1.1 30 · 1.2 10 · 2.1 5 · 2.2 5 · 3.1 20 · 3.2 10 · 3.3 10 · 4.1 5 · 4.2 5
REPARTO_4ESO = {
    "Teoría": {"1.1": 10, "1.2": 10},
    "Sensorialidad": {"1.1": 10},
    "Dictado rítmico": {"1.1": 5, "3.1": 5},
    "Dictado melódico": {"1.1": 5, "3.1": 5},
    "Lectura rítmica": {"3.1": 5, "3.2": 5},
    "Lectura melódica": {"3.1": 5, "3.3": 5},
    "Interpretación instrumental": {"3.2": 5, "3.3": 5},
    "Composición / trabajo": {"2.1": 5, "2.2": 5, "4.1": 5},
    "Cuaderno": {"4.2": 5},
}


@dataclass(frozen=True)
class Plantilla:
    clave: str
    nivel: str
    modalidad: str
    reparto: dict
    instrumentos: tuple = tuple(INSTRUMENTOS)

    @property
    def nombre(self) -> str:
        return f"{self.nivel} {self.modalidad}".strip()

    def resumen(self) -> list[dict]:
        """Lo que se dice en clase: cada instrumento y cuánto cuenta."""
        return [
            {"nombre": nombre, "peso": Decimal(sum(self.reparto[nombre].values()))}
            for nombre, _, _, _ in self.instrumentos
        ]

    def criterios(self) -> set[str]:
        return {codigo for celdas in self.reparto.values() for codigo in celdas}

    def marco_de(self, group) -> MarcoEvaluacion | None:
        """El marco de esta plantilla en la materia y el curso del grupo.

        `None` si no está cargado o si le falta algún criterio de los que la
        plantilla reparte: una plantilla que no puede cuadrar no se ofrece.
        """
        marco = MarcoEvaluacion.objects.filter(
            subject=group.subject,
            academic_year=group.academic_year,
            nivel=self.nivel,
            modalidad=self.modalidad,
        ).first()
        if marco is None:
            return None
        codigos = set(marco.criterios.values_list("codigo", flat=True))
        return marco if self.criterios() <= codigos else None

    def encaja_con(self, group) -> int:
        """Cuánto se parece al grupo. Solo ordena las sugerencias: nunca decide.

        El nivel no es un campo del grupo (fase 32), así que se mira la cifra de
        su nombre; la lengua sí lo es. Si el nombre no dice nada, las plantillas
        salen en su orden y elige el profesor.
        """
        cifra = re.search(r"\d", group.name)
        nivel = 2 if cifra and cifra.group() == self.nivel[0] else 0
        lengua = 1 if (self.modalidad == "bilingüe") == (group.idioma == "en") else 0
        return nivel + lengua

    @transaction.atomic
    def crear_plan(self, marco, trimestre: int, nombre: str) -> Plan:
        """Un plan nuevo, sin grupos, con los instrumentos y el reparto de la plantilla."""
        criterios = {c.codigo: c for c in marco.criterios.all()}
        plan = Plan.objects.create(marco=marco, trimestre=trimestre, nombre=nombre)
        for orden, (nombre_i, abreviatura, escala, opciones) in enumerate(self.instrumentos):
            instrumento = Instrumento.objects.create(
                plan=plan,
                nombre=nombre_i,
                abreviatura=abreviatura,
                orden=orden,
                escala=escala,
                opciones=[dict(o) for o in opciones],
            )
            Reparto.objects.bulk_create(
                [
                    Reparto(instrumento=instrumento, criterio=criterios[codigo], porcentaje=Decimal(pct))
                    for codigo, pct in self.reparto[nombre_i].items()
                ]
            )
        return plan


PLANTILLAS = [
    Plantilla("1eso-bil", "1º ESO", "bilingüe", REPARTO_1ESO),
    Plantilla("3eso", "3º ESO", "", REPARTO_3ESO),
    Plantilla("4eso-bil", "4º ESO", "bilingüe", REPARTO_4ESO),
]
POR_CLAVE = {p.clave: p for p in PLANTILLAS}


def plan_anterior(group, trimestre: int) -> Plan | None:
    """El plan del grupo en la evaluación más cercana: primero hacia atrás, luego hacia delante."""
    planes = {p.trimestre: p for p in group.planes_calificacion.all()}
    for t in sorted(planes, key=lambda t: (t > trimestre, abs(t - trimestre))):
        if t != trimestre:
            return planes[t]
    return None


def opciones_para_empezar(group, trimestre: int) -> dict:
    """Lo que se le ofrece a un grupo sin plan, con su contenido a la vista."""
    anterior = plan_anterior(group, trimestre)
    plantillas = []
    for plantilla in sorted(PLANTILLAS, key=lambda p: -p.encaja_con(group)):
        if plantilla.marco_de(group) is None:
            continue
        plantillas.append(
            {
                "plantilla": plantilla,
                "resumen": plantilla.resumen(),
                "recomendada": plantilla.encaja_con(group) >= 2,
            }
        )
    return {
        "anterior": anterior,
        "anterior_resumen": anterior.resumen() if anterior else [],
        "plantillas": plantillas,
    }


def empezar(group, trimestre: int, clave: str) -> Plan | None:
    """El grupo estrena plan propio desde la plantilla. `None` si no existe o no hay marco."""
    plantilla = POR_CLAVE.get(clave)
    marco = plantilla.marco_de(group) if plantilla else None
    if marco is None:
        return None
    with transaction.atomic():
        plan = plantilla.crear_plan(marco, trimestre, f"{group.name} · {trimestre}ª ev.")
        plan.groups.add(group)
    return plan
