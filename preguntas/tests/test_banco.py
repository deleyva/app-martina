"""Tramo 76·1: el banco de preguntas (C473, C474, C476)."""

import datetime as dt
import json
import random

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from api_keys.models import APIKey
from clases.models import ClassSessionItem
from preguntas import composicion
from preguntas.models import Pase, PasePregunta, Pregunta, Respuesta

from .conftest import pregunta, sesion

URL_LOTE = "/api/cms/preguntas/"


@pytest.mark.django_db
class TestPregunta:
    """C473: 4 opciones, una correcta, estado, etiquetas facetadas."""

    def test_se_crea_sin_revisar_y_sabe_su_letra(self):
        p = pregunta(estado=Pregunta.SIN_REVISAR, correcta=2)
        assert p.estado == "sin_revisar"
        assert p.letra_correcta == "C"
        assert p.conceptos() == ["figuras"]

    @pytest.mark.parametrize("opciones", [["a", "b", "c"], ["a", "b", "c", "d", "e"], []])
    def test_tres_o_cinco_opciones_se_rechazan(self, opciones):
        with pytest.raises(ValidationError):
            Pregunta.objects.create(enunciado="x", opciones=opciones, correcta=0)

    @pytest.mark.parametrize("correcta", [4, 7])
    def test_la_correcta_tiene_que_ser_una_de_las_cuatro(self, correcta):
        with pytest.raises(ValidationError):
            Pregunta.objects.create(enunciado="x", opciones=["a", "b", "c", "d"], correcta=correcta)

    def test_una_opcion_vacia_se_rechaza(self):
        with pytest.raises(ValidationError):
            Pregunta.objects.create(enunciado="x", opciones=["a", "", "c", "d"], correcta=0)


@pytest.mark.django_db
class TestRespuesta:
    def test_sin_lectura_es_erronea(self, grupo, alumno, hoy):
        """Decisión de Jesús (2026-10-26): presente sin tarjeta = fallo con marca."""
        p = pregunta(correcta=1)
        pase = composicion.crear_pase(grupo, hoy, [p])
        r = Respuesta.objects.create(pase=pase, pregunta=p, alumno=alumno, opcion=None)
        assert r.sin_lectura and not r.acierto
        r.opcion = 1
        r.save()
        assert r.acierto and not r.sin_lectura


@pytest.mark.django_db
class TestApiLote:
    """C474: el lote entra siempre «sin revisar»; nunca entra en un pase."""

    def _clave(self, profesor):
        return str(APIKey.objects.create(name="test", user=profesor).key)

    def _lote(self, client, clave, preguntas):
        return client.post(
            URL_LOTE,
            data=json.dumps({"preguntas": preguntas}),
            content_type="application/json",
            HTTP_X_API_KEY=clave,
        )

    def _una(self, **cambios):
        base = {
            "enunciado": "¿Qué figura dura la mitad de una negra?",
            "opciones": ["Blanca", "Corchea", "Redonda", "Semicorchea"],
            "correcta": 1,
            "explicacion": "La corchea vale medio tiempo.",
            "etiquetas": ["concepto:figuras", "curso:1eso"],
        }
        base.update(cambios)
        return base

    def test_sin_clave_no_entra(self, client):
        r = client.post(URL_LOTE, data=json.dumps({"preguntas": [self._una()]}), content_type="application/json")
        assert r.status_code == 401

    def test_el_lote_entra_sin_revisar_con_sus_etiquetas(self, client, profesor):
        r = self._lote(client, self._clave(profesor), [self._una(), self._una(enunciado="Otra")])
        assert r.status_code == 200, r.content
        assert r.json()["creadas"] == 2
        p = Pregunta.objects.get(pk=r.json()["ids"][0])
        assert p.estado == Pregunta.SIN_REVISAR
        assert p.autor == profesor
        assert set(p.etiquetas.names()) == {"concepto:figuras", "curso:1eso"}

    @pytest.mark.parametrize(
        "cambio, texto",
        [
            ({"opciones": ["a", "b", "c"]}, "exactamente 4"),
            ({"correcta": 4}, "entre 0 y 3"),
            ({"etiquetas": ["curso:1eso"]}, "concepto"),
            ({"etiquetas": ["concepto:figuras", "caracter:alegre"]}, "faceta desconocida"),
        ],
    )
    def test_una_mala_tira_el_lote_entero(self, client, profesor, cambio, texto):
        r = self._lote(client, self._clave(profesor), [self._una(), self._una(**cambio)])
        assert r.status_code == 400
        assert texto in r.json()["detail"].lower()
        assert Pregunta.objects.count() == 0

    def test_una_sin_revisar_jamas_entra_en_un_pase(self, client, profesor, grupo, hoy):
        from musica.models import LibroPage  # noqa: F401  (contenido con etiquetas)

        clave = self._clave(profesor)
        assert self._lote(client, clave, [self._una()]).status_code == 200
        activa = pregunta(enunciado="Activa", etiquetas=("concepto:figuras",))
        _con_concepto(grupo, hoy, "concepto:figuras")
        propuesta = composicion.proponer(grupo, hoy, k=5)
        assert [p.pk for p in propuesta.preguntas] == [activa.pk]


def _con_concepto(grupo, fecha, *etiquetas):
    """Una sesión del grupo con un elemento etiquetado (una pregunta sirve de
    contenido: tiene `etiquetas`, pero no `faceted_tags`; por eso se usa un
    recurso de verdad cuando hace falta)."""
    from wagtail.models import Page

    from musica.models import RecursoPage

    raiz = Page.objects.filter(depth=1).first() or Page.add_root(title="Root")
    recurso = RecursoPage(
        title=f"Recurso {random.random()}",
        slug=f"r-{random.random()}".replace(".", ""),
        date=fecha,
        intro="Recurso de prueba",
    )
    raiz.add_child(instance=recurso)
    recurso.faceted_tags.add(*etiquetas)
    recurso.save()
    s = sesion(grupo, fecha)
    ClassSessionItem.objects.create(
        session=s,
        content_type=ContentType.objects.get_for_model(RecursoPage),
        object_id=recurso.pk,
        order=0,
        seccion="teoria",
    )
    return s


@pytest.mark.django_db
class TestComposicion:
    """C476: conceptos recientes, lo más fallado primero, sin repetir en 3 semanas."""

    def test_sin_conceptos_recientes_devuelve_vacio_y_lo_dice(self, grupo, hoy):
        pregunta()
        propuesta = composicion.proponer(grupo, hoy)
        assert propuesta.preguntas == []
        assert "concepto" in propuesta.motivo

    def test_solo_salen_preguntas_de_los_conceptos_vistos(self, grupo, hoy):
        _con_concepto(grupo, hoy - dt.timedelta(days=2), "concepto:figuras")
        figuras = pregunta(enunciado="Figuras", etiquetas=("concepto:figuras",))
        pregunta(enunciado="Intervalos", etiquetas=("concepto:intervalos",))
        propuesta = composicion.proponer(grupo, hoy)
        assert [p.pk for p in propuesta.preguntas] == [figuras.pk]

    def test_el_concepto_mas_fallado_sube(self, grupo, alumno, hoy):
        _con_concepto(grupo, hoy - dt.timedelta(days=30), "concepto:figuras", "concepto:intervalos")
        figuras = pregunta(enunciado="Figuras", etiquetas=("concepto:figuras",), correcta=1)
        intervalos = pregunta(enunciado="Intervalos", etiquetas=("concepto:intervalos",), correcta=1)
        viejo = composicion.crear_pase(grupo, hoy - dt.timedelta(days=28), [figuras, intervalos])
        Respuesta.objects.create(pase=viejo, pregunta=figuras, alumno=alumno, opcion=1)      # acierto
        Respuesta.objects.create(pase=viejo, pregunta=intervalos, alumno=alumno, opcion=0)   # fallo
        propuesta = composicion.proponer(grupo, hoy, k=2, azar=random.Random(1))
        assert [p.pk for p in propuesta.preguntas] == [intervalos.pk, figuras.pk]
        assert propuesta.conceptos == {"figuras": 0.0, "intervalos": 1.0}

    def test_una_pregunta_de_hace_una_semana_no_sale(self, grupo, hoy):
        _con_concepto(grupo, hoy, "concepto:figuras")
        reciente = pregunta(enunciado="Reciente")
        antigua = pregunta(enunciado="Antigua")
        composicion.crear_pase(grupo, hoy - dt.timedelta(days=7), [reciente])
        composicion.crear_pase(grupo, hoy - dt.timedelta(days=22), [antigua])
        propuesta = composicion.proponer(grupo, hoy, k=5)
        assert [p.pk for p in propuesta.preguntas] == [antigua.pk]

    def test_la_menos_usada_con_el_grupo_va_antes(self, grupo, hoy):
        _con_concepto(grupo, hoy, "concepto:figuras")
        usada = pregunta(enunciado="Usada")
        nueva = pregunta(enunciado="Nueva")
        composicion.crear_pase(grupo, hoy - dt.timedelta(days=40), [usada])
        propuesta = composicion.proponer(grupo, hoy, k=2, azar=random.Random(3))
        assert [p.pk for p in propuesta.preguntas] == [nueva.pk, usada.pk]

    def test_solo_las_ultimas_n_sesiones_cuentan(self, grupo, hoy):
        _con_concepto(grupo, hoy - dt.timedelta(days=60), "concepto:intervalos")
        for d in range(4):
            _con_concepto(grupo, hoy - dt.timedelta(days=d), "concepto:figuras")
        pregunta(enunciado="Intervalos", etiquetas=("concepto:intervalos",))
        propuesta = composicion.proponer(grupo, hoy, k=5)
        assert propuesta.preguntas == []

    def test_crear_pase_guarda_el_orden(self, grupo, hoy):
        a, b = pregunta(enunciado="a"), pregunta(enunciado="b")
        pase = composicion.crear_pase(grupo, hoy, [b, a])
        assert list(pase.preguntas.order_by("pasepregunta__posicion").values_list("enunciado", flat=True)) == ["b", "a"]
        assert pase.estado == Pase.BORRADOR
        assert PasePregunta.objects.count() == 2
