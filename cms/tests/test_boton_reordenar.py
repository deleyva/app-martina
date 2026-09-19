"""El botón de reordenar capítulos en la página del libro.

Existe porque en Wagtail el modo de reordenar se llama «Ordenar menú», vive
dentro del menú de acciones y no menciona capítulos por ningún sitio: nadie lo
encuentra buscando «reordenar». Estos tests fijan las dos cosas que importan,
que aparezca a quien puede usarlo y que apunte al sitio correcto.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Page, Site

from musica.models import LibroDeEstudioPage, LibroPage, RecursoPage

Usuario = get_user_model()


class BotonEnLibroNormalTest(TestCase):
    """Aquí los capítulos son páginas hijas: se ordenan en el explorador."""

    def setUp(self):
        raiz = Site.objects.get(is_default_site=True).root_page
        self.libro = LibroPage(title="Método de ukelele", slug="metodo-de-ukelele")
        raiz.add_child(instance=self.libro)
        self.libro.save_revision().publish()
        self._capitulo("Semana 1")
        self._capitulo("Semana 2")

    def _capitulo(self, titulo):
        pagina = RecursoPage(
            title=titulo,
            slug=titulo.lower().replace(" ", "-"),
            date="2026-09-19",
            intro=titulo,
        )
        self.libro.add_child(instance=pagina)
        pagina.save_revision().publish()
        return pagina

    def _profesor(self):
        return Usuario.objects.create_superuser(email="profe@local.test", password="x")

    def test_el_profesorado_lo_ve_y_apunta_al_modo_de_ordenar(self):
        self.client.force_login(self._profesor())
        respuesta = self.client.get(self.libro.url)
        self.assertContains(respuesta, "Reordenar")
        self.assertContains(respuesta, f"/cms/pages/{self.libro.pk}/?ordering=ord")

    def test_con_un_solo_capitulo_no_aparece(self):
        """Reordenar un capítulo no significa nada; el botón sobra."""
        RecursoPage.objects.child_of(self.libro).last().delete()
        self.client.force_login(self._profesor())
        respuesta = self.client.get(self.libro.url)
        self.assertNotContains(respuesta, "?ordering=ord")

    def test_el_alumnado_no_lo_ve(self):
        alumna = Usuario.objects.create_user(email="alumna@local.test", password="x")
        self.client.force_login(alumna)
        respuesta = self.client.get(self.libro.url)
        self.assertNotContains(respuesta, "?ordering=ord")

    def test_sin_sesion_no_lo_ve(self):
        respuesta = self.client.get(self.libro.url)
        self.assertNotContains(respuesta, "?ordering=ord")


class BotonEnLibroDeEstudioTest(TestCase):
    """Aquí los capítulos son bloques de un StreamField: se ordenan en el editor."""

    def setUp(self):
        raiz = Site.objects.get(is_default_site=True).root_page
        self.indice = LibroPage(title="Índice", slug="indice-est")
        raiz.add_child(instance=self.indice)
        self.indice.save_revision().publish()

        self.libro = LibroDeEstudioPage(title="Lista de estudio", slug="lista-de-estudio")
        raiz.add_child(instance=self.libro)
        self.libro.save_revision().publish()

        self.profe = Usuario.objects.create_superuser(email="profe2@local.test", password="x")
        self.paginas = [self._cancion(n) for n in ("Jolene", "Stand by Me")]

    def _cancion(self, titulo):
        pagina = RecursoPage(
            title=titulo,
            slug=titulo.lower().replace(" ", "-"),
            date="2026-09-19",
            intro=titulo,
        )
        self.indice.add_child(instance=pagina)
        pagina.save_revision().publish()
        return pagina

    def _poner_capitulos(self, paginas):
        self.client.force_login(self.profe)
        self.client.post(
            f"/api/cms/study-books/{self.libro.pk}/chapters",
            data=json.dumps({"page_ids": [p.id for p in paginas], "publish_immediately": True}),
            content_type="application/json",
        )

    def test_el_profesorado_lo_ve_y_apunta_al_editor(self):
        self._poner_capitulos(self.paginas)
        respuesta = self.client.get(self.libro.url)
        self.assertContains(respuesta, "Reordenar capítulos")
        self.assertContains(respuesta, f"/cms/pages/{self.libro.pk}/edit/")

    def test_con_un_solo_capitulo_no_aparece(self):
        self._poner_capitulos(self.paginas[:1])
        respuesta = self.client.get(self.libro.url)
        self.assertNotContains(respuesta, "Reordenar capítulos")

    def test_el_alumnado_no_lo_ve(self):
        self._poner_capitulos(self.paginas)
        self.client.logout()
        alumna = Usuario.objects.create_user(email="alumna2@local.test", password="x")
        self.client.force_login(alumna)
        respuesta = self.client.get(self.libro.url)
        self.assertNotContains(respuesta, "Reordenar capítulos")
