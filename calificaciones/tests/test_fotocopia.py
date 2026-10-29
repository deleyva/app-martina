"""Fase 84: la foto de un folio sale enderezada, como fotocopia en color y en WebP.

Todas las imágenes son sintéticas (`folios.py`): ni una foto de alumnado.
"""

from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest
from django.core.files.storage import FileSystemStorage
from django.urls import reverse

from calificaciones import documento
from calificaciones.models import Evidencia
from calificaciones.tasks import procesar_foto

from . import folios
from .test_evidencias import subir  # noqa: F401 - el fixture del clip

A4 = 1414 / 1000


@pytest.fixture(scope="module")
def en_la_mesa():
    """Un folio A4 fotografiado a 12 MP sobre una mesa, y lo que sale de él."""
    foto = folios.sobre_la_mesa(folios.folio())
    datos = folios.jpeg(foto)
    webp, hecho = documento.procesar(datos)
    return foto, datos, webp, hecho, folios.descodificar(webp)


def _proporcion(img):
    return img.shape[0] / img.shape[1]


def _ficheros(settings):
    return [p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()]


# ----- la imagen ---------------------------------------------------------------------


def test_el_folio_se_encuentra_y_se_endereza(en_la_mesa):
    """C540: la proporción del A4 y bordes de papel, no de mesa."""
    _, _, _, hecho, salida = en_la_mesa
    assert hecho["folio"] is True
    assert _proporcion(salida) == pytest.approx(A4, rel=0.04)
    borde = np.concatenate([salida[:6].reshape(-1, 3), salida[-6:].reshape(-1, 3),
                            salida[:, :6].reshape(-1, 3), salida[:, -6:].reshape(-1, 3)])
    assert borde.mean() > 240  # la mesa está en torno a 60


def test_un_folio_pequeno_en_una_foto_apaisada():
    """C540: lejos y en horizontal, también."""
    foto = folios.sobre_la_mesa(
        folios.folio(), ancho=4032, alto=3024, esquinas=[(1500, 700), (2500, 760), (2560, 2250), (1440, 2200)]
    )
    webp, hecho = documento.procesar(folios.jpeg(foto))
    assert hecho["folio"] is True
    assert _proporcion(folios.descodificar(webp)) == pytest.approx(A4, rel=0.04)


def test_un_escaneo_no_se_recorta():
    """C541: la hoja ya es la foto. Antes de exigir «papel dentro, no papel fuera»,
    el hueco entre dos renglones pasaba por folio y salía media hoja."""
    escaneo = folios.ruido(folios.sombra(folios.folio()))
    webp, hecho = documento.procesar(folios.jpeg(escaneo))
    salida = folios.descodificar(webp)
    assert hecho == {"folio": False, "papel": True, "ancho": 1000, "alto": 1414}
    assert salida.shape[:2] == escaneo.shape[:2]


def test_lo_que_no_es_un_papel_solo_se_reduce():
    """C541 y Anti-C: ni recorte ni fotocopia; los colores, como estaban."""
    foto = folios.no_es_un_papel()
    webp, hecho = documento.procesar(folios.jpeg(foto))
    salida = folios.descodificar(webp)
    assert hecho["folio"] is False and hecho["papel"] is False
    assert _proporcion(salida) == pytest.approx(_proporcion(foto), rel=0.01)
    reducida = documento.reducir(foto, documento.LADO_MAXIMO)
    diferencia = np.abs(salida.reshape(-1, 3).mean(0) - reducida.reshape(-1, 3).mean(0))
    assert diferencia.max() < 6


def test_el_papel_sale_blanco_aunque_haya_sombra(en_la_mesa):
    """C542: la izquierda de la foto está a un 62 % de luz; en la salida no se nota."""
    foto, _, _, _, salida = en_la_mesa
    alto, ancho = salida.shape[:2]
    gris = cv2.cvtColor(salida, cv2.COLOR_BGR2GRAY)
    # Papel sin escribir entre el último renglón y el nombre.
    izquierda = gris[int(0.80 * alto) : int(0.85 * alto), int(0.10 * ancho) : int(0.30 * ancho)]
    derecha = gris[int(0.80 * alto) : int(0.85 * alto), int(0.60 * ancho) : int(0.75 * ancho)]
    for papel in (izquierda, derecha):
        assert papel.mean() >= 245
        assert papel.std() <= 6
    # La sombra sí estaba en la foto: el papel de la izquierda era bastante más oscuro.
    fila = cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY)[3300, :]
    assert fila[700] < fila[2300] - 40


def test_la_tinta_conserva_su_color(en_la_mesa):
    """C542: las correcciones siguen rojas y las figuras, azules."""
    _, _, _, _, salida = en_la_mesa
    assert folios.rojos(salida) > 3000
    assert folios.azules(salida) > 20000


def test_el_lapiz_flojo_no_se_borra(en_la_mesa):
    """C542: los dictados van a lápiz. Un blanco más bajo en los niveles lo borraba."""
    _, _, _, _, salida = en_la_mesa
    alto, ancho = salida.shape[:2]
    x0, x1, y0, y1 = folios.ZONA_LAPIZ
    zona = cv2.cvtColor(salida[int(y0 * alto) : int(y1 * alto), int(x0 * ancho) : int(x1 * ancho)], cv2.COLOR_BGR2GRAY)
    assert zona.min() < 200


def test_las_esquinas_del_folio_siguen_dentro(en_la_mesa):
    """Anti-B: una marca pegada a cada esquina del folio sobrevive al recorte."""
    _, _, _, _, salida = en_la_mesa
    alto, ancho = salida.shape[:2]
    a, b = int(0.12 * alto), int(0.12 * ancho)
    for esquina in (salida[:a, :b], salida[:a, -b:], salida[-a:, -b:], salida[-a:, :b]):
        assert folios.azules(esquina) > 20


def test_doce_megapixeles_se_quedan_en_poco(en_la_mesa):
    """C543: lado largo 1600, WebP y menos de 250 KB."""
    foto, datos, webp, _, salida = en_la_mesa
    assert foto.shape[:2] == (4032, 3024)
    assert max(salida.shape[:2]) == documento.LADO_MAXIMO
    assert webp[:4] == b"RIFF" and webp[8:12] == b"WEBP"
    assert len(webp) < 250_000
    assert len(webp) < len(datos) / 10


def test_la_orientacion_del_movil_se_respeta():
    """Una foto en vertical que el móvil guarda en horizontal con EXIF 6 sale en vertical."""
    from io import BytesIO

    from PIL import Image

    tumbada = np.ascontiguousarray(np.rot90(folios.folio(), 1))  # 1414 de ancho, 1000 de alto
    salida = BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6  # girar 90° en sentido horario para verla bien
    Image.fromarray(cv2.cvtColor(tumbada, cv2.COLOR_BGR2RGB)).save(salida, "JPEG", exif=exif)
    webp, hecho = documento.procesar(salida.getvalue())
    assert hecho["alto"] > hecho["ancho"]


# ----- la cola -----------------------------------------------------------------------


@pytest.mark.django_db
def test_una_foto_se_encola_al_confirmar(subir):
    """C539: queda pendiente y la tarea recibe su pk, pero no antes del commit."""
    with mock.patch("calificaciones.tasks.procesar_foto") as tarea:
        r = subir("foto", "image.jpg", declarado="image/jpeg", confirmar=False)
        tarea.assert_not_called()
    evidencia = Evidencia.objects.get()
    assert evidencia.estado == Evidencia.PENDIENTE
    assert r.json()["evidencia"]["estado"] == "pendiente"

    Evidencia.objects.all().delete()
    with mock.patch("calificaciones.tasks.procesar_foto") as tarea:
        subir("foto", "image.jpg", declarado="image/jpeg")
    tarea.assert_called_once_with(Evidencia.objects.get().pk)


@pytest.mark.django_db
def test_un_escaneo_por_subir_archivo_tambien_se_procesa(subir):
    """C539: «Subir archivo» con un PNG es una foto, y va a la misma cola."""
    with mock.patch("calificaciones.tasks.procesar_foto") as tarea:
        subir("archivo", "escaneo.PNG")
    evidencia = Evidencia.objects.get()
    assert evidencia.tipo == Evidencia.FOTO
    tarea.assert_called_once_with(evidencia.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tipo", "nombre", "extra"),
    [("audio", "a.webm", {}), ("video", "v.mp4", {}), ("archivo", "a.pdf", {}), ("texto", None, {"texto": "bien"})],
)
def test_lo_que_no_es_una_foto_no_va_a_la_fotocopia(subir, tipo, nombre, extra):
    """C539."""
    with mock.patch("calificaciones.tasks.procesar_foto") as tarea, mock.patch("calificaciones.tasks.comprimir_video"):
        assert subir(tipo, nombre, **extra).status_code == 200
    tarea.assert_not_called()


# ----- la tarea ----------------------------------------------------------------------


@pytest.mark.django_db
def test_al_terminar_se_sirve_el_webp_y_el_original_ya_no_esta(client, subir, settings, en_la_mesa):
    """C544, con Huey inmediato como en los tests: subir es ya procesar."""
    _, datos, _, _, _ = en_la_mesa
    r = subir("foto", "image.jpg", datos, declarado="image/jpeg")
    assert r.status_code == 200
    evidencia = Evidencia.objects.get()
    assert evidencia.estado == Evidencia.LISTO, evidencia.error
    assert not evidencia.archivo
    assert evidencia.archivo_comprimido.name.endswith(".webp")
    assert evidencia.tipo_mime == "image/webp"
    assert evidencia.nombre_original == "image.jpg"
    assert [p.suffix for p in _ficheros(settings)] == [".webp"]

    visto = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert visto["Content-Type"] == "image/webp"
    cuerpo = b"".join(visto.streaming_content)
    assert cuerpo[8:12] == b"WEBP"
    assert evidencia.tamano == len(cuerpo) < 250_000


@pytest.mark.django_db
def test_la_url_cambia_cuando_llega_la_fotocopia(client, subir, en_la_mesa):
    """C547: si la URL fuera la misma, el navegador enseñaría la foto de la caché una hora."""
    _, datos, _, _, _ = en_la_mesa
    antes = subir("foto", "image.jpg", datos, declarado="image/jpeg", confirmar=False).json()["evidencia"]
    evidencia = Evidencia.objects.get()
    procesar_foto.call_local(evidencia.pk)
    despues = client.get(reverse("calificaciones:evidencia_estado", args=[evidencia.pk]))
    assert despues["Cache-Control"] == "no-store"
    assert antes["estado"] == "pendiente" and despues.json()["estado"] == "listo"
    assert antes["url"] != despues.json()["url"]
    assert despues.json()["url"].startswith(f"/calificaciones/evidencia/{evidencia.pk}/?v=")


@pytest.mark.django_db
def test_el_estado_de_una_evidencia_solo_lo_ve_su_profesor(client, subir, otro_profesor, otro_group):
    """C547: el endpoint del sondeo tiene la misma puerta que ver la evidencia."""
    with mock.patch("calificaciones.tasks.procesar_foto"):
        subir("foto", "image.jpg")
    pk = Evidencia.objects.get().pk
    client.force_login(otro_profesor)
    assert client.get(reverse("calificaciones:evidencia_estado", args=[pk])).status_code == 404


@pytest.mark.django_db
def test_si_no_es_una_imagen_falla_y_se_sirve_el_original(client, subir, settings):
    """C545: un HEIC sin decodificador o un fichero roto no se pierden."""
    subir("foto", "image.heic", b"esto no es una imagen", declarado="image/heic")
    evidencia = Evidencia.objects.get()
    assert evidencia.estado == Evidencia.FALLIDO
    assert evidencia.error
    assert evidencia.archivo and not evidencia.archivo_comprimido
    visto = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert visto["Content-Type"] == "image/heic"
    assert b"".join(visto.streaming_content) == b"esto no es una imagen"


@pytest.mark.django_db
def test_si_no_se_puede_guardar_el_webp_el_original_sigue(subir, settings, en_la_mesa):
    """Anti-A: el original solo se borra cuando el WebP ya está guardado."""
    _, datos, _, _, _ = en_la_mesa
    subir("foto", "image.jpg", datos, declarado="image/jpeg", confirmar=False)
    evidencia = Evidencia.objects.get()
    with mock.patch.object(FileSystemStorage, "save", side_effect=OSError("disco lleno")):
        procesar_foto.call_local(evidencia.pk)
    evidencia.refresh_from_db()
    assert evidencia.estado == Evidencia.FALLIDO
    assert "disco lleno" in evidencia.error
    assert evidencia.archivo.storage.exists(evidencia.archivo.name)
    with evidencia.archivo.open("rb") as f:
        assert f.read() == datos


@pytest.mark.django_db
def test_si_la_borran_mientras_se_procesa_no_queda_nada_en_disco(subir, settings, en_la_mesa):
    """Borrar en la galería mientras Huey trabaja no deja un WebP huérfano."""
    _, datos, _, _, _ = en_la_mesa
    subir("foto", "image.jpg", datos, declarado="image/jpeg", confirmar=False)
    evidencia = Evidencia.objects.get()
    real = documento.procesar

    def borrar_y_procesar(contenido):
        Evidencia.objects.get(pk=evidencia.pk).delete()
        return real(contenido)

    with mock.patch("calificaciones.tasks.documento.procesar", side_effect=borrar_y_procesar):
        procesar_foto.call_local(evidencia.pk)
    assert not Evidencia.objects.exists()
    assert _ficheros(settings) == []


# ----- lo que encontró la revisión (2026-10-29) --------------------------------------


def _png(array, modo):
    from io import BytesIO

    from PIL import Image

    salida = BytesIO()
    Image.fromarray(array, modo).save(salida, "PNG")
    return salida.getvalue()


def test_un_png_transparente_sale_sobre_blanco():
    """Una exportación de MuseScore: notación negra sobre transparente. Salía negra entera."""
    rgba = np.zeros((1414, 1000, 4), np.uint8)
    cv2.putText(rgba, "DICTADO", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0, 255), 8)
    gris = cv2.cvtColor(folios.descodificar(documento.procesar(_png(rgba, "RGBA"))[0]), cv2.COLOR_BGR2GRAY)
    assert gris.mean() > 240  # el fondo, blanco
    assert gris.min() < 60  # y lo escrito, ahí


def test_un_png_de_16_bits_conserva_lo_escrito():
    """Lo que dan algunos escáneres. Salía blanco entero."""
    gris16 = np.full((1414, 1000), 60000, np.uint16)
    gris16[200:260, 100:900] = 5000
    gris = cv2.cvtColor(folios.descodificar(documento.procesar(_png(gris16, "I;16"))[0]), cv2.COLOR_BGR2GRAY)
    assert gris.min() < 60 and gris.mean() > 200


def test_una_animacion_no_se_toca():
    from io import BytesIO

    from PIL import Image

    salida = BytesIO()
    cuadros = [Image.new("RGB", (200, 200), c) for c in ("white", "black")]
    cuadros[0].save(salida, "GIF", save_all=True, append_images=cuadros[1:])
    with pytest.raises(ValueError):
        documento.procesar(salida.getvalue())


@pytest.mark.parametrize(
    "esquinas",
    [
        [(-500, 520), (2420, 640), (2560, 3520), (430, 3400)],  # la de arriba a la izquierda, fuera por el lado
        [(-250, -250), (2420, 640), (2560, 3520), (430, 3400)],  # fuera por la diagonal
    ],
)
def test_con_una_esquina_fuera_del_encuadre_no_se_recorta(esquinas):
    """Aproximar el pentágono a cuatro lados cortaba hasta un 10 % del folio, por arriba."""
    foto = folios.sobre_la_mesa(folios.folio(), esquinas=esquinas)
    webp, hecho = documento.procesar(folios.jpeg(foto))
    assert hecho["folio"] is False
    assert _proporcion(folios.descodificar(webp)) == pytest.approx(_proporcion(foto), rel=0.01)


@pytest.mark.parametrize("forma", [(5000, 1), (1, 5000), (1, 1), (3, 3000)])
def test_formas_extremas_no_revientan(forma):
    img = np.full((*forma, 3), 200, np.uint8)
    webp, _ = documento.procesar(folios.jpeg(img))
    assert webp[8:12] == b"WEBP"


def test_si_la_fotocopia_sale_lisa_se_lanza():
    """La red de seguridad: un resultado sin nada, de una foto con algo, no se da por bueno."""
    foto = folios.jpeg(folios.ruido(folios.sombra(folios.folio())))
    with mock.patch.object(documento, "fotocopia", side_effect=lambda img: np.full_like(img, 255)):
        with pytest.raises(ValueError, match="lisa"):
            documento.procesar(foto)


@pytest.mark.django_db
def test_una_animacion_queda_fallida_y_con_su_original(subir):
    from io import BytesIO

    from PIL import Image

    salida = BytesIO()
    cuadros = [Image.new("RGB", (200, 200), c) for c in ("white", "black")]
    cuadros[0].save(salida, "GIF", save_all=True, append_images=cuadros[1:])
    subir("foto", "metronomo.gif", salida.getvalue(), declarado="image/gif")
    evidencia = Evidencia.objects.get()
    assert evidencia.estado == Evidencia.FALLIDO
    assert evidencia.archivo.storage.exists(evidencia.archivo.name)


@pytest.mark.django_db
def test_si_no_se_puede_borrar_el_original_la_foto_sigue_lista(subir, en_la_mesa):
    """Antes, el fallo al borrar el original pasaba a `fallido` una evidencia que ya servía su WebP."""
    _, datos, _, _, _ = en_la_mesa
    subir("foto", "image.jpg", datos, declarado="image/jpeg", confirmar=False)
    evidencia = Evidencia.objects.get()
    with mock.patch.object(FileSystemStorage, "delete", side_effect=OSError("permiso")):
        procesar_foto.call_local(evidencia.pk)
    evidencia.refresh_from_db()
    assert evidencia.estado == Evidencia.LISTO
    assert evidencia.archivo_comprimido.name.endswith(".webp")


@pytest.mark.django_db
def test_borrar_con_la_evidencia_cargada_antes_de_procesar_no_deja_el_webp(subir, settings, en_la_mesa):
    """La galería carga la evidencia, Huey la cambia por el WebP y luego se borra la copia vieja."""
    _, datos, _, _, _ = en_la_mesa
    subir("foto", "image.jpg", datos, declarado="image/jpeg", confirmar=False)
    vieja = Evidencia.objects.get()
    procesar_foto.call_local(vieja.pk)
    assert vieja.archivo_comprimido.name == ""  # la instancia no se ha enterado
    vieja.delete()
    assert not Evidencia.objects.exists()
    assert _ficheros(settings) == []


@pytest.mark.django_db
def test_si_redis_no_contesta_la_subida_no_falla(subir):
    """El encolado va al confirmar y con `robust`: la foto ya está guardada y se sirve tal cual."""
    with mock.patch("calificaciones.tasks.procesar_foto", side_effect=ConnectionError("redis")):
        r = subir("foto", "image.jpg", declarado="image/jpeg")
    assert r.status_code == 200
    assert Evidencia.objects.get().estado == Evidencia.PENDIENTE


@pytest.mark.django_db
def test_las_fotos_atascadas_vuelven_a_la_cola(subir):
    from datetime import timedelta

    from django.utils import timezone

    from calificaciones.tasks import rescatar_fotos

    with mock.patch("calificaciones.tasks.procesar_foto"):
        for _ in range(3):
            subir("foto", "image.jpg", declarado="image/jpeg", confirmar=False)
    vieja, reciente, fallida = Evidencia.objects.order_by("pk")
    hace_una_hora = timezone.now() - timedelta(hours=1)
    Evidencia.objects.filter(pk__in=[vieja.pk, fallida.pk]).update(created_at=hace_una_hora)
    Evidencia.objects.filter(pk=fallida.pk).update(estado=Evidencia.FALLIDO)
    with mock.patch("calificaciones.tasks.procesar_foto") as tarea:
        rescatar_fotos.call_local()
    tarea.assert_called_once_with(vieja.pk)
