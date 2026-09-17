"""Tests de la API de recortes y del servido restringido.

Lo que se prueba de verdad aqui no es que la API responda 200: es que un PDF
marcado como restringido DEJE DE SALIR entero por ninguna puerta publica, y que
el recorte siga siendo legible.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth import get_user_model
from wagtail.documents.models import Document
from wagtail.models import Page

from api_keys.models import APIKey
from musica.models import DocumentoRestringido, LibroDeEstudioPage, Recorte

User = get_user_model()


def _pdf_de_n_paginas(n):
    """Un PDF real de `n` paginas, construido con pypdf.

    Hace falta uno de verdad: la vista de rango lo LEE, asi que un fichero falso
    con bytes sueltos probaria otra cosa (el 404 de PDF ilegible) en vez de lo
    que se quiere probar.
    """
    from pypdf import PdfWriter

    escritor = PdfWriter()
    for _ in range(n):
        escritor.add_blank_page(width=200, height=300)
    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def profe(db):
    return User.objects.create_user(email="p@ej.org", password="x", is_staff=True)


@pytest.fixture
def alumno(db):
    return User.objects.create_user(email="a@ej.org", password="x")


@pytest.fixture
def pdf(db):
    from wagtail.models import Collection

    if not Collection.objects.exists():
        Collection.add_root(name="Root")
    return Document.objects.create(
        title="Metodo",
        file=SimpleUploadedFile("metodo.pdf", _pdf_de_n_paginas(14)),
    )


@pytest.fixture
def raiz(db):
    from django.conf import settings as dj
    from wagtail.models import Locale

    if not Locale.objects.exists():
        Locale.objects.create(language_code=dj.LANGUAGE_CODE.split("-")[0])
    return Page.objects.filter(depth=1).first() or Page.add_root(title="R", slug="r")


def _lote(client, pdf, recortes, libro_id=None):
    cuerpo = {"documento_id": pdf.pk, "recortes": recortes}
    if libro_id:
        cuerpo["libro_id"] = libro_id
    return client.post(
        "/api/recortes/lote", data=cuerpo, content_type="application/json"
    )


# === Autenticacion por clave de API ===


def test_la_clave_de_api_sirve_para_crear(client, profe, pdf):
    """El caso que abre la fase: trocear un libro sin abrir el navegador."""
    clave = APIKey.objects.create(user=profe, name="scripts")

    r = client.post(
        "/api/recortes/lote",
        data={"documento_id": pdf.pk, "recortes": [{"nombre": "Uno", "pagina_desde": 1}]},
        content_type="application/json",
        HTTP_X_API_KEY=str(clave.key),
    )

    assert r.status_code == 200, r.content
    assert Recorte.objects.count() == 1


def test_sin_clave_ni_sesion_no_se_crea_nada(client, pdf):
    r = _lote(client, pdf, [{"nombre": "Uno"}])

    assert r.status_code == 401
    assert Recorte.objects.count() == 0


def test_la_clave_de_un_alumno_no_crea_contenido(client, alumno, pdf):
    """`DatabaseApiKey` autentica COMO SU DUENA, sin ambito propio, y cualquiera
    con sesion puede crearse una clave. Sin la comprobacion de profesor, un
    alumno publicaria capitulos."""
    clave = APIKey.objects.create(user=alumno, name="suya")

    r = client.post(
        "/api/recortes/lote",
        data={"documento_id": pdf.pk, "recortes": [{"nombre": "Uno"}]},
        content_type="application/json",
        HTTP_X_API_KEY=str(clave.key),
    )

    assert r.status_code == 403
    assert Recorte.objects.count() == 0


# === El lote ===


def test_un_lote_monta_el_libro_en_una_llamada(client, profe, pdf, raiz):
    libro = LibroDeEstudioPage(title="Piano Adventures", slug="pa", capitulos=[])
    raiz.add_child(instance=libro)
    libro.save_revision().publish()
    client.force_login(profe)

    r = _lote(client, pdf, [
        {"nombre": "Sailing Boat", "pagina_desde": 10, "pagina_hasta": 13},
        {"nombre": "Rain Rain", "pagina_desde": 14},
    ], libro_id=libro.pk)

    assert r.status_code == 200, r.content
    libro.refresh_from_db()
    assert [b.value.nombre for b in libro.capitulos] == ["Sailing Boat", "Rain Rain"]


def test_un_lote_a_medias_no_deja_nada(client, profe, pdf):
    """Todo o nada. Un lote a medias deja un libro con la mitad de los capitulos
    y sin forma de saber por donde iba."""
    client.force_login(profe)

    r = _lote(client, pdf, [
        {"nombre": "Bueno", "pagina_desde": 1},
        {"nombre": "Malo", "pagina_desde": 13, "pagina_hasta": 10},
    ])

    assert r.status_code == 400
    assert "Malo" in r.json()["detail"]
    assert Recorte.objects.count() == 0


def test_el_lote_valida_igual_que_la_pantalla(client, profe, pdf):
    client.force_login(profe)

    r = _lote(client, pdf, [{"nombre": "Medio", "rect_x0": 0.1, "rect_y0": 0.2}])

    assert r.status_code == 400
    assert Recorte.objects.count() == 0


def test_listar_lo_que_ya_hay(client, profe, pdf):
    """Es lo que evita duplicar al reintentar."""
    client.force_login(profe)
    _lote(client, pdf, [{"nombre": "Uno", "pagina_desde": 3}])

    r = client.get(f"/api/recortes/documento/{pdf.pk}")

    assert r.status_code == 200
    assert [x["nombre"] for x in r.json()] == ["Uno"]


def test_no_se_recorta_lo_que_no_es_pdf(client, profe, db):
    audio = Document.objects.create(
        title="Pista", file=SimpleUploadedFile("p.mp3", b"id3")
    )
    client.force_login(profe)

    r = _lote(client, audio, [{"nombre": "Uno"}])

    assert r.status_code == 400


# === Servido restringido: lo que de verdad importa ===


def test_por_defecto_el_pdf_se_sirve_entero(client, pdf):
    """El estado de partida, para que el test siguiente signifique algo.

    302 y no 200: el gancho aparta lo no restringido y lo manda al fichero, que
    es lo que conserva las peticiones por rango de las que dependen los audios.
    """
    r = client.get(pdf.url)

    assert r.status_code == 302
    assert r["Location"] == pdf.file.url


def test_un_pdf_restringido_deja_de_servirse(client, profe, pdf):
    """El agujero que cierra la fase. Hasta ahora `WAGTAILDOCS_SERVE_METHOD` no
    estaba puesto y la URL del documento redirigia al fichero de media: decir
    «el alumno solo ve las paginas 10-13» era falso."""
    DocumentoRestringido.objects.create(documento=pdf)

    r = client.get(pdf.url)

    assert r.status_code == 404


def test_ni_siquiera_el_profesorado_lo_saca_por_la_puerta_publica(client, profe, pdf):
    """Una restriccion que el propio sitio se salta por la puerta de todos deja
    de ser una restriccion."""
    DocumentoRestringido.objects.create(documento=pdf)
    client.force_login(profe)

    assert client.get(pdf.url).status_code == 404


def test_el_recorte_sigue_saliendo_cortado_al_rango(client, profe, pdf):
    from pypdf import PdfReader

    DocumentoRestringido.objects.create(documento=pdf)
    recorte = Recorte.objects.create(
        documento=pdf, nombre="Sailing Boat", pagina_desde=10, pagina_hasta=13
    )

    r = client.get(reverse("musica:pdf_del_recorte", args=[recorte.pk]))
    entregado = PdfReader(io.BytesIO(b"".join(r.streaming_content)))

    assert r.status_code == 200
    assert len(entregado.pages) == 4, "se entregan 4 paginas de las 14, no el libro"


def test_el_visor_pide_el_pdf_cortado_cuando_esta_restringido(db, pdf):
    recorte = Recorte.objects.create(
        documento=pdf, nombre="X", pagina_desde=10, pagina_hasta=13
    )
    assert recorte.get_pdf_url() == pdf.url

    DocumentoRestringido.objects.create(documento=pdf)
    recorte.refresh_from_db()

    assert recorte.get_pdf_url() == reverse("musica:pdf_del_recorte", args=[recorte.pk])


def test_el_rango_se_rebasa_a_1_cuando_el_pdf_llega_cortado(db, pdf):
    """El fallo silencioso que esto evita: el PDF cortado empieza en su pagina 1,
    asi que pedir la 10 de un fichero de cuatro paginas ensena el trozo
    equivocado sin dar ningun error."""
    recorte = Recorte.objects.create(
        documento=pdf, nombre="X", pagina_desde=10, pagina_hasta=13
    )
    assert recorte.rango_para_el_visor == (10, 13)

    DocumentoRestringido.objects.create(documento=pdf)
    recorte.refresh_from_db()

    assert recorte.rango_para_el_visor == (1, 4)


def test_un_rango_que_se_sale_del_pdf_no_revienta(client, pdf):
    """Si alguien sustituyo el PDF por uno mas corto, el rango apunta fuera."""
    from pypdf import PdfReader

    recorte = Recorte.objects.create(
        documento=pdf, nombre="X", pagina_desde=90, pagina_hasta=99
    )

    r = client.get(reverse("musica:pdf_del_recorte", args=[recorte.pk]))
    entregado = PdfReader(io.BytesIO(b"".join(r.streaming_content)))

    assert r.status_code == 200
    assert len(entregado.pages) == 1


# === La puerta del recortador ===


def test_el_recortador_ve_el_documento_entero(client, profe, pdf):
    """Para elegir un trozo hay que ver el libro: un recortador que solo ensenara
    los trozos ya recortados no serviria de nada."""
    DocumentoRestringido.objects.create(documento=pdf)
    client.force_login(profe)

    r = client.get(reverse("musica:pdf_para_recortar", args=[pdf.pk]))

    assert r.status_code == 200


def test_un_alumno_no_entra_por_la_puerta_del_recortador(client, alumno, pdf):
    DocumentoRestringido.objects.create(documento=pdf)
    client.force_login(alumno)

    r = client.get(reverse("musica:pdf_para_recortar", args=[pdf.pk]))

    assert r.status_code in (302, 403)


# === Marcar y desmarcar por API ===


def test_marcar_y_desmarcar_la_restriccion(client, profe, pdf):
    client.force_login(profe)

    client.post(
        f"/api/recortes/documento/{pdf.pk}/restriccion",
        data={"restringido": True, "motivo": "metodo comercial"},
        content_type="application/json",
    )
    assert client.get(pdf.url).status_code == 404

    client.post(
        f"/api/recortes/documento/{pdf.pk}/restriccion",
        data={"restringido": False},
        content_type="application/json",
    )
    # Vuelve a la redirección al fichero, que es el camino normal.
    assert client.get(pdf.url).status_code == 302


# === Crear el libro por API ===


@pytest.fixture
def indice(db, raiz):
    from musica.models import MusicLibraryIndexPage

    indice = MusicLibraryIndexPage(title="Indice", slug="indice-musical")
    raiz.add_child(instance=indice)
    indice.save_revision().publish()
    return indice


def test_crear_un_libro_vacio_por_api(client, profe, indice):
    """Sin esto hay que salir al admin en mitad del camino, y montar un metodo
    de cuarenta piezas por API deja de tener sentido."""
    client.force_login(profe)

    r = client.post(
        "/api/recortes/libro",
        data={"titulo": "Piano Adventures Level 1"},
        content_type="application/json",
    )

    assert r.status_code == 200, r.content
    libro = LibroDeEstudioPage.objects.get(pk=r.json()["id"])
    assert libro.get_parent().pk == indice.pk
    assert list(libro.capitulos) == []


def test_el_libro_nuevo_acepta_el_lote_directamente(client, profe, pdf, indice):
    """El flujo entero en dos llamadas: crear el libro y mandarle las piezas."""
    client.force_login(profe)
    libro_id = client.post(
        "/api/recortes/libro",
        data={"titulo": "Metodo"},
        content_type="application/json",
    ).json()["id"]

    r = _lote(client, pdf, [
        {"nombre": "Uno", "pagina_desde": 1},
        {"nombre": "Dos", "pagina_desde": 2},
    ], libro_id=libro_id)

    assert r.json()["total_capitulos"] == 2


def test_no_se_repite_el_slug_en_el_mismo_sitio(client, profe, indice):
    client.force_login(profe)
    client.post(
        "/api/recortes/libro",
        data={"titulo": "Metodo"},
        content_type="application/json",
    )

    r = client.post(
        "/api/recortes/libro",
        data={"titulo": "Metodo"},
        content_type="application/json",
    )

    assert r.status_code == 400
    assert LibroDeEstudioPage.objects.filter(title="Metodo").count() == 1


def test_un_alumno_no_crea_libros(client, alumno, indice):
    client.force_login(alumno)

    r = client.post(
        "/api/recortes/libro",
        data={"titulo": "Mio"},
        content_type="application/json",
    )

    assert r.status_code == 403
    assert LibroDeEstudioPage.objects.count() == 0


# === El servido selectivo: restringir sin penalizar al resto ===


def test_un_documento_normal_se_redirige_al_fichero(client, pdf):
    """Servirlo TODO por Django rompe el salto de la barra en los audios: su
    vista no atiende peticiones por rango. El gancho aparta lo no restringido."""
    r = client.get(pdf.url)

    assert r.status_code == 302
    assert r["Location"] == pdf.file.url


def test_un_documento_restringido_no_se_redirige_a_ninguna_parte(client, pdf):
    DocumentoRestringido.objects.create(documento=pdf)

    r = client.get(pdf.url)

    assert r.status_code == 404
