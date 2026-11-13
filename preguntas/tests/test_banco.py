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

    def test_cuenta_todo_lo_visto_y_no_solo_las_ultimas_sesiones(self, grupo, hoy):
        """C738: lo de hace dos meses sigue saliendo."""
        _con_concepto(grupo, hoy - dt.timedelta(days=60), "concepto:intervalos")
        for d in range(4):
            _con_concepto(grupo, hoy - dt.timedelta(days=d), "concepto:figuras")
        vieja = pregunta(enunciado="Intervalos", etiquetas=("concepto:intervalos",))
        propuesta = composicion.proponer(grupo, hoy, k=5)
        assert [p.pk for p in propuesta.preguntas] == [vieja.pk]

    def test_lo_visto_hace_poco_sale_antes(self, grupo, hoy):
        """C738: a igualdad de fallos, manda lo reciente."""
        _con_concepto(grupo, hoy - dt.timedelta(days=60), "concepto:intervalos")
        _con_concepto(grupo, hoy - dt.timedelta(days=1), "concepto:figuras")
        vieja = pregunta(enunciado="Intervalos", etiquetas=("concepto:intervalos",))
        nueva = pregunta(enunciado="Figuras", etiquetas=("concepto:figuras",))
        for semilla in range(5):
            propuesta = composicion.proponer(grupo, hoy, k=2, azar=random.Random(semilla))
            assert [p.pk for p in propuesta.preguntas] == [nueva.pk, vieja.pk]

    def test_crear_pase_guarda_el_orden(self, grupo, hoy):
        a, b = pregunta(enunciado="a"), pregunta(enunciado="b")
        pase = composicion.crear_pase(grupo, hoy, [b, a])
        assert list(pase.preguntas.order_by("pasepregunta__posicion").values_list("enunciado", flat=True)) == ["b", "a"]
        assert pase.estado == Pase.BORRADOR
        assert PasePregunta.objects.count() == 2


def _elemento(grupo, fecha, visto=False, tratado=None, etiquetas=("concepto:notacion",), recurso=None):
    """Un recurso con un enlace externo dentro (un medio de verdad del material)
    y una sesión del grupo que lo lleva. Devuelve (recurso, medio, elemento)."""
    from wagtail.models import Page

    from musica.models import EnlaceExterno, RecursoPage

    if recurso is None:
        raiz = Page.objects.filter(depth=1).first() or Page.add_root(title="Root")
        recurso = RecursoPage(
            title=f"Unidad {random.random()}",
            slug=f"u-{random.random()}".replace(".", ""),
            date=fecha,
            intro="Unidad de prueba",
        )
        raiz.add_child(instance=recurso)
        recurso.faceted_tags.add(*etiquetas)
        recurso.save()
    numero = EnlaceExterno.objects.filter(source_page=recurso).count()
    medio = EnlaceExterno.objects.create(
        source_page=recurso, titulo=f"Apartado {numero}", url=f"https://example.org/{recurso.pk}/{numero}", orden=numero
    )
    elemento = ClassSessionItem.objects.create(
        session=sesion(grupo, fecha),
        content_type=ContentType.objects.get_for_model(EnlaceExterno),
        object_id=medio.pk,
        source_page=recurso,
        order=0,
        seccion="teoria",
        visto=visto,
        tratado=tratado,
    )
    return recurso, medio, elemento


def _anclar(p, medio, pagina):
    p.ancla_tipo = ContentType.objects.get_for_model(medio.__class__)
    p.ancla_id = medio.pk
    p.ancla_pagina = pagina
    p.save()
    return p


@pytest.mark.django_db
class TestLengua:
    """C736: cada grupo recibe las preguntas de su lengua y solo esas."""

    def test_el_grupo_en_ingles_solo_recibe_las_de_ingles(self, grupo, hoy):
        _con_concepto(grupo, hoy, "concepto:figuras")
        castellano = pregunta(enunciado="Negra")
        ingles = pregunta(enunciado="Crotchet", etiquetas=("concepto:figuras", "idioma:en"))
        assert [p.pk for p in composicion.proponer(grupo, hoy).preguntas] == [castellano.pk]
        grupo.idioma = "en"
        grupo.save()
        assert [p.pk for p in composicion.proponer(grupo, hoy).preguntas] == [ingles.pk]


@pytest.mark.django_db
class TestAncla:
    """C737: una pregunta anclada espera a que el grupo vea su elemento."""

    def test_estar_en_la_sesion_sin_marcar_no_basta(self, grupo, hoy):
        recurso, medio, elemento = _elemento(grupo, hoy)
        anclada = _anclar(pregunta(enunciado="Anclada", etiquetas=("concepto:notacion",)), medio, recurso)
        assert composicion.proponer(grupo, hoy).preguntas == []
        elemento.visto = True
        elemento.save()
        assert [p.pk for p in composicion.proponer(grupo, hoy).preguntas] == [anclada.pk]

    def test_tratado_tambien_cuenta_y_saltado_no(self, grupo, hoy):
        recurso, medio, elemento = _elemento(grupo, hoy, tratado=False)
        anclada = _anclar(pregunta(enunciado="Anclada", etiquetas=("concepto:notacion",)), medio, recurso)
        assert composicion.proponer(grupo, hoy).preguntas == []
        elemento.tratado = True
        elemento.save()
        assert [p.pk for p in composicion.proponer(grupo, hoy).preguntas] == [anclada.pk]

    def test_la_mitad_de_la_unidad(self, grupo, hoy):
        """El caso de Jesús: dos elementos de la misma unidad, visto solo el primero."""
        recurso, primero, _ = _elemento(grupo, hoy, visto=True)
        _, segundo, _ = _elemento(grupo, hoy, recurso=recurso)
        de_lo_visto = _anclar(pregunta(enunciado="Lo visto", etiquetas=("concepto:notacion",)), primero, recurso)
        _anclar(pregunta(enunciado="Lo que falta", etiquetas=("concepto:notacion",)), segundo, recurso)
        propuesta = composicion.proponer(grupo, hoy)
        assert [p.pk for p in propuesta.preguntas] == [de_lo_visto.pk]
        assert [p.pk for p in propuesta.banco] == [de_lo_visto.pk]

    def test_lo_que_ve_otro_grupo_no_cuenta(self, grupo, profesor, hoy):
        from clases.models import Group

        otro = Group.objects.create(name="3º ESO Y", subject=grupo.subject, academic_year="2026-2027")
        otro.teachers.add(profesor)
        recurso, medio, _ = _elemento(otro, hoy, visto=True)
        _anclar(pregunta(enunciado="Anclada", etiquetas=("concepto:notacion",)), medio, recurso)
        _con_concepto(grupo, hoy, "concepto:notacion")
        assert composicion.proponer(grupo, hoy).preguntas == []

    def test_dado_por_visto_en_el_libro_tambien_vale(self, grupo, hoy):
        from clases.models import GroupBook, GroupBookItem

        recurso, medio, _ = _elemento(grupo, hoy)
        anclada = _anclar(pregunta(enunciado="Anclada", etiquetas=("concepto:notacion",)), medio, recurso)
        libro = GroupBook.objects.create(group=grupo, libro=recurso, seccion="teoria")
        GroupBookItem.objects.create(
            group_book=libro,
            content_type=ContentType.objects.get_for_model(medio.__class__),
            object_id=medio.pk,
            source_page=recurso,
            estado=GroupBookItem.VISTO,
        )
        assert [p.pk for p in composicion.proponer(grupo, hoy).preguntas] == [anclada.pk]


@pytest.mark.django_db
class TestHuerfanas:
    """C740: si el elemento sale del material, la pregunta ni entra ni se pierde."""

    def test_al_quitar_el_elemento_la_pregunta_queda_huerfana(self, grupo, hoy):
        recurso, medio, _ = _elemento(grupo, hoy, visto=True)
        anclada = _anclar(pregunta(enunciado="Anclada", etiquetas=("concepto:notacion",)), medio, recurso)
        assert composicion.huerfanas() == []
        medio.delete()
        assert [p.pk for p in composicion.huerfanas()] == [anclada.pk]
        assert composicion.proponer(grupo, hoy).preguntas == []

    def test_al_borrar_la_pagina_tambien(self, grupo, hoy):
        recurso, medio, _ = _elemento(grupo, hoy, visto=True)
        anclada = _anclar(pregunta(enunciado="Anclada", etiquetas=("concepto:notacion",)), medio, recurso)
        recurso.delete()
        anclada.refresh_from_db()
        assert [p.pk for p in composicion.huerfanas()] == [anclada.pk]

    def test_sin_ancla_no_es_huerfana(self, grupo, hoy):
        pregunta()
        assert composicion.huerfanas() == []


@pytest.mark.django_db
class TestVocabulario:
    """C739: si hay de vocabulario, una entra."""

    def test_una_de_vocabulario_entra_aunque_no_le_toque(self, grupo, alumno, hoy):
        _con_concepto(grupo, hoy, "concepto:figuras", "concepto:intervalos")
        falladas = [pregunta(enunciado=f"Intervalo {n}", etiquetas=("concepto:intervalos",)) for n in range(4)]
        viejo = composicion.crear_pase(grupo, hoy - dt.timedelta(days=40), falladas[:1])
        Respuesta.objects.create(pase=viejo, pregunta=falladas[0], alumno=alumno, opcion=0)
        vocabulario = pregunta(enunciado="¿Qué es una negra?", etiquetas=("concepto:figuras", "tipo:vocabulario"))
        propuesta = composicion.proponer(grupo, hoy, k=3, azar=random.Random(2))
        assert vocabulario in propuesta.preguntas
        assert len(propuesta.preguntas) == 3

    def test_sin_vocabulario_no_cambia_nada(self, grupo, hoy):
        _con_concepto(grupo, hoy, "concepto:figuras")
        a, b = pregunta(enunciado="a"), pregunta(enunciado="b")
        assert {p.pk for p in composicion.proponer(grupo, hoy, k=2).preguntas} == {a.pk, b.pk}


@pytest.mark.django_db
class TestAnclasPorApiYEnElBanco:
    """C740 y el alta con ancla: API, lista de huérfanas y formulario."""

    def _clave(self, profesor):
        return str(APIKey.objects.create(name="anclas", user=profesor).key)

    def _json(self, client, clave, url, cuerpo):
        return client.post(url, data=json.dumps(cuerpo), content_type="application/json", HTTP_X_API_KEY=clave)

    def test_el_material_se_lista_y_se_ancla_por_indice(self, client, profesor, grupo, hoy):
        recurso, primero, _ = _elemento(grupo, hoy)
        _, segundo, _ = _elemento(grupo, hoy, recurso=recurso)
        clave = self._clave(profesor)
        material = client.get(f"{URL_LOTE}material/{recurso.pk}", HTTP_X_API_KEY=clave).json()
        assert [m["id"] for m in material] == [primero.pk, segundo.pk]
        assert material[1]["tipo"] == "musica.enlaceexterno"

        p = pregunta()
        r = self._json(client, clave, f"{URL_LOTE}anclas", {"anclas": [{"pregunta_id": p.pk, "ancla": {"pagina_id": recurso.pk, "indice": 1}}]})
        assert r.status_code == 200, r.content
        p.refresh_from_db()
        assert (p.ancla_id, p.ancla_pagina_id) == (segundo.pk, recurso.pk)

        r = self._json(client, clave, f"{URL_LOTE}anclas", {"anclas": [{"pregunta_id": p.pk, "ancla": {"pagina_id": recurso.pk, "indice": 9}}]})
        assert r.status_code == 400
        r = self._json(client, clave, f"{URL_LOTE}anclas", {"anclas": [{"pregunta_id": p.pk, "ancla": None}]})
        p.refresh_from_db()
        assert r.json() == {"ancladas": 0, "desancladas": 1} and not p.anclada

    def test_el_alta_puede_venir_ya_anclada(self, client, profesor, grupo, hoy):
        recurso, medio, _ = _elemento(grupo, hoy)
        r = self._json(
            client,
            self._clave(profesor),
            URL_LOTE,
            {"preguntas": [{"enunciado": "¿?", "opciones": ["a", "b", "c", "d"], "correcta": 0,
                            "etiquetas": ["concepto:notacion"], "ancla": {"pagina_id": recurso.pk, "indice": 0}}]},
        )
        assert r.status_code == 200, r.content
        assert Pregunta.objects.get(pk=r.json()["ids"][0]).ancla_id == medio.pk

    def test_el_banco_lista_las_huerfanas_y_el_formulario_las_recoloca(self, client, profesor, grupo, hoy):
        recurso, primero, _ = _elemento(grupo, hoy)
        _, segundo, _ = _elemento(grupo, hoy, recurso=recurso)
        huerfana = _anclar(pregunta(enunciado="Me quedé sin sitio", etiquetas=("concepto:notacion",)), primero, recurso)
        sana = _anclar(pregunta(enunciado="Sigo en mi sitio", etiquetas=("concepto:notacion",)), segundo, recurso)
        primero.delete()

        client.force_login(profesor)
        r = client.get("/preguntas/")
        assert r.context["n_huerfanas"] == 1 and "ver-huerfanas" in r.content.decode()
        r = client.get("/preguntas/?ancla=huerfanas")
        html = r.content.decode()
        assert "Me quedé sin sitio" in html and "Sigo en mi sitio" not in html and "data-huerfana" in html

        r = client.get(f"/preguntas/{huerfana.pk}/editar/")
        assert r.context["ancla_huerfana"] and [m["id"] for m in r.context["ancla_material"]] == [segundo.pk]
        tipo = ContentType.objects.get_for_model(segundo.__class__).pk
        r = client.post(
            f"/preguntas/{huerfana.pk}/editar/",
            {"enunciado": huerfana.enunciado, "opcion_0": "Una", "opcion_1": "Dos", "opcion_2": "Tres", "opcion_3": "Cuatro",
             "correcta": "1", "etiquetas": "concepto:notacion", "ancla_pagina": recurso.pk, "ancla": f"{tipo}:{segundo.pk}"},
        )
        assert r.status_code == 302
        assert composicion.huerfanas() == []
        huerfana.refresh_from_db()
        assert huerfana.ancla_id == segundo.pk and sana.ancla_id == segundo.pk
