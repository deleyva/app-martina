# ruff: noqa: E501
"""Las acciones sobre una incidencia, en un solo sitio.

Vistas HTML y API llaman a estas funciones para que asignar, cambiar de
estado, comentar y derivar produzcan el mismo historial y las mismas
notificaciones vengan de donde vengan.
"""

from django.conf import settings
from django.template.loader import select_template

from incidencias.models import Comentario
from incidencias.models import Derivacion
from incidencias.models import HistorialAsignacion
from incidencias.models import Incidencia
from incidencias.models import Servicio
from incidencias.models import Tecnico
from incidencias.services.notification_service import IncidenciaNotificationService


def asignar(
    incidencia: Incidencia,
    tecnico: Tecnico | None,
    por: Tecnico | None,
    *,
    nota: str = "",
) -> HistorialAsignacion:
    """Asigna (o desasigna con `None`) y deja constancia en el historial."""
    if not nota:
        nota = f"Asignada a {tecnico}" if tecnico else f"Desasignada (antes: {incidencia.asignado_a or '—'})"
    historial = HistorialAsignacion.objects.create(
        incidencia=incidencia,
        asignado_por=por,
        asignado_a=tecnico,
        nota=nota,
    )
    incidencia.asignado_a = tecnico
    incidencia.save(update_fields=["asignado_a", "updated_at"])
    return historial


def cambiar_estado(incidencia: Incidencia, estado: str) -> bool:
    """Cambia el estado y notifica solo si de verdad cambia. Devuelve si cambió."""
    if estado not in Incidencia.Estado.values:
        msg = f"Estado desconocido: {estado}"
        raise ValueError(msg)
    anterior = incidencia.estado
    if anterior == estado:
        return False
    incidencia.estado = estado
    incidencia.save(update_fields=["estado", "updated_at"])
    IncidenciaNotificationService.notify_estado_changed(incidencia.pk, anterior, estado)
    return True


def comentar(incidencia: Incidencia, autor: str, texto: str) -> Comentario:
    comentario = Comentario.objects.create(incidencia=incidencia, autor_nombre=autor, texto=texto)
    IncidenciaNotificationService.notify_new_comment(incidencia.pk, comentario.pk)
    return comentario


def cuerpo_por_defecto(incidencia: Incidencia, servicio: Servicio) -> str:
    """El correo que secretaría copiará, con los datos concretos de la incidencia."""
    plantilla = select_template(
        [
            f"incidencias/derivaciones/cuerpo_{servicio.slug}.txt",
            "incidencias/derivaciones/cuerpo_default.txt",
        ],
    )
    comentarios_tecnicos = [
        c
        for c in incidencia.comentarios.all()
        if Tecnico.objects.filter(user__email__istartswith=f"{c.autor_nombre.lower().split('@')[0]}@").exists()
    ]
    return plantilla.render(
        {
            "incidencia": incidencia,
            "servicio": servicio,
            "ubicacion": incidencia.ubicacion,
            "comentarios_tecnicos": comentarios_tecnicos,
            "url_incidencia": f"{settings.INCIDENCIAS_SITE_URL}/{incidencia.pk}/",
            "url_servicio": servicio.url_publica,
            "telefono_contacto": settings.INCIDENCIAS_TELEFONO_CONTACTO,
        },
    ).strip() + "\n"


def derivar(
    incidencia: Incidencia,
    servicio: Servicio,
    por: Tecnico | None,
    *,
    asunto: str | None = None,
    cuerpo: str | None = None,
) -> Derivacion:
    """Crea la derivación en borrador y saca la incidencia de «pendiente».

    A un oficio (`modo=visita`) no se le escribe: queda apuntada en su lista, sin correo.
    """
    derivacion = Derivacion.objects.create(
        incidencia=incidencia,
        servicio=servicio,
        creada_por=por,
        asunto=asunto or Derivacion.asunto_por_defecto(incidencia),
        cuerpo=cuerpo if cuerpo is not None else ("" if servicio.es_por_visita else cuerpo_por_defecto(incidencia, servicio)),
    )
    if incidencia.estado == Incidencia.Estado.PENDIENTE:
        cambiar_estado(incidencia, Incidencia.Estado.EN_PROGRESO)
    return derivacion
