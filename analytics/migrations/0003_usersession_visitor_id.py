"""
`UserSession.session_key` -> `UserSession.visitor_id`.

El campo guardaba la clave de sesión de Django, lo que ataba la telemetría a la
sesión de autenticación: el endpoint de tracking llamaba a
`request.session.create()` y reescribía la cookie de sesión del navegador a
mitad de un login con Google, borrando el `state` de allauth.

Se escribe a mano en vez de con `makemigrations` para que sea un RENAME y no un
drop + add: las 338 filas existentes conservan su identificador histórico (la
antigua clave de sesión de 32 caracteres), que sigue siendo único y válido.
En Postgres `RENAME COLUMN` es una operación de metadatos.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0002_pagevisit_title"),
    ]

    operations = [
        migrations.RenameField(
            model_name="usersession",
            old_name="session_key",
            new_name="visitor_id",
        ),
        migrations.AlterField(
            model_name="usersession",
            name="visitor_id",
            field=models.CharField(max_length=40, unique=True),
        ),
    ]
