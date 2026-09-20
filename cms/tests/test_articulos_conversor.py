"""El conversor de Markdown a RichText: énfasis anidado y etiquetas cerradas.

**Por qué existe este fichero.** El 2026-09-20 se publicó una unidad que se veía
perfecta y que reventaba el editor de Wagtail con
`AssertionError: Unmatched tags: expected i, got b` al abrirla. La causa era
`**texto *en cursiva* texto**`: el conversor cerraba la negrita antes que la
cursiva y producía HTML cruzado. Se publica bien y no se puede editar, que es la
peor forma de fallar, porque nadie se entera hasta que alguien va a corregir una
errata.

El test que de verdad importa es `test_no_hay_etiquetas_cruzadas`: no comprueba
una cadena concreta, comprueba el invariante —que las etiquetas cierran en el
orden en que abren— sobre todas las combinaciones de énfasis que sabemos
escribir.
"""

from html.parser import HTMLParser

import pytest

from musica.articulos import _en_linea, markdown_a_richtext


class _Apilador(HTMLParser):
    """Falla si una etiqueta cierra fuera de orden. Es lo que hace Draftail."""

    def __init__(self):
        super().__init__()
        self.pila = []
        self.errores = []

    def handle_starttag(self, tag, attrs):
        if tag not in ("embed", "br"):
            self.pila.append(tag)

    def handle_endtag(self, tag):
        if not self.pila:
            self.errores.append(f"cierra {tag} sin abrir")
        elif self.pila[-1] != tag:
            self.errores.append(f"esperaba {self.pila[-1]}, llegó {tag}")
        else:
            self.pila.pop()


def _cruzadas(html):
    p = _Apilador()
    p.feed(html)
    return p.errores + [f"sin cerrar: {t}" for t in p.pila]


def test_negrita_sola():
    assert _en_linea("**hola**") == "<b>hola</b>"


def test_cursiva_sola():
    assert _en_linea("*hola*") == "<i>hola</i>"


def test_cursiva_dentro_de_negrita():
    """El caso que rompía el editor."""
    assert (
        _en_linea("**Durante la escucha de *Blinding Lights***")
        == "<b>Durante la escucha de <i>Blinding Lights</i></b>"
    )


def test_cursiva_en_medio_de_una_negrita():
    assert (
        _en_linea("**While *We Will Rock You* plays**")
        == "<b>While <i>We Will Rock You</i> plays</b>"
    )


def test_dos_negritas_en_la_misma_linea():
    assert _en_linea("**uno** y **dos**") == "<b>uno</b> y <b>dos</b>"


def test_el_asterisco_dentro_de_una_palabra_no_es_cursiva():
    assert _en_linea("4*4 no es cursiva") == "4*4 no es cursiva"


def test_se_escapa_el_html_de_entrada():
    assert _en_linea("<script>") == "&lt;script&gt;"


@pytest.mark.parametrize(
    "fuente",
    [
        "**Durante la escucha de *Blinding Lights***",
        "**While *We Will Rock You* plays**",
        "***todo a la vez***",
        "**negrita** y *cursiva* sueltas",
        "*cursiva con **negrita** dentro*",
        "**a *b* c *d* e**",
        "texto sin ningún énfasis",
    ],
)
def test_no_hay_etiquetas_cruzadas(fuente):
    assert _cruzadas(_en_linea(fuente)) == []


def test_el_parrafo_entero_tambien_cierra_bien():
    md = "- **Durante la escucha de *Blinding Lights***: levanta la mano.\n"
    assert _cruzadas(markdown_a_richtext(md)) == []


# --- Enlaces (2026-09-20) -------------------------------------------------
#
# Las unidades de historia enlazan a los artículos de canción: el profesor da
# la teoría y salta a la canción dentro de la misma sesión. Sin esto, un
# `[texto](url)` salía literal en la página, con los corchetes puestos.


def test_enlace_externo():
    assert (
        _en_linea("[la ficha](https://jamzone.musicwill.org/songs/x)")
        == '<a href="https://jamzone.musicwill.org/songs/x">la ficha</a>'
    )


def test_enlace_a_una_pagina_del_sitio():
    """`page:875` usa el linktype de Wagtail, que rehace la URL si la página se
    mueve o le cambian el slug. Un href absoluto no sobrevive a eso."""
    assert (
        _en_linea("[Blinding Lights](page:875)")
        == '<a linktype="page" id="875">Blinding Lights</a>'
    )


def test_el_enlace_convive_con_la_negrita():
    assert (
        _en_linea("**[Blinding Lights](page:875)**")
        == '<b><a linktype="page" id="875">Blinding Lights</a></b>'
    )


def test_lo_que_no_es_un_enlace_se_queda_como_esta():
    assert _en_linea("[esto no] (es un enlace)") == "[esto no] (es un enlace)"


def test_un_enlace_no_deja_etiquetas_cruzadas():
    assert _cruzadas(_en_linea("**Toca [esta canción](page:875) hoy**")) == []
