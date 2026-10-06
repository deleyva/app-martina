# ruff: noqa: E501, PLR2004
"""Menciones con @usuario en comentarios: avisan solo de ese comentario (fase 66)."""

import pytest
from api_keys.models import APIKey
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse

from incidencias.models import Comentario
from incidencias.services import acciones
from incidencias.tests.factories import IncidenciaFactory
from incidencias.tests.factories import TecnicoFactory

User = get_user_model()
DOMINIO = "iesmartinabescos.es"


@pytest.fixture
def ana(db):
    return User.objects.create_user(email=f"ana@{DOMINIO}", password="x")


@pytest.fixture
def incidencia(db):
    return IncidenciaFactory(titulo="Persiana rota", reportero_nombre="reportera")


def _comentar(django_capture_on_commit_callbacks, incidencia, autor, texto):
    with django_capture_on_commit_callbacks(execute=True):
        return acciones.comentar(incidencia, autor, texto)


def _destinatarios_de_mencion():
    return [d for m in mail.outbox if "te menciona" in m.subject for d in m.to]


# --- Lectura del texto ------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Mira esto @ana", ["ana"]),
        ("@Ana, @ana y @luis.perez.", ["ana", "luis.perez"]),
        ("Escríbele a jlopez@iesmartinabescos.es", []),
        ("Sin menciones", []),
        ("(@ana)", ["ana"]),
    ],
)
def test_usuarios_citados(texto, esperado):
    assert Comentario.usuarios_citados(texto) == esperado


@pytest.mark.django_db
def test_solo_usuarios_activos_que_existen(ana):
    User.objects.create_user(email=f"baja@{DOMINIO}", password="x", is_active=False)
    c = Comentario(texto="@ana @baja @noexiste @ANA")
    assert c.correos_mencionados() == [f"ana@{DOMINIO}"]


# --- Avisos ------------------------------------------------------------------------


@pytest.mark.django_db
def test_mencion_avisa_a_la_persona_citada(ana, incidencia, django_capture_on_commit_callbacks):
    _comentar(django_capture_on_commit_callbacks, incidencia, "secretaria", "¿Puedes mirarlo, @ana?")
    assert _destinatarios_de_mencion() == [f"ana@{DOMINIO}"]
    aviso = next(m for m in mail.outbox if "te menciona" in m.subject)
    assert aviso.subject == "[Incidencias] secretaria te menciona en: Persiana rota"
    assert "¿Puedes mirarlo, @ana?" in aviso.body
    assert f"/{incidencia.pk}/" in aviso.body
    # Los participantes siguen recibiendo su aviso de siempre
    normal = next(m for m in mail.outbox if "Nuevo comentario" in m.subject)
    assert normal.to == [f"reportera@{DOMINIO}"]


@pytest.mark.django_db
def test_mencionada_no_recibe_los_siguientes(ana, incidencia, django_capture_on_commit_callbacks):
    _comentar(django_capture_on_commit_callbacks, incidencia, "secretaria", "Ojo @ana")
    mail.outbox.clear()
    _comentar(django_capture_on_commit_callbacks, incidencia, "secretaria", "Ya está pedido el repuesto")
    destinatarios = {d for m in mail.outbox for d in m.to}
    assert f"ana@{DOMINIO}" not in destinatarios
    assert f"reportera@{DOMINIO}" in destinatarios


@pytest.mark.django_db
def test_sin_duplicados_ni_autoaviso(incidencia, django_capture_on_commit_callbacks):
    for u in ("reportera", "secretaria"):
        User.objects.create_user(email=f"{u}@{DOMINIO}", password="x")
    _comentar(django_capture_on_commit_callbacks, incidencia, "secretaria", "@reportera @secretaria mirad")
    # La reportera ya es participante: un solo correo, el normal. La autora no se avisa a sí misma.
    assert _destinatarios_de_mencion() == []
    todos = [d for m in mail.outbox for d in m.to]
    assert todos.count(f"reportera@{DOMINIO}") == 1
    assert f"secretaria@{DOMINIO}" not in todos


@pytest.mark.django_db
def test_mencion_inexistente_no_manda_nada_fuera(incidencia, django_capture_on_commit_callbacks):
    _comentar(django_capture_on_commit_callbacks, incidencia, "secretaria", "@fulanito y @otro@gmail.com")
    assert _destinatarios_de_mencion() == []
    assert all(d.endswith(f"@{DOMINIO}") for m in mail.outbox for d in m.to)


@pytest.mark.django_db
def test_mencion_por_api(ana, incidencia, django_capture_on_commit_callbacks):
    tecnico = TecnicoFactory(user__email=f"secretaria@{DOMINIO}")
    clave = APIKey.objects.create(name="skill", user=tecnico.user)
    with django_capture_on_commit_callbacks(execute=True):
        r = Client().post(
            f"/api/incidencias/{incidencia.pk}/comentar",
            {"texto": "Para @ana"},
            content_type="application/json",
            HTTP_X_API_KEY=str(clave.key),
        )
    assert r.status_code == 200
    assert _destinatarios_de_mencion() == [f"ana@{DOMINIO}"]


# --- Pantalla ----------------------------------------------------------------------


@pytest.mark.django_db
def test_detalle_resalta_menciones_y_escapa(ana, incidencia):
    Comentario.objects.create(incidencia=incidencia, autor_nombre="secretaria", texto="Hola @ana <script>alert(1)</script>\nsegunda línea")
    html = Client().get(reverse("incidencias:detalle", args=[incidencia.pk])).content.decode()
    assert 'title="Le ha llegado este comentario por correo">@ana</span>' in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<br>segunda línea" in html
    assert "Para avisar a alguien, escribe" in html
    assert "{#" not in html


@pytest.mark.django_db
def test_mencion_a_quien_no_existe_no_se_resalta(incidencia):
    Comentario.objects.create(incidencia=incidencia, autor_nombre="secretaria", texto="Hola @fulanito")
    html = Client().get(reverse("incidencias:detalle", args=[incidencia.pk])).content.decode()
    assert "Hola @fulanito" in html
    assert ">@fulanito</span>" not in html


@pytest.mark.django_db
def test_enlaces_se_pueden_pulsar(ana, incidencia):
    Comentario.objects.create(
        incidencia=incidencia,
        autor_nombre="jlopez",
        texto='Guía: https://docs.iesmartinabescos.es/books/x/page/y. Y otra (https://a.es/?p=1&q=2), @ana mira https://b.es/@ana"onmouseover=alert(1)',
    )
    html = Client().get(reverse("incidencias:detalle", args=[incidencia.pk])).content.decode()
    assert '<a href="https://docs.iesmartinabescos.es/books/x/page/y" class="link' in html
    assert 'page/y</a>.' in html  # el punto final se queda fuera
    assert '<a href="https://a.es/?p=1&amp;q=2"' in html
    assert '2</a>)' in html  # el paréntesis de cierre también
    assert 'title="Le ha llegado este comentario por correo">@ana</span> mira' in html
    assert '<a href="https://b.es/@ana"' in html  # la @ de la URL no es mención
    assert 'onmouseover=alert(1)"' not in html
    assert 'rel="noopener noreferrer"' in html
