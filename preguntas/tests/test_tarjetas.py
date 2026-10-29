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


# =============================================================================
# C550 — Juego genérico y pegatinas del dorso
# =============================================================================


def _pegatinas(n):
    return [{"numero": i, "lineas": [f"3-FH: Alumno {i}", f"3-EA: Alumna {i}"]} for i in range(1, n + 1)]


def test_veintisiete_pegatinas_son_una_hoja_y_veintiocho_dos():
    assert len(PdfReader(io.BytesIO(tarjetas.pdf_pegatinas(_pegatinas(27)))).pages) == 1
    assert len(PdfReader(io.BytesIO(tarjetas.pdf_pegatinas(_pegatinas(28)))).pages) == 2


def test_cada_pegatina_lleva_su_numero_y_una_linea_por_grupo():
    texto = PdfReader(io.BytesIO(tarjetas.pdf_pegatinas(_pegatinas(7)))).pages[0].extract_text()
    assert "3-FH: Alumno 7" in texto and "3-EA: Alumna 7" in texto
    assert "3-FH: Alumno 8" not in texto


def test_una_pegatina_con_seis_grupos_y_nombres_largos_no_rompe():
    largas = [{"numero": 23, "lineas": [f"3-ESO-BIL-{g}: Nombre Apellido Apellidolargo {g}" for g in range(6)]}]
    pdf = tarjetas.pdf_pegatinas(largas)
    assert pdf.startswith(b"%PDF") and len(PdfReader(io.BytesIO(pdf)).pages) == 1


def test_la_tarjeta_generica_no_lleva_nombre():
    texto = PdfReader(io.BytesIO(tarjetas.pdf_tarjetas([{"id": 5, "numero": 5, "nombre": ""}]))).pages[0].extract_text()
    assert "5" in texto and "Levanta la tarjeta" in texto
    assert "Tarjeta" not in texto
