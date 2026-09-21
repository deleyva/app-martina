"""Los falsadores de la reparación del texto enriquecido.

Las formas de aquí **están copiadas de las seis páginas reales que daban 500
en producción** (esqueleto de etiquetas del 2026-09-21, con el texto
sustituido). Probarlo contra HTML inventado habría pasado sin tocar el fallo
real: el caso que rompe no es «una etiqueta sin cerrar», que es lo que uno
inventa, sino una etiqueta de línea bien cerrada envolviendo un bloque.
"""

import pytest

from cms.texto_enriquecido import el_editor_lo_abre, reparar, texto_visible

# El conversor mira la base cuando encuentra un embed, así que sin esto el
# widget levanta «Database access not allowed» y el test lo leería como «el
# editor no lo abre»: un falso positivo justo en la comprobación central.
pytestmark = pytest.mark.django_db

# Las seis formas, tal y como estaban guardadas.
ROTAS = {
    "estilo_sobre_titular": (
        "<ul><li><strong><h2>Aviso importante</h2></strong></li>"
        "<li><strong>Entrada</strong> por el patio<strong>.</strong> Gracias</li></ul>"
        '<p><br/>Más abajo<br/><a href="https://ejemplo.test">el plano</a><br/></p>'
    ),
    "enlace_sobre_parrafo": (
        '<p><br/>Texto<br/><a href="https://ejemplo.test/foto">'
        '<p><a href="https://ejemplo.test/foto">la foto</a></p></a>'
        "<br/>y más texto<br/></p>"
    ),
    "enlace_sobre_parrafo_corto": (
        '<p><a href="https://ejemplo.test/a"><p><a href="https://ejemplo.test/a">x</a></p></a></p>'
        "<p>Segundo párrafo</p>"
    ),
    "estilo_sobre_dos_parrafos": (
        '<p><u><b>Unidad 1</b></u><br/>texto'
        '<b><p><embed embedtype="media" url="https://youtu.be/xyz"/></p><p>pie de vídeo</p></b>'
        "seguimos<br/></p>"
    ),
}

SANAS = {
    "parrafo_normal": "<p>Un párrafo <b>con negrita</b> y un <i>cursiva</i>.</p>",
    "lista": "<ul><li>uno</li><li>dos</li></ul>",
    "enlace_externo": '<p>Ver <a href="https://ejemplo.test">la página</a>.</p>',
    "embed_suelto": '<embed embedtype="media" url="https://youtu.be/xyz"/>',
    "titular": "<h2>Un titular</h2><p>y su texto</p>",
    # Estas dos vienen del mismo Blogspot y ASUSTAN, pero el editor las abre:
    # el estilo no envuelve a ningún bloque. Están aquí para que la
    # reparación no se invente trabajo.
    "estilos_mezclados": (
        "<p><b><u>Título</u></b><b><u><br/></u></b>"
        '<b><a href="https://ejemplo.test">enlace en negrita</a></b><u><br/></u></p>'
    ),
    "parrafo_dentro_de_parrafo": "<p>Arriba<br/><p>dentro uno</p><p>dentro dos</p></p>",
}


@pytest.mark.parametrize("nombre", list(ROTAS))
def test_el_editor_no_puede_abrirlas_antes(nombre):
    """Sin esto, el resto de los tests no prueban nada: si el editor ya las
    abriera, la reparación no tendría de qué salvarlas."""
    assert el_editor_lo_abre(ROTAS[nombre]) is False


@pytest.mark.parametrize("nombre", list(ROTAS))
def test_reparadas_el_editor_las_abre(nombre):
    """El falsador principal, y el mismo que el 500: el widget del editor."""
    assert el_editor_lo_abre(reparar(ROTAS[nombre])) is True


@pytest.mark.parametrize("nombre", list(ROTAS))
def test_la_reparacion_no_se_come_texto(nombre):
    """Reparar no es reescribir: el artículo tiene que decir lo mismo."""
    assert texto_visible(reparar(ROTAS[nombre])) == texto_visible(ROTAS[nombre])


def test_el_estilo_sobrevive_al_empujon():
    """La negrita que alguien puso a propósito no se tira: se mete dentro."""
    reparado = reparar(ROTAS["estilo_sobre_titular"])

    assert "<strong>" in reparado
    assert "<h2><strong>Aviso importante</strong></h2>" in reparado


def test_el_enlace_no_acaba_dentro_de_otro_enlace():
    """Empujar el enlace daría `<a><a>`, que no dibuja igual ningún navegador."""
    reparado = reparar(ROTAS["enlace_sobre_parrafo"])

    assert "<a" in reparado, "el enlace de dentro sigue ahí"
    assert reparado.count("<a ") == 1, "el de fuera se ha ido, no se ha duplicado"
    assert "<a href=\"https://ejemplo.test/foto\"><a" not in reparado


def test_el_embed_no_se_envuelve():
    """Un estilo alrededor de un embed devuelve el mismo fallo por otra puerta."""
    reparado = reparar(ROTAS["estilo_sobre_dos_parrafos"])

    assert "embedtype" in reparado
    assert "<b><embed" not in reparado
    assert "<u><embed" not in reparado


@pytest.mark.parametrize("nombre", list(SANAS))
def test_lo_que_ya_funciona_no_se_toca(nombre):
    """El invariante que hace que esto se pueda lanzar sobre 627 campos: lo que
    el editor ya abre sale byte a byte igual."""
    assert reparar(SANAS[nombre]) == SANAS[nombre]
    assert el_editor_lo_abre(SANAS[nombre]) is True


def test_el_vacio_no_revienta():
    assert reparar("") == ""
    assert reparar(None) is None


# ── El comando, de punta a punta ──────────────────────────────────────────
# Lo que se prueba aquí es lo que el fallo enseñó: que la página de edición
# abre la ÚLTIMA REVISIÓN y no el campo publicado, así que reparar solo el
# campo deja el 500 donde estaba.


@pytest.fixture
def articulo_roto(db):
    from blogs.models import ArticuloPage, BlogIndexPage
    from wagtail.models import Page

    raiz = Page.objects.get(depth=1)
    inicio = raiz.add_child(instance=Page(title="Inicio", slug="inicio-roto"))
    blog = inicio.add_child(
        instance=BlogIndexPage(title="Departamento", slug="departamento-roto")
    )
    articulo = blog.add_child(
        instance=ArticuloPage(
            title="Aviso",
            slug="aviso-roto",
            intro="Un aviso",
            date="2026-09-21",
            body=ROTAS["estilo_sobre_titular"],
        )
    )
    articulo.save_revision()
    return articulo


def _correr(*args):
    from io import StringIO

    from django.core.management import call_command

    salida = StringIO()
    call_command("reparar_texto_enriquecido", *args, stdout=salida)
    return salida.getvalue()


def test_en_seco_no_guarda_nada(articulo_roto):
    """Un comando que escribe por defecto se ejecuta una vez sin querer."""
    salida = _correr("--pk", str(articulo_roto.pk))

    articulo_roto.refresh_from_db()
    assert "EN SECO" in salida
    assert el_editor_lo_abre(articulo_roto.body) is False


def test_repara_el_campo_y_la_revision(articulo_roto):
    """El falsador del fallo real: si solo se arregla el campo, el editor —que
    abre la última revisión— sigue dando 500."""
    _correr("--pk", str(articulo_roto.pk), "--escribir")

    articulo_roto.refresh_from_db()
    revision = articulo_roto.get_latest_revision()

    assert el_editor_lo_abre(articulo_roto.body) is True, "el campo publicado"
    assert el_editor_lo_abre(revision.content["body"]) is True, "la última revisión"
    assert texto_visible(articulo_roto.body) == texto_visible(ROTAS["estilo_sobre_titular"])


def test_no_toca_lo_sano(db):
    """627 campos revisados y solo se escriben los rotos."""
    from blogs.models import ArticuloPage, BlogIndexPage
    from wagtail.models import Page

    raiz = Page.objects.get(depth=1)
    inicio = raiz.add_child(instance=Page(title="Inicio", slug="inicio-sano"))
    blog = inicio.add_child(instance=BlogIndexPage(title="Depto", slug="depto-sano"))
    sano = blog.add_child(
        instance=ArticuloPage(
            title="Bien",
            slug="bien",
            intro="Va bien",
            date="2026-09-21",
            body=SANAS["parrafo_normal"],
        )
    )
    sano.save_revision()
    antes = sano.body

    salida = _correr("--pk", str(sano.pk), "--escribir")

    sano.refresh_from_db()
    assert sano.body == antes
    assert "Páginas con algo que arreglar: 0" in salida
