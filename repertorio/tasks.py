"""Resincronización mensual del catálogo de JamZone.

Mensual y no diaria porque el catálogo se mueve poco: en la comprobación del
2026-09-19, dos importaciones seguidas dieron 575 sin cambios. Pedir el
catálogo entero cada noche sería ruido para ellos y para nosotros.

El `lock_task` es la convención de la casa y aquí no es decorativo: la
importación es larga, y dos pasadas simultáneas se pelearían por las mismas
filas.
"""

import logging

from django.core.management import call_command
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, lock_task

logger = logging.getLogger(__name__)


@db_periodic_task(crontab(day="1", hour="5", minute="0"))
@lock_task("sincronizar-jamzone")
def sincronizar_jamzone():
    """El día 1 de cada mes a las 5:00.

    No propaga la excepción: que falle una sincronización mensual no debe
    tumbar al consumidor de Huey. Queda en el log y, sobre todo, queda en
    `Sincronizacion`, que es lo que mira la pantalla del catálogo.
    """
    from repertorio.models import Sincronizacion

    try:
        call_command("importar_jamzone", automatica=True)
    except Exception:
        logger.exception("Falló la sincronización mensual con JamZone")
        Sincronizacion.objects.create(
            automatica=True, recibidas=0, fallos=1, detalle="La descarga no llegó a completarse."
        )
        return

    ultima = Sincronizacion.ultima()
    if ultima:
        logger.info(
            "Sincronización con JamZone: %d recibidas, %d creadas, %d actualizadas, %d fallos",
            ultima.recibidas,
            ultima.creadas,
            ultima.actualizadas,
            ultima.fallos,
        )
