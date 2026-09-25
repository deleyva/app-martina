"""El clasificador de medios: un cajón por tipo, y el dict siempre completo.

Estas pruebas no tocan la base de datos a propósito. `clasificar` solo mira el
nombre del fichero y el nombre del modelo, así que un objeto de mentira basta y
la batería sigue siendo instantánea.

Existen porque el fallo que arreglaron era invisible: un `.gp` no encajaba en
ninguna rama y la tablatura desaparecía en mitad de una clase sin una sola
excepción en los logs.
"""

import pytest

from my_library import medios


class _Fichero:
    def __init__(self, name):
        self.name = name


class _Documento:
    def __init__(self, name):
        self.file = _Fichero(name)


@pytest.mark.parametrize(
    "nombre, clave",
    [
        ("partituras/rise.gp", "gp_files"),
        ("partituras/rise.gp3", "gp_files"),
        ("partituras/rise.gp4", "gp_files"),
        ("partituras/rise.gp5", "gp_files"),
        ("partituras/rise.gpx", "gp_files"),
        ("partituras/RISE.GP5", "gp_files"),
        ("metodos/aerobics.pdf", "pdfs"),
        ("audios/lectura.mp3", "audios"),
        ("audios/lectura.m4a", "audios"),
    ],
)
def test_un_documento_va_a_su_cajon_por_la_extension(nombre, clave):
    documentos = medios.clasificar(_Documento(nombre), "document")

    assert documentos[clave] and documentos[clave][0].file.name == nombre
    assert sum(len(v) for v in documentos.values()) == 1


def test_una_tablatura_no_cae_en_el_visor_de_pdf():
    """El fallo exacto del 2026-09-22: `.gp` sin rama propia acababa en el
    «No se encontró contenido para visualizar» de la pantalla de clase."""
    documentos = medios.clasificar(_Documento("rise.gp5"), "document")

    assert documentos["gp_files"]
    assert documentos["pdfs"] == []


def test_un_documento_con_extension_rara_se_intenta_como_pdf():
    """Mejor un visor que enseña un error legible que una pantalla en blanco."""
    documentos = medios.clasificar(_Documento("apuntes.mscz"), "document")

    assert documentos["pdfs"]


@pytest.mark.parametrize(
    "modelo, clave",
    [
        ("image", "images"),
        ("embed", "embeds"),
        ("recorte", "recortes"),
        ("enlaceexterno", "enlaces"),
        ("externalresource", "external_links"),
    ],
)
def test_cada_modelo_tiene_su_cajon(modelo, clave):
    objeto = object()

    documentos = medios.clasificar(objeto, modelo)

    assert documentos[clave] == [objeto]


def test_el_dict_trae_siempre_todas_las_claves():
    """Es la invariante que impide que vuelva a pasar: en una plantilla de
    Django una clave que falta y una clave vacía se comportan igual."""
    for documentos in (
        medios.clasificar(None),
        medios.clasificar(object(), "modeloquenoexiste"),
        medios.clasificar(_Documento("x.pdf"), "document"),
    ):
        assert set(documentos) == set(medios.CLAVES)


def test_una_pagina_no_es_un_medio():
    """`ScorePage` y `RecursoPage` son contenedores: sus bloques los extrae la
    vista que los necesita, no este módulo."""
    documentos = medios.clasificar(object(), "scorepage")

    assert all(v == [] for v in documentos.values())


def test_la_letra_con_acordes_tiene_cajon_propio():
    """`LetraConAcordes` va a `chordpro`, no a ninguno de los visores de fichero."""
    letra = object()
    documentos = medios.clasificar(letra, "letraconacordes")

    assert documentos["chordpro"] == [letra]
    assert sum(len(v) for v in documentos.values()) == 1
