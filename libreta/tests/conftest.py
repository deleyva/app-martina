# ruff: noqa: PT018, PLR2004, RUF001, RUF002, COM812, E501, S101
"""Fixtures de la libreta. Los PDF de prueba se generan aquí con ReportLab
(A4, A5 y apaisado) para no depender de nada de `media/`."""

import json
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import A5
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from wagtail.documents.models import Document
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection
from wagtail.models import Locale
from wagtail.models import Page

from martina_bescos_app.users.tests.factories import UserFactory


def pdf_de_prueba(etiqueta="DOC", paginas=1, tamano=A4) -> bytes:
    buffer = BytesIO()
    lienzo = canvas.Canvas(buffer, pagesize=tamano)
    for i in range(1, paginas + 1):
        lienzo.setFont("Helvetica", 14)
        lienzo.drawString(50, tamano[1] - 60, f"{etiqueta} p{i}")
        lienzo.showPage()
    lienzo.save()
    return buffer.getvalue()


@pytest.fixture
def documento(db):
    if not Collection.objects.exists():
        Collection.add_root(name="Root")

    def _crear(nombre="doc.pdf", etiqueta="DOC", paginas=1, tamano=A4, titulo=None):
        return Document.objects.create(
            title=titulo or nombre,
            file=SimpleUploadedFile(nombre, pdf_de_prueba(etiqueta, paginas, tamano)),
        )

    return _crear


@pytest.fixture
def imagen(db):
    from wagtail.images import get_image_model

    def _crear(titulo="Foto"):
        return get_image_model().objects.create(
            title=titulo,
            file=get_test_image_file(filename=f"{titulo}.png"),
        )

    return _crear


@pytest.fixture
def usuario(db):
    return UserFactory()


@pytest.fixture
def alumno(db):
    """Un usuario sin `is_staff`, sin grupo Profesorado y sin grupos donde dé clase."""
    return UserFactory(is_staff=False)


@pytest.fixture
def cliente(client, usuario):
    client.force_login(usuario)
    return client


@pytest.fixture
def libreta(usuario):
    from libreta.models import Libreta

    return Libreta.objects.create(
        user=usuario,
        titulo="Libreta de música",
        subtitulo="4º ESO",
    )


@pytest.fixture
def raiz(db):
    from django.conf import settings

    if not Locale.objects.exists():
        Locale.objects.create(language_code=settings.LANGUAGE_CODE.split("-")[0])
    return Page.objects.filter(depth=1).first() or Page.add_root(
        title="Root",
        slug="root",
    )


@pytest.fixture
def indice(raiz):
    from musica.models import MusicLibraryIndexPage

    pagina = MusicLibraryIndexPage(
        title="Índice de recursos musicales",
        slug="indice-de-recursos-musicales",
        intro="",
    )
    raiz.add_child(instance=pagina)
    return pagina


def pagina_con_pdfs(indice, titulo, slug, documentos):
    from musica.models import ScorePage

    pagina = ScorePage(
        title=titulo,
        slug=slug,
        content=json.dumps(
            [
                {
                    "type": "pdf_score",
                    "value": {
                        "title": d.title,
                        "pdf_file": d.pk,
                        "description": "",
                        "page_count": None,
                    },
                }
                for d in documentos
            ],
        ),
    )
    indice.add_child(instance=pagina)
    return pagina


@pytest.fixture
def plantillas(indice, documento):
    """La página `plantillas-para-escribir` con tres PDF de tamaños distintos."""
    docs = [
        documento("no-clef-12.pdf", "PENTAGRAMA", 1, A4, titulo="Pentagrama"),
        documento("guitar-tab.pdf", "TAB", 1, A5, titulo="Guitar tab"),
        documento(
            "guitar-diagram-horizontal.pdf",
            "DIAGRAMA",
            1,
            landscape((750, 554)),
            titulo="Guitar diagram",
        ),
    ]
    return pagina_con_pdfs(
        indice,
        "Plantillas para escribir",
        "plantillas-para-escribir",
        docs,
    ), docs
