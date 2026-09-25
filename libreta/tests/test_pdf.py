# ruff: noqa: PT018, PLR2004, RUF001, RUF002, COM812, E501, S101
"""C237–C241 y Anti-I: lo que sale por la impresora."""

from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import A5
from reportlab.lib.pagesizes import landscape

from libreta.models import Elemento

pytestmark = pytest.mark.django_db

A4_PT = (595, 842)


def paginas_de(pdf_bytes):
    return PdfReader(BytesIO(pdf_bytes)).pages


def tamano(pagina):
    return round(float(pagina.mediabox.width)), round(float(pagina.mediabox.height))


def texto(pagina):
    return " ".join(pagina.extract_text().split())


def test_todas_las_paginas_salen_a4_vertical_aunque_la_fuente_sea_a5_o_apaisada(
    libreta,
    documento,
):
    libreta.portada = libreta.indice = False
    libreta.save()
    libreta.insertar(Elemento.desde_medio(documento("a4.pdf", "A4", 1, A4)))
    libreta.insertar(Elemento.desde_medio(documento("a5.pdf", "A5", 1, A5)))
    libreta.insertar(
        Elemento.desde_medio(
            documento("apaisado.pdf", "APAISADO", 1, landscape((750, 554))),
        ),
    )
    libreta.insertar(Elemento(titulo="Normas", texto="Cuida la libreta."))
    paginas = paginas_de(libreta.pdf())
    assert {tamano(p) for p in paginas} == {A4_PT}
    assert "A5 p1" in texto(paginas[1])  # rótulo y contenido siguen ahí tras escalar


def test_cada_elemento_se_repite_sus_copias_una_pagina_tras_otra(
    libreta,
    documento,
    imagen,
):
    libreta.portada = libreta.indice = libreta.hoja_nueva_por_seccion = False
    libreta.save()
    pdf = libreta.insertar(
        Elemento.desde_medio(documento("dos.pdf", "DOS", 2), titulo="Dos páginas"),
    )
    pdf.copias = 3
    pdf.save()
    foto = libreta.insertar(Elemento.desde_medio(imagen("Teclado")))
    foto.copias = 2
    foto.save()
    paginas = paginas_de(libreta.pdf())
    assert len(paginas) == 8
    origen = ["DOS p1", "DOS p2"] * 3 + ["Teclado"] * 2
    for pagina, esperado in zip(paginas, origen, strict=True):
        assert esperado in texto(pagina)


def test_el_pie_dice_hoja_i_de_n_y_numera_desde_primera_pagina(libreta, documento):
    libreta.portada = libreta.indice = libreta.hoja_nueva_por_seccion = False
    libreta.primera_pagina = 7
    libreta.save()
    e = libreta.insertar(
        Elemento.desde_medio(documento("p.pdf", "PENT"), titulo="Pentagrama"),
    )
    e.copias = 3
    e.save()
    paginas = paginas_de(libreta.pdf())
    assert "Pentagrama · hoja 1 de 3" in texto(paginas[0])
    assert " 7" in texto(paginas[0])
    assert "Pentagrama · hoja 3 de 3" in texto(paginas[2])
    assert " 9" in texto(paginas[2])


def test_portada_e_indice_con_rangos_sobre_la_numeracion_real(libreta, documento):
    libreta.hoja_nueva_por_seccion = False
    libreta.save()
    a = libreta.insertar(
        Elemento.desde_medio(documento("a.pdf", "A"), titulo="Pentagrama"),
    )
    a.copias = 6
    a.save()
    libreta.insertar(Elemento.desde_medio(documento("b.pdf", "B", 2), titulo="Teclado"))
    paginas = paginas_de(libreta.pdf())
    assert len(paginas) == 2 + 6 + 2
    portada, indice = texto(paginas[0]), texto(paginas[1])
    assert "Libreta de música" in portada
    assert "4º ESO" in portada
    assert "IES Martina Bescós" in portada
    assert "Nombre:" in portada
    assert "Clase:" in portada
    assert "Índice" in indice
    assert "Pentagrama" in indice
    assert "3 – 8" in indice
    assert "Teclado" in indice
    assert "9 – 10" in indice
    assert "Pentagrama · hoja 1 de 6" in texto(paginas[2])


def test_sin_portada_ni_indice_el_cuerpo_empieza_en_la_primera_pagina(
    libreta,
    documento,
):
    libreta.portada = libreta.indice = libreta.hoja_nueva_por_seccion = False
    libreta.save()
    libreta.insertar(Elemento.desde_medio(documento("a.pdf", "A"), titulo="Pentagrama"))
    paginas = paginas_de(libreta.pdf())
    assert len(paginas) == 1
    assert "Pentagrama · hoja 1 de 1" in texto(paginas[0])


def test_hoja_nueva_por_seccion_rellena_las_secciones_impares(libreta, documento):
    libreta.portada = libreta.indice = False
    libreta.save()
    a = libreta.insertar(Elemento.desde_medio(documento("a.pdf", "A"), titulo="Impar"))
    a.copias = 3
    a.save()
    b = libreta.insertar(Elemento.desde_medio(documento("b.pdf", "B"), titulo="Par"))
    b.copias = 2
    b.save()
    libreta.hoja_nueva_por_seccion = True
    libreta.save()
    paginas = paginas_de(libreta.pdf())
    assert len(paginas) == 3 + 1 + 2
    assert texto(paginas[3]) == "4"  # la de relleno: sin rótulo, pero numerada
    assert "Par · hoja 1 de 2" in texto(paginas[4])
    assert " 5" in texto(paginas[4])
    libreta.hoja_nueva_por_seccion = False
    libreta.save()
    assert len(paginas_de(libreta.pdf())) == 5


def test_solo_portada_tambien_se_rellena_para_que_el_cuerpo_empiece_en_hoja_nueva(
    libreta,
    documento,
):
    libreta.indice = False
    libreta.hoja_nueva_por_seccion = True
    libreta.save()
    libreta.insertar(Elemento.desde_medio(documento("a.pdf", "A"), titulo="Pentagrama"))
    paginas = paginas_de(libreta.pdf())
    assert len(paginas) == 4  # portada, blanco, hoja, blanco
    assert "Pentagrama · hoja 1 de 1" in texto(paginas[2])
    assert " 3" in texto(paginas[2])


def test_la_hoja_de_pedido_resume_elementos_copias_y_total(libreta, documento, imagen):
    libreta.hoja_nueva_por_seccion = True
    libreta.save()
    a = libreta.insertar(
        Elemento.desde_medio(documento("a.pdf", "A", 2), titulo="Pentagrama"),
    )
    a.copias = 4
    a.save()
    libreta.insertar(Elemento.desde_medio(imagen("Teclado")))
    paginas = paginas_de(libreta.pedido())
    assert len(paginas) == 1
    t = texto(paginas[0])
    assert "Pedido de fotocopias" in t
    assert "Libreta de música 4º ESO" in t
    assert "Pentagrama 4 8" in t
    assert "Teclado 1 1" in t
    assert "Total 9" in t
    assert "doble cara" in t
    assert "lado largo" in t
    assert "libreta-de-musica-4o-eso.pdf" in t
    # 2 de frente + 8 + 1 imagen + 1 relleno = 12 páginas, 6 hojas
    assert "12 páginas: 6 hojas" in t
