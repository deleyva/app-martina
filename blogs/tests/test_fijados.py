"""Un departamento puede fijar artículos para que no se hundan en la cronología.

La programación, los criterios de calificación o las pendientes no son noticias:
son documentos de referencia que tienen que estar a mano todo el curso. Sin
`is_pinned` iban cayendo una fila por cada artículo nuevo hasta desaparecer de
la primera pantalla. Aquí se prueba el contrato del contexto de departamento:
los fijados van aparte, ordenados por título, y no se repiten en la cronología;
y un fijado que el visitante no puede ver tampoco aparece por estar fijado.
"""

from datetime import date

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from wagtail.models import Page, Site

from blogs.models import ArticuloPage, BlogIndexPage


class FijadosTest(TestCase):
    def setUp(self):
        root = Page.objects.filter(depth=1).first()
        self.portada = BlogIndexPage(title="Blogs", slug="blogs-fijados-test")
        root.add_child(instance=self.portada)
        self.departamento = BlogIndexPage(title="Matemáticas", slug="mates-fijados-test")
        self.portada.add_child(instance=self.departamento)

        self.programacion = self._articulo("Programación didáctica", pinned=True)
        self.criterios = self._articulo("Criterios de calificación", pinned=True)
        self.noticia = self._articulo("Salida al museo", pinned=False)
        self.protegido = self._articulo(
            "Actas del departamento", pinned=True, protegido=True
        )

        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()

    def _articulo(self, titulo, *, pinned, protegido=False):
        articulo = ArticuloPage(
            title=titulo,
            slug=titulo.lower().replace(" ", "-"),
            date=date(2026, 9, 1),
            intro=f"Resumen de {titulo}",
            is_pinned=pinned,
            is_protected=protegido,
        )
        self.departamento.add_child(instance=articulo)
        return articulo

    def _contexto(self):
        return self.departamento.get_context(self.request)

    def test_los_fijados_van_aparte_y_ordenados_por_titulo(self):
        fijados = self._contexto()["fijados"]
        self.assertEqual(
            [a.title for a in fijados],
            ["Criterios de calificación", "Programación didáctica"],
        )

    def test_un_fijado_no_se_repite_en_la_cronologia(self):
        articulos = self._contexto()["articulos"]
        self.assertEqual([a.title for a in articulos], ["Salida al museo"])

    def test_fijar_no_salta_la_visibilidad(self):
        # Un artículo protegido no aparece a un visitante anónimo, esté fijado
        # o no. Fijar cambia la posición, nunca quién lo ve.
        contexto = self._contexto()
        titulos = {a.title for a in contexto["fijados"]} | {
            a.title for a in contexto["articulos"]
        }
        self.assertNotIn("Actas del departamento", titulos)

    def test_un_departamento_sin_fijados_no_cambia(self):
        self.programacion.is_pinned = False
        self.programacion.save()
        self.criterios.is_pinned = False
        self.criterios.save()
        contexto = self._contexto()
        self.assertEqual(contexto["fijados"], [])
        self.assertEqual(len(contexto["articulos"]), 3)

    def test_la_pagina_pinta_la_seccion_siempre_a_mano(self):
        # Por el cliente de pruebas y no por `serve()`: los procesadores de
        # contexto del sitio piden sesión, y `RequestFactory` no la trae.
        # El sitio por defecto de pruebas cuelga de otra raíz; se apunta a la
        # portada de este árbol para que el departamento tenga URL servible.
        sitio = Site.objects.get(is_default_site=True)
        sitio.root_page = self.portada
        sitio.save()
        # La caché de rutas raíz sobrevive al rollback; sin esto la siguiente
        # prueba que sirva una página se encuentra un 404.
        self.addCleanup(Site.clear_site_root_paths_cache)
        respuesta = self.client.get(f"/{self.departamento.slug}/")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn("Siempre a mano", html)
        self.assertLess(
            html.index("Criterios de calificación"), html.index("Salida al museo")
        )
