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
    assert b"Esta es la app de m" in r.content
    assert b"analytics.js" not in r.content, "la página de rechazo no debe contar como visita"
    assert b"{#" not in r.content


def test_el_candado_no_lleva_a_otras_apps(client, django_user_model):
    """Las apps de `apps.` están aisladas (2026-11-06).

    Desde la app de música no se llega a incidencias, wifi ni blogs pulsando
    botones: quien quiera ir sabe la dirección o tiene su acceso directo.
    """
    user = _usuario(django_user_model, "fisica@iesmartinabescos.es")
    html = _get(client, user, RUTA_MUSICA).content.decode()
    for prohibido in ("/incidencias/", "/wifi/", "blogs.iesmartinabescos.es"):
        assert prohibido not in html, prohibido
    assert "pide acceso a Jesús López" in html
    assert "enlace de invitación" in html


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


def test_tras_el_login_cada_uno_vuelve_a_su_app(rf, django_user_model):
    """Quien entra por la app de música no acaba en incidencias.

    El 2026-11-06 una profesora aún sin alta entró por la portada de `apps.` y
    el login la dejó en `/incidencias/`. Quien viene de incidencias o de wifi
    sí vuelve allí: es su app.
    """
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
    assert _redirect(otro) == "/"
    assert _redirect(otro, "incidencias") == "/incidencias/"
    assert _redirect(otro, "wifi") == "/wifi/"

    staff = _usuario(django_user_model, "admin@iesmartinabescos.es", is_staff=True)
    assert _redirect(staff) != "/incidencias/"


@pytest.mark.parametrize(
    ("desde", "acaba_en"),
    [("/", "/"), ("/incidencias/", "/incidencias/")],
)
def test_el_login_de_verdad_no_cruza_de_app(client, django_user_model, desde, acaba_en):
    """El camino entero: visitar una app, entrar con contraseña, ver adónde lleva.

    Sin `next`, como hizo la profesora del 2026-11-06. Desde la portada de
    música el login acaba en la portada (y ahí el candado); desde incidencias,
    en incidencias.
    """
    from allauth.account.models import EmailAddress

    correo = "fisica@iesmartinabescos.es"
    user = _usuario(django_user_model, correo)
    EmailAddress.objects.create(user=user, email=correo, verified=True, primary=True)

    client.get(desde, HTTP_HOST=APPS)
    r = client.post(
        "/accounts/login/",
        {"login": correo, "password": "x"},
        HTTP_HOST=APPS,
    )
    assert r.status_code == 302, r.content[:300]
    assert r["Location"] == acaba_en
    if acaba_en == "/":
        pagina = client.get("/", HTTP_HOST=APPS)
        assert pagina.status_code == 403
        assert b"/incidencias/" not in pagina.content


def test_un_profesor_invitado_ve_la_barra_de_la_app(client, django_user_model):
    """La barra de iconos no puede depender de estar matriculado.

    Hasta el 2026-11-06 salía solo con `enrollments` o `is_staff`. Un profesor
    invitado no es ninguna de las dos cosas, así que entraba en una app sin
    Sesiones, Mi librería ni Calificaciones en la barra. Jesús, que es staff,
    nunca lo vio.
    """
    from django.contrib.auth.models import Group as GrupoDePermisos
    from django.urls import reverse

    from martina_bescos_app.users.permisos import GRUPO_PROFESORADO

    user = _usuario(django_user_model, "nueva.musica@iesmartinabescos.es")
    user.groups.add(GrupoDePermisos.objects.get_or_create(name=GRUPO_PROFESORADO)[0])
    html = _get(client, user, reverse("clases:class_session_list")).content.decode()
    for destino in ("my_library:inicio", "clases:class_session_list", "calificaciones:index"):
        assert f'href="{reverse(destino)}"' in html, destino
