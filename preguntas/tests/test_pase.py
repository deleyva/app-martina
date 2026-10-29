"""El pase en clase (tramo 76·2): tarjetas, el pase en la sesión, lecturas en
vivo, revelar, cerrar, y que ningún fotograma persista.

Se prueba por HTTP donde la puerta importa (permisos, lecturas) y por el
servicio donde lo que se falsa es una regla (la última lectura antes de revelar
es la que vale; sin lectura es errónea; los ausentes no tienen fila).
"""

import json
import os
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse

from clases.models import Asistencia, ClassSessionItem, Enrollment, Group
from martina_bescos_app.users.tests.factories import UserFactory
from preguntas import vivo
from preguntas.models import Pase, Respuesta

from .conftest import pregunta, sesion
from .lienzos import girado, jpeg, lienzo

A, B, C, D = 0, 1, 2, 3  # giros antihorarios de la tarjeta = letra arriba


@pytest.fixture
def alumnos(grupo):
    """Tres matriculados; el orden de lista es el del nombre."""
    us = [UserFactory(name=f"Alumno {n}") for n in ("Ana", "Bea", "Cai")]
    for u in us:
        Enrollment.objects.create(user=u, group=grupo)
    return us


@pytest.fixture
def cuatro(db):
    return [pregunta(f"Pregunta {i}", correcta=i) for i in range(4)]


@pytest.fixture
def montaje(grupo, hoy, alumnos, cuatro, profesor):
    s = sesion(grupo, hoy)
    pase, item = vivo.crear_desde_sesion(s, cuatro, profesor)
    vivo.asignar_tarjetas(grupo)  # Ana=1, Bea=2, Cai=3
    return {"sesion": s, "pase": pase, "item": item, "alumnos": alumnos, "preguntas": cuatro}


def _frame(client, pase, tarjetas, img=None):
    datos = jpeg(img if img is not None else lienzo(tarjetas))
    return client.post(
        reverse("preguntas:pase_leer", args=[pase.pk]),
        {"frame": SimpleUploadedFile("frame.jpg", datos, content_type="image/jpeg")},
    )


def _post(client, nombre, pase):
    return client.post(reverse(f"preguntas:{nombre}", args=[pase.pk]))


def _estado(client, pase):
    return client.get(reverse("preguntas:pase_estado", args=[pase.pk])).json()


# =============================================================================
# C478 — Tarjetas por matrícula
# =============================================================================


@pytest.mark.django_db
class TestTarjetas:
    def test_numeros_unicos_por_grupo_y_estables(self, grupo, alumnos):
        assert [m.tarjeta for m in vivo.asignar_tarjetas(grupo)] == [1, 2, 3]
        # Idempotente: volver a pedirlo no renumera a nadie.
        assert [m.tarjeta for m in vivo.asignar_tarjetas(grupo)] == [1, 2, 3]
        # Uno nuevo coge el siguiente libre, aunque vaya antes en la lista.
        Enrollment.objects.create(user=UserFactory(name="Alumno Aaron"), group=grupo)
        assert [m.tarjeta for m in vivo.asignar_tarjetas(grupo)] == [4, 1, 2, 3]
        # Una baja conserva su número (la tarjeta impresa existe y puede volver):
        # el siguiente que entra coge uno nuevo, nunca el de la baja.
        Enrollment.objects.filter(group=grupo, tarjeta=2).update(is_active=False)
        Enrollment.objects.create(user=UserFactory(name="Alumno Zoe"), group=grupo)
        assert {m.tarjeta for m in vivo.asignar_tarjetas(grupo)} == {1, 3, 4, 5}
        assert Enrollment.objects.get(group=grupo, is_active=False).tarjeta == 2

    def test_otro_grupo_reutiliza_los_numeros(self, grupo, alumnos, profesor):
        otro = Group.objects.create(name="3º ESO Y", subject=grupo.subject, academic_year="2026-2027")
        otro.teachers.add(profesor)
        Enrollment.objects.create(user=alumnos[2], group=otro)
        vivo.asignar_tarjetas(grupo)
        assert [m.tarjeta for m in vivo.asignar_tarjetas(otro)] == [1]
        assert Enrollment.objects.get(user=alumnos[2], group=grupo).tarjeta == 3

    def test_dos_matriculas_del_grupo_no_comparten_tarjeta(self, grupo, alumnos):
        vivo.asignar_tarjetas(grupo)
        with pytest.raises(IntegrityError), transaction.atomic():
            Enrollment.objects.filter(user=alumnos[0], group=grupo).update(tarjeta=2)

    def test_pdf_del_grupo_por_http(self, client, grupo, alumnos, profesor, django_user_model):
        client.force_login(profesor)
        r = client.get(reverse("preguntas:tarjetas_grupo", args=[grupo.pk]))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert Enrollment.objects.filter(group=grupo, tarjeta__isnull=False).count() == 3

        otro = django_user_model.objects.create_user(email="otro@x.es", password="x")
        otro.is_staff = False
        otro.save()
        from django.contrib.auth.models import Group as GrupoPermisos
        from martina_bescos_app.users.permisos import GRUPO_PROFESORADO

        otro.groups.add(GrupoPermisos.objects.get_or_create(name=GRUPO_PROFESORADO)[0])
        client.force_login(otro)
        assert client.get(reverse("preguntas:tarjetas_grupo", args=[grupo.pk])).status_code == 404

    def test_pegatinas_cruzan_los_grupos_del_profesor_por_numero(self, grupo, alumnos, profesor):
        """C550: la misma tarjeta 1 es Ana en un grupo y Dan en otro; el archivado no entra."""
        otro = Group.objects.create(name="3º ESO Y", subject=grupo.subject, academic_year="2026-2027")
        otro.teachers.add(profesor)
        Enrollment.objects.create(user=UserFactory(name="Alumno Dan"), group=otro)
        viejo = Group.objects.create(name="Viejo", subject=grupo.subject, academic_year="2025-2026", archivado=True)
        viejo.teachers.add(profesor)
        Enrollment.objects.create(user=UserFactory(name="Alumno Eva"), group=viejo)

        pegatinas = vivo.pegatinas_de(profesor)
        assert [p["numero"] for p in pegatinas] == [1, 2, 3]
        assert pegatinas[0]["lineas"] == ["3º ESO Y: Alumno Dan", "3º ESO Z: Alumno Ana"]
        assert pegatinas[2]["lineas"] == ["3º ESO Z: Alumno Cai"]
        assert "Eva" not in json.dumps(pegatinas)
        # Los números los ha repartido la app al generar las pegatinas.
        assert Enrollment.objects.filter(group=otro, tarjeta=1).exists()
        assert Enrollment.objects.filter(group=viejo, tarjeta__isnull=False).count() == 0

        juego = vivo.juego_generico(27)
        assert [t["numero"] for t in juego] == list(range(1, 28)) and all(t["nombre"] == "" for t in juego)
        assert len(vivo.juego_generico(500)) == vivo.TARJETA_MAXIMA

    def test_juego_generico_y_pegatinas_por_http(self, client, grupo, alumnos, profesor):
        from io import BytesIO

        from pypdf import PdfReader

        client.force_login(profesor)
        r = client.get(reverse("preguntas:tarjetas_genericas"))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert len(PdfReader(BytesIO(r.content)).pages) == 14  # 27 tarjetas, dos por A4
        assert len(PdfReader(BytesIO(client.get(reverse("preguntas:tarjetas_genericas"), {"n": "4"}).content)).pages) == 2
        assert client.get(reverse("preguntas:tarjetas_genericas"), {"n": "0"}).status_code == 400
        assert client.get(reverse("preguntas:tarjetas_genericas"), {"n": "x"}).status_code == 400

        assert Enrollment.objects.filter(group=grupo, tarjeta__isnull=False).count() == 0
        r = client.get(reverse("preguntas:pegatinas"))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert "3º ESO Z: Alumno Bea" in PdfReader(BytesIO(r.content)).pages[0].extract_text()
        assert Enrollment.objects.filter(group=grupo, tarjeta__isnull=False).count() == 3
        assert client.get(reverse("preguntas:pegatinas"), {"alto": "300"}).status_code == 400
        assert client.get(reverse("preguntas:pegatinas"), {"ancho": "abc"}).status_code == 400

        client.force_login(alumnos[0])
        assert client.get(reverse("preguntas:pegatinas")).status_code == 302  # el alumnado no imprime


# =============================================================================
# C479 — El pase como elemento de la sesión
# =============================================================================


@pytest.mark.django_db
class TestPaseEnSesion:
    def test_crear_desde_sesion_mete_un_elemento_de_teoria(self, montaje):
        item = montaje["item"]
        assert item.session == montaje["sesion"] and item.seccion == "teoria"
        assert item.content_object == montaje["pase"]
        assert item.get_content_title() == "Pase de preguntas · 4 preguntas"
        assert item.get_icon() == "❓" and item.get_content_type_name() == "Pase de preguntas"
        assert [pp.pregunta for pp in montaje["pase"].orden.all()] == montaje["preguntas"]

    def test_la_presentacion_sabe_que_es_un_pase(self, client, montaje, profesor):
        client.force_login(profesor)
        r = client.get(reverse("clases:class_session_present", args=[montaje["sesion"].pk]))
        playlist = json.loads(r.context["playlist_json"])
        assert playlist[0]["pase"] == montaje["pase"].pk and playlist[0]["seccion"] == "Teoría"
        contenido = client.get(
            reverse("clases:class_session_item_content", args=[montaje["sesion"].pk, montaje["item"].pk])
        ).content.decode()
        assert 'id="pase-vivo"' in contenido and 'id="pv-barra"' in contenido

    def test_el_alumno_ve_la_pantalla_sin_barra(self, client, montaje):
        client.force_login(montaje["alumnos"][0])
        contenido = client.get(
            reverse("clases:class_session_item_content", args=[montaje["sesion"].pk, montaje["item"].pk])
        ).content.decode()
        assert 'id="pase-vivo"' in contenido and 'id="pv-barra"' not in contenido

    def test_la_sesion_ofrece_anadir_pase_y_la_fila_es_evaluable(self, client, montaje, profesor):
        client.force_login(profesor)
        html = client.get(reverse("clases:class_session_edit", args=[montaje["sesion"].pk])).content.decode()
        assert reverse("preguntas:pase_nuevo") + "?session=" in html
        assert f'data-item-id="{montaje["item"].pk}"' in html
        assert f'data-item="{montaje["item"].pk}"' in html  # el popup «evaluable» de la fase 62

    def test_pase_nuevo_propone_deja_elegir_y_guarda(self, client, grupo, hoy, cuatro, profesor):
        s = sesion(grupo, hoy)
        client.force_login(profesor)
        url = reverse("preguntas:pase_nuevo") + f"?session={s.pk}"
        r = client.get(url)
        assert r.status_code == 200
        # Sin conceptos recientes no propone nada y lo dice; las activas están abajo.
        assert r.context["propuestas"] == [] and r.context["motivo"]
        assert {p.pk for p in r.context["otras"]} == {p.pk for p in cuatro}

        r = client.post(url, {"session": s.pk, "preguntas": [cuatro[2].pk, cuatro[0].pk]})
        assert r.status_code == 302 and r["Location"] == reverse("clases:class_session_edit", args=[s.pk])
        pase = Pase.objects.get(session=s)
        assert [pp.pregunta for pp in pase.orden.all()] == [cuatro[2], cuatro[0]]
        assert ClassSessionItem.objects.filter(session=s, object_id=pase.pk, seccion="teoria").exists()

        r = client.post(url, {"session": s.pk})
        assert r.status_code == 200 and r.context["error"]

    def test_una_sin_revisar_no_entra_aunque_se_envie(self, client, grupo, hoy, profesor):
        s = sesion(grupo, hoy)
        activa = pregunta("Activa")
        cruda = pregunta("Cruda", estado="sin_revisar")
        client.force_login(profesor)
        client.post(reverse("preguntas:pase_nuevo"), {"session": s.pk, "preguntas": [cruda.pk, activa.pk]})
        assert [pp.pregunta for pp in Pase.objects.get(session=s).orden.all()] == [activa]

    def test_la_sesion_de_otro_profesor_da_404(self, client, grupo, hoy, django_user_model):
        s = sesion(grupo, hoy)
        otro = django_user_model.objects.create_user(email="otro@x.es", password="x", is_staff=True)
        client.force_login(otro)
        assert client.get(reverse("preguntas:pase_nuevo") + f"?session={s.pk}").status_code == 404


# =============================================================================
# C480, C481 — Lecturas en vivo
# =============================================================================


@pytest.mark.django_db
class TestLecturas:
    def test_vale_la_ultima_lectura_antes_de_revelar(self, client, montaje, profesor):
        pase = montaje["pase"]
        client.force_login(profesor)
        assert _frame(client, pase, [(1, A)]).status_code == 400  # borrador
        assert _post(client, "pase_abrir", pase).json()["estado"] == "abierto"

        e = _frame(client, pase, [(1, A), (2, C)]).json()
        assert e["contadas"] == 2 and e["respondido"] == ["Alumno Ana", "Alumno Bea"]
        assert "correcta" not in e["pregunta"] and "reparto" not in e
        e = _frame(client, pase, [(1, C)]).json()  # Ana cambia de A a C
        assert pase.actual().lecturas == {str(montaje["alumnos"][0].pk): C, str(montaje["alumnos"][1].pk): C}

        e = _post(client, "pase_revelar", pase).json()
        assert e["revelada"] and e["pregunta"]["correcta"] == 0 and e["pregunta"]["letra"] == "A"
        assert e["reparto"] == [0, 0, 2, 0]

        e = _frame(client, pase, [(1, B)]).json()  # tras revelar: se ignora y se cuenta
        assert e["contadas"] == 0 and e["reparto"] == [0, 0, 2, 0] and e["desconocidas"] == 1
        assert pase.actual().lecturas[str(montaje["alumnos"][0].pk)] == C

    def test_id_sin_matricula_y_tarjeta_ambigua(self, client, montaje, profesor):
        pase = montaje["pase"]
        client.force_login(profesor)
        _post(client, "pase_abrir", pase)
        e = _frame(client, pase, [(50, A)]).json()
        assert e["leidas"] == 1 and e["contadas"] == 0 and e["desconocidas"] == 1 and e["respondido"] == []
        # A 45° la letra es nula: ni cuenta ni es desconocida, se espera al siguiente fotograma.
        e = _frame(client, pase, [], img=girado(lienzo([(1, A)], lado=120), 45)).json()
        assert e["contadas"] == 0 and e["desconocidas"] == 1 and pase.actual().lecturas == {}

    def test_siguiente_hasta_terminar(self, client, montaje, profesor):
        pase = montaje["pase"]
        client.force_login(profesor)
        _post(client, "pase_abrir", pase)
        for n in range(1, 4):
            assert _post(client, "pase_siguiente", pase).json()["posicion"] == n
        e = _post(client, "pase_siguiente", pase).json()
        assert e["terminado"] and "pregunta" not in e
        assert _post(client, "pase_siguiente", pase).json()["posicion"] == 4  # no pasa de ahí
        assert _frame(client, pase, [(1, A)]).json()["contadas"] == 0

    def test_la_pantalla_se_actualiza_en_menos_de_dos_segundos(self, client, montaje, profesor):
        """La pantalla proyectada sondea cada segundo; aquí se comprueba que lo
        que devuelve el sondeo ya lleva la lectura del fotograma anterior."""
        pase = montaje["pase"]
        client.force_login(profesor)
        _post(client, "pase_abrir", pase)
        _frame(client, pase, [(3, D)])
        assert _estado(client, pase)["respondido"] == ["Alumno Cai"]

    def test_quien_ve_que(self, client, montaje, profesor, django_user_model):
        pase = montaje["pase"]
        client.force_login(profesor)
        _post(client, "pase_abrir", pase)
        _frame(client, pase, [(1, A)])

        client.force_login(montaje["alumnos"][1])
        e = _estado(client, pase)
        assert e["respondido"] == ["Alumno Ana"] and "correcta" not in e["pregunta"]
        assert _frame(client, pase, [(2, B)]).status_code == 302  # el alumnado no lee tarjetas
        assert _post(client, "pase_revelar", pase).status_code == 302

        ajeno = django_user_model.objects.create_user(email="ajeno@x.es", password="x")
        client.force_login(ajeno)
        assert client.get(reverse("preguntas:pase_estado", args=[pase.pk])).status_code == 403

        otro_profe = django_user_model.objects.create_user(email="profe2@x.es", password="x")
        otro_grupo = Group.objects.create(name="1º ESO Q", subject=pase.group.subject, academic_year="2026-2027")
        otro_grupo.teachers.add(otro_profe)
        client.force_login(otro_profe)
        assert _post(client, "pase_abrir", pase).status_code == 404
        assert _frame(client, pase, [(1, A)]).status_code == 404
        assert _post(client, "pase_cerrar", pase).status_code == 404


# =============================================================================
# C482 — Cerrar
# =============================================================================


@pytest.mark.django_db
class TestCerrar:
    def test_una_respuesta_por_presente_y_pregunta(self, client, montaje, profesor):
        pase, (ana, bea, cai), preguntas = montaje["pase"], montaje["alumnos"], montaje["preguntas"]
        Asistencia.objects.create(session=montaje["sesion"], alumno=cai, estado=Asistencia.FALTA)
        client.force_login(profesor)
        _post(client, "pase_abrir", pase)
        # P0 (correcta A): Ana A, Bea B. P1 (correcta B): solo Ana, B. P2 y P3: nadie.
        _frame(client, pase, [(1, A), (2, B)])
        _post(client, "pase_revelar", pase)
        _post(client, "pase_siguiente", pase)
        _frame(client, pase, [(1, B)])
        _post(client, "pase_revelar", pase)
        for _ in range(3):
            _post(client, "pase_siguiente", pase)

        e = _post(client, "pase_cerrar", pase).json()
        assert e["estado"] == "cerrado" and e["respuestas"] == 8
        assert Respuesta.objects.filter(pase=pase, alumno=cai).count() == 0

        de_ana = {r.pregunta_id: r for r in Respuesta.objects.filter(pase=pase, alumno=ana)}
        assert [de_ana[p.pk].acierto for p in preguntas] == [True, True, False, False]
        assert de_ana[preguntas[2].pk].sin_lectura and de_ana[preguntas[2].pk].opcion is None
        pase.refresh_from_db()
        assert pase.nota_de(ana.pk) == 5.0 and pase.nota_de(bea.pk) == 0.0 and pase.nota_de(cai.pk) is None

        # Cerrar dos veces no duplica ni cambia nada.
        _post(client, "pase_cerrar", pase)
        assert Respuesta.objects.filter(pase=pase).count() == 8
        assert _frame(client, pase, [(1, A)]).status_code == 400

    def test_cerrar_sin_empezar_se_rechaza(self, client, montaje, profesor):
        client.force_login(profesor)
        assert _post(client, "pase_cerrar", montaje["pase"]).status_code == 400
        assert Respuesta.objects.count() == 0


# =============================================================================
# C483 — Ningún fotograma persiste
# =============================================================================


def _ficheros(raiz):
    raiz = Path(raiz)
    return sum(len(f) for _, _, f in os.walk(raiz)) if raiz.exists() else 0


@pytest.mark.django_db
def test_los_fotogramas_no_se_guardan(client, montaje, profesor, settings):
    pase = montaje["pase"]
    client.force_login(profesor)
    _post(client, "pase_abrir", pase)
    antes = _ficheros(settings.MEDIA_ROOT)
    for n in range(20):
        assert _frame(client, pase, [(1 + n % 3, n % 4)]).status_code == 200
    assert _ficheros(settings.MEDIA_ROOT) == antes

    fuente = Path(__file__).resolve().parents[1]
    for nombre in ("views_pase.py", "vivo.py"):
        codigo = (fuente / nombre).read_text()
        for prohibido in ("open(", "default_storage", "Evidencia(", "import Evidencia", "ContentFile", ".save(datos", "logger.info(datos"):
            assert prohibido not in codigo, f"{nombre} no debe escribir el fotograma: {prohibido}"
