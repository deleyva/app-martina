"""Aviso por correo cuando un dispositivo queda dado de alta en la red."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from huey.contrib.djhuey import db_task

logger = logging.getLogger(__name__)


def _contexto():
    return {
        "ssid": getattr(settings, "WIFI_SSID", ""),
        "clave": getattr(settings, "WIFI_PASSWORD", ""),
    }


@db_task()
def enviar_avisos_alta(dispositivo_ids: list[int]) -> int:
    """Escribe a cada solicitante con la clave. Devuelve cuántos correos salieron.

    Se manda en una sola tarea y no una por dispositivo porque el administrativo
    marca veinte de golpe: veinte conexiones SMTP a Gmail dentro de la petición
    la dejarían colgada.
    """
    from .models import DispositivoWifi

    ssid = getattr(settings, "WIFI_SSID", "")
    clave = getattr(settings, "WIFI_PASSWORD", "")
    if not clave:
        logger.error(
            "WIFI_PASSWORD no está configurada: no se avisa a %s solicitantes. "
            "Define DJANGO_WIFI_PASSWORD en el entorno.",
            len(dispositivo_ids),
        )
        return 0

    pendientes = DispositivoWifi.objects.filter(
        pk__in=dispositivo_ids,
        estado=DispositivoWifi.Estado.ANADIDA,
        notificado_at__isnull=True,
    ).select_related("usuario")

    asunto = f"Acceso a la red WiFi {ssid}"
    cuerpo = render_to_string("wifi/emails/alta_confirmada.txt", _contexto())
    enviados = 0

    for dispositivo in pendientes:
        destino = dispositivo.email_destino
        if not destino:
            logger.warning(
                "Dispositivo %s dado de alta sin correo de destino.", dispositivo.pk,
            )
            continue
        try:
            send_mail(
                asunto,
                cuerpo,
                settings.DEFAULT_FROM_EMAIL,
                [destino],
                fail_silently=False,
            )
        except Exception:
            # Sin sellar `notificado_at`: así se puede reintentar sin perder
            # el rastro de quién se quedó sin aviso.
            logger.exception("No se pudo avisar del alta del dispositivo %s.", dispositivo.pk)
            continue

        dispositivo.notificado_at = timezone.now()
        dispositivo.save(update_fields=["notificado_at", "updated_at"])
        enviados += 1

    logger.info("Avisos de alta WiFi enviados: %s de %s.", enviados, len(dispositivo_ids))
    return enviados
