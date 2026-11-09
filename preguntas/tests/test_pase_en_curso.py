"""Fase 105: `/pase/`, el mando del móvil, y que dos pantallas no se pisen.

`/pase/` es la dirección que Jesús guarda en la pantalla de inicio del iPhone:
tiene que llevar siempre al pase que está corriendo, sin navegar, y quedarse
quieta (sin redirigir) para que el icono valga la clase siguiente.
"""

import datetime as dt

import pytest
from django.contrib.auth.models import Group as GrupoPermisos
from django.urls import reverse
from django.utils import timezone

from clases.models import ClassSessionItem, Enrollment, Group
from martina_bescos_app.users.permisos import GRUPO_PROFESORADO
from martina_bescos_app.users.tests.factories import UserFactory
from preguntas import vivo
from preguntas.models import Pase

from .conftest import pregunta, sesion


@pytest.fixture
def preguntas(db):
    return [pregunta(f"Pregunta {i}", correcta=i) for i in range(3)]


@pytest.fixture
def otro_grupo(grupo, profesor):
    g = Group.objects.create(name="3º ESO Y", subject=grupo.subject, academic_year="2026-2027")
    g.teachers.add(profesor)
    return g


def _pase(grupo, fecha, preguntas, profesor):
    pase, _item = vivo.crear_desde_sesion(sesion(grupo, fecha), preguntas, profesor)
    return pase


def _otro_profesor(email="otra@x.es"):
    u = UserFactory(email=email, name="Otra Profe")
    u.groups.add(GrupoPermisos.objects.get_or_create(name=GRUPO_PROFESORADO)[0])
    return u


# =============================================================================
# C721 — Dos pantallas no se pisan
# =============================================================================


@pytest.mark.django_db
class TestDesde:
    @pytest.fixture
    def abierto(self, grupo, preguntas, profesor, client):
        pase = vivo.abrir(_pase(grupo, timezone.localdate(), preguntas, profesor))
        client.force_login(profesor)
        return pase

    def _orden(self, client, nombre, pase, desde=None):
        datos = {} if desde is None else {"desde": str(desde)}
        return client.post(reverse(f"preguntas:{nombre}", args=[pase.pk]), datos)

    def test_dos_siguientes_desde_la_misma_pregunta_avanzan_una(self, client, abierto):
        primera = self._orden(client, "pase_siguiente", abierto, desde=0)
        segunda = self._orden(client, "pase_siguiente", abierto, desde=0)
        assert primera.status_code == segunda.status_code == 200
        abierto.refresh_from_db()
        assert abierto.posicion == 1
        assert "ignorada" not in primera.json()
        assert segunda.json()["ignorada"] is True
        assert segunda.json()["posicion"] == 1

    def test_revelar_que_llega_tarde_no_revela_la_pregunta_nueva(self, client, abierto):
        self._orden(client, "pase_siguiente", abierto, desde=0)
        r = self._orden(client, "pase_revelar", abierto, desde=0)
        assert r.json()["ignorada"] is True
        abierto.refresh_from_db()
        assert abierto.actual().revelada is False

    def test_revelar_desde_la_pregunta_en_pantalla_revela(self, client, abierto):
        r = self._orden(client, "pase_revelar", abierto, desde=0)
        assert "ignorada" not in r.json()
        assert abierto.actual().revelada is True

    def test_sin_desde_todo_sigue_como_antes(self, client, abierto):
        self._orden(client, "pase_siguiente", abierto)
        self._orden(client, "pase_siguiente", abierto)
        abierto.refresh_from_db()
        assert abierto.posicion == 2

    def test_anterior_en_la_vuelta_tambien_mira_desde(self, client, abierto):
        for i in range(3):
            self._orden(client, "pase_siguiente", abierto, desde=i)
        client.post(reverse("preguntas:pase_revisar", args=[abierto.pk]))
        self._orden(client, "pase_siguiente", abierto, desde=0)
        self._orden(client, "pase_anterior", abierto, desde=1)
        r = self._orden(client, "pase_anterior", abierto, desde=1)
        assert r.json()["ignorada"] is True
        abierto.refresh_from_db()
        assert abierto.revision and abierto.posicion == 0


# =============================================================================
# C718 — Qué abre /pase/
# =============================================================================


@pytest.mark.django_db
class TestEnCurso:
    def test_lo_abierto_hoy_gana_a_lo_preparado_hoy(self, grupo, otro_grupo, preguntas, profesor):
        hoy = timezone.localdate()
        _pase(grupo, hoy, preguntas, profesor)
        abierto = vivo.abrir(_pase(otro_grupo, hoy, preguntas, profesor))
        elegido, opciones, olvidados = vivo.en_curso(profesor, hoy)
        assert elegido == abierto and opciones == [abierto] and olvidados == []

    def test_sin_nada_abierto_va_lo_preparado_para_hoy(self, grupo, preguntas, profesor):
        hoy = timezone.localdate()
        _pase(grupo, hoy - dt.timedelta(days=1), preguntas, profesor)  # de ayer, sin empezar
        preparado = _pase(grupo, hoy, preguntas, profesor)
        assert vivo.en_curso(profesor, hoy)[0] == preparado

    def test_un_abierto_olvidado_de_otro_dia_no_gana_y_se_avisa(self, grupo, preguntas, profesor):
        hoy = timezone.localdate()
        ayer = hoy - dt.timedelta(days=1)
        olvidado = vivo.abrir(_pase(grupo, ayer, preguntas, profesor))
        Pase.objects.filter(pk=olvidado.pk).update(abierto=timezone.now() - dt.timedelta(days=1))
        preparado = _pase(grupo, hoy, preguntas, profesor)
        elegido, _opciones, olvidados = vivo.en_curso(profesor, hoy)
        assert elegido == preparado
        assert olvidados == [olvidado]

    def test_un_pase_sin_elemento_en_su_sesion_no_cuenta(self, grupo, preguntas, profesor):
        hoy = timezone.localdate()
        pase = _pase(grupo, hoy, preguntas, profesor)
        ClassSessionItem.objects.filter(object_id=pase.pk).delete()
        assert vivo.en_curso(profesor, hoy) == (None, [], [])

    def test_varios_se_eligen(self, grupo, otro_grupo, preguntas, profesor):
        hoy = timezone.localdate()
        a = _pase(grupo, hoy, preguntas, profesor)
        b = _pase(otro_grupo, hoy, preguntas, profesor)
        elegido, opciones, _ = vivo.en_curso(profesor, hoy)
        assert elegido is None and set(opciones) == {a, b}

    def test_los_pases_de_otro_profesor_no_cuentan(self, grupo, preguntas, profesor):
        hoy = timezone.localdate()
        _pase(grupo, hoy, preguntas, profesor)
        assert vivo.en_curso(_otro_profesor(), hoy) == (None, [], [])


# =============================================================================
# C719, C722, C723 — La página: quieta, con icono, con pantalla encendida
# =============================================================================


@pytest.mark.django_db
class TestPagina:
    def test_un_solo_pase_pinta_el_mando_sin_redirigir(self, client, grupo, preguntas, profesor):
        pase = _pase(grupo, timezone.localdate(), preguntas, profesor)
        client.force_login(profesor)
        r = client.get("/pase/")
        assert r.status_code == 200
        html = r.content.decode()
        assert f'data-pase="{pase.pk}"' in html and 'class="mando"' in html
        assert "<title>Pase</title>" in html
        assert 'rel="apple-touch-icon"' in html
        assert "apple-mobile-web-app-capable" not in html
        assert "js/pantalla_encendida.js" in html
        # El mando ve las letras; la presentación solo si se piden.
        assert "var MANDO = true;" in html

    def test_ninguno_lo_dice(self, client, profesor):
        client.force_login(profesor)
        r = client.get("/pase/")
        assert r.status_code == 200
        assert "No hay ningún pase en curso" in r.content.decode()

    def test_varios_da_a_elegir(self, client, grupo, otro_grupo, preguntas, profesor):
        hoy = timezone.localdate()
        a = _pase(grupo, hoy, preguntas, profesor)
        b = _pase(otro_grupo, hoy, preguntas, profesor)
        client.force_login(profesor)
        html = client.get("/pase/").content.decode()
        assert reverse("preguntas:pase_mando", args=[a.pk]) in html
        assert reverse("preguntas:pase_mando", args=[b.pk]) in html

    def test_alumnado_y_anonimos_no_entran(self, client, grupo, preguntas, profesor):
        pase = _pase(grupo, timezone.localdate(), preguntas, profesor)
        alumno = UserFactory(name="Alumno X")
        Enrollment.objects.create(user=alumno, group=grupo)
        assert client.get("/pase/").status_code == 302
        client.force_login(alumno)
        assert client.get("/pase/").status_code == 302
        assert client.get(reverse("preguntas:pase_mando", args=[pase.pk])).status_code == 302

    def test_el_mando_de_un_pase_ajeno_es_404(self, client, grupo, preguntas, profesor):
        pase = _pase(grupo, timezone.localdate(), preguntas, profesor)
        client.force_login(_otro_profesor())
        assert client.get(reverse("preguntas:pase_mando", args=[pase.pk])).status_code == 404

    def test_la_presentacion_no_es_el_mando(self, client, grupo, preguntas, profesor):
        pase = _pase(grupo, timezone.localdate(), preguntas, profesor)
        item = ClassSessionItem.objects.get(object_id=pase.pk)
        client.force_login(profesor)
        html = client.get(
            reverse("clases:class_session_item_content", args=[item.session_id, item.pk])
        ).content.decode()
        assert 'id="pase-vivo"' in html and 'class="mando"' not in html
        assert "var MANDO = false;" in html

    def test_el_boton_de_la_barra_es_solo_del_profesorado(self, client, grupo, profesor):
        client.force_login(profesor)
        assert "data-pase-en-curso" in client.get("/about/").content.decode()
        alumno = UserFactory(name="Alumno Y")
        Enrollment.objects.create(user=alumno, group=grupo)
        client.force_login(alumno)
        assert "data-pase-en-curso" not in client.get("/about/").content.decode()
