"""El botón «evaluable» de cada elemento de la sesión (fase 62)."""

from django import template

register = template.Library()


@register.simple_tag
def planes_evaluables(session):
    """Los planes del grupo con sus instrumentos, el del trimestre de la sesión primero.

    El botón sale en cada fila y todas comparten el mismo objeto `session`: se
    guarda en él para no repetir la consulta por fila.
    """
    if not hasattr(session, "_planes_evaluables"):
        from calificaciones.evaluar import instrumentos_del_grupo

        session._planes_evaluables = instrumentos_del_grupo(session.group, session.date)
    return session._planes_evaluables
