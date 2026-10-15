import statistics

import pytest
from django.urls import reverse

from .lienzos import jpeg, lienzo

SEIS = [(1, 0), (7, 1), (13, 2), (42, 3), (77, 0), (99, 1)]


def _post_frame(client, datos):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return client.post(
        reverse("preguntas:detectar"),
        {"frame": SimpleUploadedFile("frame.jpg", datos, content_type="image/jpeg")},
    )


@pytest.mark.django_db
class TestPermisos:
    @pytest.mark.parametrize("nombre", ["prototipo", "tarjetas_prueba"])
    def test_sin_sesion_al_login(self, client, nombre):
        r = client.get(reverse(f"preguntas:{nombre}"))
        assert r.status_code == 302 and "login" in r["Location"]

    def test_un_alumno_no_entra(self, client, alumno):
        client.force_login(alumno)
        assert client.get(reverse("preguntas:prototipo")).status_code == 302
        assert _post_frame(client, jpeg(lienzo(SEIS))).status_code == 302


@pytest.mark.django_db
class TestPrototipo:
    def test_la_pagina_carga_con_el_enlace_al_pdf(self, client, profesor):
        client.force_login(profesor)
        r = client.get(reverse("preguntas:prototipo"))
        assert r.status_code == 200
        html = r.content.decode()
        assert reverse("preguntas:tarjetas_prueba") in html
        assert "{#" not in html

    def test_el_pdf_de_prueba_llega_como_pdf(self, client, profesor):
        client.force_login(profesor)
        r = client.get(reverse("preguntas:tarjetas_prueba"))
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")


@pytest.mark.django_db
class TestDetectar:
    def test_un_fotograma_con_seis_tarjetas(self, client, profesor):
        client.force_login(profesor)
        r = _post_frame(client, jpeg(lienzo(SEIS)))
        assert r.status_code == 200
        datos = r.json()
        assert [(m["id"], m["letra"]) for m in datos["marcadores"]] == [
            (1, "A"), (7, "B"), (13, "C"), (42, "D"), (77, "A"), (99, "B")
        ]
        assert datos["ms"] > 0

    def test_el_cuerpo_entero_tambien_vale(self, client, profesor):
        client.force_login(profesor)
        r = client.post(reverse("preguntas:detectar"), jpeg(lienzo([(3, 2)])), content_type="image/jpeg")
        assert r.status_code == 200
        assert r.json()["marcadores"] == [{"id": 3, "letra": "C", "centro": r.json()["marcadores"][0]["centro"]}]

    def test_basura_da_400_no_500(self, client, profesor):
        client.force_login(profesor)
        r = _post_frame(client, b"no soy una imagen")
        assert r.status_code == 400 and "legible" in r.json()["error"]

    def test_sin_imagen_da_400(self, client, profesor):
        client.force_login(profesor)
        r = client.post(reverse("preguntas:detectar"))
        assert r.status_code == 400

    def test_demasiado_grande_da_400(self, client, profesor):
        client.force_login(profesor)
        r = client.post(reverse("preguntas:detectar"), b"x" * 2_000_001, content_type="image/jpeg")
        assert r.status_code == 400

    def test_nada_se_escribe_en_disco(self, client, profesor, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        client.force_login(profesor)
        for _ in range(20):
            assert _post_frame(client, jpeg(lienzo(SEIS))).status_code == 200
        assert list(tmp_path.iterdir()) == []

    def test_cincuenta_fotogramas_bajo_cien_ms_cada_uno(self, client, profesor):
        """C472: el servidor tarda menos de 100 ms por fotograma de 640×480 (p95)."""
        client.force_login(profesor)
        datos = jpeg(lienzo(SEIS))
        tiempos = [_post_frame(client, datos).json()["ms"] for _ in range(50)]
        tiempos.sort()
        p95 = tiempos[int(len(tiempos) * 0.95) - 1]
        print(f"\nC472 detección: mediana {statistics.median(tiempos):.1f} ms · p95 {p95:.1f} ms · máx {tiempos[-1]:.1f} ms")
        assert p95 < 100
