# ruff: noqa: ERA001, E501
"""Data migration to populate Ubicacion and Etiqueta from CSV data."""
from django.db import migrations


def load_fixtures(apps, schema_editor):
    Ubicacion = apps.get_model("incidencias", "Ubicacion")
    Etiqueta = apps.get_model("incidencias", "Etiqueta")

    # --- Planta Baja (Hoja 3) ---
    planta_baja = [
        ("Música 1", "1º ESO G"),
        ("Aula N1", "1º ESO PAI"),
        ("Aula N2", "1º ESO A"),
        ("Aula N3", "1º ESO B"),
        ("Aula N4", "1º ESO C"),
        ("Aula N5", "1º ESO D"),
        ("Aula N6", "1º ESO E"),
        ("Aula N7", "1º ESO F"),
        ("TUT 3", "AULA PT"),
        ("TUT 2", "AULA TEA"),
        ("Aula N8", "Desdoble"),
        ("Música 2", ""),
        ("INFO 3", ""),
        ("TECNO 3", ""),
    ]
    for nombre, grupo in planta_baja:
        Ubicacion.objects.get_or_create(
            nombre=nombre, planta="PB",
            defaults={"grupo": grupo},
        )

    # --- Primera Planta (Hoja 4) ---
    primera_planta = [
        ("Aula 6", "2º ESO PAI"),
        ("Aula 7", "2º ESO A"),
        ("Aula 8", "2º ESO B"),
        ("Aula 9", "2º ESO C"),
        ("Aula 10", "2º ESO I"),
        ("Plástica 1", "2º BACH D"),
        ("Aula N9", "2º ESO D"),
        ("Aula N10", "2º ESO E"),
        ("Aula N11", "2º ESO F"),
        ("Aula N12", "2º ESO G"),
        ("Aula N13", "2º ESO H"),
        ("Plástica 2", "2º BACH C"),
        ("DEP 1", "4º ESO G"),
        ("DEP 2", "4º ESO F"),
        ("DEP 5", "4º ESO DIVER"),
        ("D1", "Desdoble"),
        ("TECNO 1", "FP Básica"),
        ("Aula 1", "4º ESO A"),
        ("Aula 2", "4º ESO B"),
        ("Aula 3", "4º ESO C"),
        ("Aula 4", "4º ESO D"),
        ("Aula 5", "4º ESO E"),
        ("INFO 1", ""),
        ("Dibujo", ""),
    ]
    for nombre, grupo in primera_planta:
        Ubicacion.objects.get_or_create(
            nombre=nombre, planta="P1",
            defaults={"grupo": grupo},
        )

    # --- Segunda Planta (Hoja 5) ---
    segunda_planta = [
        ("D5", "2º BACH A"),
        ("Aula 16", "3º ESO DIVER"),
        ("Aula 17", "3º ESO A"),
        ("Aula 18", "3º ESO B"),
        ("Aula 19", "3º ESO C"),
        ("Aula 20", "2º BACH B"),
        ("Aula N14", "3º ESO D"),
        ("Aula N15", "3º ESO E"),
        ("Aula N16", "3º ESO F"),
        ("Aula N17", "3º ESO G"),
        ("Aula N18", "3º ESO H"),
        ("Aula 11", "1º BACH A"),
        ("Aula 12", "1º BACH B"),
        ("Aula 13", "1º BACH C"),
        ("Aula 14", "1º BACH D"),
        ("Aula 15", ""),
        ("TECNO 2", ""),
        ("D4", ""),
        ("D3", ""),
        ("LAB QUÍMICA", ""),
        ("LAB FÍSICA", ""),
        ("LAB CCNN", ""),
        ("INFO 2", ""),
        ("TECNO 4", ""),
        ("D8", ""),
    ]
    for nombre, grupo in segunda_planta:
        Ubicacion.objects.get_or_create(
            nombre=nombre, planta="P2",
            defaults={"grupo": grupo},
        )

    # --- Etiquetas (Hoja 1) ---
    etiquetas = [
        ("Ordenador MI (Video)", "ordenador-to-mi"),
        ("Ordenador (Sonido)", "ordenador-sonido"),
        ("Ratón", "raton"),
        ("Proyectar", "proyectar"),
        ("Internet", "internet"),
        ("Teclado", "teclado"),
        ("Apps no activas", "apps-no-activas"),
        ("WiFi", "wifi"),
        ("Teclas", "teclas"),
        ("Falta algún componente", "componentes"),
        ("Falta Proyector/Pantalla", "falta-mi"),
        ("Software", "software"),
    ]
    for nombre, slug in etiquetas:
        Etiqueta.objects.get_or_create(
            slug=slug,
            defaults={"nombre": nombre},
        )


def reverse_fixtures(apps, schema_editor):
    Ubicacion = apps.get_model("incidencias", "Ubicacion")
    Etiqueta = apps.get_model("incidencias", "Etiqueta")
    Ubicacion.objects.all().delete()
    Etiqueta.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidencias", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(load_fixtures, reverse_fixtures),
    ]
