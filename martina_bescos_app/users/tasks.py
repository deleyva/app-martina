"""
Tareas periódicas de mantenimiento de sesiones.

La tabla `django_session` no se limpia sola: Django trae el comando
`clearsessions` precisamente porque el backend de BD no caduca filas por su
cuenta. En agosto de 2026 había 107.016 filas, de las que solo 17.408 seguían
vivas, casi todas creadas por visitantes anónimos a los que se les abría sesión
sin necesitarla (ver `martina_bescos_app.middleware.AppModeMiddleware`).

Arreglada la causa, esto se encarga del resto: barre lo ya caducado, que es lo
único que `clearsessions` toca por definición.
"""

import logging

from django.core.management import call_command
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, lock_task

logger = logging.getLogger(__name__)


@db_periodic_task(crontab(hour="4", minute="30"))
@lock_task("clear-expired-sessions")
def clear_expired_sessions():
    """Borra las sesiones ya caducadas. Cada noche a las 04:30."""
    logger.info("clearsessions: empezando barrido de sesiones caducadas")
    call_command("clearsessions")
    logger.info("clearsessions: barrido terminado")
