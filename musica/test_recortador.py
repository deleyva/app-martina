"""Tests de la pantalla de recorte.

Lo que se prueba aqui es el servidor: permisos, validacion y colocacion. El
dibujo del rectangulo es JavaScript y se verifica en navegador; lo que si entra
en estos tests es que el formulario acepte las coordenadas que el dibujo escribe.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from wagtail.documents.models import Document
from wagtail.models import Page

from musica.models import LibroDeEstudioPage, Recorte, RecursoPage

User = get_user_model()


@pytest.fixture
def profe(db):
    return User.objects.create_user(email="profe@ej.org", password="x", is_staff=True)


@pytest.fixture
def alumno(db):
    return User.objects.create_user(email="alumno@ej.org", password="x")


@pytest.fixture
def raiz(db):
    from django.conf import settings as dj
    from wagtail.models import Locale

    if not Locale.objects.exists():
        Locale.objects.create(language_code=dj.LANGUAGE_CODE.split("-")[0])
    return Page.objects.filter(depth=1).first() or Page.add_root(title="Root", slug="root")


@pytest.fixture
def pdf(db):
    from wagtail.models import Collection

    if not Collection.objects.exists():
        Collection.add_root(name="Root")
    return Document.objects.create(
        title="Piano Adventures",
        file=SimpleUploadedFile("metodo.pdf", b"%PDF-1.4 falso"),
    )


def _crear(client, pdf, **campos):
    datos = {"nombre": "Sailing Boat", "pagina_desde": "10", "destino": "suelto"}
    datos.update(campos)
    return client.post(reverse("musica:crear_recorte", args=[pdf.pk]), datos)


# === Quien entra ===


def test_un_alumno_no_puede_recortar(client, alumno, pdf):
    """La pantalla crea contenido publicado: no es del alumnado."""
    client.force_login(alumno)

    r = client.get(reverse("musica:recortador", args=[pdf.pk]))

    assert r.status_code in (302, 403)


def test_sin_sesion_manda_al_login(client, pdf):
    r = client.get(reverse("musica:recortador", args=[pdf.pk]))

    assert r.status_code == 302
    assert "/accounts/login/" in r["Location"]


def test_un_profesor_abre_la_pantalla(client, profe, pdf):
    client.force_login(profe)

    r = client.get(reverse("musica:recortador", args=[pdf.pk]))
    html = r.content.decode()

    assert r.status_code == 200
    assert "recortador-canvas" in html
    assert "{#" not in html, "comentario de Django pintado en la pagina"


def test_no_se_recorta_lo_que_no_es_un_pdf(client, profe, db):
    """Un mp3 no tiene paginas: recortarlo daria un recorte impintable."""
    audio = Document.objects.create(
        title="Pista", file=SimpleUploadedFile("pista.mp3", b"id3")
    )
    client.force_login(profe)

    r = client.get(reverse("musica:recortador", args=[audio.pk]))

    assert r.status_code == 404


# === Crear ===


def test_crear_un_recorte_de_pagina_entera(client, profe, pdf):
    client.force_login(profe)

    _crear(client, pdf, pagina_hasta="13")
    recorte = Recorte.objects.get()

    assert recorte.nombre == "Sailing Boat"
    assert recorte.rango_paginas == (10, 13)
    assert recorte.rect is None


def test_crear_un_recorte_con_recuadro(client, profe, pdf):
    """Las coordenadas llegan como las escribe el dibujo: normalizadas 0..1."""
    client.force_login(profe)

    _crear(
        client, pdf,
        rect_x0="0.000000", rect_y0="0.331000",
        rect_x1="1.000000", rect_y1="0.662000",
    )
    recorte = Recorte.objects.get()

    assert recorte.tiene_rect
    assert recorte.rect == (0.0, 0.331, 1.0, 0.662)


def test_un_recorte_sin_nombre_no_se_crea(client, profe, pdf):
    """El nombre es por lo que se busca luego: sin el, el recorte no sirve."""
    client.force_login(profe)

    r = _crear(client, pdf, nombre="   ")

    assert Recorte.objects.count() == 0
    assert "nombre" in r.content.decode().lower()


def test_un_rango_al_reves_se_rechaza_con_mensaje(client, profe, pdf):
    """Y en la misma pantalla: perder el sitio es perder el trabajo hecho."""
    client.force_login(profe)

    r = _crear(client, pdf, pagina_desde="13", pagina_hasta="10")

    assert Recorte.objects.count() == 0
    assert r.status_code == 200
    assert "alert-error" in r.content.decode()


def test_medio_rectangulo_se_rechaza(client, profe, pdf):
    client.force_login(profe)

    r = _crear(client, pdf, rect_x0="0.1", rect_y0="0.2")

    assert Recorte.objects.count() == 0
    assert "alert-error" in r.content.decode()


# === Donde va ===


def test_destino_libro_lo_anade_como_capitulo(client, profe, pdf, raiz):
    """El caso que abre la fase: montar el libro desde la pantalla."""
    libro = LibroDeEstudioPage(title="Piano Adventures", slug="pa", capitulos=[])
    raiz.add_child(instance=libro)
    libro.save_revision().publish()
    client.force_login(profe)

    _crear(client, pdf, destino="libro", destino_id=str(libro.pk))

    libro.refresh_from_db()
    bloques = list(libro.capitulos)
    assert [b.block_type for b in bloques] == ["recorte"]
    assert bloques[0].value.nombre == "Sailing Boat"


def test_destino_capitulo_lo_adjunta_a_la_pagina(client, profe, pdf, raiz):
    pagina = RecursoPage(
        title="Tema 1", slug="tema-1", date="2026-09-16", intro="x", attachments=[]
    )
    raiz.add_child(instance=pagina)
    pagina.save_revision().publish()
    client.force_login(profe)

    _crear(client, pdf, destino="capitulo", destino_id=str(pagina.pk))

    pagina.refresh_from_db()
    assert [b.block_type for b in pagina.attachments] == ["recorte"]
    assert pagina.get_recortes()[0].nombre == "Sailing Boat"


def test_destino_suelto_no_engancha_a_nada(client, profe, pdf, raiz):
    libro = LibroDeEstudioPage(title="Vacio", slug="vacio", capitulos=[])
    raiz.add_child(instance=libro)
    libro.save_revision().publish()
    client.force_login(profe)

    _crear(client, pdf, destino="suelto")

    libro.refresh_from_db()
    assert Recorte.objects.count() == 1
    assert len(list(libro.capitulos)) == 0


def test_un_libro_borrado_no_pierde_el_recorte(client, profe, pdf):
    """El recorte se guarda ANTES de colocarlo: si el destino ya no existe, el
    trabajo de dibujarlo no se tira."""
    client.force_login(profe)

    r = _crear(client, pdf, destino="libro", destino_id="999999")

    assert Recorte.objects.count() == 1
    assert "ya no existe" in r.content.decode()


# === Borrar ===


def test_borrar_un_recorte_no_toca_el_pdf(client, profe, pdf):
    client.force_login(profe)
    _crear(client, pdf)
    recorte = Recorte.objects.get()

    client.post(reverse("musica:borrar_recorte", args=[recorte.pk]))

    assert Recorte.objects.count() == 0
    assert Document.objects.filter(pk=pdf.pk).exists()


def test_un_alumno_no_puede_borrar(client, alumno, profe, pdf):
    client.force_login(profe)
    _crear(client, pdf)
    recorte = Recorte.objects.get()
    client.force_login(alumno)

    client.post(reverse("musica:borrar_recorte", args=[recorte.pk]))

    assert Recorte.objects.count() == 1


def test_la_lista_se_puede_pedir_suelta(client, profe, pdf):
    """Es el parcial que HTMX intercambia."""
    client.force_login(profe)
    _crear(client, pdf)

    html = client.get(
        reverse("musica:lista_de_recortes", args=[pdf.pk])
    ).content.decode()

    assert "Sailing Boat" in html
    assert "{#" not in html


# === El flujo de importacion completo, sin admin de Wagtail ===


@pytest.fixture
def indice(db, raiz):
    from musica.models import MusicLibraryIndexPage

    indice = MusicLibraryIndexPage(title="Indice", slug="indice-musical")
    raiz.add_child(instance=indice)
    indice.save_revision().publish()
    return indice


def _libro(raiz, titulo="Metodo", slug="metodo", bloques=None):
    libro = LibroDeEstudioPage(title=titulo, slug=slug, capitulos=bloques or [])
    raiz.add_child(instance=libro)
    libro.save_revision().publish()
    return libro


def test_el_indice_de_importacion_se_abre(client, profe, pdf):
    client.force_login(profe)

    html = client.get(reverse("musica:importar")).content.decode()

    assert "Importar un método" in html
    assert "{#" not in html


def test_un_alumno_no_importa(client, alumno):
    client.force_login(alumno)

    r = client.get(reverse("musica:importar"))

    assert r.status_code in (302, 403)


def test_subir_un_pdf_lleva_directo_a_recortarlo(client, profe, db):
    """Subir un metodo es el paso previo a trocearlo, nunca un fin en si mismo."""
    from wagtail.models import Collection

    if not Collection.objects.exists():
        Collection.add_root(name="Root")
    client.force_login(profe)

    r = client.post(reverse("musica:subir_pdf"), {
        "title": "Piano Adventures",
        "file": SimpleUploadedFile("pa.pdf", b"%PDF-1.4 falso"),
    })

    doc = Document.objects.get(title="Piano Adventures")
    assert r.status_code == 204
    assert r["HX-Redirect"] == f"/musica/recortar/{doc.pk}/"


def test_subir_algo_que_no_es_pdf_se_rechaza(client, profe, db):
    client.force_login(profe)

    r = client.post(reverse("musica:subir_pdf"), {
        "title": "Audio",
        "file": SimpleUploadedFile("x.mp3", b"id3"),
    })

    assert Document.objects.filter(title="Audio").count() == 0
    assert "PDF" in r.content.decode()


def test_crear_el_libro_desde_el_frontend(client, profe, indice):
    """Sin esto hay que salir al admin en mitad del flujo."""
    client.force_login(profe)

    r = client.post(reverse("musica:crear_libro"), {"titulo": "Piano Adventures L1"})

    libro = LibroDeEstudioPage.objects.get(title="Piano Adventures L1")
    assert r.status_code == 204
    assert libro.get_parent().pk == indice.pk


def test_no_se_repite_el_slug_del_libro(client, profe, indice):
    client.force_login(profe)
    client.post(reverse("musica:crear_libro"), {"titulo": "Metodo"})

    r = client.post(reverse("musica:crear_libro"), {"titulo": "Metodo"})

    assert "slug" in r.content.decode()
    assert LibroDeEstudioPage.objects.filter(title="Metodo").count() == 1


# === Editar en vez de borrar y rehacer ===


def test_editar_un_recorte_conserva_su_sitio_en_el_libro(client, profe, pdf, raiz):
    """El motivo de que exista la edicion: rehacerlo lo sacaria del libro y lo
    mandaria al final."""
    client.force_login(profe)
    libro = _libro(raiz, "Metodo", "metodo-editar")
    _crear(client, pdf, destino="libro", destino_id=str(libro.pk))
    _crear(client, pdf, nombre="Segundo", destino="libro", destino_id=str(libro.pk))
    primero = Recorte.objects.get(nombre="Sailing Boat")

    client.post(reverse("musica:editar_recorte", args=[primero.pk]), {
        "nombre": "Sailing in the Sun", "pagina_desde": "8", "pagina_hasta": "9",
    })

    primero.refresh_from_db()
    libro.refresh_from_db()
    assert primero.nombre == "Sailing in the Sun"
    assert primero.rango_paginas == (8, 9)
    assert [b.value.pk for b in libro.capitulos] == [primero.pk, Recorte.objects.get(nombre="Segundo").pk]


def test_editar_puede_anadir_un_recuadro(client, profe, pdf):
    client.force_login(profe)
    _crear(client, pdf)
    recorte = Recorte.objects.get()

    client.post(reverse("musica:editar_recorte", args=[recorte.pk]), {
        "nombre": recorte.nombre, "pagina_desde": "10",
        "rect_x0": "0.0", "rect_y0": "0.3", "rect_x1": "1.0", "rect_y1": "0.55",
    })

    recorte.refresh_from_db()
    assert recorte.rect == (0.0, 0.3, 1.0, 0.55)


def test_una_edicion_invalida_no_rompe_el_recorte(client, profe, pdf):
    client.force_login(profe)
    _crear(client, pdf, pagina_hasta="13")
    recorte = Recorte.objects.get()

    r = client.post(reverse("musica:editar_recorte", args=[recorte.pk]), {
        "nombre": "X", "pagina_desde": "13", "pagina_hasta": "10",
    })

    recorte.refresh_from_db()
    assert recorte.nombre == "Sailing Boat", "el recorte sigue como estaba"
    assert "alert-error" in r.content.decode()


def test_un_alumno_no_edita(client, alumno, profe, pdf):
    client.force_login(profe)
    _crear(client, pdf)
    recorte = Recorte.objects.get()
    client.force_login(alumno)

    client.post(reverse("musica:editar_recorte", args=[recorte.pk]), {"nombre": "Mio"})

    recorte.refresh_from_db()
    assert recorte.nombre == "Sailing Boat"


# === Saber por donde ibas ===


def test_la_lista_marca_cuales_ya_son_capitulo(client, profe, pdf, raiz):
    """A mitad de un metodo de cincuenta paginas, sin esto no hay forma de
    saberlo sin abrir el libro en otra pestana."""
    client.force_login(profe)
    libro = _libro(raiz, "Metodo", "metodo-marcas")
    _crear(client, pdf, nombre="Dentro", destino="libro", destino_id=str(libro.pk))
    _crear(client, pdf, nombre="Fuera", destino="suelto")

    html = client.get(
        reverse("musica:recortador", args=[pdf.pk]) + f"?libro={libro.pk}"
    ).content.decode()

    assert "capítulo 1" in html


def test_sin_libro_atado_no_se_pinta_el_panel(client, profe, pdf):
    client.force_login(profe)

    html = client.get(reverse("musica:recortador", args=[pdf.pk])).content.decode()

    assert "capitulos-del-libro" not in html


# === Reordenar ===


def test_reordenar_el_libro_desde_la_pantalla(client, profe, pdf, raiz):
    import json

    client.force_login(profe)
    libro = _libro(raiz, "Metodo", "metodo-orden")
    for nombre in ("Uno", "Dos", "Tres"):
        _crear(client, pdf, nombre=nombre, destino="libro", destino_id=str(libro.pk))
    libro.refresh_from_db()
    claves = [f"recorte:{b.value.pk}" for b in libro.capitulos]

    client.post(reverse("musica:reordenar_libro", args=[libro.pk]),
                {"claves": json.dumps([claves[2], claves[0], claves[1]])})

    libro.refresh_from_db()
    assert [b.value.nombre for b in libro.capitulos] == ["Tres", "Uno", "Dos"]


def test_reordenar_a_medias_no_pierde_capitulos(client, profe, pdf, raiz):
    """Los bloques que no vengan en la lista se quedan al final en vez de
    perderse. La diferencia entre descolocar y borrar sin avisar."""
    import json

    client.force_login(profe)
    libro = _libro(raiz, "Metodo", "metodo-medias")
    for nombre in ("Uno", "Dos", "Tres"):
        _crear(client, pdf, nombre=nombre, destino="libro", destino_id=str(libro.pk))
    libro.refresh_from_db()
    claves = [f"recorte:{b.value.pk}" for b in libro.capitulos]

    client.post(reverse("musica:reordenar_libro", args=[libro.pk]),
                {"claves": json.dumps([claves[1]])})

    libro.refresh_from_db()
    assert len(list(libro.capitulos)) == 3
    assert list(libro.capitulos)[0].value.nombre == "Dos"


# === Restriccion desde la pantalla ===


def test_alternar_la_restriccion_desde_la_pantalla(client, profe, pdf):
    from musica.models import DocumentoRestringido

    client.force_login(profe)

    client.post(reverse("musica:alternar_restriccion", args=[pdf.pk]))
    assert DocumentoRestringido.esta_restringido(pdf.pk)

    client.post(reverse("musica:alternar_restriccion", args=[pdf.pk]))
    assert not DocumentoRestringido.esta_restringido(pdf.pk)


# === Aligerar el PDF al subirlo ===


def _pdf_con_imagen(ancho=2000, alto=2600, paginas=3):
    """Un PDF con imagenes de verdad, que es lo unico que se puede aligerar."""
    import io

    import pikepdf
    from PIL import Image

    pdf = pikepdf.new()
    for _ in range(paginas):
        # Ruido, no un liso: un JPEG de color plano ya pesa casi nada y el test
        # no distinguiria "aligerado" de "no habia nada que hacer".
        import random

        img = Image.new("RGB", (ancho, alto))
        pix = img.load()
        for y in range(0, alto, 4):
            for x in range(0, ancho, 4):
                c = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                for dy in range(4):
                    for dx in range(4):
                        if x + dx < ancho and y + dy < alto:
                            pix[x + dx, y + dy] = c
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        pagina = pikepdf.Page(pdf.add_blank_page(page_size=(612, 792)))
        stream = pikepdf.Stream(pdf, buf.getvalue())
        stream.Type = pikepdf.Name.XObject
        stream.Subtype = pikepdf.Name.Image
        stream.Width, stream.Height = ancho, alto
        stream.ColorSpace = pikepdf.Name.DeviceRGB
        stream.BitsPerComponent = 8
        stream.Filter = pikepdf.Name.DCTDecode
        pagina.add_resource(stream, pikepdf.Name.XObject, pikepdf.Name("/Im0"))
    salida = io.BytesIO()
    pdf.save(salida)
    return salida.getvalue()


def test_un_pdf_pesado_se_aligera(db):
    from musica.optimizar import optimizar

    datos = _pdf_con_imagen()
    salida, informe = optimizar(datos)

    assert informe.optimizado, informe
    assert len(salida) < len(datos)
    assert informe.ahorro_pct > 20


def test_aligerar_conserva_las_paginas(db):
    import io

    from pypdf import PdfReader

    from musica.optimizar import optimizar

    datos = _pdf_con_imagen(paginas=3)
    salida, _ = optimizar(datos)

    assert len(PdfReader(io.BytesIO(salida)).pages) == 3


def test_un_pdf_ligero_no_se_toca(db):
    """Recomprimir algo que ya pesa poco gasta tiempo de subida para nada."""
    from musica.optimizar import optimizar

    datos = b"%PDF-1.4 pequenito"
    salida, informe = optimizar(datos)

    assert salida == datos
    assert not informe.optimizado


def test_un_pdf_roto_no_tumba_la_subida(db):
    """Corre en mitad de una subida: un PDF raro no puede costarle a nadie el
    fichero que acaba de elegir."""
    from musica.optimizar import optimizar

    datos = b"x" * (3 * 1024 * 1024)
    salida, informe = optimizar(datos)

    assert salida == datos
    assert not informe.optimizado
    assert "tal cual" in informe.motivo


def test_subir_un_pdf_lo_guarda_aligerado(client, profe, db):
    from wagtail.models import Collection

    if not Collection.objects.exists():
        Collection.add_root(name="Root")
    datos = _pdf_con_imagen()
    client.force_login(profe)

    client.post(reverse("musica:subir_pdf"), {
        "title": "Metodo pesado",
        "file": SimpleUploadedFile("pesado.pdf", datos),
    })

    doc = Document.objects.get(title="Metodo pesado")
    assert doc.file.size < len(datos)


# === Volver a un metodo a medias ===


def test_el_recortador_abre_por_donde_lo_dejaste(client, profe, pdf, raiz):
    """Abrir siempre por la 1 obliga a avanzar a mano hasta la 30 cada vez que
    vuelves. En un libro de 56 paginas eso es mas trabajo que el recorte."""
    client.force_login(profe)
    _crear(client, pdf, nombre="Uno", pagina_desde="4", pagina_hasta="5")

    html = client.get(reverse("musica:recortador", args=[pdf.pk])).content.decode()

    assert 'data-pagina-inicial="6"' in html


def test_sin_recortes_abre_por_la_primera(client, profe, pdf):
    client.force_login(profe)

    html = client.get(reverse("musica:recortador", args=[pdf.pk])).content.decode()

    assert 'data-pagina-inicial="1"' in html


def test_el_indice_recuerda_a_que_libro_va_cada_pdf(client, profe, pdf, raiz):
    """Sin esto, volver a un metodo a medias te dejaba en el documento pero sin
    libro, y habia que elegirlo otra vez."""
    libro = _libro(raiz, "Metodo", "metodo-recuerda")
    client.force_login(profe)
    _crear(client, pdf, destino="libro", destino_id=str(libro.pk))

    html = client.get(reverse("musica:importar")).content.decode()

    assert f"?libro={libro.pk}" in html
    assert "Seguir" in html
