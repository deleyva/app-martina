"""Leer un sitio de Google Sites e importarlo, sin tocar la red.

La página de prueba tiene la forma que sirve Google Sites —franjas en
`<section>`, negrita en el `style` de un `<span>`, botones con un bloque dentro
del enlace— pero el contenido es inventado.
"""

import urllib.error
from io import BytesIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import Page

from blogs.google_sites import (
    enlaces_internos,
    extraer_pagina,
    prefijo_del_sitio,
    reescribir_enlaces_internos,
    ruta_interna,
    slug_de_ruta,
    url_canonica,
)
from blogs.models import ArticuloPage, BlogIndexPage
from blogs.tests.test_import_blogspot import PNG_1PX

PREFIJO = "/centro.es/depto"
RAIZ = "https://sites.google.com/centro.es/depto"

MENU = f"""
<nav><ul>
  <li><a href="{PREFIJO}/inicio?authuser=0">Inicio</a></li>
  <li><a href="{PREFIJO}/documentos?authuser=0">Documentos</a></li>
  <li><a href="{PREFIJO}/cursos/3%C2%BA-eso?authuser=0">3º ESO</a></li>
</ul></nav>
"""

NEGRITA = 'style="font-size: 11pt; font-weight: 700; vertical-align: baseline;"'

INICIO = f"""<html><body>{MENU}
<section><div><h1 class="x"><span>Departamento de Pruebas</span></h1></div></section>
<section><div>
  <img src="https://sites.google.com/sitesv-images-rt/abc=w1280" alt="">
  <p><span>Bienvenidos. Aquí están los </span><a href="{PREFIJO}/documentos"><span {NEGRITA}>documentos </span></a><span>del curso.</span></p>
</div></section>
<section><div><h2><div class="ancla"><a href="#h.abc"><div></div></a></div><span>PROFESORADO CURSO 202</span><span>6</span><span>/2</span><span>7</span></h2></div></section>
<section><div>
  <p><span {NEGRITA}>ADA </span><span {NEGRITA}>LOVELACE</span></p>
  <p><span>Materias:</span></p>
  <ul><li><p><span>Programación 3º ESO</span></p></li><li><p><span>Robótica 4º ESO</span></p></li></ul>
  <p><span>Correo: </span><span {NEGRITA}>ada</span><span {NEGRITA}>@centro.es</span></p>
  <p><span {NEGRITA}>¡Os esperamos!</span></p>
</div></section>
</body></html>"""

DOCUMENTOS = f"""<html><body>{MENU}
<section><h1><span>Documentos</span></h1></section>
<section><ul>
  <li><p><a href="https://drive.google.com/file/d/AAAAAAAAAAAAAAAAAAAAAAAAA/view?usp=drive_link"><span>Programación de 3º</span></a></p></li>
</ul></section>
</body></html>"""

CURSO = f"""<html><body>{MENU}
<section><h1><span>3º de ESO</span></h1></section>
<section><div><p style="text-align: center;"><span {NEGRITA}>ROBÓTICA</span></p></div></section>
<section><div>
  <p><span {NEGRITA}>¿QUÉ ES?</span></p>
  <p><span>Una materia para construir robots.</span></p>
  <div class="boton"><a href="{PREFIJO}/inicio"><div><p>Volver al inicio</p></div></a></div>
  <p><a href="{PREFIJO}/no-existe"><span>Otra página</span></a></p>
</div></section>
</body></html>"""

SITIO = {
    f"{RAIZ}/inicio": INICIO,
    f"{RAIZ}/documentos": DOCUMENTOS,
    url_canonica(PREFIJO, "cursos/3º-eso"): CURSO,
}


class GoogleSitesPuroTest(SimpleTestCase):
    def test_prefijo_con_dominio_y_sin_dominio(self):
        self.assertEqual(prefijo_del_sitio(f"{RAIZ}/inicio?pli=1&authuser=0"), PREFIJO)
        self.assertEqual(
            prefijo_del_sitio("https://sites.google.com/view/mi-sitio/pagina"), "/view/mi-sitio"
        )

    def test_una_direccion_que_no_es_de_sites_no_se_recorre(self):
        with self.assertRaises(ValueError):
            prefijo_del_sitio("https://example.com/centro.es/depto/inicio")

    def test_ruta_interna(self):
        self.assertEqual(ruta_interna(f"{PREFIJO}/cursos/3%C2%BA-eso?authuser=0", PREFIJO), "cursos/3º-eso")
        self.assertIsNone(ruta_interna("#h.abc", PREFIJO))
        self.assertIsNone(ruta_interna("https://drive.google.com/file/d/x/view", PREFIJO))
        self.assertIsNone(ruta_interna("/centro.es/otro-sitio/inicio", PREFIJO))

    def test_el_menu_da_todas_las_paginas_sin_repetir(self):
        self.assertEqual(
            enlaces_internos(INICIO, PREFIJO), ["inicio", "documentos", "cursos/3º-eso"]
        )

    def test_el_slug_lleva_la_ruta_entera(self):
        self.assertEqual(slug_de_ruta("cursos/3º-eso"), "cursos-3o-eso")

    def test_el_h1_es_el_titulo_y_sale_del_cuerpo(self):
        titulo, cuerpo = extraer_pagina(INICIO)
        self.assertEqual(titulo, "Departamento de Pruebas")
        self.assertNotIn("Departamento de Pruebas", cuerpo)
        self.assertNotIn("<nav", cuerpo)
        self.assertNotIn("Inicio", cuerpo)

    def test_un_encabezado_partido_en_trozos_no_gana_espacios(self):
        _, cuerpo = extraer_pagina(INICIO)
        self.assertIn("<h2>PROFESORADO CURSO 2026/27</h2>", cuerpo)

    def test_la_negrita_del_estilo_pasa_a_etiqueta(self):
        _, cuerpo = extraer_pagina(INICIO)
        # Párrafo corto entero en negrita: subtítulo. Y los dos trozos, juntos.
        self.assertIn("<h3>ADA LOVELACE</h3>", cuerpo)
        # Negrita partida dentro de un párrafo que no lo es entero: una sola.
        self.assertEqual(cuerpo.count("<strong>"), 2)
        self.assertIn("ada</span>", cuerpo)

    def test_una_exclamacion_en_negrita_no_es_un_subtitulo(self):
        _, cuerpo = extraer_pagina(INICIO)
        self.assertNotIn("<h3>¡Os esperamos!</h3>", cuerpo)
        self.assertIn("¡Os esperamos!", cuerpo)

    def test_la_negrita_de_un_enlace_no_se_trae(self):
        _, cuerpo = extraer_pagina(INICIO)
        enlace = cuerpo[cuerpo.index("<a ") : cuerpo.index("</a>")]
        self.assertNotIn("<strong>", enlace)

    def test_las_vinetas_no_llevan_parrafo_dentro(self):
        _, cuerpo = extraer_pagina(INICIO)
        self.assertNotIn("<li><p", cuerpo.replace("\n", ""))

    def test_una_franja_de_una_linea_es_un_rotulo(self):
        _, cuerpo = extraer_pagina(CURSO)
        self.assertIn("<h2>ROBÓTICA</h2>", cuerpo)
        self.assertIn("<h3>¿QUÉ ES?</h3>", cuerpo)

    def test_un_boton_pasa_a_parrafo_con_enlace(self):
        _, cuerpo = extraer_pagina(CURSO)
        self.assertIn(f'<p><a href="{PREFIJO}/inicio">Volver al inicio</a></p>', cuerpo)

    def test_enlaces_internos_a_paginas_nuestras_o_al_sitio_original(self):
        _, cuerpo = extraer_pagina(CURSO)
        salida = reescribir_enlaces_internos(cuerpo, PREFIJO, {"inicio": 7})
        self.assertIn('<a id="7" linktype="page">Volver al inicio</a>', salida)
        self.assertIn(f'href="{RAIZ}/no-existe"', salida)


class ImportGoogleSitesTest(TestCase):
    def setUp(self):
        root = Page.objects.filter(depth=1).first()
        self.depto = BlogIndexPage(title="Pruebas", slug="pruebas")
        root.add_child(instance=self.depto)
        self.depto.save_revision().publish()

    def _importar(self, **opciones):
        def leer(url, binario=False):
            if url not in SITIO:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            return SITIO[url]

        def imagen_falsa(self_cmd, url, titulo, coleccion, informe):
            imagen = get_image_model()(title=titulo[:255], collection=coleccion)
            imagen.file = ImageFile(BytesIO(PNG_1PX), name="falsa.png")
            imagen.save()
            informe.imagenes_ok += 1
            return imagen

        def documento_falso(self_cmd, url, identificador, extension, texto, coleccion, informe, original):
            documento = get_document_model()(title=texto, collection=coleccion)
            documento.file.save("programacion.pdf", ContentFile(b"%PDF-1.4"), save=False)
            documento.save()
            return documento

        base = "blogs.management.commands.import_blogspot.Command."
        with mock.patch("blogs.management.commands.import_google_sites._get", leer), \
             mock.patch(base + "_descargar_imagen", imagen_falsa), \
             mock.patch(base + "_descargar_documento", documento_falso):
            call_command(
                "import_google_sites", f"{RAIZ}/inicio?pli=1", departamento="pruebas",
                verbosity=0, **opciones,
            )

    def _articulos(self):
        return {a.slug: a for a in ArticuloPage.objects.child_of(self.depto)}

    def test_cada_pagina_del_sitio_es_un_articulo_publicado(self):
        self._importar()
        articulos = self._articulos()
        self.assertEqual(set(articulos), {"inicio", "documentos", "cursos-3o-eso"})
        self.assertTrue(all(a.live for a in articulos.values()))
        self.assertEqual(articulos["inicio"].title, "Departamento de Pruebas")
        self.assertEqual(articulos["cursos-3o-eso"].source_url, url_canonica(PREFIJO, "cursos/3º-eso"))

    def test_relanzar_no_duplica(self):
        self._importar()
        self._importar()
        self.assertEqual(ArticuloPage.objects.child_of(self.depto).count(), 3)

    def test_el_pdf_de_drive_queda_como_documento_nuestro(self):
        self._importar()
        cuerpo = self._articulos()["documentos"].body
        documento = get_document_model().objects.get(title="Programación de 3º")
        self.assertIn(f'<a id="{documento.pk}" linktype="document">Programación de 3º</a>', cuerpo)
        self.assertNotIn("drive.google.com", cuerpo)

    def test_los_enlaces_entre_paginas_apuntan_a_los_articulos(self):
        self._importar()
        articulos = self._articulos()
        self.assertIn(
            f'id="{articulos["documentos"].pk}" linktype="page"', articulos["inicio"].body
        )
        self.assertIn(
            f'id="{articulos["inicio"].pk}" linktype="page"', articulos["cursos-3o-eso"].body
        )

    def test_ninguna_imagen_se_queda_apuntando_a_google(self):
        self._importar()
        cuerpo = self._articulos()["inicio"].body
        self.assertIn('embedtype="image"', cuerpo)
        self.assertNotIn("sitesv-images", cuerpo)

    def test_titulo_fijar_saltar_y_borrador(self):
        self._importar(
            titulo=["inicio=Profesorado"], fijar=["documentos"],
            saltar=["cursos/3º-eso"], draft=True,
        )
        articulos = self._articulos()
        self.assertEqual(set(articulos), {"profesorado", "documentos"})
        self.assertEqual(articulos["profesorado"].title, "Profesorado")
        self.assertTrue(articulos["documentos"].is_pinned)
        self.assertFalse(articulos["profesorado"].is_pinned)
        self.assertFalse(any(a.live for a in articulos.values()))

    def test_el_ensayo_no_escribe_nada(self):
        self._importar(dry_run=True)
        self.assertEqual(ArticuloPage.objects.child_of(self.depto).count(), 0)
        self.assertEqual(get_document_model().objects.count(), 0)

    def test_una_ruta_mal_escrita_para_antes_de_escribir(self):
        with self.assertRaises(CommandError):
            self._importar(fijar=["programaciones"])
        self.assertEqual(ArticuloPage.objects.child_of(self.depto).count(), 0)

    def test_un_departamento_que_no_existe_para(self):
        with self.assertRaises(CommandError):
            call_command(
                "import_google_sites", f"{RAIZ}/inicio", departamento="no-existe", verbosity=0
            )
