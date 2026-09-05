"""El pajarito de Wagtail en el subdominio de blogs (2026-09-05).

`{% wagtailuserbar %}` llevaba puesto en `blogs/base.html` desde siempre y aun
asi no salia nunca en `blogs.iesmartinabescos.es`. No faltaba la etiqueta:
faltaba el usuario. La cookie de sesion es *host-only* —no hay
`SESSION_COOKIE_DOMAIN`—, asi que estar logueado en `apps.iesmartinabescos.es`
no logueaba en `blogs.`, y el footer de blogs no tenia ningun enlace de login.
Un profesor llegaba al subdominio como anonimo y sin forma de dejar de serlo,
y el userbar hacia lo correcto: no pintarse.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Site

from blogs.models import ArticuloPage, BlogIndexPage

User = get_user_model()


class UserbarEnBlogsTest(TestCase):
    def setUp(self):
        # Bajo la raiz del sitio, no bajo la raiz del arbol: una pagina
        # colgada de `depth=1` no pertenece a ningun Site y `page.url` es None.
        root = Site.objects.get(is_default_site=True).root_page
        self.index = BlogIndexPage(title="Blogs", slug="blogs-userbar")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()

        self.articulo = ArticuloPage(
            title="Un articulo", slug="un-articulo", date="2026-09-05", intro="x"
        )
        self.index.add_child(instance=self.articulo)
        self.articulo.save_revision().publish()

        self.editor = User.objects.create_superuser(
            email="editor@example.com", password="x123456789"
        )

    def _get(self, page):
        return self.client.get(page.url)

    def test_anonimo_ve_por_donde_entrar(self):
        """Lo que faltaba: sin esto el profesor no tenia ningun enlace."""
        html = self._get(self.articulo).content.decode()
        self.assertIn("/accounts/login/", html)
        self.assertIn("Entrar", html)

    def test_anonimo_no_ve_el_userbar(self):
        self.assertNotIn("wagtail-userbar", self._get(self.articulo).content.decode())

    def test_editor_logueado_ve_el_userbar(self):
        """El pajarito. Es el criterio de verdad de todo este arreglo."""
        self.client.force_login(self.editor)
        self.assertIn("wagtail-userbar", self._get(self.articulo).content.decode())

    def test_editor_logueado_ve_el_enlace_al_cms_en_vez_de_entrar(self):
        self.client.force_login(self.editor)
        html = self._get(self.articulo).content.decode()
        self.assertIn('href="/cms/"', html)
        self.assertNotIn("/accounts/login/", html)

    def test_tambien_en_el_indice_no_solo_en_el_articulo(self):
        """Los dos templates de blogs extienden el mismo base; que se note."""
        self.client.force_login(self.editor)
        self.assertIn("wagtail-userbar", self._get(self.index).content.decode())
