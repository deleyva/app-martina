# Fase 90 (2026-11-01): favoritos, lo que entra en todas las sesiones.
#
# Solo añade una columna a las secciones. El campo de `LibraryItem` ya existía
# desde la migración inicial; aquí solo cambia su nombre visible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('my_library', '0014_fuera_los_mazos'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemsection',
            name='favorite',
            field=models.BooleanField(default=False, verbose_name='Favorito'),
        ),
        migrations.AlterField(
            model_name='libraryitem',
            name='favorite',
            field=models.BooleanField(default=False, verbose_name='Favorito'),
        ),
    ]
