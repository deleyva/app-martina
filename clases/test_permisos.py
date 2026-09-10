"""Un profesor no llega a lo de otro, ni escribiendo la URL a mano.

Estos tests existen porque el 2026-09-10 se abrió la puerta: hasta entonces «ser
profesor» era `is_staff` y había un solo profesor, así que ninguna comprobación
de pertenencia se había puesto a prueba de verdad. La auditoría encontró doce
vistas que aceptaban un `group_id` o un `student_id` de cualquiera.

**Se prueba por HTTP y no llamando a la función.** El agujero no estaba en la
lógica sino en la puerta, y una llamada directa se salta justo la puerta.
"""

import pytest
from django.urls import reverse

from clases.models import Enrollment, Group, Student, Subject
from martina_bescos_app.users.permisos import GRUPO_PROFESORADO, es_profesor


@pytest.fixture
def asignatura(db):
    return Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]


def _profesor(django_user_model, correo, asignatura, nombre_grupo):
    """Un profesor con su grupo, sin `is_staff`: el caso nuevo."""
    user = django_user_model.objects.create_user(email=correo, password="x")
    grupo = Group.objects.create(
        name=nombre_grupo, subject=asignatura, academic_year="2026-2027"
    )
    grupo.teachers.add(user)
    return user, grupo


# =============================================================================
# El rol
# =============================================================================


def test_dar_clase_a_un_grupo_ya_te_hace_profesor(db, django_user_model, asignatura):
    """Sin esto, los profesores que ya existían dejarían de entrar el día del
    cambio, y una mejora se convertiría en una caída."""
    user, _grupo = _profesor(django_user_model, "profe1@x.es", asignatura, "1-A")
    assert not user.is_staff
    assert es_profesor(user)


def test_el_grupo_de_permisos_habilita_sin_dar_el_admin(db, django_user_model):
    """La razón de ser de todo esto: profesor sí, admin de Django no."""
    from django.contrib.auth.models import Group as GrupoPermisos

    user = django_user_model.objects.create_user(email="invitado@x.es", password="x")
    assert not es_profesor(user)

    user.groups.add(GrupoPermisos.objects.get_or_create(name=GRUPO_PROFESORADO)[0])

    assert es_profesor(user)
    assert not user.is_staff, "pertenecer al profesorado no puede dar acceso al admin"


def test_un_usuario_cualquiera_no_es_profesor(db, django_user_model):
    alumno = django_user_model.objects.create_user(email="alumno@x.es", password="x")
    assert not es_profesor(alumno)


# =============================================================================
# El aislamiento entre profesores
# =============================================================================


@pytest.mark.parametrize(
    "ruta",
    [
        "clases:group_books_index",
        "clases:group_library_index",
        "clases:study_cards_group_tracking",
    ],
)
def test_un_profesor_no_entra_en_el_grupo_de_otro(
    db, client, django_user_model, asignatura, ruta
):
    """El caso que abre la puerta: dos profesores, y uno prueba con el id del otro."""
    ana, grupo_de_ana = _profesor(django_user_model, "ana@x.es", asignatura, "1-A")
    beto, _suyo = _profesor(django_user_model, "beto@x.es", asignatura, "1-B")

    client.force_login(beto)
    respuesta = client.get(reverse(ruta, args=[grupo_de_ana.pk]))

    assert respuesta.status_code == 404, (
        f"{ruta} deja entrar en el grupo de otro profesor"
    )


def test_su_propio_grupo_si_se_abre(db, client, django_user_model, asignatura):
    """El contrapunto obligatorio: si esto no pasara, el test de arriba pasaría
    con la aplicación entera rota."""
    ana, grupo_de_ana = _profesor(django_user_model, "ana2@x.es", asignatura, "2-A")

    client.force_login(ana)
    respuesta = client.get(reverse("clases:group_books_index", args=[grupo_de_ana.pk]))

    assert respuesta.status_code == 200


def test_no_se_puede_ver_el_expediente_de_un_alumno_ajeno(
    db, client, django_user_model, asignatura
):
    """El peor de los encontrados: `student_id` sin comprobar daba el expediente
    completo de cualquier alumno del centro."""
    ana, grupo_de_ana = _profesor(django_user_model, "ana3@x.es", asignatura, "3-A")
    beto, _suyo = _profesor(django_user_model, "beto3@x.es", asignatura, "3-B")

    alumno = django_user_model.objects.create_user(email="alu3@x.es", password="x")
    Enrollment.objects.create(user=alumno, group=grupo_de_ana, is_active=True)
    ficha = Student.objects.create(user=alumno, group=grupo_de_ana)

    client.force_login(beto)
    respuesta = client.get(
        reverse("evaluations:teacher_view_student_dashboard", args=[ficha.pk])
    )

    assert respuesta.status_code == 404


def test_no_se_puede_calificar_a_un_alumno_ajeno(
    db, client, django_user_model, asignatura
):
    """Escribir es más grave que leer: esto era poner una nota al alumno de otro."""
    ana, grupo_de_ana = _profesor(django_user_model, "ana4@x.es", asignatura, "4-A")
    beto, _suyo = _profesor(django_user_model, "beto4@x.es", asignatura, "4-B")

    alumno = django_user_model.objects.create_user(email="alu4@x.es", password="x")
    ficha = Student.objects.create(user=alumno, group=grupo_de_ana)

    client.force_login(beto)
    respuesta = client.post(
        reverse("evaluations:save_evaluation", args=[ficha.pk]),
        {"evaluation_item_id": "1", "direct_score": "10"},
    )

    assert respuesta.status_code == 404
