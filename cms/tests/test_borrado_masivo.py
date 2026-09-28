"""El borrado masivo del explorador sobrevive a una segunda petición.

Reproduce el 500 del 25-09-2026: la confirmación de borrar 29 artículos llegó
dos veces, la primera borró y la segunda reventó con `ArticuloPage matching
query does not exist` sobre páginas que ya no estaban.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from wagtail.admin.views.bulk_action.registry import bulk_action_registry
from wagtail.admin.views.pages.bulk_actions.delete import DeleteBulkAction
from wagtail.models import Page, Site

from blogs.models import ArticuloPage, BlogIndexPage
from cms.wagtail_hooks import BorradoMasivoTolerante

Usuario = get_user_model()


class BorradoMasivoTest(TestCase):
    def setUp(self):
        raiz = Site.objects.get(is_default_site=True).root_page
        self.departamento = BlogIndexPage(title="Música", slug="musica-borrado-test")
        raiz.add_child(instance=self.departamento)
        self.articulos = [self._articulo(f"Artículo {n}") for n in range(3)]
        self.profe = Usuario.objects.create_superuser(email="profe@local.test", password="x")

    def _articulo(self, titulo):
        articulo = ArticuloPage(
            title=titulo,
            slug=titulo.lower().replace(" ", "-"),
            date=date(2026, 9, 25),
            intro=f"Resumen de {titulo}",
        )
        self.departamento.add_child(instance=articulo)
        articulo.save_revision().publish()
        return articulo

    def _paginas_base(self):
        """Lo que recibe la acción: instancias de `Page`, no de `ArticuloPage`."""
        return list(Page.objects.filter(pk__in=[a.pk for a in self.articulos]).order_by("pk"))

    def test_la_accion_registrada_para_borrar_paginas_es_la_tolerante(self):
        clase = bulk_action_registry.get_bulk_action_class("wagtailcore", "page", "delete")
        self.assertIs(clase, BorradoMasivoTolerante)

    def test_la_accion_de_wagtail_revienta_si_una_pagina_ya_no_esta(self):
        """El fallo que se corrige, tal cual llegó por correo."""
        paginas = self._paginas_base()
        Page.objects.get(pk=paginas[0].pk).delete()
        with self.assertRaises(ArticuloPage.DoesNotExist):
            DeleteBulkAction.execute_action(paginas, user=self.profe)

    def test_una_pagina_que_ya_cayo_se_salta_y_el_resto_se_borra(self):
        paginas = self._paginas_base()
        Page.objects.get(pk=paginas[0].pk).delete()

        borradas, hijas = BorradoMasivoTolerante.execute_action(paginas, user=self.profe)

        self.assertEqual((borradas, hijas), (2, 0))
        self.assertFalse(Page.objects.filter(pk__in=[p.pk for p in paginas]).exists())

    def test_la_vista_del_explorador_borra_por_la_accion_tolerante(self):
        """De extremo a extremo: la petición real del explorador, con las páginas vivas."""
        self.client.force_login(self.profe)
        url = reverse("wagtail_bulk_action", args=("wagtailcore", "page", "delete"))
        ids = "&".join(f"id={a.pk}" for a in self.articulos)
        respuesta = self.client.post(
            f"{url}?{ids}&next=/cms/pages/{self.departamento.pk}/",
            {"next": f"/cms/pages/{self.departamento.pk}/"},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(ArticuloPage.objects.filter(pk__in=[a.pk for a in self.articulos]).exists())
