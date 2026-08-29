"""Privacidad de paginas y libros de estudio (2026-08-29).

El agujero que estos tests cierran: `_check_page_visibility` activaba el
bloqueo con `private_owner is not None`, asi que una pagina marcada privada
pero SIN owner se saltaba la comprobacion entera y se servia a cualquiera con
la URL, aunque los listados si la escondieran. Media privacidad se lee como
privacidad. Lo destaparon 31 paginas creadas por API, que nacen sin owner.
"""

import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from wagtail.models import Page

from cms.models import (
    BlogIndexPage,
    BlogPage,
    LibroDeEstudioPage,
    _check_page_visibility,
    _filter_visible_pages,
)

User = get_user_model()


class PrivacidadTest(TestCase):
    def setUp(self):
        self.duenyo = User.objects.create_superuser(
            email="duenyo@example.com", password="x123456789"
        )
        self.otro = User.objects.create_user(
            email="otro@example.com", password="x123456789"
        )
        root = Page.objects.filter(depth=1).first()
        self.index = BlogIndexPage(title="Idx", slug="idx-priv")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()

    def _pagina(self, **kw):
        p = BlogPage(title="Cancion", slug=kw.pop("slug", "cancion"),
                     date="2026-08-29", intro="x", **kw)
        self.index.add_child(instance=p)
        p.save_revision().publish()
        return p

    def _peticion(self, user):
        r = RequestFactory().get("/")
        r.user = user
        r.session = {}
        return r

    def test_privada_sin_duenyo_no_se_sirve_a_un_tercero(self):
        """El caso exacto del agujero: sin owner, antes devolvia None (pasa)."""
        p = self._pagina(is_private=True, slug="huerfana")
        self.assertIsNone(p.owner)
        resp = _check_page_visibility(p, self._peticion(self.otro))
        self.assertIsNotNone(resp, "una privada sin dueno se estaba sirviendo")
        self.assertEqual(resp.status_code, 403)

    def test_privada_sin_duenyo_si_la_ve_un_superusuario(self):
        p = self._pagina(is_private=True, slug="huerfana2")
        self.assertIsNone(_check_page_visibility(p, self._peticion(self.duenyo)))

    def test_privada_con_duenyo_la_ve_su_duenyo_y_no_un_tercero(self):
        p = self._pagina(is_private=True, slug="conduenyo")
        p.owner = self.otro
        p.save()
        self.assertIsNone(_check_page_visibility(p, self._peticion(self.otro)))
        tercero = User.objects.create_user(email="t@example.com", password="x123456789")
        resp = _check_page_visibility(p, self._peticion(tercero))
        self.assertEqual(resp.status_code, 403)

    def test_una_pagina_normal_sigue_siendo_publica(self):
        """Anti-criterio: no hemos cerrado el sitio entero."""
        p = self._pagina(slug="publica")
        self.assertIsNone(_check_page_visibility(p, self._peticion(self.otro)))

    def test_los_listados_esconden_la_privada_sin_duenyo(self):
        self._pagina(is_private=True, slug="huerfana3")
        qs = _filter_visible_pages(BlogPage.objects.all(), self._peticion(self.otro))
        self.assertEqual(qs.count(), 0)

    def test_el_libro_privado_tapa_sus_capitulos(self):
        """Un capitulo publico dentro de un libro privado no debe servirse."""
        root = Page.objects.filter(depth=1).first()
        libro = LibroDeEstudioPage(title="Repertorio", slug="rep-priv", is_private=True)
        root.add_child(instance=libro)
        libro.owner = self.otro
        libro.save()
        libro.save_revision().publish()
        tercero = User.objects.create_user(email="t2@example.com", password="x123456789")
        self.assertIsNotNone(_check_page_visibility(libro, self._peticion(tercero)))


class VisibilidadAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="api@example.com", password="x123456789"
        )
        self.client.force_login(self.user)
        root = Page.objects.filter(depth=1).first()
        self.index = BlogIndexPage(title="Idx", slug="idx-api-priv")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()
        self.libro = LibroDeEstudioPage(title="Rep", slug="rep-api")
        root.add_child(instance=self.libro)
        self.libro.save_revision().publish()

    def test_el_api_pone_owner_al_crear(self):
        """Sin esto, is_private no protege nada."""
        r = self.client.post(
            "/api/cms/blog-pages",
            data=json.dumps({"title": "C", "date": "2026-08-29", "intro": "x",
                             "parent_page_id": self.index.id}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["owner_id"], self.user.id)

    def test_marcar_privada_por_api_adopta_una_pagina_huerfana(self):
        p = BlogPage(title="H", slug="h-api", date="2026-08-29", intro="x")
        self.index.add_child(instance=p)
        p.save_revision().publish()
        self.assertIsNone(p.owner)
        r = self.client.put(
            f"/api/cms/blog-pages/{p.id}",
            data=json.dumps({"is_private": True}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["is_private"])
        self.assertEqual(r.json()["owner_id"], self.user.id)

    def test_visibilidad_del_libro_por_api(self):
        r = self.client.post(
            f"/api/cms/study-books/{self.libro.id}/visibility",
            data=json.dumps({"is_private": True}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["is_private"])
        self.assertEqual(r.json()["owner_id"], self.user.id)
