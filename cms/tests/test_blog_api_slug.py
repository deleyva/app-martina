"""El slug que manda el cliente, y por qué hace falta mandarlo.

Sin `slug` en el payload, Wagtail lo deriva del título conservando los acentos:
«¿Quién toca la batería en esta canción?» nació en
`/quién-toca-la-batería-en-esta-canción/`. Responde 200, pero viaja
porcentajeado en cada enlace y no se puede dictar por teléfono (2026-09-20).

Sigue el patrón de `test_blog_api.py`: sesión de Django, no cabecera de API.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Page

from musica.models import MusicLibraryIndexPage, RecursoPage

User = get_user_model()


class SlugDelClienteTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="slugtest@example.com", password="testpassword123"
        )
        self.client.force_login(self.user)
        raiz = Page.objects.filter(depth=1).first()
        self.indice = MusicLibraryIndexPage(
            title="Índice de prueba", slug="indice-de-prueba"
        )
        raiz.add_child(instance=self.indice)

    def _crear(self, **extra):
        carga = {
            "title": "¿Quién toca la batería en esta canción?",
            "date": "2026-09-20",
            "intro": "Una entradilla.",
            "body": "<p>Cuerpo.</p>",
            "parent_page_id": self.indice.id,
            "publish_immediately": True,
            **extra,
        }
        return self.client.post(
            "/api/cms/blog-pages",
            data=json.dumps(carga),
            content_type="application/json",
        )

    def test_sin_slug_wagtail_lo_deriva_con_acentos(self):
        """El comportamiento que motivó el cambio. Se documenta, no se celebra."""
        r = self._crear()
        self.assertEqual(r.status_code, 200, r.content)
        pagina = RecursoPage.objects.get(id=r.json()["id"])
        self.assertTrue(
            any(c in pagina.slug for c in "áéíóúñ"),
            f"esperaba acentos en el slug derivado, salió {pagina.slug!r}",
        )

    def test_con_slug_manda_el_del_cliente(self):
        r = self._crear(slug="quien-toca-la-bateria-en-esta-cancion")
        self.assertEqual(r.status_code, 200, r.content)
        pagina = RecursoPage.objects.get(id=r.json()["id"])
        self.assertEqual(pagina.slug, "quien-toca-la-bateria-en-esta-cancion")

    def test_el_slug_se_normaliza_a_ascii(self):
        r = self._crear(slug="Canción Ñoña CON Acentos")
        self.assertEqual(r.status_code, 200, r.content)
        pagina = RecursoPage.objects.get(id=r.json()["id"])
        self.assertEqual(pagina.slug, "cancion-nona-con-acentos")

    def test_un_slug_que_se_queda_vacio_da_400(self):
        r = self._crear(slug="¿?¡!")
        self.assertEqual(r.status_code, 400)
        self.assertIn("vac", r.json()["detail"].lower())

    def test_actualizar_cambia_el_slug(self):
        page_id = self._crear(slug="slug-viejo").json()["id"]
        r = self.client.put(
            f"/api/cms/blog-pages/{page_id}",
            data=json.dumps({"slug": "slug-nuevo", "publish_immediately": True}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(RecursoPage.objects.get(id=page_id).slug, "slug-nuevo")
