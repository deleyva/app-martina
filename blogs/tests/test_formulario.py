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
