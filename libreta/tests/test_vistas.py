# ruff: noqa: PT018, PLR2004, RUF001, RUF002, COM812, E501, S101
"""C233–C236, C242, Anti-H: el compositor por HTTP, como lo usa el navegador."""

import pytest
from django.urls import reverse
from wagtail.images.tests.utils import get_test_image_file

from libreta.models import Elemento
from libreta.models import Libreta

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


def titulos(libreta):
    return [e.titulo for e in libreta.elementos_ordenados()]


def test_sin_sesion_se_va_al_login(client, libreta):
    for url in (
        reverse("libreta:index"),
        reverse("libreta:editar", args=[libreta.pk]),
        reverse("libreta:pdf", args=[libreta.pk]),
    ):
        respuesta = client.get(url)
        assert respuesta.status_code == 302
        assert "/accounts/login/" in respuesta["Location"]


def test_la_libreta_de_otro_no_existe(client, libreta, alumno):
    client.force_login(alumno)
    assert client.get(reverse("libreta:editar", args=[libreta.pk])).status_code == 404
    assert client.get(reverse("libreta:pdf", args=[libreta.pk])).status_code == 404
    assert (
        client.post(
            reverse("libreta:anadir", args=[libreta.pk]),
            {"tipo": "texto", "titulo": "x", "texto": "y"},
        ).status_code
        == 404
    )
    assert libreta.elementos.count() == 0


def test_crear_y_listar(cliente, usuario):
    respuesta = cliente.post(
        reverse("libreta:crear"),
        {"titulo": "Mi libreta", "subtitulo": "2º ESO"},
    )
    libreta = Libreta.objects.get(user=usuario)
    assert respuesta["Location"] == reverse("libreta:editar", args=[libreta.pk])
    html = cliente.get(reverse("libreta:index")).content.decode()
    assert "Mi libreta" in html
    assert "2º ESO" in html
    assert "{#" not in html


def test_el_compositor_ofrece_las_plantillas_y_anade_en_posicion(
    cliente,
    libreta,
    plantillas,
):
    _, docs = plantillas
    html = cliente.get(reverse("libreta:editar", args=[libreta.pk])).content.decode()
    assert "{#" not in html
    for d in docs:
        assert f"＋ {d.title}" in html
    anadir = reverse("libreta:anadir", args=[libreta.pk])
    cliente.post(anadir, {"tipo": "documento", "pk": docs[0].pk}, **HX)
    cliente.post(anadir, {"tipo": "documento", "pk": docs[1].pk}, **HX)
    primero = libreta.elementos_ordenados().first()
    respuesta = cliente.post(
        anadir,
        {"tipo": "documento", "pk": docs[2].pk, "posicion": f"tras:{primero.pk}"},
        **HX,
    )
    assert respuesta.status_code == 200
    assert titulos(libreta) == ["Pentagrama", "Guitar diagram", "Guitar tab"]
    parcial = respuesta.content.decode()
    assert 'id="elementos"' in parcial
    assert "hx-swap-oob" in parcial
    assert "Después de «Guitar tab»" in parcial
    assert "{#" not in parcial


def test_sin_htmx_anadir_redirige_al_compositor(cliente, libreta, plantillas):
    _, docs = plantillas
    respuesta = cliente.post(
        reverse("libreta:anadir", args=[libreta.pk]),
        {"tipo": "documento", "pk": docs[0].pk},
    )
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse(
        "libreta:editar",
        args=[libreta.pk],
    )


def test_buscar_en_el_indice_devuelve_paginas_con_sus_pdf(
    cliente,
    libreta,
    indice,
    documento,
):
    from libreta.tests.conftest import pagina_con_pdfs

    pagina_con_pdfs(
        indice,
        "Escalas mayores",
        "escalas",
        [documento("esc.pdf", "ESC", titulo="Escalas PDF")],
    )
    pagina_con_pdfs(
        indice,
        "Ritmos",
        "ritmos",
        [documento("rit.pdf", "RIT", titulo="Ritmos PDF")],
    )
    html = cliente.get(
        reverse("libreta:buscar", args=[libreta.pk]),
        {"q": "escala"},
    ).content.decode()
    assert "Escalas mayores" in html
    assert "＋ Escalas PDF" in html
    assert "Ritmos" not in html
    assert (
        cliente.get(reverse("libreta:buscar", args=[libreta.pk]), {"q": "e"})
        .content.decode()
        .strip()
        == ""
    )


def test_anadir_una_imagen_subida_y_un_texto(cliente, libreta, usuario):
    anadir = reverse("libreta:anadir", args=[libreta.pk])
    fichero = get_test_image_file(filename="teclado.png")
    fichero.name = "teclado.png"
    fichero.seek(0)
    cliente.post(
        anadir,
        {"tipo": "subida", "fichero": fichero, "titulo": "Teclado"},
        **HX,
    )
    cliente.post(
        anadir,
        {
            "tipo": "texto",
            "titulo": "Normas",
            "texto": "Cuida la libreta.\n\nTrae lápiz.",
        },
        **HX,
    )
    imagen, texto = libreta.elementos_ordenados()
    assert imagen.tipo == "imagen"
    assert imagen.imagen.uploaded_by_user == usuario
    assert imagen.titulo == "Teclado"
    assert texto.tipo == "texto"
    assert "lápiz" in texto.texto


def test_una_subida_que_no_es_imagen_no_crea_nada(cliente, libreta):
    from django.core.files.uploadedfile import SimpleUploadedFile

    respuesta = cliente.post(
        reverse("libreta:anadir", args=[libreta.pk]),
        {
            "tipo": "subida",
            "fichero": SimpleUploadedFile("x.txt", b"hola"),
            "titulo": "x",
        },
        **HX,
    )
    assert respuesta.status_code == 200
    assert libreta.elementos.count() == 0
    assert "no es una imagen" in respuesta.content.decode()


def test_copias_titulo_orden_y_borrado_por_elemento(cliente, libreta, documento):
    a = libreta.insertar(Elemento.desde_medio(documento(titulo="A")))
    b = libreta.insertar(Elemento.desde_medio(documento(titulo="B")))
    respuesta = cliente.post(
        reverse("libreta:elemento_guardar", args=[a.pk]),
        {"copias": "12", "titulo": "Pentagrama"},
        **HX,
    )
    a.refresh_from_db()
    assert a.copias == 12
    assert a.titulo == "Pentagrama"
    assert "Pentagrama" in respuesta.content.decode()
    cliente.post(
        reverse("libreta:elemento_mover", args=[b.pk]),
        {"direccion": "arriba"},
        **HX,
    )
    assert titulos(libreta) == ["B", "Pentagrama"]
    cliente.post(reverse("libreta:elemento_borrar", args=[b.pk]), **HX)
    assert titulos(libreta) == ["Pentagrama"]
    assert libreta.elementos_ordenados().first().orden == 1


def test_el_elemento_de_otro_no_se_toca(client, libreta, alumno, documento):
    a = libreta.insertar(Elemento.desde_medio(documento(titulo="A")))
    client.force_login(alumno)
    assert (
        client.post(reverse("libreta:elemento_borrar", args=[a.pk]), **HX).status_code
        == 404
    )
    assert libreta.elementos.count() == 1


def test_ajustes(cliente, libreta):
    cliente.post(
        reverse("libreta:ajustes", args=[libreta.pk]),
        {
            "titulo": "Cuaderno",
            "subtitulo": "1º ESO",
            "indice": "on",
            "primera_pagina": "5",
        },
    )
    libreta.refresh_from_db()
    assert (
        libreta.titulo,
        libreta.subtitulo,
        libreta.portada,
        libreta.indice,
        libreta.primera_pagina,
        libreta.hoja_nueva_por_seccion,
    ) == (
        "Cuaderno",
        "1º ESO",
        False,
        True,
        5,
        False,
    )


def test_el_pdf_y_el_pedido_se_sirven_como_pdf(cliente, libreta, documento):
    libreta.insertar(Elemento.desde_medio(documento(titulo="A")))
    respuesta = cliente.get(reverse("libreta:pdf", args=[libreta.pk]))
    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert respuesta.content.startswith(b"%PDF")
    assert "libreta-de-musica-4o-eso.pdf" in respuesta["Content-Disposition"]
    pedido = cliente.get(reverse("libreta:pedido", args=[libreta.pk]))
    assert pedido.status_code == 200
    assert pedido.content.startswith(b"%PDF")


def test_un_alumno_compone_y_exporta_su_propia_libreta(client, alumno, plantillas):
    from martina_bescos_app.users.permisos import es_profesor

    assert not es_profesor(alumno)
    client.force_login(alumno)
    client.post(reverse("libreta:crear"), {"titulo": "La mía"})
    libreta = Libreta.objects.get(user=alumno)
    _, docs = plantillas
    client.post(
        reverse("libreta:anadir", args=[libreta.pk]),
        {"tipo": "documento", "pk": docs[0].pk},
        **HX,
    )
    respuesta = client.get(reverse("libreta:pdf", args=[libreta.pk]))
    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF")
