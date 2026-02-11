# ruff: noqa: ERA001, E501
import json

import pytest
from django.test import Client
from django.urls import reverse

from ..models import Comentario
from ..models import Incidencia
from ..models import Tecnico
from .factories import ComentarioFactory
from .factories import EtiquetaFactory
from .factories import IncidenciaFactory
from .factories import TecnicoFactory
from .factories import UbicacionFactory

from martina_bescos_app.users.tests.factories import UserFactory


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def tecnico(db):
    return TecnicoFactory()


@pytest.fixture
def tecnico_client(tecnico):
    c = Client()
    c.force_login(tecnico.user)
    return c


@pytest.fixture
def superuser(db):
    user = UserFactory(is_superuser=True, is_staff=True)
    return user


@pytest.fixture
def superuser_client(superuser):
    c = Client()
    c.force_login(superuser)
    return c


# =============================================================================
# LandingView
# =============================================================================


@pytest.mark.django_db
class TestLandingView:
    def test_renders(self, client):
        response = client.get(reverse("incidencias:landing"))
        assert response.status_code == 200

    def test_shows_public_incidencias(self, client):
        inc = IncidenciaFactory(es_privada=False)
        response = client.get(reverse("incidencias:landing"))
        assert inc.titulo in response.content.decode()

    def test_hides_private_incidencias_from_anonymous(self, client):
        inc = IncidenciaFactory(es_privada=True)
        response = client.get(reverse("incidencias:landing"))
        assert inc.titulo not in response.content.decode()

    def test_counts_by_estado(self, client):
        IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        IncidenciaFactory(estado=Incidencia.Estado.EN_PROGRESO)
        IncidenciaFactory(estado=Incidencia.Estado.RESUELTA)
        response = client.get(reverse("incidencias:landing"))
        context = response.context
        assert context["total_pendientes"] == 1
        assert context["total_en_progreso"] == 1
        assert context["total_resueltas"] == 1


# =============================================================================
# BuscarView
# =============================================================================


@pytest.mark.django_db
class TestBuscarView:
    def test_search_by_titulo(self, client):
        IncidenciaFactory(titulo="Proyector roto")
        IncidenciaFactory(titulo="Ordenador lento")
        response = client.get(reverse("incidencias:buscar"), {"q": "Proyector"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Proyector roto" in content
        assert "Ordenador lento" not in content

    def test_search_by_descripcion(self, client):
        IncidenciaFactory(titulo="Inc1", descripcion="El ratón no funciona")
        response = client.get(reverse("incidencias:buscar"), {"q": "ratón"})
        assert "Inc1" in response.content.decode()

    def test_search_by_etiqueta(self, client):
        et = EtiquetaFactory(nombre="WiFi")
        IncidenciaFactory(titulo="Sin WiFi", etiquetas=[et])
        response = client.get(reverse("incidencias:buscar"), {"q": "WiFi"})
        assert "Sin WiFi" in response.content.decode()

    def test_empty_search(self, client):
        IncidenciaFactory(titulo="Algo")
        response = client.get(reverse("incidencias:buscar"), {"q": ""})
        assert "Algo" in response.content.decode()


# =============================================================================
# CrearIncidenciaView
# =============================================================================


@pytest.mark.django_db
class TestCrearIncidenciaView:
    def test_get_renders_form(self, client):
        response = client.get(reverse("incidencias:crear"))
        assert response.status_code == 200
        assert "form" in response.context

    def test_post_creates_incidencia(self, client):
        ubi = UbicacionFactory()
        data = {
            "titulo": "Nueva incidencia test",
            "descripcion": "Descripción de prueba",
            "urgencia": "media",
            "reportero_nombre": "Prof. García",
            "ubicacion": ubi.pk,
            "es_privada": False,
            "etiquetas_ids": "",
        }
        response = client.post(reverse("incidencias:crear"), data)
        assert response.status_code == 302
        assert Incidencia.objects.filter(titulo="Nueva incidencia test").exists()

    def test_post_sets_cookie(self, client):
        ubi = UbicacionFactory()
        data = {
            "titulo": "Cookie test",
            "descripcion": "",
            "urgencia": "baja",
            "reportero_nombre": "Prof. Test",
            "ubicacion": ubi.pk,
            "es_privada": False,
            "etiquetas_ids": "",
        }
        response = client.post(reverse("incidencias:crear"), data)
        assert "incidencias_reportero" in response.cookies

    def test_post_with_etiquetas(self, client):
        ubi = UbicacionFactory()
        et1 = EtiquetaFactory()
        et2 = EtiquetaFactory()
        data = {
            "titulo": "Con etiquetas",
            "descripcion": "",
            "urgencia": "alta",
            "reportero_nombre": "Prof. Tag",
            "ubicacion": ubi.pk,
            "es_privada": False,
            "etiquetas_ids": f"{et1.pk},{et2.pk}",
        }
        client.post(reverse("incidencias:crear"), data)
        inc = Incidencia.objects.get(titulo="Con etiquetas")
        assert inc.etiquetas.count() == 2


# =============================================================================
# DetalleIncidenciaView
# =============================================================================


@pytest.mark.django_db
class TestDetalleIncidenciaView:
    def test_renders(self, client):
        inc = IncidenciaFactory(es_privada=False)
        response = client.get(reverse("incidencias:detalle", args=[inc.pk]))
        assert response.status_code == 200
        assert inc.titulo in response.content.decode()

    def test_shows_comentarios(self, client):
        inc = IncidenciaFactory(es_privada=False)
        com = ComentarioFactory(incidencia=inc, texto="Comentario de prueba")
        response = client.get(reverse("incidencias:detalle", args=[inc.pk]))
        assert "Comentario de prueba" in response.content.decode()

    def test_private_redirects_anonymous(self, client):
        inc = IncidenciaFactory(es_privada=True)
        response = client.get(reverse("incidencias:detalle", args=[inc.pk]))
        assert response.status_code == 302
        assert "login" in response.url.lower() or "account" in response.url.lower()

    def test_private_accessible_to_logged_in(self, tecnico_client):
        inc = IncidenciaFactory(es_privada=True)
        response = tecnico_client.get(reverse("incidencias:detalle", args=[inc.pk]))
        assert response.status_code == 200


# =============================================================================
# AgregarComentarioView
# =============================================================================


@pytest.mark.django_db
class TestAgregarComentarioView:
    def test_post_creates_comentario(self, client):
        inc = IncidenciaFactory()
        data = {
            "autor_nombre": "María",
            "texto": "Ya lo he mirado",
        }
        response = client.post(reverse("incidencias:comentar", args=[inc.pk]), data)
        assert response.status_code == 302
        assert Comentario.objects.filter(incidencia=inc, texto="Ya lo he mirado").exists()

    def test_post_invalid_data(self, client):
        inc = IncidenciaFactory()
        data = {"autor_nombre": "", "texto": ""}
        response = client.post(reverse("incidencias:comentar", args=[inc.pk]), data)
        # Redirects even on invalid (form not re-rendered)
        assert response.status_code == 302
        assert Comentario.objects.filter(incidencia=inc).count() == 0


# =============================================================================
# ApiUbicacionesView
# =============================================================================


@pytest.mark.django_db
class TestApiUbicacionesView:
    def test_returns_json(self, client):
        UbicacionFactory(nombre="Laboratorio")
        response = client.get(reverse("incidencias:api_ubicaciones"))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_search_filter(self, client):
        UbicacionFactory(nombre="Xyzxyz-Especial")
        UbicacionFactory(nombre="Gimnasio-Filtro")
        response = client.get(reverse("incidencias:api_ubicaciones"), {"q": "Xyzxyz"})
        data = response.json()
        assert len(data) == 1
        assert data[0]["nombre"] == "Xyzxyz-Especial"


# =============================================================================
# ApiEtiquetasView
# =============================================================================


@pytest.mark.django_db
class TestApiEtiquetasView:
    def test_returns_json(self, client):
        EtiquetaFactory(nombre="Internet")
        response = client.get(reverse("incidencias:api_etiquetas"))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_search_filter(self, client):
        EtiquetaFactory(nombre="Internet", slug="internet")
        EtiquetaFactory(nombre="Proyector", slug="proyector")
        response = client.get(reverse("incidencias:api_etiquetas"), {"q": "Inter"})
        data = response.json()
        assert len(data) == 1
        assert data[0]["text"] == "Internet"


# =============================================================================
# PanelDashboardView
# =============================================================================


@pytest.mark.django_db
class TestPanelDashboardView:
    def test_requires_auth(self, client):
        response = client.get(reverse("incidencias:panel"))
        assert response.status_code == 302  # Redirect to login

    def test_requires_tecnico(self, client, db):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("incidencias:panel"))
        assert response.status_code in (302, 403)  # Redirect to login or Permission Denied

    def test_superuser_can_access(self, superuser_client):
        response = superuser_client.get(reverse("incidencias:panel"))
        assert response.status_code == 200

    def test_tecnico_can_access(self, tecnico_client):
        response = tecnico_client.get(reverse("incidencias:panel"))
        assert response.status_code == 200

    def test_shows_kanban_columns(self, tecnico_client):
        IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE, titulo="Pendiente test")
        IncidenciaFactory(estado=Incidencia.Estado.EN_PROGRESO, titulo="Progreso test")
        IncidenciaFactory(estado=Incidencia.Estado.RESUELTA, titulo="Resuelta test")
        response = tecnico_client.get(reverse("incidencias:panel"))
        context = response.context
        pendientes = list(context["pendientes"])
        en_progreso = list(context["en_progreso"])
        resueltas = list(context["resueltas"])
        assert len(pendientes) == 1
        assert len(en_progreso) == 1
        assert len(resueltas) == 1

    def test_filter_by_planta(self, tecnico_client):
        ubi_pb = UbicacionFactory(nombre="Aula PB", planta="PB")
        ubi_p1 = UbicacionFactory(nombre="Aula P1", planta="P1")
        IncidenciaFactory(titulo="En PB", ubicacion=ubi_pb)
        IncidenciaFactory(titulo="En P1", ubicacion=ubi_p1)
        response = tecnico_client.get(reverse("incidencias:panel"), {"planta": "PB"})
        pendientes = list(response.context["pendientes"])
        assert len(pendientes) == 1
        assert pendientes[0].titulo == "En PB"

    def test_filter_by_urgencia(self, tecnico_client):
        IncidenciaFactory(titulo="Urgente", urgencia="critica")
        IncidenciaFactory(titulo="Normal", urgencia="baja")
        response = tecnico_client.get(reverse("incidencias:panel"), {"urgencia": "critica"})
        pendientes = list(response.context["pendientes"])
        assert len(pendientes) == 1
        assert pendientes[0].titulo == "Urgente"

    def test_mis_incidencias(self, tecnico_client, tecnico):
        IncidenciaFactory(titulo="Mía", asignado_a=tecnico, estado=Incidencia.Estado.PENDIENTE)
        IncidenciaFactory(titulo="De otro")
        response = tecnico_client.get(reverse("incidencias:panel"))
        mis = list(response.context["mis_incidencias"])
        assert len(mis) == 1
        assert mis[0].titulo == "Mía"

    def test_card_has_overflow_visible(self, tecnico_client):
        """Cards must have overflow-visible so dropdowns are not clipped."""
        IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        response = tecnico_client.get(reverse("incidencias:panel"))
        content = response.content.decode()
        assert "overflow-visible" in content

    def test_dropdown_has_high_z_index(self, tecnico_client):
        """Dropdown must use z-50 to sit above sibling cards."""
        IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        response = tecnico_client.get(reverse("incidencias:panel"))
        content = response.content.decode()
        assert "z-50" in content

    def test_kanban_cards_have_descending_zindex(self, tecnico_client):
        """Kanban contains JS function to assign descending z-index to cards."""
        IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        response = tecnico_client.get(reverse("incidencias:panel"))
        content = response.content.decode()
        assert "assignCardZIndex" in content or "assignZIndex" in content


# =============================================================================
# Custom Navbar Tests
# =============================================================================


@pytest.mark.django_db
class TestIncidenciasNavbar:
    def test_landing_has_custom_title(self, client):
        """Navbar must show 'Incidencias Tecnológicas IES Martina Bescós'."""
        response = client.get(reverse("incidencias:landing"))
        content = response.content.decode()
        assert "Incidencias Tecnológicas" in content
        assert "IES Martina Bescós" in content

    def test_landing_does_not_show_music_app(self, client):
        """Navbar must NOT show the Music App title."""
        response = client.get(reverse("incidencias:landing"))
        content = response.content.decode()
        assert "Music App" not in content

    def test_landing_has_theme_toggle(self, client):
        """Navbar must have a theme toggle button."""
        response = client.get(reverse("incidencias:landing"))
        content = response.content.decode()
        assert "theme-toggle" in content or "swap swap-rotate" in content

    def test_panel_has_custom_title(self, tecnico_client):
        """Panel navbar must show incidencias title."""
        response = tecnico_client.get(reverse("incidencias:panel"))
        content = response.content.decode()
        assert "Incidencias Tecnológicas" in content

    def test_panel_does_not_show_music_app(self, tecnico_client):
        """Panel navbar must NOT show Music App title."""
        response = tecnico_client.get(reverse("incidencias:panel"))
        content = response.content.decode()
        assert "Music App" not in content

    def test_authenticated_user_sees_profile_link(self, tecnico_client, tecnico):
        """Logged in users should see their profile info in the navbar."""
        response = tecnico_client.get(reverse("incidencias:panel"))
        content = response.content.decode()
        assert "Cerrar sesión" in content or "Sign Out" in content or "Logout" in content


# =============================================================================
# AsignarIncidenciaView
# =============================================================================


@pytest.mark.django_db
class TestAsignarIncidenciaView:
    def test_self_assign(self, tecnico_client, tecnico):
        inc = IncidenciaFactory()
        response = tecnico_client.post(
            reverse("incidencias:panel_asignar", args=[inc.pk]),
            {"tecnico_id": "self"},
        )
        assert response.status_code == 302
        inc.refresh_from_db()
        assert inc.asignado_a == tecnico

    def test_assign_to_other(self, tecnico_client):
        other = TecnicoFactory()
        inc = IncidenciaFactory()
        response = tecnico_client.post(
            reverse("incidencias:panel_asignar", args=[inc.pk]),
            {"tecnico_id": str(other.pk)},
        )
        assert response.status_code == 302
        inc.refresh_from_db()
        assert inc.asignado_a == other

    def test_unassign(self, tecnico_client, tecnico):
        inc = IncidenciaFactory(asignado_a=tecnico)
        response = tecnico_client.post(
            reverse("incidencias:panel_asignar", args=[inc.pk]),
            {"tecnico_id": "none"},
        )
        assert response.status_code == 302
        inc.refresh_from_db()
        assert inc.asignado_a is None

    def test_creates_historial(self, tecnico_client, tecnico):
        inc = IncidenciaFactory()
        tecnico_client.post(
            reverse("incidencias:panel_asignar", args=[inc.pk]),
            {"tecnico_id": "self"},
        )
        assert inc.historial_asignaciones.count() == 1


# =============================================================================
# CambiarEstadoView
# =============================================================================


@pytest.mark.django_db
class TestCambiarEstadoView:
    def test_changes_estado(self, tecnico_client):
        inc = IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        response = tecnico_client.post(
            reverse("incidencias:panel_estado", args=[inc.pk]),
            {"estado": "en_progreso"},
        )
        assert response.status_code == 302
        inc.refresh_from_db()
        assert inc.estado == Incidencia.Estado.EN_PROGRESO

    def test_rejects_invalid_estado(self, tecnico_client):
        inc = IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        tecnico_client.post(
            reverse("incidencias:panel_estado", args=[inc.pk]),
            {"estado": "invalid_state"},
        )
        inc.refresh_from_db()
        assert inc.estado == Incidencia.Estado.PENDIENTE  # Unchanged

    def test_requires_auth(self, client):
        inc = IncidenciaFactory()
        response = client.post(
            reverse("incidencias:panel_estado", args=[inc.pk]),
            {"estado": "en_progreso"},
        )
        assert response.status_code == 302  # Redirect to login


# =============================================================================
# GestionTecnicosView
# =============================================================================


@pytest.mark.django_db
class TestGestionTecnicosView:
    def test_renders(self, tecnico_client):
        response = tecnico_client.get(reverse("incidencias:panel_tecnicos"))
        assert response.status_code == 200

    def test_add_tecnico(self, tecnico_client):
        response = tecnico_client.post(
            reverse("incidencias:panel_tecnicos"),
            {"action": "add", "email": "nuevo@test.com", "nombre": "Nuevo Técnico"},
        )
        assert response.status_code == 302
        assert Tecnico.objects.filter(user__email="nuevo@test.com").exists()

    def test_toggle_tecnico(self, tecnico_client):
        otro = TecnicoFactory(activo=True)
        tecnico_client.post(
            reverse("incidencias:panel_tecnicos"),
            {"action": "toggle", "tecnico_id": str(otro.pk)},
        )
        otro.refresh_from_db()
        assert otro.activo is False

    def test_requires_auth(self, client):
        response = client.get(reverse("incidencias:panel_tecnicos"))
        assert response.status_code == 302


# =============================================================================
# CambiarEstadoApiView (Drag-and-Drop API — NEW)
# =============================================================================


@pytest.mark.django_db
class TestCambiarEstadoApiView:
    def test_changes_estado_via_api(self, tecnico_client):
        inc = IncidenciaFactory(estado=Incidencia.Estado.PENDIENTE)
        response = tecnico_client.post(
            reverse("incidencias:panel_estado_api", args=[inc.pk]),
            data=json.dumps({"estado": "en_progreso"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        inc.refresh_from_db()
        assert inc.estado == Incidencia.Estado.EN_PROGRESO

    def test_returns_error_for_invalid_estado(self, tecnico_client):
        inc = IncidenciaFactory()
        response = tecnico_client.post(
            reverse("incidencias:panel_estado_api", args=[inc.pk]),
            data=json.dumps({"estado": "invalid"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False

    def test_requires_auth(self, client):
        inc = IncidenciaFactory()
        response = client.post(
            reverse("incidencias:panel_estado_api", args=[inc.pk]),
            data=json.dumps({"estado": "en_progreso"}),
            content_type="application/json",
        )
        assert response.status_code == 302  # Redirect to login

    def test_returns_404_for_nonexistent(self, tecnico_client):
        response = tecnico_client.post(
            reverse("incidencias:panel_estado_api", args=[99999]),
            data=json.dumps({"estado": "en_progreso"}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_move_to_resuelta(self, tecnico_client):
        inc = IncidenciaFactory(estado=Incidencia.Estado.EN_PROGRESO)
        response = tecnico_client.post(
            reverse("incidencias:panel_estado_api", args=[inc.pk]),
            data=json.dumps({"estado": "resuelta"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        inc.refresh_from_db()
        assert inc.estado == Incidencia.Estado.RESUELTA

    def test_move_back_to_pendiente(self, tecnico_client):
        inc = IncidenciaFactory(estado=Incidencia.Estado.RESUELTA)
        response = tecnico_client.post(
            reverse("incidencias:panel_estado_api", args=[inc.pk]),
            data=json.dumps({"estado": "pendiente"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        inc.refresh_from_db()
        assert inc.estado == Incidencia.Estado.PENDIENTE
