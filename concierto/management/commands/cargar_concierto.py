"""Carga los datos del concierto desde el CSV y crea las tareas de voluntariado."""

from django.core.management.base import BaseCommand

from concierto.models import Acto
from concierto.models import Tarea


# Datos del CSV (Final 25-26 v3)
ACTOS_DATA = [
    {
        "orden": 1,
        "artistas": "Alumnado de 1o de ESO",
        "canciones": "Sinfonia no 5 con mucho ritmo",
        "autores": "Beethoven",
        "material": "Sillas (las sacaran los chicos en el momento)",
        "duracion": 8,
    },
    {
        "orden": 2,
        "artistas": "Coro",
        "canciones": "Makumana\nEl Pescador\nViva la vida",
        "autores": "Jose Benito Barros Palomino / Cold Play",
        "material": "Teclado",
        "duracion": 15,
    },
    {
        "orden": 3,
        "artistas": "Lucia Mitchell Gonzalez de Aguero",
        "canciones": "Little Again\nDrowning in memories",
        "autores": "Lu Mitchell",
        "material": "Microfono y amplificador para su guitarra",
        "duracion": 10,
    },
    {
        "orden": 4,
        "artistas": "Eduardo Artigas Pico, Francisco Javier Revilla Benito, Alejandro Corella Escario, Jesus Lopez de Leyva",
        "canciones": "Hoy por hoy\nPlug in baby",
        "autores": "Eduardo Luka / Muse",
        "material": "",
        "duracion": 7,
    },
    {
        "orden": 5,
        "artistas": "Raziel Pascual Serrano",
        "canciones": "MAGIA",
        "autores": "",
        "material": "Microfono de pinza",
        "duracion": 5,
    },
    {
        "orden": 6,
        "artistas": "Lucas Morcillo Vallestin",
        "canciones": "Smells like teen spirit\nLithium",
        "autores": "Nirvana",
        "material": "Microfonos, bateria, bajo, guitarra electrica, pedal de distorsion",
        "duracion": 10,
    },
    {
        "orden": 7,
        "artistas": "Africa Fernandez Garcia, Mateo Bueno Roy, Lucas Morcillo Vallestin, Marco Lopez Alejandre, Adrian Comenge Ibanez, David Revilla Gonzalo",
        "canciones": "Should I stay or should I go\nGrana y oro\nHey oh, let's go",
        "autores": "The Clash / Reincidentes / Ramones",
        "material": "2 microfonos, 1 guitarra electrica, bajo, bateria",
        "duracion": 15,
    },
]

TAREAS_GENERALES = [
    {
        "nombre": "Disenar e imprimir carteles",
        "descripcion": "Disenar y preparar los carteles del concierto para colgar en el centro.",
        "max": 3,
    },
    {
        "nombre": "Preparar zona de agape",
        "descripcion": "Llevar bebidas y comida desde donde esten guardadas, y preparar la zona para que quede bonita y accesible para los artistas.",
        "max": 3,
    },
    {
        "nombre": "Vigilar zona de agape durante el concierto",
        "descripcion": "Estar pendiente de la zona de agape durante el concierto, asegurandose de que todo esta en orden.",
        "max": 3,
    },
    {
        "nombre": "Pegar y custodiar set lists",
        "descripcion": "Pegar la lista del programa en la zona de agape de los artistas y en dos zonas del escenario. Tener custodiadas al menos dos copias extra.",
        "max": 3,
    },
]


class Command(BaseCommand):
    help = "Carga los actos y tareas del concierto final de curso 2025-2026"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra todos los datos existentes antes de cargar",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            Acto.objects.all().delete()
            Tarea.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos anteriores borrados."))

        # Crear actos
        for data in ACTOS_DATA:
            acto, created = Acto.objects.update_or_create(
                orden=data["orden"],
                defaults={
                    "artistas": data["artistas"],
                    "canciones": data["canciones"],
                    "autores": data["autores"],
                    "material": data["material"],
                    "duracion_minutos": data["duracion"],
                },
            )
            status = "creado" if created else "actualizado"
            self.stdout.write(f"  Acto {acto.orden}: {acto.artistas} [{status}]")

        # Crear tareas generales
        for data in TAREAS_GENERALES:
            tarea, created = Tarea.objects.update_or_create(
                nombre=data["nombre"],
                acto=None,
                defaults={
                    "descripcion": data["descripcion"],
                    "max_voluntarios": data["max"],
                },
            )
            status = "creada" if created else "actualizada"
            self.stdout.write(f"  Tarea: {tarea.nombre} [{status}]")

        # Crear tareas de grabacion (1 por acto)
        for acto in Acto.objects.all():
            tarea, created = Tarea.objects.update_or_create(
                acto=acto,
                defaults={
                    "nombre": f"Grabar video: {acto.artistas[:80]}",
                    "descripcion": f"Grabar video completo de todas las canciones de {acto.artistas}.",
                    "max_voluntarios": 1,
                },
            )
            status = "creada" if created else "actualizada"
            self.stdout.write(f"  Grabacion: {tarea.nombre} [{status}]")

        total_actos = Acto.objects.count()
        total_tareas = Tarea.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"\nCargados {total_actos} actos y {total_tareas} tareas.")
        )
