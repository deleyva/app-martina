"""Semilla de oficios: electricista y carpintería, los dos que pidió secretaría (incidencia 219).

Se apuntan en su lista y se les llama cuando hay bastante, así que van en modo
`visita` y sin contacto: lo rellena secretaría desde el panel. Idempotente por
slug; la inversa borra solo estos slugs y solo sin derivaciones.
"""

from django.db import migrations

OFICIOS = [
    {
        "slug": "electricista",
        "nombre": "Electricista",
        "que_va_aqui": "Enchufes, luces, fluorescentes, diferenciales, regletas fijas, timbres.",
        "orden": 200,
    },
    {
        "slug": "carpinteria-y-ventanas",
        "nombre": "Carpintería y ventanas",
        "que_va_aqui": "Ventanas que no cierran o no abren, persianas, puertas, cerraduras, mobiliario roto.",
        "orden": 210,
    },
]


def sembrar(apps, schema_editor):
    Servicio = apps.get_model("incidencias", "Servicio")
    for fila in OFICIOS:
        datos = dict(fila)
        slug = datos.pop("slug")
        Servicio.objects.get_or_create(slug=slug, defaults={**datos, "modo": "visita"})


def deshacer(apps, schema_editor):
    Servicio = apps.get_model("incidencias", "Servicio")
    Servicio.objects.filter(slug__in=[o["slug"] for o in OFICIOS], derivaciones__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("incidencias", "0008_servicio_modo")]

    operations = [migrations.RunPython(sembrar, deshacer)]
