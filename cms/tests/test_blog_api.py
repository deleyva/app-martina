"""Tests para el endpoint POST /api/cms/blog-pages."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Page

from cms.models import BlogIndexPage, BlogPage, MusicCategory, MusicTag

User = get_user_model()


class BlogPageAPITest(TestCase):
    """Tests para el endpoint POST /api/cms/blog-pages.

    Usa django_auth (sesión de Django) para autenticación,
    siguiendo el patrón estándar del proyecto.
    """

    def setUp(self):
        # Usuario admin para autenticación
        self.user = User.objects.create_superuser(
            email="testadmin@example.com",
            password="testpassword123",
        )
        self.client.force_login(self.user)

        # Página raíz de Wagtail (depth=1)
        self.root_page = Page.objects.filter(depth=1).first()

        # Crear BlogIndexPage como padre
        self.blog_index = BlogIndexPage(title="Blog Test", slug="blog-test-api")
        self.root_page.add_child(instance=self.blog_index)
        self.blog_index.save_revision().publish()

        # Snippets auxiliares
        self.cat = MusicCategory.objects.create(name="Teoría Musical")
        self.tag = MusicTag.objects.create(name="Principiantes", color="#FF5733")

        self.url = "/api/cms/blog-pages"

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    # ------------------------------------------------------------------
    # Casos de éxito
    # ------------------------------------------------------------------

    def test_crear_blogpage_minima_como_borrador(self):
        """Debe crear una BlogPage como borrador con los campos mínimos."""
        response = self._post(
            {
                "title": "Mi primer artículo",
                "date": "2024-09-01",
                "intro": "Este es un resumen del artículo.",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["title"], "Mi primer artículo")
        self.assertFalse(data["live"])
        self.assertIn("/cms/pages/", data["edit_url"])
        self.assertIn("view_draft", data["preview_url"])

        page = BlogPage.objects.get(id=data["id"])
        self.assertEqual(page.intro, "Este es un resumen del artículo.")
        self.assertFalse(page.live)

    def test_crear_blogpage_completa_y_publicar(self):
        """Debe crear una BlogPage completa y publicarla inmediatamente."""
        response = self._post(
            {
                "title": "Artículo completo",
                "date": "2024-10-15",
                "intro": "Resumen completo del artículo.",
                "body": "<p>Cuerpo del artículo en <strong>HTML</strong>.</p>",
                "category_ids": [self.cat.id],
                "tag_ids": [self.tag.id],
                "parent_page_id": self.blog_index.id,
                "publish_immediately": True,
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["live"])

        page = BlogPage.objects.get(id=data["id"])
        self.assertEqual(page.body, "<p>Cuerpo del artículo en <strong>HTML</strong>.</p>")
        self.assertIn(self.cat, page.categories.all())
        self.assertIn(self.tag, page.tags.all())

    def test_sin_parent_usa_primer_blogindexpage(self):
        """Sin parent_page_id debe autodetectar la primera BlogIndexPage."""
        response = self._post(
            {
                "title": "Sin padre explícito",
                "date": "2024-11-01",
                "intro": "Test autodetección de padre.",
            }
        )
        self.assertEqual(response.status_code, 200)
        page = BlogPage.objects.get(id=response.json()["id"])
        self.assertEqual(page.get_parent().specific, self.blog_index)

    # ------------------------------------------------------------------
    # Validaciones / errores
    # ------------------------------------------------------------------

    def test_parent_page_id_invalido_devuelve_400(self):
        """Un parent_page_id inexistente debe devolver 400."""
        response = self._post(
            {
                "title": "Artículo huérfano",
                "date": "2024-09-01",
                "intro": "Padre inexistente.",
                "parent_page_id": 99999,
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_category_id_invalido_devuelve_400(self):
        """Un category_id inexistente debe devolver 400."""
        response = self._post(
            {
                "title": "Categoría rota",
                "date": "2024-09-01",
                "intro": "Resumen.",
                "category_ids": [99999],
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_tag_id_invalido_devuelve_400(self):
        """Un tag_id inexistente debe devolver 400."""
        response = self._post(
            {
                "title": "Tag roto",
                "date": "2024-09-01",
                "intro": "Resumen.",
                "tag_ids": [99999],
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_borrador_no_live(self):
        """Una página creada sin publish_immediately debe quedar como borrador."""
        response = self._post(
            {
                "title": "Borrador",
                "date": "2024-09-01",
                "intro": "Este es un borrador.",
                "publish_immediately": False,
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 200)
        page = BlogPage.objects.get(id=response.json()["id"])
        self.assertFalse(page.live)

    def test_sin_autenticar_devuelve_401(self):
        """Sin sesión activa debe devolver 401 o 403."""
        self.client.logout()
        response = self._post(
            {
                "title": "Sin auth",
                "date": "2024-09-01",
                "intro": "Intento sin autenticar.",
            }
        )
        self.assertIn(response.status_code, [401, 403])
