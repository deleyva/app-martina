"""Tests para POST /api/cms/study-books/{id}/chapters (2026-08-28)."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Page

from cms.models import BlogIndexPage, BlogPage, LibroDeEstudioPage

User = get_user_model()


class LibroCapitulosAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="testcap@example.com", password="testpassword123"
        )
        self.client.force_login(self.user)
        root = Page.objects.filter(depth=1).first()

        self.blog_index = BlogIndexPage(title="Blog Cap", slug="blog-cap")
        root.add_child(instance=self.blog_index)
        self.blog_index.save_revision().publish()

        self.libro = LibroDeEstudioPage(title="Repertorio Test", slug="repertorio-test")
        root.add_child(instance=self.libro)
        self.libro.save_revision().publish()

        self.canciones = []
        for n in ("Uptown Funk", "Wonderwall", "Starman"):
            p = BlogPage(title=n, slug=n.lower().replace(" ", "-"), date="2026-08-28", intro=n)
            self.blog_index.add_child(instance=p)
            p.save_revision().publish()
            self.canciones.append(p)

    def _post(self, libro_id, payload):
        return self.client.post(
            f"/api/cms/study-books/{libro_id}/chapters",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_anade_capitulos_en_el_orden_dado(self):
        ids = [c.id for c in self.canciones]
        resp = self._post(self.libro.id, {"page_ids": ids})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["anadidos"], ids)
        libro = LibroDeEstudioPage.objects.get(id=self.libro.id).get_latest_revision_as_object()
        self.assertEqual([b.value.id for b in libro.capitulos], ids)

    def test_conserva_los_capitulos_que_ya_habia(self):
        """El caso de Jesús: 4 capítulos existentes que no se tocan."""
        self._post(self.libro.id, {"page_ids": [self.canciones[0].id]})
        libro = LibroDeEstudioPage.objects.get(id=self.libro.id).get_latest_revision_as_object()
        libro.save_revision().publish()

        resp = self._post(self.libro.id, {"page_ids": [self.canciones[1].id]})
        self.assertEqual(resp.status_code, 200, resp.content)
        libro = LibroDeEstudioPage.objects.get(id=self.libro.id).get_latest_revision_as_object()
        self.assertEqual(
            [b.value.id for b in libro.capitulos],
            [self.canciones[0].id, self.canciones[1].id],
        )

    def test_no_duplica_al_reintentar(self):
        ids = [c.id for c in self.canciones]
        self._post(self.libro.id, {"page_ids": ids, "publish_immediately": True})
        resp = self._post(self.libro.id, {"page_ids": ids})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["anadidos"], [])
        self.assertEqual(resp.json()["ya_estaban"], ids)
        self.assertEqual(resp.json()["total_capitulos"], len(ids))

    def test_rechaza_un_tipo_de_pagina_no_admitido(self):
        resp = self._post(self.libro.id, {"page_ids": [self.blog_index.id]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("BlogIndexPage", resp.json()["detail"])

    def test_rechaza_paginas_inexistentes(self):
        resp = self._post(self.libro.id, {"page_ids": [999999]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("999999", resp.json()["detail"])

    def test_libro_inexistente_da_404(self):
        resp = self._post(999999, {"page_ids": [self.canciones[0].id]})
        self.assertEqual(resp.status_code, 404)

    def test_lista_vacia_da_400(self):
        resp = self._post(self.libro.id, {"page_ids": []})
        self.assertEqual(resp.status_code, 400)
