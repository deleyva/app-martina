# ruff: noqa: PT018, PLR2004, RUF001, RUF002, COM812, E501, S101
"""C232, C236: un elemento es exactamente una cosa; el orden se mantiene solo."""

import pytest
from django.core.exceptions import ValidationError
from django.http import Http404

from libreta.models import Elemento
from libreta.models import Libreta

pytestmark = pytest.mark.django_db


def titulos(libreta):
    return [e.titulo for e in libreta.elementos_ordenados()]


def ordenes(libreta):
    return [e.orden for e in libreta.elementos_ordenados()]


def test_un_elemento_con_dos_contenidos_o_ninguno_no_se_guarda(
    libreta,
    documento,
    imagen,
):
    with pytest.raises(ValidationError):
        libreta.insertar(Elemento(titulo="Nada"))
    with pytest.raises(ValidationError):
        libreta.insertar(Elemento(titulo="Dos", documento=documento(), imagen=imagen()))
    assert libreta.elementos.count() == 0


def test_solo_se_aceptan_documentos_pdf(libreta, db):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from wagtail.documents.models import Document
    from wagtail.models import Collection

    if not Collection.objects.exists():
        Collection.add_root(name="Root")
    audio = Document.objects.create(
        title="Audio",
        file=SimpleUploadedFile("a.mp3", b"no-es-pdf"),
    )
    with pytest.raises(ValidationError):
        libreta.insertar(Elemento.desde_medio(audio))


def test_insertar_al_final_al_principio_y_tras_otro(libreta, documento):
    a = libreta.insertar(Elemento.desde_medio(documento(titulo="A")))
    libreta.insertar(Elemento.desde_medio(documento(titulo="B")))
    libreta.insertar(Elemento.desde_medio(documento(titulo="C")), "inicio")
    libreta.insertar(Elemento.desde_medio(documento(titulo="D")), f"tras:{a.pk}")
    libreta.insertar(
        Elemento.desde_medio(documento(titulo="E")),
        "tras:999999",
    )  # pk ajeno → al final
    assert titulos(libreta) == ["C", "A", "D", "B", "E"]
    assert ordenes(libreta) == [1, 2, 3, 4, 5]


def test_mover_intercambia_con_el_vecino_y_los_extremos_no_se_mueven(
    libreta,
    documento,
):
    a = libreta.insertar(Elemento.desde_medio(documento(titulo="A")))
    b = libreta.insertar(Elemento.desde_medio(documento(titulo="B")))
    libreta.insertar(Elemento.desde_medio(documento(titulo="C")))
    a.mover("arriba")
    assert titulos(libreta) == ["A", "B", "C"]
    b.mover("abajo")
    assert titulos(libreta) == ["A", "C", "B"]
    b.mover("abajo")
    assert titulos(libreta) == ["A", "C", "B"]


def test_borrar_renumera(libreta, documento):
    libreta.insertar(Elemento.desde_medio(documento(titulo="A")))
    b = libreta.insertar(Elemento.desde_medio(documento(titulo="B")))
    libreta.insertar(Elemento.desde_medio(documento(titulo="C")))
    b.borrar()
    assert titulos(libreta) == ["A", "C"]
    assert ordenes(libreta) == [1, 2]


def test_las_paginas_son_copias_por_paginas_del_pdf(libreta, documento, imagen):
    pdf = libreta.insertar(Elemento.desde_medio(documento(paginas=2)))
    pdf.copias = 3
    pdf.save()
    foto = libreta.insertar(Elemento.desde_medio(imagen()))
    foto.copias = 2
    foto.save()
    libreta.insertar(Elemento(titulo="Normas", texto="Cuida la libreta."))
    assert pdf.paginas() == 6
    assert foto.paginas() == 2
    assert libreta.total_hojas() == 9


def test_la_libreta_de_otro_da_404(libreta, db):
    from martina_bescos_app.users.tests.factories import UserFactory

    otro = UserFactory(is_staff=False)
    with pytest.raises(Http404):
        Libreta.del_usuario(otro, libreta.pk)
    assert Libreta.del_usuario(libreta.user, libreta.pk) == libreta
