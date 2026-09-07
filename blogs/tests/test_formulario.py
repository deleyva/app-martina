"""Lo que un profesor ve al abrir el editor de un blog de departamento.

Los blogs y la biblioteca musical salieron del mismo modelo, y el formulario
seguía arrastrando piezas del otro lado: un desplegable para vincular el
departamento con una asignatura de `clases`, y un texto de ayuda que prometía
un botón de librería que en un blog no existe.

Estas pruebas miran el formulario renderizado, no el modelo, porque el problema
era justamente lo que se pintaba en pantalla.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page

from blogs.models import ArticuloPage, BlogIndexPage

User = get_user_model()


class FormularioDeBlogTest(TestCase):
    def setUp(self):
        root = Page.objects.filter(depth=1).first()
        self.portada = BlogIndexPage(title="Blogs", slug="blogs-form-test")
        root.add_child(instance=self.portada)
        self.departamento = BlogIndexPage(title="Filosofía", slug="filosofia-form-test")
        self.portada.add_child(instance=self.departamento)
        self.articulo = ArticuloPage(
            title="Un artículo", slug="un-articulo-form-test",
            date="2026-09-07", intro="Resumen",
        )
        self.departamento.add_child(instance=self.articulo)

        self.user = User.objects.create_superuser(
            email="formulario-admin@example.com",
            password="testpassword123",
        )
        self.client.force_login(self.user)

    def test_el_modelo_ya_no_tiene_asignatura(self):
        with self.assertRaises(FieldDoesNotExist):
            BlogIndexPage._meta.get_field("subject")

    def test_el_editor_de_un_departamento_no_ofrece_asignatura(self):
        respuesta = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.departamento.id])
        )
        self.assertEqual(respuesta.status_code, 200)
        # El panel «Departamento» sigue ahí; lo que se va es el desplegable.
        self.assertContains(respuesta, "Encargado/a")
        self.assertNotContains(respuesta, "Asignatura")
        self.assertNotContains(respuesta, "hereda icono y color")

    def test_los_adjuntos_no_prometen_una_libreria_que_no_hay(self):
        respuesta = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.articulo.id])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Archivos adjuntos")
        self.assertNotContains(respuesta, "botón de librería")
        self.assertNotContains(respuesta, "librería")


class SalidaEnLaMenchetaTest(TestCase):
    """Poder salir. Sin esto, quien entra en el subdominio de blogs se queda
    dentro: la cookie es host-only y en `blogs.` no había ningún enlace de
    logout, ni en el pie ni en ningún sitio.
    """

    def setUp(self):
        from wagtail.models import Site

        root = Site.objects.get(is_default_site=True).root_page
        self.index = BlogIndexPage(title="Blogs", slug="blogs-salida")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()

        self.user = User.objects.create_user(
            email="profe-salida@example.com", password="testpassword123"
        )

    def test_quien_tiene_sesion_ve_por_donde_salir(self):
        self.client.force_login(self.user)
        html = self.client.get(self.index.url).content.decode()
        self.assertIn("/accounts/logout/", html)
        self.assertIn("Salir", html)
        # Y sigue viendo su acceso al panel, no el de entrar.
        self.assertIn('href="/cms/"', html)

    def test_el_anonimo_no_ve_salir_sino_entrar(self):
        html = self.client.get(self.index.url).content.decode()
        self.assertNotIn("/accounts/logout/", html)
        self.assertIn("/accounts/login/", html)

    def test_se_ve_con_que_cuenta_estas_dentro(self):
        self.client.force_login(self.user)
        html = self.client.get(self.index.url).content.decode()
        self.assertIn("profe-salida@example.com", html)
