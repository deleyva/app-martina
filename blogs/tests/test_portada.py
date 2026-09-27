"""La portada cuenta qué pasa en el centro, y el menú es el único acceso a los
departamentos (fase 52).

Antes la portada listaba los diecinueve departamentos en una rejilla de tarjetas
que repetía el menú, y no había ningún sitio donde ver lo último publicado en
todo el instituto. Aquí se prueba el contrato nuevo: «Últimas publicaciones»
con el departamento de cada artículo resuelto en una consulta, sin repetir los
destacados; los fijados de la raíz en la portada; y el menú marcando el
departamento actual sin hacer consultas.

También el arreglo de adjuntos que llegó con la misma fase: el formulario de un
artículo no menciona Guitar Pro ni recortes, y los documentos adjuntos se ven en
la página, que antes solo pintaba vídeos.
"""

from datetime import date

from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase
from wagtail.documents import get_document_model
from wagtail.models import Page, Site

from blogs.context_processors import blog_navigation
from blogs.models import ArticuloPage, BlogIndexPage

Document = get_document_model()


class ArbolConDosDepartamentos:
    def _montar(self):
        root = Page.objects.filter(depth=1).first()
        self.portada = BlogIndexPage(title="Blogs", slug="portada-52")
        root.add_child(instance=self.portada)
        self.mates = BlogIndexPage(title="Matemáticas", slug="mates-52")
        self.portada.add_child(instance=self.mates)
        self.lengua = BlogIndexPage(title="Lengua", slug="lengua-52")
        self.portada.add_child(instance=self.lengua)

        sitio = Site.objects.get(is_default_site=True)
        sitio.root_page = self.portada
        sitio.save()

    def tearDown(self):
        # Wagtail cachea las rutas raíz de los sitios fuera de la base de
        # datos. El rollback de la prueba devuelve el sitio a su raíz, pero la
        # caché sigue apuntando a una portada que ya no existe, y la siguiente
        # prueba que sirva una página se encuentra un 404.
        Site.clear_site_root_paths_cache()

    def _articulo(self, padre, titulo, dia, **campos):
        articulo = ArticuloPage(
            title=titulo,
            slug=titulo.lower().replace(" ", "-"),
            date=date(2026, 9, dia),
            intro=f"Resumen de {titulo}",
            **campos,
        )
        padre.add_child(instance=articulo)
        # `first_published_at` manda en el orden; `add_child` lo deja en el
        # instante de creación, así que se fuerza a la fecha del artículo.
        ArticuloPage.objects.filter(pk=articulo.pk).update(
            first_published_at=f"2026-09-{dia:02d}T10:00:00Z"
        )
        return articulo

    def _peticion(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        return request


class PortadaTest(ArbolConDosDepartamentos, TestCase):
    def setUp(self):
        self._montar()
        self.vieja = self._articulo(self.mates, "Olimpiada", 1)
        self.destacada = self._articulo(self.lengua, "Certamen", 5, is_featured=True)
        self.nueva = self._articulo(self.lengua, "Recital", 9)
        self.del_centro = self._articulo(self.portada, "Calendario", 2, is_pinned=True)

    def test_ultimas_de_todo_el_centro_con_su_departamento(self):
        contexto = self.portada.get_context(self._peticion())
        ultimas = contexto["ultimas"]
        self.assertEqual(
            [(a.title, a.departamento_titulo) for a in ultimas],
            [("Recital", "Lengua"), ("Olimpiada", "Matemáticas")],
        )

    def test_un_destacado_no_se_repite_en_ultimas(self):
        contexto = self.portada.get_context(self._peticion())
        self.assertEqual([a.title for a in contexto["featured_posts"]], ["Certamen"])
        self.assertNotIn("Certamen", [a.title for a in contexto["ultimas"]])

    def test_los_fijados_de_la_raiz_salen_en_la_portada(self):
        contexto = self.portada.get_context(self._peticion())
        self.assertEqual([a.title for a in contexto["fijados"]], ["Calendario"])

    def test_la_portada_ya_no_repite_los_departamentos(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Últimas publicaciones", html)
        self.assertIn("Siempre a mano", html)
        self.assertNotIn("Ver publicaciones", html)
        # El menú sigue siendo el acceso: cada departamento aparece enlazado.
        self.assertIn('href="/mates-52/"', html)
        self.assertIn('href="/lengua-52/"', html)


class MenuTest(ArbolConDosDepartamentos, TestCase):
    def setUp(self):
        self._montar()
        self._articulo(self.mates, "Olimpiada", 1)

    def _contexto_menu(self, ruta):
        request = RequestFactory().get(ruta)
        request.user = AnonymousUser()
        return blog_navigation(request)

    def test_marca_el_departamento_desde_su_portada_y_desde_sus_articulos(self):
        self.assertEqual(self._contexto_menu("/mates-52/")["blog_departamento_actual"], "mates-52")
        self.assertEqual(
            self._contexto_menu("/mates-52/olimpiada/")["blog_departamento_actual"],
            "mates-52",
        )
        self.assertEqual(self._contexto_menu("/")["blog_departamento_actual"], "")

    def test_el_menu_va_por_orden_alfabetico(self):
        titulos = [d.title for d in self._contexto_menu("/")["blog_departments"]]
        self.assertEqual(titulos, ["Lengua", "Matemáticas"])

    def test_la_pagina_subraya_el_departamento_actual(self):
        html = self.client.get("/mates-52/").content.decode()
        self.assertIn('aria-current="page"', html)


class AdjuntosDelArticuloTest(ArbolConDosDepartamentos, TestCase):
    def setUp(self):
        self._montar()
        self.documento = Document.objects.create(
            title="Recuperación - Matemáticas I",
            file=ContentFile(b"%PDF-1.4 prueba", name="recuperacion.pdf"),
        )
        self.articulo = self._articulo(
            self.mates,
            "Pendientes",
            3,
            attachments=[("pdf_score", {"pdf_file": self.documento})],
        )

    def test_el_formulario_no_habla_de_guitar_pro_ni_de_recortes(self):
        bloques = ArticuloPage._meta.get_field("attachments").stream_block.child_blocks
        self.assertNotIn("recorte", bloques)
        self.assertEqual(bloques["pdf_score"].label, "Documento")
        ayuda = str(bloques["pdf_score"].child_blocks["pdf_file"].field.help_text)
        self.assertNotIn("Guitar Pro", ayuda)

    def test_el_documento_adjunto_se_ve_en_el_articulo(self):
        html = self.client.get("/mates-52/pendientes/").content.decode()
        self.assertIn("Documentos", html)
        self.assertIn("Recuperación - Matemáticas I", html)
        self.assertIn(self.documento.url, html)
