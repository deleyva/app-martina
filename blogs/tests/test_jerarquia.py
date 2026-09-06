"""El árbol de blogs tiene dos niveles, y el panel de Wagtail lo respeta.

`subpage_types` no puede expresar esta regla porque la portada y el departamento
son el MISMO modelo: la portada necesita admitir `BlogIndexPage` para tener
departamentos colgando, y el departamento se encuentra esa declaración heredada.
Los permisos tampoco sirven: `add_page` autoriza un sitio del árbol, no un tipo
de página.

La expresa `BlogIndexPage.can_create_at()`, y aquí se prueba en los dos sitios
donde Wagtail la consulta —`wagtail/admin/views/pages/create.py`, líneas 53 y
110—: al construir el menú de tipos y al abrir el formulario por URL directa.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page

from blogs.models import ArticuloPage, BlogIndexPage

User = get_user_model()


class ArbolMixin:
    """Raíz de Wagtail -> portada -> departamento. Los tres niveles reales."""

    def _montar_arbol(self):
        self.root = Page.objects.filter(depth=1).first()
        self.portada = BlogIndexPage(title="Blogs", slug="blogs-portada-test")
        self.root.add_child(instance=self.portada)
        self.departamento = BlogIndexPage(title="Filosofía", slug="filosofia-test")
        self.portada.add_child(instance=self.departamento)


class JerarquiaDeBlogsTest(ArbolMixin, TestCase):
    """La regla, a nivel de modelo."""

    def setUp(self):
        self._montar_arbol()

    def test_la_portada_puede_crearse_bajo_la_raiz(self):
        self.assertTrue(BlogIndexPage.can_create_at(self.root))

    def test_un_departamento_puede_crearse_bajo_la_portada(self):
        self.assertTrue(BlogIndexPage.can_create_at(self.portada))

    def test_un_blog_no_puede_crearse_bajo_un_departamento(self):
        self.assertFalse(BlogIndexPage.can_create_at(self.departamento))

    def test_un_articulo_si_puede_crearse_bajo_un_departamento(self):
        self.assertTrue(ArticuloPage.can_create_at(self.departamento))


class AdminDeBlogsTest(ArbolMixin, TestCase):
    """La regla, tal y como la ve quien abre el panel."""

    def setUp(self):
        self._montar_arbol()
        self.user = User.objects.create_superuser(
            email="jerarquia-admin@example.com",
            password="testpassword123",
        )
        self.client.force_login(self.user)

    def test_en_un_departamento_ya_no_hay_pantalla_de_eleccion(self):
        # Al quedar un solo tipo posible, Wagtail se salta el menú y lleva
        # directo al formulario de artículo (`create.py:57`). Una pantalla menos
        # para el profesor que va a escribir.
        respuesta = self.client.get(
            reverse("wagtailadmin_pages:add_subpage", args=[self.departamento.id])
        )
        self.assertRedirects(
            respuesta,
            reverse(
                "wagtailadmin_pages:add",
                args=["blogs", "articulopage", self.departamento.id],
            ),
            fetch_redirect_response=False,
        )

    def test_la_portada_sigue_ofreciendo_los_dos_tipos(self):
        respuesta = self.client.get(
            reverse("wagtailadmin_pages:add_subpage", args=[self.portada.id])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Blog de departamento")
        self.assertContains(respuesta, "Artículo de departamento")

    def test_la_url_directa_del_formulario_esta_cerrada(self):
        # El menú se puede esquivar escribiendo la URL a mano. `create.py:110`
        # no: vuelve a preguntar por `can_create_at`. Wagtail no devuelve un 403
        # pelado en una petición normal —`wagtail/admin/auth.py:23` traduce el
        # `PermissionDenied` a un aviso y una vuelta al panel—, así que la
        # prueba mira las dos caras: adónde manda al humano y qué contesta a XHR.
        url = reverse(
            "wagtailadmin_pages:add",
            args=["blogs", "blogindexpage", self.departamento.id],
        )

        respuesta = self.client.get(url)
        self.assertRedirects(
            respuesta,
            reverse("wagtailadmin_home"),
            fetch_redirect_response=False,
        )

        # En XHR sí sale el 403, y eso confirma que lo que corta es el permiso
        # y no una redirección cualquiera.
        xhr = self.client.get(url, headers={"x-requested-with": "XMLHttpRequest"})
        self.assertEqual(xhr.status_code, 403)
