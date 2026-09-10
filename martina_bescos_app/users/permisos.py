"""Quién es profesor, y a qué llega cada profesor.

**Por qué existe.** Hasta 2026-09-10 «ser profesor» en esta app era `is_staff`, y
`is_staff` es exactamente lo que abre el **admin de Django**. Es decir: no se
podía dar acceso de profesor a un compañero sin darle también el admin. Aquí se
separan las dos cosas.

Y hay una segunda mitad que no es opcional. Con un solo profesor, que una vista
no comprobara de quién es el grupo daba igual. Con varios, eso es una fuga: la
auditoría del 2026-09-10 encontró **doce vistas** que aceptaban un `group_id` o
un `student_id` de cualquiera. Los ayudantes de aquí abajo son la respuesta, y
están en un solo sitio para que la comprobación no se escriba de doce maneras.
"""

from django.http import Http404

# El grupo de permisos de Django que habilita a un profesor invitado. No usa
# `is_staff` a propósito: pertenecer aquí no da acceso al admin.
GRUPO_PROFESORADO = "Profesorado"


def es_profesor(user):
    """Si puede usar las pantallas de profesor.

    Tres caminos, y los tres cuentan:

    - `is_staff`, para que el administrador siga entrando como siempre.
    - Estar en el grupo de permisos «Profesorado», que es lo que concede una
      invitación de profesorado.
    - **Tener al menos un grupo donde figura como profesor.** Sin esto, los
      profesores que ya existen dejarían de entrar el día que se cambie el
      criterio, y eso convertiría una mejora en una caída.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if user.groups.filter(name=GRUPO_PROFESORADO).exists():
        return True
    return user.teaching_groups.exists()


def grupo_del_profesor(user, group_id):
    """El grupo, si este profesor le da clase. Si no, 404.

    404 y no 403 a propósito: un 403 confirma que el grupo existe, y eso ya es
    información que un profesor no tiene por qué obtener de otro.

    El administrador (`is_staff`) pasa por encima: es quien tiene que poder
    mirar cualquier grupo cuando algo va mal.
    """
    from clases.models import Group

    grupo = Group.objects.filter(pk=group_id).first()
    if grupo is None:
        raise Http404("No existe ese grupo.")
    if user.is_staff or grupo.teachers.filter(pk=user.pk).exists():
        return grupo
    raise Http404("No das clase a ese grupo.")


def alumno_del_profesor(user, student):
    """Comprueba que ese alumno está en algún grupo de este profesor.

    Se mira por las DOS vías porque conviven: `Enrollment`, que es la actual, y
    `Student.group`, que es la heredada y sigue poblada. Comprobar solo una
    dejaría fuera a la mitad del alumnado según por dónde entrara.
    """
    from clases.models import Enrollment

    if user.is_staff:
        return student

    grupos = set(user.teaching_groups.values_list("pk", flat=True))
    if not grupos:
        raise Http404("No tienes alumnado a tu cargo.")

    if getattr(student, "group_id", None) in grupos:
        return student
    if student.user_id and Enrollment.objects.filter(
        user_id=student.user_id, group_id__in=grupos, is_active=True
    ).exists():
        return student

    raise Http404("Ese alumno no está en ninguno de tus grupos.")
