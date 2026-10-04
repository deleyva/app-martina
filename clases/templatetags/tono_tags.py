"""El tono de clase de una canción con acordes en el visor (fase 63)."""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def tono_de_clase(context, letra):
    """`{grupo, semitonos, puede_guardar}` para el visor de ChordPro.

    El grupo es el de la página (`grupo_tono`: la clase, la biblioteca del
    grupo) o el del alumno si solo tiene uno. Solo el profesorado de ese grupo
    puede guardar.
    """
    from clases.models import TonoDeGrupo

    request = context.get("request")
    user = getattr(request, "user", None)
    grupo = TonoDeGrupo.grupo_para(user, context.get("grupo_tono"))
    puede = bool(
        grupo is not None
        and user is not None
        and user.is_authenticated
        and (user.is_staff or grupo.teachers.filter(pk=user.pk).exists())
    )
    return {"grupo": grupo, "semitonos": TonoDeGrupo.de(grupo, letra), "puede_guardar": puede}
