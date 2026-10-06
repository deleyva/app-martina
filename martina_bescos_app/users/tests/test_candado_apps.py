"""La app de música de `apps.` es solo para música; lo demás, para todo el centro.

Existe porque el 2026-10-06 Jesús vio en `/analytics/` a cinco profesores de
otros departamentos dentro de la app. Ninguno la usaba: entraban a poner una
incidencia y el login los dejaba en su perfil, pintado con la app de música.

Se prueba por HTTP y con el `Host` de cada dominio, porque el candado vive en
el middleware y depende del dominio.
"""

import pytest
from wagtail.models import Page, Site

from clases.models import Enrollment, Group, Subject

APPS = "apps.iesmartinabescos.es"
BLOGS = "blogs.iesmartinabescos.es"
RUTA_MUSICA = "/my-library/"


@pytest.fixture(autouse=True)
def sitios(db, settings):
    """El sitio de blogs de Wagtail, con su `BlogIndexPage` de raíz.

    `apps.` no necesita sitio propio: un dominio sin sitio cae en el de por
    defecto, que es la app.
    """
    from blogs.models import BlogIndexPage

    settings.ALLOWED_HOSTS = [APPS, BLOGS, "testserver"]
    settings.APPS_CANDADO = True
    portada = BlogIndexPage(title="Blogs", slug="portada-candado")
    Page.get_first_root_node().add_child(instance=portada)
    Site.objects.create(hostname=BLOGS, port=80, root_page=portada, site_name="Blogs")
    Site.clear_site_root_paths_cache()


@pytest.fixture
def grupo(db):
    asignatura = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]
    return Group.objects.create(name="1-A", subject=asignatura, academic_year="2026-2027")


def _usuario(django_user_model, correo, **extra):
    return django_user_model.objects.create_user(email=correo, password="x", **extra)


def _get(client, user, ruta, host=APPS):
    client.force_login(user)
    return client.get(ruta, HTTP_HOST=host)


def test_profesor_de_otro_departamento_no_entra_en_la_app(client, django_user_model):
    user = _usuario(django_user_model, "fisica@iesmartinabescos.es")
    r = _get(client, user, RUTA_MUSICA)
    assert r.status_code == 403
    assert b"Esta parte es la app de m" in r.content
    assert b"analytics.js" not in r.content, "la página de rechazo no debe contar como visita"


def test_la_raiz_de_apps_tambien_esta_cerrada(client, django_user_model):
    user = _usuario(django_user_model, "fisica@iesmartinabescos.es")
    assert _get(client, user, "/").status_code == 403


@pytest.mark.parametrize(
    "ruta",
    ["/incidencias/", "/wifi/", "/accounts/logout/", "/clases/groups/join/00000000-0000-0000-0000-000000000000/"],
)
def test_lo_que_es_de_todo_el_centro_sigue_abierto(client, django_user_model, ruta):
    user = _usuario(django_user_model, "fisica@iesmartinabescos.es")
    assert _get(client, user, ruta).status_code != 403


def test_en_blogs_el_candado_no_actua(client, django_user_model):
    user = _usuario(django_user_model, "fisica@iesmartinabescos.es")
    assert _get(client, user, RUTA_MUSICA, host=BLOGS).status_code != 403


def test_anonimo_no_ve_el_candado(client):
    r = client.get(RUTA_MUSICA, HTTP_HOST=APPS)
    assert r.status_code != 403


def test_profesor_de_musica_entra(client, django_user_model, grupo):
    user = _usuario(django_user_model, "sheila@iesmartinabescos.es")
    grupo.teachers.add(user)
    assert _get(client, user, RUTA_MUSICA).status_code != 403


def test_alumno_matriculado_entra(client, django_user_model, grupo):
    user = _usuario(django_user_model, "12345@iesmartinabescos.es")
    Enrollment.objects.create(user=user, group=grupo, is_active=True)
    assert _get(client, user, RUTA_MUSICA).status_code != 403


def test_matricula_inactiva_no_basta(client, django_user_model, grupo):
    user = _usuario(django_user_model, "12345@iesmartinabescos.es")
    Enrollment.objects.create(user=user, group=grupo, is_active=False)
    assert _get(client, user, RUTA_MUSICA).status_code == 403


def test_alta_externa_del_administrador_entra(client, django_user_model):
    user = _usuario(django_user_model, "fuera@gmail.com", acceso_con_contrasena=True)
    assert _get(client, user, RUTA_MUSICA).status_code != 403


def test_staff_entra(client, django_user_model):
    user = _usuario(django_user_model, "admin@iesmartinabescos.es", is_staff=True)
    assert _get(client, user, RUTA_MUSICA).status_code != 403


def test_tras_el_login_el_profesorado_general_va_a_incidencias(rf, django_user_model):
    from django.contrib.sessions.middleware import SessionMiddleware

    from martina_bescos_app.users.adapters import AccountAdapter

    def _redirect(user, modo=None):
        request = rf.get("/accounts/login/", HTTP_HOST=APPS)
        SessionMiddleware(lambda r: None).process_request(request)
        if modo:
            request.session["app_mode"] = modo
        request.user = user
        return AccountAdapter(request).get_login_redirect_url(request)

    otro = _usuario(django_user_model, "fisica@iesmartinabescos.es")
    assert _redirect(otro) == "/incidencias/"
    assert _redirect(otro, "wifi") == "/wifi/"

    staff = _usuario(django_user_model, "admin@iesmartinabescos.es", is_staff=True)
    assert _redirect(staff) != "/incidencias/"
