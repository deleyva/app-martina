from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Habilita `unaccent` para que el buscador del índice musical ignore tildes.

    Sin esto, buscar "armonia" no encontraba "Armonía": `icontains` en Postgres
    respeta los acentos, así que media biblioteca era invisible salvo que se
    escribiera la tilde exacta.

    Crear la extensión requiere privilegios de superusuario en la base de datos.
    """

    dependencies = [
        ("cms", "0034_remove_blogpage_duration_minutes_and_more"),
    ]

    operations = [
        UnaccentExtension(),
    ]
