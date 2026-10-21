"""Vídeos de YouTube citados en un segundo concreto.

**Por qué existe este fichero.** Una unidad de historia cita el mismo vídeo
largo varias veces, cada una donde empieza lo que interesa. Hasta el 2026-10-21
el conversor cortaba el `&t=` de la URL y el oEmbed de YouTube devolvía el
iframe sin inicio: todos los reproductores arrancaban en 0:00 y nadie se
enteraba, porque la página se veía bien.
"""

from unittest import mock

import pytest

from cms.embed_finders import YouTubeInicioEmbedFinder, segundos_de_inicio
from musica.articulos import markdown_a_richtext


@pytest.mark.parametrize(
    "url,esperado",
    [
        ("https://www.youtube.com/watch?v=abc&t=95", 95),
        ("https://www.youtube.com/watch?v=abc&t=95s", 95),
        ("https://www.youtube.com/watch?v=abc&t=1m35s", 95),
        ("https://youtu.be/abc?t=1h2m3s", 3723),
        ("https://www.youtube.com/watch?v=abc&start=40", 40),
        ("https://www.youtube.com/watch?v=abc", None),
    ],
)
def test_segundos_de_inicio(url, esperado):
    assert segundos_de_inicio(url) == esperado


def test_el_conversor_conserva_el_inicio():
    html = markdown_a_richtext("El organum, desde aquí — https://www.youtube.com/watch?v=abc123&t=205")
    assert 'url="https://www.youtube.com/watch?v=abc123&amp;t=205"' in html


def test_el_conversor_sin_inicio_no_cambia():
    html = markdown_a_richtext("Videoclip — https://www.youtube.com/watch?v=abc123")
    assert 'url="https://www.youtube.com/watch?v=abc123"' in html


def test_el_finder_solo_acepta_youtube_con_inicio():
    finder = YouTubeInicioEmbedFinder()
    assert finder.accept("https://www.youtube.com/watch?v=abc&t=95")
    assert not finder.accept("https://www.youtube.com/watch?v=abc")
    assert not finder.accept("https://vimeo.com/123?t=95")


def test_el_iframe_arranca_en_el_segundo_pedido():
    finder = YouTubeInicioEmbedFinder()
    oembed = {"html": '<iframe src="https://www.youtube.com/embed/abc?feature=oembed"></iframe>'}
    with mock.patch("wagtail.embeds.finders.oembed.OEmbedFinder.find_embed", return_value=oembed):
        datos = finder.find_embed("https://www.youtube.com/watch?v=abc&t=1m35s")
    assert 'src="https://www.youtube.com/embed/abc?feature=oembed&start=95"' in datos["html"]


def test_no_repite_el_inicio_si_youtube_ya_lo_trae():
    finder = YouTubeInicioEmbedFinder()
    oembed = {"html": '<iframe src="https://www.youtube.com/embed/abc?start=95&feature=oembed"></iframe>'}
    with mock.patch("wagtail.embeds.finders.oembed.OEmbedFinder.find_embed", return_value=oembed):
        datos = finder.find_embed("https://www.youtube.com/watch?v=abc&t=95")
    assert datos["html"].count("start=") == 1
