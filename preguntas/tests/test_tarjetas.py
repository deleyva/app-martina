import io

from pypdf import PdfReader

from preguntas import aruco, tarjetas


def _diez():
    return [{"id": n, "numero": n, "nombre": f"Tarjeta {n}"} for n in range(1, 11)]


def test_diez_tarjetas_son_cinco_paginas_de_pdf():
    pdf = tarjetas.pdf_tarjetas(_diez())
    assert pdf.startswith(b"%PDF")
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 5


def test_una_sola_tarjeta_es_una_pagina():
    assert len(PdfReader(io.BytesIO(tarjetas.pdf_tarjetas(_diez()[:1]))).pages) == 1


def test_el_marcador_que_va_a_la_tarjeta_se_lee_como_su_id():
    """La imagen que se incrusta en el PDF, con el margen blanco del papel, vuelve con su id y A."""
    import numpy as np

    marcador = aruco.marcador(37, tarjetas.PIXELES_MARCADOR // 4)
    con_margen = np.pad(marcador, 60, constant_values=255)
    [m] = aruco.detectar_en_imagen(con_margen)
    assert (m["id"], m["letra"]) == (37, "A")
