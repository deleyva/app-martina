"""Quién entra al catálogo y qué se lleva de vuelta."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from repertorio.tests.test_importador import DOC, RUTA
from django.core.management import call_command

Usuario = get_user_model()


class AccesoTest(TestCase):
    def setUp(self):
        self.url = reverse("repertorio:catalogo")

    def test_anonimo_no_entra(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("login", respuesta["Location"])

    def test_alumno_no_entra(self):
        alumno = Usuario.objects.create_user(email="alumna@local.test", password="x")
        self.client.force_login(alumno)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)

    def test_profesor_entra(self):
        profe = Usuario.objects.create_user(
            email="profe@local.test", password="x", is_staff=True
        )
        self.client.force_login(profe)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Catálogo de repertorio")


class ConsultaEnLaVistaTest(TestCase):
    def setUp(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.profe = Usuario.objects.create_user(
            email="profe2@local.test", password="x", is_staff=True
        )
        self.client.force_login(self.profe)
        self.url = reverse("repertorio:catalogo")

    def test_la_caja_de_texto_filtra(self):
        respuesta = self.client.get(self.url, {"q": "de los 70 con 3 acordes"})
        self.assertContains(respuesta, "Jolene")
        self.assertContains(respuesta, "años 1970")
        self.assertContains(respuesta, "3 acordes")

    def test_una_consulta_que_no_casa_no_devuelve_nada(self):
        respuesta = self.client.get(self.url, {"q": "de los 90 con 5 acordes"})
        self.assertNotContains(respuesta, "Jolene")

    def test_htmx_devuelve_solo_el_panel(self):
        respuesta = self.client.get(self.url, {"q": "jolene"}, HTTP_HX_REQUEST="true")
        self.assertContains(respuesta, 'id="panel"')
        self.assertNotContains(respuesta, "<html")

    def test_acepta_el_parametro_repetido_y_el_separado_por_comas(self):
        """HTMX puede mandar el mismo valor dos veces; no puede cambiar el resultado."""
        una = self.client.get(self.url, {"acordes": "3"})
        repetida = self.client.get(self.url, {"acordes": ["3", "3"]})
        self.assertEqual(una.context["total"], repetida.context["total"])
        coma = self.client.get(self.url, {"acordes": "3,4"})
        self.assertEqual(coma.context["total"], 1)
