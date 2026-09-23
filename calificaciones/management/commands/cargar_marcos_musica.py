"""Siembra los marcos de evaluación de Música desde las programaciones 26-27.

Tres marcos: 1º ESO bilingüe, 3º ESO y 4º ESO bilingüe, con los criterios y
sus pesos tal como están en `PRO_MUS*_26_27.docx` del departamento. Y para
cada marco, un plan de la 1ª evaluación con los nueve instrumentos de Jesús y
un reparto de partida que cuadra fila a fila. El reparto es un punto de
partida editable, no una regla.

Idempotente: se puede lanzar dos veces sin duplicar nada. Los criterios se
actualizan por (marco, código); los planes por defecto solo se crean si no
existe ya un plan con ese nombre en el marco.

    just manage cargar_marcos_musica --curso 2026-2027
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from calificaciones.models import Criterio, Instrumento, MarcoEvaluacion, Plan, Reparto
from clases.models import Subject

CRITERIOS_PRIMER_CICLO = [
    ("1.1", "CE.MU.1", "Identificar algunos de los principales rasgos estilísticos de obras musicales y dancísticas de diferentes épocas y culturas, evidenciando una actitud de apertura, interés y respeto en la escucha o el visionado de las mismas."),
    ("1.2", "CE.MU.1", "Explicar, con actitud abierta y respetuosa, las funciones desempeñadas por determinadas producciones musicales y dancísticas, relacionándolas con las principales características de su contexto histórico, social y cultural."),
    ("1.3", "CE.MU.1", "Establecer conexiones entre manifestaciones musicales y dancísticas de diferentes épocas y culturas, valorando su influencia sobre la música y la danza actuales."),
    ("2.1", "CE.MU.2", "Participar, con iniciativa, confianza y creatividad, en la exploración de técnicas musicales y dancísticas básicas, por medio de improvisaciones pautadas, individuales o grupales, en las que se empleen la voz, el cuerpo, instrumentos musicales o herramientas tecnológicas."),
    ("2.2", "CE.MU.2", "Expresar ideas, sentimientos y emociones en actividades pautadas de improvisación, seleccionando las técnicas más adecuadas de entre las que conforman el repertorio personal de recursos."),
    ("3.1", "CE.MU.3", "Leer partituras sencillas, identificando de forma guiada los elementos básicos del lenguaje musical, con o sin apoyo de la audición."),
    ("3.2", "CE.MU.3", "Emplear técnicas básicas de interpretación vocal, corporal o instrumental, aplicando estrategias de memorización y valorando los ensayos como espacios de escucha y aprendizaje."),
    ("3.3", "CE.MU.3", "Interpretar con corrección piezas musicales y dancísticas sencillas, individuales y grupales, dentro y fuera del aula, gestionando de forma guiada la ansiedad y el miedo escénico, y manteniendo la concentración."),
    ("4.1", "CE.MU.4", "Planificar y desarrollar, con creatividad, propuestas artístico-musicales, tanto individuales como colaborativas, empleando medios musicales y dancísticos, así como herramientas analógicas y digitales."),
    ("4.2", "CE.MU.4", "Participar activamente en la planificación y en la ejecución de propuestas artístico-musicales colaborativas, valorando las aportaciones del resto de integrantes del grupo y descubriendo oportunidades de desarrollo personal, social, académico y profesional."),
]

CRITERIOS_CUARTO = [
    ("1.1", "CE.MU.1", "Analizar obras musicales y dancísticas de diferentes épocas y culturas, identificando sus rasgos estilísticos, explicando su relación con el contexto y evidenciando una actitud de apertura, interés y respeto en la escucha o el visionado de las mismas."),
    ("1.2", "CE.MU.1", "Valorar críticamente los hábitos, los gustos y los referentes musicales y dancísticos de diferentes épocas y culturas, reflexionando sobre su evolución y sobre su relación con los del presente."),
    ("2.1", "CE.MU.2", "Participar, con iniciativa, confianza y creatividad, en la exploración de técnicas musicales y dancísticas básicas, por medio de improvisaciones pautadas, individuales o grupales, en las que se empleen la voz, el cuerpo, instrumentos musicales o herramientas tecnológicas."),
    ("2.2", "CE.MU.2", "Elaborar piezas musicales o dancísticas estructuradas, a partir de actividades de improvisación, seleccionando las técnicas del repertorio personal de recursos más adecuadas a la intención expresiva."),
    ("3.1", "CE.MU.3", "Leer partituras sencillas, identificando los elementos básicos del lenguaje musical y analizando de forma guiada las estructuras de las piezas, con o sin apoyo de la audición."),
    ("3.2", "CE.MU.3", "Emplear diferentes técnicas de interpretación vocal, corporal o instrumental, aplicando estrategias de memorización y valorando los ensayos como espacios de escucha y aprendizaje."),
    ("3.3", "CE.MU.3", "Interpretar con corrección piezas musicales y dancísticas sencillas, individuales y grupales, dentro y fuera del aula, gestionando de forma guiada la ansiedad y el miedo escénico, y manteniendo la concentración."),
    ("4.1", "CE.MU.4", "Planificar y desarrollar, con creatividad, propuestas artístico-musicales, tanto individuales como colaborativas, seleccionando, de entre los disponibles, los medios musicales y dancísticos más oportunos, así como las herramientas analógicas o digitales más adecuadas."),
    ("4.2", "CE.MU.4", "Participar activamente en la planificación y en la ejecución de propuestas artístico-musicales colaborativas, asumiendo diferentes funciones, valorando las aportaciones del resto de integrantes del grupo e identificando diversas oportunidades de desarrollo personal, social, académico y profesional."),
]

# Los pesos de cada programación, en el orden de los criterios de arriba.
PESOS_1ESO = [15, 15, 10, 5, 5, 15, 15, 10, 5, 5]
PESOS_3ESO = [10] * 10
PESOS_4ESO = [30, 10, 5, 5, 20, 10, 10, 5, 5]

# Los nueve instrumentos. (nombre, abreviatura, escala, opciones)
CUADERNO = [
    {"etiqueta": "Sin cuaderno", "valor": 0},
    {"etiqueta": "Incompleto", "valor": 3},
    {"etiqueta": "Bien", "valor": 6},
    {"etiqueta": "Muy bien", "valor": 9},
]
INSTRUMENTOS = [
    ("Teoría", "Teoría", "numerica", []),
    ("Sensorialidad", "Sensor.", "numerica", []),
    ("Dictado rítmico", "D. rít.", "numerica", []),
    ("Dictado melódico", "D. mel.", "numerica", []),
    ("Lectura rítmica", "L. rít.", "numerica", []),
    ("Lectura melódica", "L. mel.", "numerica", []),
    ("Interpretación instrumental", "Interp.", "numerica", []),
    ("Composición / trabajo", "Compos.", "numerica", []),
    ("Cuaderno", "Cuad.", "opciones", CUADERNO),
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

MARCOS = [
    ("1º ESO", "bilingüe", CRITERIOS_PRIMER_CICLO, PESOS_1ESO, {}, REPARTO_1ESO),
    ("3º ESO", "", CRITERIOS_PRIMER_CICLO, PESOS_3ESO, {"1": 20, "2": 30, "3": 50}, REPARTO_3ESO),
    ("4º ESO", "bilingüe", CRITERIOS_CUARTO, PESOS_4ESO, {}, REPARTO_4ESO),
]


class Command(BaseCommand):
    help = "Siembra los marcos de evaluación de Música (1º bil, 3º, 4º bil) y un plan por defecto."

    def add_arguments(self, parser):
        parser.add_argument("--curso", default="2026-2027", help="Curso académico, ej. 2026-2027")
        parser.add_argument("--materia", default="Música", help="Nombre de la asignatura en clases.Subject")

    @transaction.atomic
    def handle(self, *args, **options):
        subject = Subject.objects.filter(name__iexact=options["materia"]).first()
        if subject is None:
            subject = Subject.objects.create(name=options["materia"], code="MUS")
            self.stdout.write(f"Creada la asignatura {subject.name}")

        for nivel, modalidad, criterios, pesos, trimestres, reparto in MARCOS:
            marco, creado = MarcoEvaluacion.objects.get_or_create(
                subject=subject,
                nivel=nivel,
                modalidad=modalidad,
                academic_year=options["curso"],
                defaults={"peso_trimestres": trimestres},
            )
            if creado and trimestres:
                marco.peso_trimestres = trimestres
                marco.save(update_fields=["peso_trimestres"])
            por_codigo = {}
            for orden, ((codigo, competencia, texto), peso) in enumerate(zip(criterios, pesos)):
                criterio, _ = Criterio.objects.update_or_create(
                    marco=marco,
                    codigo=codigo,
                    defaults={
                        "competencia": competencia,
                        "descripcion": texto,
                        "peso": Decimal(peso),
                        "orden": orden,
                    },
                )
                por_codigo[codigo] = criterio
            assert marco.peso_total == 100, f"{marco}: los pesos suman {marco.peso_total}"

            nombre_plan = f"Plan por defecto · {nivel}{' ' + modalidad if modalidad else ''}"
            if marco.planes.filter(nombre=nombre_plan).exists():
                self.stdout.write(f"{marco}: plan por defecto ya existía")
                continue
            plan = Plan.objects.create(marco=marco, trimestre=1, nombre=nombre_plan)
            for orden, (nombre, abreviatura, escala, opciones) in enumerate(INSTRUMENTOS):
                instrumento = Instrumento.objects.create(
                    plan=plan,
                    nombre=nombre,
                    abreviatura=abreviatura,
                    orden=orden,
                    escala=escala,
                    opciones=opciones,
                )
                Reparto.objects.bulk_create(
                    [
                        Reparto(instrumento=instrumento, criterio=por_codigo[codigo], porcentaje=Decimal(pct))
                        for codigo, pct in reparto[nombre].items()
                    ]
                )
            cuadre = plan.cuadre()
            estado = "cuadra" if cuadre["cuadra"] else "NO CUADRA"
            self.stdout.write(f"{marco}: plan por defecto creado, {cuadre['total']} % · {estado}")
