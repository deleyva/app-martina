"""La nota de voz de una reflexión solo la oye el profesor que la grabó.

Estos tests existen por una pregunta del principal del 2026-09-22: «cuando
finalizo una sesión y hago un comentario, ¿eso lo ven los alumnos?». El texto
no, nunca lo estuvo. El audio sí lo habría estado en cuanto grabara el primero:
nginx entrega `/media/` sin pasar por Django, y el nombre del fichero se
construía como `reflexion_sesion_<pk>.webm`, con el id que el alumnado tiene en
su propia barra de direcciones. Se adivinaba entero.

**Se prueba por HTTP.** El agujero no estaba en la lógica sino en quién entrega
el fichero, y llamar a la función directamente se salta justo esa parte.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from clases.models import ClassSession, Enrollment, Group, Subject

AUDIO = b"esto-hace-de-nota-de-voz"


@pytest.fixture
def asignatura(db):
    return Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]


@pytest.fixture
def clase(db, django_user_model, asignatura):
    """Un profesor con su grupo, una sesión suya y un alumno matriculado."""
    profe = django_user_model.objects.create_user(email="profe@x.es", password="x")
    grupo = Group.objects.create(
        name="3-FH", subject=asignatura, academic_year="2026-2027"
    )
    grupo.teachers.add(profe)

    alumno = django_user_model.objects.create_user(email="alumna@x.es", password="x")
    Enrollment.objects.create(user=alumno, group=grupo, is_active=True)

    sesion = ClassSession.objects.create(
        title="Test", group=grupo, teacher=profe, date="2026-09-22"
    )
    return {"profe": profe, "alumno": alumno, "grupo": grupo, "sesion": sesion}


def _cerrar_con_audio(client, sesion, texto="Pepito no trae la flauta"):
    return client.post(
        reverse("clases:class_session_close", args=[sesion.pk]),
        {
            "reflection": texto,
            "reflection_audio": SimpleUploadedFile(
                "reflexion.webm", AUDIO, content_type="audio/webm"
            ),
        },
    )


def test_el_profesor_que_la_grabo_la_oye(client, clase):
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"])

    r = client.get(
        reverse("clases:class_session_reflection_audio", args=[clase["sesion"].pk])
    )

    assert r.status_code == 200
    assert b"".join(r.streaming_content) == AUDIO
    assert r["Content-Type"] == "audio/webm"


def test_un_alumno_matriculado_no_la_oye(client, clase):
    """El caso que motivó todo: el alumno ve la sesión, pero no la reflexión."""
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"])

    client.force_login(clase["alumno"])
    r = client.get(
        reverse("clases:class_session_reflection_audio", args=[clase["sesion"].pk])
    )

    assert r.status_code != 200


def test_otro_profesor_tampoco(client, clase, django_user_model, asignatura):
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"])

    otro = django_user_model.objects.create_user(email="otro@x.es", password="x")
    suyo = Group.objects.create(
        name="4-A", subject=asignatura, academic_year="2026-2027"
    )
    suyo.teachers.add(otro)

    client.force_login(otro)
    r = client.get(
        reverse("clases:class_session_reflection_audio", args=[clase["sesion"].pk])
    )

    assert r.status_code == 404


def test_sin_iniciar_sesion_no_se_llega(client, clase):
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"])
    client.logout()

    r = client.get(
        reverse("clases:class_session_reflection_audio", args=[clase["sesion"].pk])
    )

    assert r.status_code != 200


def test_el_nombre_del_fichero_no_se_adivina(client, clase):
    """El cinturón, además del tirante. Si algún día se cae la regla de nginx,
    que al menos haga falta acertar un token al azar y no el id de la sesión."""
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"])

    sesion = ClassSession.objects.get(pk=clase["sesion"].pk)
    nombre = sesion.reflection_audio.name

    assert f"reflexion_sesion_{sesion.pk}" not in nombre
    # `reflexion_<pk>_<token>.webm`: el token tiene que estar y ser largo.
    sufijo = nombre.rsplit("/", 1)[-1].removeprefix(f"reflexion_{sesion.pk}_")
    assert len(sufijo.removesuffix(".webm")) >= 12


def test_la_pagina_de_la_sesion_no_enlaza_a_media(client, clase):
    """Si la plantilla volviera a `.url`, el audio saldría por nginx otra vez."""
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"])

    r = client.get(reverse("clases:class_session_view", args=[clase["sesion"].pk]))
    cuerpo = r.content.decode()

    assert "/media/class_reflections/" not in cuerpo
    assert (
        reverse("clases:class_session_reflection_audio", args=[clase["sesion"].pk])
        in cuerpo
    )


def test_el_texto_de_la_reflexion_no_viaja_al_alumno(client, clase):
    """Lo que ya estaba bien, fijado para que siga estándolo."""
    marca = "CANARIO-PRIVADO Pepito no trae la flauta"
    client.force_login(clase["profe"])
    _cerrar_con_audio(client, clase["sesion"], texto=marca)

    client.force_login(clase["alumno"])
    for nombre in ("class_session_view", "class_session_present"):
        r = client.get(reverse(f"clases:{nombre}", args=[clase["sesion"].pk]))
        assert marca not in r.content.decode(), nombre
