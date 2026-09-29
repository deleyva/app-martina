"""C343–C345: qué es cada evidencia y cómo se sirve."""

from io import BytesIO
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from calificaciones import ficheros
from calificaciones.models import Evidencia, Prueba


@pytest.fixture
def subir(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    prueba = Prueba.objects.filter(instrumento__plan=plan).first()

    def _subir(tipo, nombre, contenido=b"x" * 1000, declarado="application/octet-stream", **extra):
        datos = {"prueba": prueba.pk, "alumno": alumnos[0].pk, "tipo": tipo, **extra}
        if nombre:
            datos["archivo"] = SimpleUploadedFile(nombre, contenido, content_type=declarado)
        return client.post(reverse("calificaciones:evidencia_subir", args=[group.pk]), datos)

    return _subir


@pytest.mark.django_db
def test_html_disfrazado_baja_como_adjunto(client, subir):
    r = subir("archivo", "inocente.html", b"<script>alert(1)</script>", declarado="image/jpeg")
    assert r.status_code == 200
    evidencia = Evidencia.objects.get()
    assert evidencia.tipo == "archivo"
    assert evidencia.tipo_mime == ""
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert visto["Content-Type"] == "application/octet-stream"
    assert visto["Content-Disposition"].startswith("attachment")
    assert "inocente.html" in visto["Content-Disposition"]
    assert visto["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in visto["Content-Security-Policy"]


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", ["dibujo.svg", "pagina.htm", "macro.js", "sin_extension"])
def test_nada_que_ejecute_se_sirve_en_linea(client, subir, nombre):
    subir("archivo", nombre, b"<svg onload=alert(1)>", declarado="image/svg+xml")
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[Evidencia.objects.get().pk]))
    assert visto["Content-Disposition"].startswith("attachment")
    assert visto["Content-Type"] == "application/octet-stream"


@pytest.mark.django_db
def test_mime_del_cliente_no_manda(client, subir):
    subir("foto", "foto.jpg", declarado="text/html")
    evidencia = Evidencia.objects.get()
    assert evidencia.tipo_mime == "image/jpeg"
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert visto["Content-Type"] == "image/jpeg"
    assert "Content-Disposition" not in visto or visto["Content-Disposition"].startswith("inline")


@pytest.mark.django_db
def test_lo_declarado_tiene_que_casar_con_el_fichero(subir):
    assert subir("foto", "programa.exe").status_code == 400
    assert subir("audio", "foto.jpg").status_code == 400
    assert subir("video", "apuntes.pdf").status_code == 400
    assert not Evidencia.objects.exists()


@pytest.mark.django_db
def test_subir_archivo_reconoce_lo_que_es(subir):
    with mock.patch("calificaciones.tasks.comprimir_video"):
        for nombre, tipo in [
            ("a.jpg", "foto"),
            ("a.PNG", "foto"),
            ("a.mp3", "audio"),
            ("a.mov", "video"),
            ("a.pdf", "archivo"),
            ("a.docx", "archivo"),
        ]:
            assert subir("archivo", nombre).json()["evidencia"]["tipo"] == tipo, nombre


@pytest.mark.django_db
def test_nombre_y_peso_se_guardan(subir):
    r = subir("archivo", "Partitura de Ana.pdf", b"%PDF-" + b"0" * 2043)
    evidencia = r.json()["evidencia"]
    assert evidencia["nombre"] == "Partitura de Ana.pdf"
    assert evidencia["tamano"] == 2048
    guardada = Evidencia.objects.get()
    # En disco el nombre sigue siendo un uuid: el original no se puede adivinar.
    assert "Partitura" not in guardada.archivo.name


@pytest.mark.django_db
def test_un_pdf_se_ve_en_linea(client, subir):
    subir("archivo", "apuntes.pdf", b"%PDF-1.4")
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[Evidencia.objects.get().pk]))
    assert visto["Content-Type"] == "application/pdf"
    assert "Content-Security-Policy" not in visto


@pytest.mark.django_db
def test_audio_webm_no_va_a_ffmpeg(client, subir):
    with mock.patch("calificaciones.tasks.comprimir_video") as tarea:
        r = subir("audio", "grabacion-1.webm", declarado="audio/webm")
    assert r.status_code == 200
    tarea.assert_not_called()
    evidencia = Evidencia.objects.get()
    assert evidencia.tipo == "audio"
    assert evidencia.estado == Evidencia.LISTO
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert visto["Content-Type"] == "audio/webm"


@pytest.mark.django_db
def test_video_va_a_la_cola(client, subir):
    with mock.patch("calificaciones.tasks.comprimir_video") as tarea:
        r = subir("video", "video.webm", declarado="video/webm")
    assert r.status_code == 200
    evidencia = Evidencia.objects.get()
    tarea.assert_called_once_with(evidencia.pk)
    assert evidencia.estado == Evidencia.PENDIENTE
    assert r.json()["evidencia"]["estado"] == "pendiente"
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert visto["Content-Type"] == "video/webm"


@pytest.mark.django_db
def test_rango_de_bytes_devuelve_206(client, subir):
    contenido = bytes(range(256)) * 4
    with mock.patch("calificaciones.tasks.comprimir_video"):
        subir("audio", "a.mp3", contenido)
    url = reverse("calificaciones:evidencia_ver", args=[Evidencia.objects.get().pk])

    entero = client.get(url)
    assert entero.status_code == 200
    assert entero["Accept-Ranges"] == "bytes"
    assert b"".join(entero.streaming_content) == contenido

    trozo = client.get(url, HTTP_RANGE="bytes=10-19")
    assert trozo.status_code == 206
    assert trozo["Content-Range"] == "bytes 10-19/1024"
    assert trozo["Content-Length"] == "10"
    assert b"".join(trozo.streaming_content) == contenido[10:20]

    hasta_el_final = client.get(url, HTTP_RANGE="bytes=1000-")
    assert hasta_el_final["Content-Range"] == "bytes 1000-1023/1024"
    assert b"".join(hasta_el_final.streaming_content) == contenido[1000:]

    los_ultimos = client.get(url, HTTP_RANGE="bytes=-24")
    assert b"".join(los_ultimos.streaming_content) == contenido[-24:]

    pasado = client.get(url, HTTP_RANGE="bytes=5000-6000")
    assert pasado.status_code == 416
    assert pasado["Content-Range"] == "bytes */1024"


@pytest.mark.django_db
def test_comentario_y_borrado(client, subir):
    r = subir("texto", None, texto="Ha mejorado la afinación")
    evidencia = r.json()["evidencia"]
    assert evidencia["tipo"] == "texto"
    assert evidencia["texto"] == "Ha mejorado la afinación"
    assert evidencia["url"] == ""
    borrado = client.post(reverse("calificaciones:evidencia_borrar", args=[evidencia["id"]]))
    assert borrado.json()["ok"] is True
    assert not Evidencia.objects.exists()


@pytest.mark.parametrize(
    ("tipo", "nombre", "esperado"),
    [
        ("audio", "x.webm", "audio/webm"),
        ("video", "x.webm", "video/webm"),
        ("audio", "x.mp4", "audio/mp4"),
        ("video", "x.mp4", "video/mp4"),
        ("foto", "x.svg", None),
        ("archivo", "x.html", None),
        ("archivo", "x.PDF", "application/pdf"),
    ],
)
def test_tipo_de_contenido(tipo, nombre, esperado):
    assert ficheros.tipo_de_contenido(tipo, nombre) == esperado
