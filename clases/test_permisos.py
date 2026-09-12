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


# =============================================================================
# La invitación de profesorado
# =============================================================================


def test_aceptar_una_invitacion_de_profesorado_habilita_sin_dar_el_admin(
    db, django_user_model, asignatura
):
    """La razón de ser de todo el bloque: profesor sí, admin de Django no."""
    from clases.models import GroupInvitation

    anfitrion = django_user_model.objects.create_user(email="jefe@x.es", password="x", is_staff=True)
    invitado = django_user_model.objects.create_user(email="nuevo@x.es", password="x")
    assert not es_profesor(invitado)

    inv = GroupInvitation.objects.create(
        rol=GroupInvitation.PROFESORADO, created_by=anfitrion
    )
    _objeto, estado = inv.accept_for_user(invitado)

    invitado.refresh_from_db()
    assert estado == "habilitado"
    assert es_profesor(invitado)
    assert not invitado.is_staff, "una invitación no puede abrir el admin de Django"


def test_una_invitacion_de_profesorado_con_grupo_le_hace_profesor_de_ese_grupo(
    db, django_user_model, asignatura
):
    """El otro caso: invitar a un compañero a dar clase contigo en un grupo."""
    from clases.models import GroupInvitation

    ana, grupo = _profesor(django_user_model, "ana9@x.es", asignatura, "9-A")
    beto = django_user_model.objects.create_user(email="beto9@x.es", password="x")

    inv = GroupInvitation.objects.create(
        rol=GroupInvitation.PROFESORADO, group=grupo, created_by=ana
    )
    inv.accept_for_user(beto)

    assert grupo.teachers.filter(pk=beto.pk).exists()
    assert es_profesor(beto)


def test_la_invitacion_de_alumnado_sigue_matriculando(db, django_user_model, asignatura):
    """El contrapunto: lo que ya funcionaba no puede haberse roto al añadir el rol."""
    from clases.models import Enrollment, GroupInvitation

    ana, grupo = _profesor(django_user_model, "ana10@x.es", asignatura, "10-A")
    alumno = django_user_model.objects.create_user(email="alu10@x.es", password="x")

    inv = GroupInvitation.objects.create(group=grupo, created_by=ana)
    _obj, estado = inv.accept_for_user(alumno)

    assert estado == "joined"
    assert Enrollment.objects.filter(user=alumno, group=grupo, is_active=True).exists()
    assert not es_profesor(alumno), "matricularse no puede hacerte profesor"


def test_una_invitacion_caducada_no_habilita(db, django_user_model):
    """La maquinaria de validez que ya existía tiene que seguir valiendo para el
    rol nuevo: si no, una invitación de profesorado revocada seguiría dando
    acceso para siempre."""
    from django.utils import timezone
    from datetime import timedelta

    from clases.models import GroupInvitation

    invitado = django_user_model.objects.create_user(email="tarde@x.es", password="x")
    inv = GroupInvitation.objects.create(
        rol=GroupInvitation.PROFESORADO,
        expires_at=timezone.now() - timedelta(days=1),
    )

    _obj, estado = inv.accept_for_user(invitado)

    assert estado == "invalid"
    assert not es_profesor(invitado)


def test_un_profesor_puede_crear_su_grupo_desde_el_frontend(
    db, client, django_user_model, asignatura
):
    """Fase 3: sin esto, un profesor invitado no puede empezar."""
    from clases.models import Group

    ana, _grupo = _profesor(django_user_model, "ana11@x.es", asignatura, "11-A")
    client.force_login(ana)

    respuesta = client.post(
        reverse("clases:group_create"),
        {"name": "2-D-BIL", "academic_year": "2026-2027", "subject": asignatura.pk},
    )

    assert respuesta.status_code == 302
    nuevo = Group.objects.get(name="2-D-BIL")
    assert nuevo.teachers.filter(pk=ana.pk).exists(), "quien lo crea queda como profesor"


def test_crear_un_grupo_con_asignatura_nueva_no_duplica(
    db, client, django_user_model, asignatura
):
    """Las asignaturas son globales y las ve todo el profesorado: sin deduplicar
    acabarían conviviendo «Lenguaje musical» y «Lenguaje Musical»."""
    from clases.models import Subject

    ana, _grupo = _profesor(django_user_model, "ana12@x.es", asignatura, "12-A")
    client.force_login(ana)

    for nombre in ["Lenguaje musical", "LENGUAJE MUSICAL"]:
        client.post(
            reverse("clases:group_create"),
            {"name": f"G-{nombre[:3]}", "academic_year": "2026-2027",
             "asignatura_nueva": nombre},
        )

    assert Subject.objects.filter(name__iexact="lenguaje musical").count() == 1


# =============================================================================
# Repartir y retirar el acceso
# =============================================================================


def test_un_profesor_corriente_no_puede_repartir_acceso(
    db, client, django_user_model, asignatura
):
    """El guarda que impide que el acceso se propague solo.

    Si cualquier profesor pudiera invitar, bastaría un enlace reenviado para que
    entrara medio claustro sin que el administrador se enterara.
    """
    ana, _grupo = _profesor(django_user_model, "ana20@x.es", asignatura, "20-A")
    client.force_login(ana)

    assert client.get(reverse("clases:profesorado")).status_code in (302, 403)
    assert client.post(reverse("clases:profesorado"), {"max_uses": "1"}).status_code in (302, 403)


def test_el_administrador_si_puede(db, client, django_user_model):
    """El contrapunto: si esto no pasara, el test de arriba pasaría con la
    pantalla rota para todo el mundo."""
    from clases.models import GroupInvitation

    jefe = django_user_model.objects.create_user(
        email="jefe20@x.es", password="x", is_staff=True
    )
    client.force_login(jefe)

    assert client.get(reverse("clases:profesorado")).status_code == 200

    client.post(reverse("clases:profesorado"), {"max_uses": "1"})
    assert GroupInvitation.objects.filter(rol=GroupInvitation.PROFESORADO).count() == 1


def test_revocar_quita_el_acceso_de_quien_solo_lo_tenia_por_invitacion(
    db, client, django_user_model
):
    from clases.models import GroupInvitation

    jefe = django_user_model.objects.create_user(
        email="jefe21@x.es", password="x", is_staff=True
    )
    invitado = django_user_model.objects.create_user(email="inv21@x.es", password="x")
    GroupInvitation.objects.create(rol=GroupInvitation.PROFESORADO).accept_for_user(invitado)
    assert es_profesor(invitado)

    client.force_login(jefe)
    client.post(reverse("clases:profesorado_revocar", args=[invitado.pk]))

    invitado.refresh_from_db()
    assert not es_profesor(invitado)


def test_revocar_no_engana_a_quien_sigue_dando_clase(
    db, client, django_user_model, asignatura
):
    """El límite honesto de «quitar acceso».

    A quien da clase en un grupo, quitarle el grupo de permisos no le quita nada:
    sigue siendo profesor por esa vía. La pantalla avisa en vez de fingir que ha
    hecho algo.
    """
    from clases.models import GroupInvitation

    jefe = django_user_model.objects.create_user(
        email="jefe22@x.es", password="x", is_staff=True
    )
    ana, _grupo = _profesor(django_user_model, "ana22@x.es", asignatura, "22-A")
    GroupInvitation.objects.create(rol=GroupInvitation.PROFESORADO).accept_for_user(ana)

    client.force_login(jefe)
    respuesta = client.post(
        reverse("clases:profesorado_revocar", args=[ana.pk]), follow=True
    )

    ana.refresh_from_db()
    assert es_profesor(ana), "sigue dando clase, así que sigue siendo profesor"
    textos = [m.message for m in respuesta.context["messages"]]
    assert any("sigue teniendo acceso" in t for t in textos), (
        "la pantalla tiene que decirlo, no fingir que lo ha quitado"
    )


def test_revocar_un_enlace_lo_deja_inservible(db, client, django_user_model, asignatura):
    from clases.models import GroupInvitation

    ana, grupo = _profesor(django_user_model, "ana23@x.es", asignatura, "23-A")
    inv = GroupInvitation.objects.create(group=grupo, created_by=ana)
    alumno = django_user_model.objects.create_user(email="alu23@x.es", password="x")

    client.force_login(ana)
    client.post(reverse("clases:invitation_revoke", args=[inv.pk]))

    inv.refresh_from_db()
    _obj, estado = inv.accept_for_user(alumno)
    assert estado == "invalid"


def test_no_se_revoca_el_enlace_de_otro_profesor(db, client, django_user_model, asignatura):
    """Aislamiento también aquí: los enlaces son del grupo de quien los hizo."""
    from clases.models import GroupInvitation

    ana, grupo_de_ana = _profesor(django_user_model, "ana24@x.es", asignatura, "24-A")
    beto, _suyo = _profesor(django_user_model, "beto24@x.es", asignatura, "24-B")
    inv = GroupInvitation.objects.create(group=grupo_de_ana, created_by=ana)

    client.force_login(beto)
    respuesta = client.post(reverse("clases:invitation_revoke", args=[inv.pk]))

    inv.refresh_from_db()
    assert respuesta.status_code == 404
    assert inv.is_active, "el enlace de otra profesora sigue vivo"


def test_el_grupo_de_wagtail_no_toca_la_raiz_del_arbol(db):
    """C168. La decisión del principal: solo lo que cuelga del índice musical.

    Es lo que separa «editar los libros» de «editar el sitio entero». Los grupos
    que trae Wagtail (`Editors`, `Moderators`) tienen permiso sobre `Root`, así
    que meter ahí a un profesor le daría también los 16 blogs de departamento.

    El falsador mira dónde caen los permisos, no que el comando no reviente.
    """
    from django.contrib.auth.models import Group as GrupoPermisos
    from django.core.management import call_command
    from wagtail.models import GroupPagePermission, Page

    raiz = Page.objects.get(depth=1)
    indice = Page(title="Índice de recursos musicales", slug="indice-musical")
    Page.objects.get(id=2).add_child(instance=indice)

    call_command("preparar_profesorado", "--pagina", "Índice de recursos musicales")

    grupo = GrupoPermisos.objects.get(name=GRUPO_PROFESORADO)
    permisos = GroupPagePermission.objects.filter(group=grupo)

    assert permisos.exists(), "no ha dado ningún permiso"
    assert not permisos.filter(page=raiz).exists(), "tiene permiso sobre la RAÍZ"
    assert set(permisos.values_list("page__title", flat=True)) == {
        "Índice de recursos musicales"
    }


def test_preparar_profesorado_se_puede_repetir(db):
    """C168. Se va a lanzar en producción más de una vez; no puede duplicar."""
    from django.contrib.auth.models import Group as GrupoPermisos
    from django.core.management import call_command
    from wagtail.models import GroupPagePermission

    indice = Page_indice()
    call_command("preparar_profesorado", "--pagina", indice.title)
    call_command("preparar_profesorado", "--pagina", indice.title)

    grupo = GrupoPermisos.objects.get(name=GRUPO_PROFESORADO)
    assert GroupPagePermission.objects.filter(group=grupo).count() == 3


def Page_indice():
    from wagtail.models import Page

    indice = Page(title="Índice de recursos musicales", slug="indice-musical-2")
    Page.objects.get(id=2).add_child(instance=indice)
    return indice


def test_el_panel_no_lista_al_alumnado_cuando_aun_no_hay_grupo_de_permisos(
    db, client, django_user_model, asignatura
):
    """C169. El defecto que se vio en pantalla el 2026-09-11.

    Con el grupo «Profesorado» todavía sin crear, `Q(groups=None)` se traduce a
    `groups IS NULL` y arrastra a todo usuario sin grupos de permisos: el
    alumnado entero aparecía como profesorado, con la casilla «vía» vacía.
    """
    from django.contrib.auth.models import Group as GrupoPermisos

    GrupoPermisos.objects.filter(name=GRUPO_PROFESORADO).delete()

    jefe = django_user_model.objects.create_user(
        email="jefe30@x.es", password="x", is_staff=True
    )
    ana, grupo = _profesor(django_user_model, "ana30@x.es", asignatura, "30-A")
    alumno = django_user_model.objects.create_user(email="alu30@x.es", password="x")
    Enrollment.objects.create(user=alumno, group=grupo, is_active=True)

    client.force_login(jefe)
    respuesta = client.get(reverse("clases:profesorado"))

    correos = [f["user"].email for f in respuesta.context["gente"]]
    assert "alu30@x.es" not in correos, "el alumnado no es profesorado"
    assert {"jefe30@x.es", "ana30@x.es"} <= set(correos)


# =============================================================================
# La raíz de la aplicación
# =============================================================================


def test_la_raiz_de_clases_lleva_a_las_sesiones(db, client, django_user_model):
    """`/clases/` daba 404: la URL que uno escribe de memoria no llevaba a
    ninguna parte. Se comprueba a dónde apunta, no solo que no sea 404, porque
    un 302 hacia el login también dejaría pasar el test."""
    user, _grupo = _profesor(
        django_user_model,
        "raiz@x.es",
        Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0],
        "9-Z",
    )
    client.force_login(user)

    respuesta = client.get(reverse("clases:index"))

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("clases:class_session_list")


def test_la_redireccion_de_la_raiz_no_es_permanente(db, client):
    """Un 301 se le queda grabado al navegador y no hay forma de despegarlo
    desde el servidor el día que `/clases/` tenga portada propia."""
    respuesta = client.get(reverse("clases:index"))

    assert respuesta.status_code == 302, "una permanente sería un 301"
