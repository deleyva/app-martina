"""Notas tomadas en mitad de la clase, que van a la reflexión sin cerrarla.

Petición del principal (2026-09-24): «tomar notas sobre la clase en mitad de la
clase que vayan al campo "💭 Reflexión de la clase" (texto y/o audio)». Hasta
ahora la reflexión solo aparecía al pulsar «Finalizar clase».

Se prueba por HTTP, igual que `test_reflexion_audio.py`: lo delicado es quién
recibe qué, y eso vive en las vistas.
"""

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

AUDIO = b"esto-hace-de-nota-de-voz"


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
        title="Test", group=grupo, teacher=profe, date="2026-09-24"
    )
    return {"profe": profe, "alumno": alumno, "grupo": grupo, "sesion": sesion}


def _audio(nombre="nota.webm", contenido=AUDIO):
    return SimpleUploadedFile(nombre, contenido, content_type="audio/webm")


def _nota(client, sesion, **datos):
    return client.post(reverse("clases:class_session_notes", args=[sesion.pk]), datos)


# ── C223: añade sin cerrar ────────────────────────────────────────────────


def test_la_nota_se_anade_a_la_reflexion_sin_cerrar_la_clase(client, clase):
    sesion = clase["sesion"]
    sesion.reflection = "Lo que ya había"
    sesion.save()
    client.force_login(clase["profe"])

    with mock.patch("programacion.services.update_coverage_for_session") as cobertura:
        r1 = _nota(client, sesion, texto="Lucía por fin coge el ritmo")
        r2 = _nota(client, sesion, texto="El canon no ha funcionado")

    assert r1.status_code == 200 and r2.status_code == 200
    sesion.refresh_from_db()
    assert sesion.closed_at is None
    cobertura.assert_not_called()

    lineas = sesion.reflection.split("\n")
    assert lineas[0] == "Lo que ya había"
    assert lineas[1].endswith("Lucía por fin coge el ritmo")
    assert lineas[2].endswith("El canon no ha funcionado")
    assert SessionNote.objects.filter(session=sesion).count() == 2


def test_la_nota_apunta_el_elemento_que_habia_en_pantalla(client, clase):
    sesion = clase["sesion"]
    # Cualquier objeto sirve de contenido: basta con que tenga título.
    item = ClassSessionItem.objects.create(
        session=sesion,
        content_type=ContentType.objects.get_for_model(ClassSession),
        object_id=sesion.pk,
        order=0,
    )
    client.force_login(clase["profe"])

    _nota(client, sesion, texto="Aquí se pierden", item=str(item.pk))

    nota = SessionNote.objects.get(session=sesion)
    assert nota.item == item
    assert nota.item_titulo == item.get_content_title()
    sesion.refresh_from_db()
    assert f"· {item.get_content_title()}]" in sesion.reflection


def test_un_elemento_de_otra_sesion_no_se_cuela(client, clase):
    otra = ClassSession.objects.create(
        title="Otra", group=clase["grupo"], teacher=clase["profe"], date="2026-09-24"
    )
    ajeno = ClassSessionItem.objects.create(
        session=otra,
        content_type=ContentType.objects.get_for_model(ClassSession),
        object_id=otra.pk,
        order=0,
    )
    client.force_login(clase["profe"])

    _nota(client, clase["sesion"], texto="x", item=str(ajeno.pk))

    assert SessionNote.objects.get(session=clase["sesion"]).item is None


# ── C224: audio aparte, sin pisarse; vacía no vale ─────────────────────────


def test_tres_notas_de_voz_son_tres_ficheros(client, clase):
    sesion = clase["sesion"]
    client.force_login(clase["profe"])

    for i in range(3):
        r = _nota(client, sesion, audio=_audio(contenido=AUDIO + bytes([i])))
        assert r.status_code == 200
        assert r.json()["audio_url"]

    notas = list(SessionNote.objects.filter(session=sesion))
    nombres = {n.audio.name for n in notas}
    assert len(notas) == 3 and len(nombres) == 3
    sesion.refresh_from_db()
    assert sesion.reflection.count("🎤 nota de voz") == 3
    # El audio de cierre no se toca: las notas tienen su propio sitio.
    assert not sesion.reflection_audio


def test_una_nota_vacia_da_400_y_no_escribe_nada(client, clase):
    client.force_login(clase["profe"])

    r = _nota(client, clase["sesion"], texto="   ")

    assert r.status_code == 400
    assert not SessionNote.objects.exists()
    clase["sesion"].refresh_from_db()
    assert clase["sesion"].reflection == ""


# ── C225: el audio solo lo oye su profesor ─────────────────────────────────


def _url_audio(r):
    return r.json()["audio_url"]


def test_el_profesor_oye_su_nota_de_voz(client, clase):
    client.force_login(clase["profe"])
    url = _url_audio(_nota(client, clase["sesion"], audio=_audio()))

    r = client.get(url)

    assert r.status_code == 200
    assert b"".join(r.streaming_content) == AUDIO
    assert r["Content-Type"] == "audio/webm"


def test_otro_profesor_recibe_404(client, clase, django_user_model):
    client.force_login(clase["profe"])
    url = _url_audio(_nota(client, clase["sesion"], audio=_audio()))

    otro = django_user_model.objects.create_user(email="otro@x.es", password="x")
    otro_grupo = Group.objects.create(
        name="4-AC", subject=clase["grupo"].subject, academic_year="2026-2027"
    )
    otro_grupo.teachers.add(otro)
    client.force_login(otro)

    assert client.get(url).status_code == 404
    assert _nota(client, clase["sesion"], texto="intruso").status_code == 404
    reflexion = reverse("clases:class_session_reflection_actual", args=[clase["sesion"].pk])
    assert client.get(reflexion).status_code == 404


def test_el_alumno_no_llega_ni_a_las_notas_ni_al_audio(client, clase):
    """Anti-D: el alumnado ve la sesión, pero nada de sus notas."""
    client.force_login(clase["profe"])
    _nota(client, clase["sesion"], texto="Pepito no trae la flauta")
    url = _url_audio(_nota(client, clase["sesion"], audio=_audio()))

    client.force_login(clase["alumno"])
    pk = clase["sesion"].pk
    for u in (
        url,
        reverse("clases:class_session_notes", args=[pk]),
        reverse("clases:class_session_reflection_actual", args=[pk]),
    ):
        assert client.get(u).status_code in (302, 403, 404), u

    vista = client.get(reverse("clases:class_session_view", args=[pk]))
    if vista.status_code == 200:
        html = vista.content.decode()
        assert "Pepito no trae la flauta" not in html
        assert url not in html


def test_el_fichero_cuelga_de_la_ruta_cerrada_y_no_se_adivina(client, clase):
    client.force_login(clase["profe"])
    _nota(client, clase["sesion"], audio=_audio())

    nombre = SessionNote.objects.get().audio.name
    # nginx devuelve 404 en todo `/media/class_reflections/`.
    assert nombre.startswith("class_reflections/")
    sufijo = nombre.rsplit("/", 1)[-1].removeprefix(f"nota_{clase['sesion'].pk}_")
    assert len(sufijo.split(".")[0]) >= 16


# ── C226: el mismo límite que el cierre ────────────────────────────────────


def test_un_audio_de_mas_de_20_mb_da_400(client, clase, settings):
    client.force_login(clase["profe"])
    grande = _audio(contenido=b"0" * (20 * 1024 * 1024 + 1))

    r = _nota(client, clase["sesion"], audio=grande)

    assert r.status_code == 400
    assert not SessionNote.objects.exists()


# ── C227: cerrar no borra las notas ────────────────────────────────────────


def test_la_reflexion_actual_trae_las_notas_tomadas_desde_otra_ventana(client, clase):
    """La pantalla de cierre la pide al abrirse: es lo que evita que
    `close()`, que sobrescribe, borre las notas de la hora."""
    client.force_login(clase["profe"])
    _nota(client, clase["sesion"], texto="Primera")
    _nota(client, clase["sesion"], texto="Segunda")

    r = client.get(
        reverse("clases:class_session_reflection_actual", args=[clase["sesion"].pk])
    )

    assert r.status_code == 200
    reflexion = r.json()["reflection"]
    assert "Primera" in reflexion and "Segunda" in reflexion


def test_la_pagina_de_notas_lista_lo_tomado_y_no_escupe_comentarios(client, clase):
    client.force_login(clase["profe"])
    _nota(client, clase["sesion"], texto="Algo que apuntar")

    r = client.get(reverse("clases:class_session_notes", args=[clase["sesion"].pk]))

    html = r.content.decode()
    assert r.status_code == 200
    assert "Algo que apuntar" in html
    assert "{#" not in html and "{% comment" not in html


def test_la_pantalla_de_la_sesion_ofrece_el_audio_de_cada_nota(client, clase):
    client.force_login(clase["profe"])
    url = _url_audio(_nota(client, clase["sesion"], audio=_audio()))

    r = client.get(reverse("clases:class_session_view", args=[clase["sesion"].pk]))

    assert r.status_code == 200
    assert url in r.content.decode()
