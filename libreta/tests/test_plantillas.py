# ruff: noqa: PT018, PLR2004, RUF001, RUF002, COM812, E501, S101
"""C245–C247 y Anti-K: las hojas A4 generadas en código."""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from libreta import plantillas
from libreta.models import Elemento

HX = {"HTTP_HX_REQUEST": "true"}


def pagina_de(clave):
    buffer = BytesIO()
    lienzo = canvas.Canvas(buffer, pagesize=A4)
    plantillas.dibujar(clave, lienzo)
    lienzo.showPage()
    lienzo.save()
    return PdfReader(BytesIO(buffer.getvalue())).pages[0]


def test_hay_diez_hojas_y_todas_dibujan_algo_en_a4_sin_texto_dentro():
    assert len(plantillas.HOJAS) == 10
    for clave in plantillas.HOJAS:
        pagina = pagina_de(clave)
        assert (
            round(float(pagina.mediabox.width)),
            round(float(pagina.mediabox.height)),
        ) == (595, 842)
        assert len(pagina.get_contents().get_data()) > 500, clave
        # Anti-K: ni cabecera ni número dentro; las letras T A B de las tablaturas son lo único
        assert (
            pagina.extract_text()
            .replace("T", "")
            .replace("A", "")
            .replace("B", "")
            .strip()
            == ""
        ), clave


def test_las_claves_del_piano_estan_en_el_repo():
    assert plantillas.CLAVES_PIANO.exists()


@pytest.mark.django_db
def test_un_elemento_plantilla_es_una_pagina_por_copia(libreta):
    e = libreta.insertar(Elemento.desde_plantilla("acordes_ukelele_v"))
    assert (
        e.tipo == "plantilla" and e.titulo == "Acordes de ukelele" and e.paginas() == 1
    )
    e.copias = 4
    e.save()
    assert e.paginas() == 4
    with pytest.raises(ValidationError):
        Elemento.desde_plantilla("no-existe")
    with pytest.raises(ValidationError):
        libreta.insertar(
            Elemento(titulo="dos", plantilla="pentagrama", texto="y texto")
        )


@pytest.mark.django_db
def test_el_pdf_de_la_libreta_incluye_la_hoja_generada_con_su_pie(libreta):
    libreta.portada = libreta.indice = libreta.hoja_nueva_por_seccion = False
    libreta.save()
    e = libreta.insertar(Elemento.desde_plantilla("pentagrama"))
    e.copias = 2
    e.save()
    paginas = PdfReader(BytesIO(libreta.pdf())).pages
    assert len(paginas) == 2
    assert "Pentagrama · hoja 2 de 2" in " ".join(paginas[1].extract_text().split())


@pytest.mark.django_db
def test_el_compositor_ofrece_las_hojas_generadas_y_las_anade(cliente, libreta):
    html = cliente.get(reverse("libreta:editar", args=[libreta.pk])).content.decode()
    assert "Para imprimir (A4)" in html and "＋ Acordes de ukelele (horizontal)" in html
    assert html.index("Para imprimir (A4)") < html.index("Del CMS")
    respuesta = cliente.post(
        reverse("libreta:anadir", args=[libreta.pk]),
        {"tipo": "plantilla", "clave": "teclados"},
        **HX,
    )
    assert respuesta.status_code == 200
    assert [e.titulo for e in libreta.elementos_ordenados()] == ["Teclados"]
    respuesta = cliente.post(
        reverse("libreta:anadir", args=[libreta.pk]),
        {"tipo": "plantilla", "clave": "nada"},
        **HX,
    )
    assert (
        "No existe esa plantilla" in respuesta.content.decode()
        and libreta.elementos.count() == 1
    )
