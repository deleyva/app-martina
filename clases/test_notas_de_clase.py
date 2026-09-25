"""Notas de voz grabadas en clase, transcritas por Whisper y revisadas al final.

Petición del principal (2026-09-25), después de ver la fase 40 funcionando:
«Durante la clase sólo quiero grabar notas de audio […] en la pantalla final de
clase, que me muestre, bajo la caja "💭 Reflexión de la clase", una lista de
los audios grabados durante la clase […] la transcripción que ha cazado el
modelo y que yo pueda modificarla y aceptarla, para que se añada al campo
"💭 Reflexión de la clase" y se borre el audio y la transcripción.»

Whisper vive en otro contenedor: aquí su llamada HTTP (`requests.post`) se
simula siempre. Huey corre en modo inmediato en los tests, y la transcripción se
encola al confirmar la transacción, así que los tests que la necesitan envuelven
el POST en `django_capture_on_commit_callbacks(execute=True)`.
"""

import os
from unittest import mock

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from clases.models import (
    ClassSession,
    ClassSessionItem,
    Enrollment,
    Group,
    SessionNote,
    Subject,
)
from clases.tasks import transcribir_nota

AUDIO = b"esto-hace-de-nota-de-voz"
LO_QUE_ENTIENDE = "Lucía por fin coge el ritmo del seis por ocho."


@pytest.fixture
def asignatura(db):
    return Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]


@pytest.fixture
def clase(db, django_user_model, asignatura):
    profe = django_user_model.objects.create_user(email="profe@x.es", password="x")
    grupo = Group.objects.create(
        name="3-FH", subject=asignatura, academic_year="2026-2027"
    )
    grupo.teachers.add(profe)
    alumno = django_user_model.objects.create_user(email="alumna@x.es", password="x")
    Enrollment.objects.create(user=alumno, group=grupo, is_active=True)
    sesion = ClassSession.objects.create(
        title="Test", group=grupo, teacher=profe, date="2026-09-25"
    )
    return {"profe": profe, "alumno": alumno, "grupo": grupo, "sesion": sesion}


@pytest.fixture
def item(clase):
    # Cualquier objeto sirve de contenido: basta con que tenga título.
    sesion = clase["sesion"]
    return ClassSessionItem.objects.create(
        session=sesion,
        content_type=ContentType.objects.get_for_model(ClassSession),
        object_id=sesion.pk,
        order=0,
    )


@pytest.fixture
def whisper():
    """Whisper contesta bien."""
    respuesta = mock.Mock()
    respuesta.json.return_value = {"texto": LO_QUE_ENTIENDE}
    respuesta.raise_for_status.return_value = None
    with mock.patch("requests.post", return_value=respuesta) as post:
        yield post


def _audio(contenido=AUDIO):
    return SimpleUploadedFile("nota.webm", contenido, content_type="audio/webm")


def _grabar(client, sesion, **extra):
    datos = {"audio": _audio()}
    datos.update(extra)
    return client.post(reverse("clases:class_session_notes", args=[sesion.pk]), datos)


def _grabar_y_transcribir(client, sesion, capturar, **extra):
    with capturar(execute=True):
        r = _grabar(client, sesion, **extra)
    assert r.status_code == 200
    return SessionNote.objects.get(pk=r.json()["nota"]["pk"])


# ── C233: grabar no toca la reflexión; Whisper rellena la nota ─────────────


def test_grabar_deja_la_nota_pendiente_sin_tocar_la_reflexion(client, clase, whisper):
    sesion = clase["sesion"]
    sesion.reflection = "Lo que ya había"
    sesion.save()
    client.force_login(clase["profe"])

    with mock.patch("programacion.services.update_coverage_for_session") as cobertura:
        r = _grabar(client, sesion)  # sin ejecutar on_commit: aún no se transcribe

    assert r.status_code == 200
    nota = SessionNote.objects.get()
    assert nota.estado == SessionNote.PENDIENTE
    sesion.refresh_from_db()
    assert sesion.reflection == "Lo que ya había"
    assert sesion.closed_at is None
    cobertura.assert_not_called()
    whisper.assert_not_called()


def test_whisper_rellena_la_transcripcion(client, clase, whisper, django_capture_on_commit_callbacks):
    client.force_login(clase["profe"])

    nota = _grabar_y_transcribir(client, clase["sesion"], django_capture_on_commit_callbacks)

    assert nota.estado == SessionNote.TRANSCRITA
    assert nota.transcripcion == LO_QUE_ENTIENDE
    assert whisper.call_args.kwargs["data"] == AUDIO
    clase["sesion"].refresh_from_db()
    assert clase["sesion"].reflection == ""


def test_un_post_sin_audio_da_400(client, clase):
    client.force_login(clase["profe"])

    r = client.post(reverse("clases:class_session_notes", args=[clase["sesion"].pk]), {})

    assert r.status_code == 400
    assert not SessionNote.objects.exists()


# ── C234: aceptar pasa el texto corregido y borra audio y nota ─────────────


def test_aceptar_pasa_el_texto_corregido_y_borra_el_audio(
    client, clase, item, whisper, django_capture_on_commit_callbacks
):
    sesion = clase["sesion"]
    sesion.reflection = "Lo que ya había"
    sesion.save()
    client.force_login(clase["profe"])
    nota = _grabar_y_transcribir(
        client, sesion, django_capture_on_commit_callbacks, item=str(item.pk)
    )
    ruta = nota.audio.path
    assert os.path.exists(ruta)

    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(
            reverse("clases:class_session_note_aceptar", args=[sesion.pk, nota.pk]),
            {"texto": "Lucía por fin coge el 6/8."},
        )

    assert r.status_code == 200
    linea = r.json()["linea"]
    assert linea.endswith(f"· {item.get_content_title()}] Lucía por fin coge el 6/8.")
    sesion.refresh_from_db()
    assert sesion.reflection == f"Lo que ya había\n{linea}"
    assert not SessionNote.objects.exists()
    assert not os.path.exists(ruta)


def test_aceptar_vacio_da_400_y_no_borra_nada(
    client, clase, whisper, django_capture_on_commit_callbacks
):
    client.force_login(clase["profe"])
    nota = _grabar_y_transcribir(client, clase["sesion"], django_capture_on_commit_callbacks)

    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(
            reverse("clases:class_session_note_aceptar", args=[clase["sesion"].pk, nota.pk]),
            {"texto": "   "},
        )

    assert r.status_code == 400
    assert SessionNote.objects.filter(pk=nota.pk).exists()
    assert os.path.exists(nota.audio.path)


# ── C235: descartar borra sin tocar la reflexión ───────────────────────────


def test_descartar_borra_nota_y_audio_sin_tocar_la_reflexion(
    client, clase, whisper, django_capture_on_commit_callbacks
):
    sesion = clase["sesion"]
    sesion.reflection = "Intacta"
    sesion.save()
    client.force_login(clase["profe"])
    nota = _grabar_y_transcribir(client, sesion, django_capture_on_commit_callbacks)
    ruta = nota.audio.path

    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(
            reverse("clases:class_session_note_descartar", args=[sesion.pk, nota.pk])
        )

    assert r.status_code == 200
    assert not SessionNote.objects.exists()
    assert not os.path.exists(ruta)
    sesion.refresh_from_db()
    assert sesion.reflection == "Intacta"


# ── C236 y C237: los fallos de Whisper no pierden el audio ─────────────────


def test_si_whisper_falla_la_nota_queda_en_error_con_su_audio(client, clase):
    client.force_login(clase["profe"])
    _grabar(client, clase["sesion"])  # sin on_commit: la transcripción no corre
    nota = SessionNote.objects.get()

    with mock.patch("requests.post", side_effect=ConnectionError("whisper caído")):
        resultado = transcribir_nota.call_local(nota.pk)

    assert resultado == "error"
    nota.refresh_from_db()
    assert nota.estado == SessionNote.ERROR
    assert os.path.exists(nota.audio.path)

    # Y se puede aceptar igual, escribiendo el texto a mano.
    r = client.post(
        reverse("clases:class_session_note_aceptar", args=[clase["sesion"].pk, nota.pk]),
        {"texto": "Escrito a mano"},
    )
    assert r.status_code == 200


def test_un_fallo_con_reintentos_pendientes_no_marca_error(
    client, clase, django_capture_on_commit_callbacks
):
    """Huey reintenta: el primer fallo no debe dar la nota por perdida."""
    client.force_login(clase["profe"])
    with mock.patch("requests.post", side_effect=ConnectionError("whisper caído")):
        with django_capture_on_commit_callbacks(execute=True):
            r = _grabar(client, clase["sesion"])

    assert r.status_code == 200
    assert SessionNote.objects.get().estado == SessionNote.PENDIENTE


def test_una_nota_descartada_antes_de_transcribirse_no_rompe_la_tarea(
    client, clase, whisper
):
    client.force_login(clase["profe"])
    _grabar(client, clase["sesion"])
    nota = SessionNote.objects.get()
    nota.descartar()

    assert transcribir_nota.call_local(nota.pk) == "sin nota"
    whisper.assert_not_called()


# ── La lista que pintan las dos pantallas ──────────────────────────────────


def test_la_lista_trae_las_notas_de_esta_sesion(
    client, clase, whisper, django_capture_on_commit_callbacks
):
    client.force_login(clase["profe"])
    nota = _grabar_y_transcribir(client, clase["sesion"], django_capture_on_commit_callbacks)
    otra = ClassSession.objects.create(
        title="Otra", group=clase["grupo"], teacher=clase["profe"], date="2026-09-25"
    )
    _grabar(client, otra)

    r = client.get(reverse("clases:class_session_notes_lista", args=[clase["sesion"].pk]))

    notas = r.json()["notas"]
    assert [n["pk"] for n in notas] == [nota.pk]
    assert notas[0]["estado"] == "transcrita"
    assert notas[0]["transcripcion"] == LO_QUE_ENTIENDE
    assert notas[0]["audio_url"].endswith(f"/notas/{nota.pk}/audio/")


# ── C239: permisos ─────────────────────────────────────────────────────────


def _urls_de(sesion, nota):
    return {
        "lista": ("get", reverse("clases:class_session_notes_lista", args=[sesion.pk])),
        "audio": ("get", reverse("clases:class_session_note_audio", args=[sesion.pk, nota.pk])),
        "aceptar": ("post", reverse("clases:class_session_note_aceptar", args=[sesion.pk, nota.pk])),
        "descartar": ("post", reverse("clases:class_session_note_descartar", args=[sesion.pk, nota.pk])),
        "grabar": ("post", reverse("clases:class_session_notes", args=[sesion.pk])),
    }


def test_otro_profesor_recibe_404_en_todo(client, clase, django_user_model):
    client.force_login(clase["profe"])
    _grabar(client, clase["sesion"])
    nota = SessionNote.objects.get()

    otro = django_user_model.objects.create_user(email="otro@x.es", password="x")
    otro_grupo = Group.objects.create(
        name="4-AC", subject=clase["grupo"].subject, academic_year="2026-2027"
    )
    otro_grupo.teachers.add(otro)
    client.force_login(otro)

    for nombre, (metodo, url) in _urls_de(clase["sesion"], nota).items():
        datos = {"texto": "intruso", "audio": _audio()} if metodo == "post" else None
        r = getattr(client, metodo)(url, datos) if datos else getattr(client, metodo)(url)
        assert r.status_code == 404, nombre

    assert SessionNote.objects.filter(pk=nota.pk).exists()


def test_el_alumno_no_llega_a_nada(client, clase):
    """Una nota de clase puede nombrar a un alumno."""
    client.force_login(clase["profe"])
    _grabar(client, clase["sesion"])
    nota = SessionNote.objects.get()

    client.force_login(clase["alumno"])
    for nombre, (metodo, url) in _urls_de(clase["sesion"], nota).items():
        r = getattr(client, metodo)(url)
        assert r.status_code in (302, 403, 404), nombre

    vista = client.get(reverse("clases:class_session_view", args=[clase["sesion"].pk]))
    if vista.status_code == 200:
        html = vista.content.decode()
        assert "notas_de_voz.js" not in html
        assert f"/notas/{nota.pk}/audio/" not in html


# ── El fichero: ruta cerrada, nombre impredecible, límite ─────────────────


def test_el_fichero_cuelga_de_la_ruta_cerrada_y_no_se_adivina(client, clase):
    client.force_login(clase["profe"])
    _grabar(client, clase["sesion"])

    nombre = SessionNote.objects.get().audio.name
    # nginx devuelve 404 en todo `/media/class_reflections/`.
    assert nombre.startswith("class_reflections/")
    sufijo = nombre.rsplit("/", 1)[-1].removeprefix(f"nota_{clase['sesion'].pk}_")
    assert len(sufijo.split(".")[0]) >= 16


def test_el_profesor_oye_su_nota(client, clase):
    client.force_login(clase["profe"])
    _grabar(client, clase["sesion"])
    nota = SessionNote.objects.get()

    r = client.get(
        reverse("clases:class_session_note_audio", args=[clase["sesion"].pk, nota.pk])
    )

    assert r.status_code == 200
    assert b"".join(r.streaming_content) == AUDIO
    assert r["Content-Type"] == "audio/webm"


def test_un_audio_de_mas_de_20_mb_da_400(client, clase):
    client.force_login(clase["profe"])

    r = client.post(
        reverse("clases:class_session_notes", args=[clase["sesion"].pk]),
        {"audio": _audio(b"0" * (20 * 1024 * 1024 + 1))},
    )

    assert r.status_code == 400
    assert not SessionNote.objects.exists()


# ── Las pantallas ──────────────────────────────────────────────────────────


def test_la_pantalla_de_la_sesion_monta_la_lista_para_el_profesor(client, clase):
    client.force_login(clase["profe"])

    r = client.get(reverse("clases:class_session_view", args=[clase["sesion"].pk]))

    html = r.content.decode()
    assert r.status_code == 200
    assert 'id="notas-de-voz"' in html
    assert "notas_de_voz.js" in html
    assert "{#" not in html and "{% comment" not in html


def test_el_visor_graba_directo_y_no_abre_ventanas(client, clase):
    client.force_login(clase["profe"])

    r = client.get(reverse("clases:class_session_present", args=[clase["sesion"].pk]))

    html = r.content.decode()
    assert r.status_code == 200
    assert 'onclick="alternarNotaDeVoz()"' in html
    assert "panel-notas" not in html
    assert "window.open" not in html
    assert "{% comment" not in html


def test_la_reflexion_actual_sigue_disponible_para_la_pantalla_de_cierre(client, clase):
    clase["sesion"].reflection = "Algo"
    clase["sesion"].save()
    client.force_login(clase["profe"])

    r = client.get(
        reverse("clases:class_session_reflection_actual", args=[clase["sesion"].pk])
    )

    assert r.json()["reflection"] == "Algo"
