"""Tonalidades: lectura en castellano, modo, y que el filtro mire la misma versión."""

from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from repertorio import tonalidades
from repertorio.models import Cancion
from repertorio.tests.test_importador import DOC, RUTA


class NombreTest(SimpleTestCase):
    def test_castellano(self):
        casos = {
            "G": "Sol",
            "C": "Do",
            "Ami": "La menor",
            "E♭": "Mi bemol",
            "C#mi": "Do sostenido menor",
            "B♭mi": "Si bemol menor",
            "F#": "Fa sostenido",
        }
        for cifrado, esperado in casos.items():
            with self.subTest(cifrado=cifrado):
                self.assertEqual(tonalidades.nombre(cifrado), esperado)

    def test_etiqueta_lleva_las_dos_formas(self):
        self.assertEqual(tonalidades.etiqueta("Ami"), "La menor · Ami")

    def test_es_menor(self):
        self.assertTrue(tonalidades.es_menor("Ami"))
        self.assertTrue(tonalidades.es_menor("E♭mi"))
        self.assertFalse(tonalidades.es_menor("A"))
        self.assertFalse(tonalidades.es_menor(""))

    def test_lo_que_no_reconoce_lo_devuelve_tal_cual(self):
        self.assertEqual(tonalidades.nombre("H"), "H")


class DesdeTextoTest(SimpleTestCase):
    def test_notas_en_castellano(self):
        casos = {
            "en sol": "G",
            "en do": "C",
            "en la menor": "Ami",
            "en mi bemol": "E♭",
            "en do sostenido menor": "C#mi",
            "en re mayor": "D",
        }
        for frase, esperado in casos.items():
            with self.subTest(frase=frase):
                self.assertEqual(tonalidades.desde_texto(frase)[0], esperado)

    def test_cifrado_anglosajon(self):
        self.assertEqual(tonalidades.desde_texto("en C")[0], "C")
        self.assertEqual(tonalidades.desde_texto("en Ami de los 90")[0], "Ami")
        self.assertEqual(tonalidades.desde_texto("en G al ukelele")[0], "G")

    def test_la_alteracion_no_se_pierde(self):
        """`E♭\\b` fallaba porque el bemol no es carácter de palabra."""
        self.assertEqual(tonalidades.desde_texto("en E♭")[0], "E♭")
        self.assertEqual(tonalidades.desde_texto("en Bb")[0], "B♭")

    def test_no_confunde_articulos_con_notas(self):
        """«la» y «mi» son palabras corrientes: sin modificador ni final, no cuentan."""
        for frase in ["la bamba", "canciones en la bamba", "yo vi algo en mi casa"]:
            with self.subTest(frase=frase):
                self.assertIsNone(tonalidades.desde_texto(frase)[0])

    def test_modo_suelto(self):
        self.assertEqual(tonalidades.modo_desde_texto("algo en menor"), "menor")
        self.assertEqual(tonalidades.modo_desde_texto("quiero mayores"), "mayor")
        self.assertIsNone(tonalidades.modo_desde_texto("en sol"))


class FiltroDeTonalidadTest(TestCase):
    """La tonalidad es de la versión, y eso tiene consecuencias."""

    def setUp(self):
        doc = dict(
            DOC,
            _id="t1",
            title="Dos tonalidades",
            slug="dos",
            charts=[
                {
                    "version": "original",
                    "nivel": "Advanced",
                    "tonalidad": "B♭mi",
                    "acordes": ["B♭mi"],
                    "instrumentos": [{"nombre": "Guitar"}],
                },
                {
                    "version": "transposed",
                    "nivel": "Beginner",
                    "tonalidad": "C",
                    "acordes": ["C"],
                    "instrumentos": [{"nombre": "Ukulele"}],
                },
            ],
        )
        with patch(RUTA, return_value=[doc]):
            call_command("importar_jamzone")

    def test_encuentra_por_cualquiera_de_las_dos(self):
        self.assertTrue(Cancion.buscar(tonalidad=["B♭mi"]).exists())
        self.assertTrue(Cancion.buscar(tonalidad=["C"]).exists())

    def test_instrumento_y_tonalidad_van_contra_la_misma_version(self):
        """El ukelele existe en Do, no en Si bemol menor. No puede salir."""
        self.assertTrue(Cancion.buscar(instrumento=["Ukulele"], tonalidad=["C"]).exists())
        self.assertFalse(Cancion.buscar(instrumento=["Ukulele"], tonalidad=["B♭mi"]).exists())

    def test_el_modo_tambien_va_contra_la_misma_version(self):
        self.assertTrue(Cancion.buscar(instrumento=["Guitar"], modo=["menor"]).exists())
        self.assertFalse(Cancion.buscar(instrumento=["Ukulele"], modo=["menor"]).exists())

    def test_el_modo_se_marca_al_importar(self):
        cancion = Cancion.objects.get(fuente_id="t1")
        modos = {v.tonalidad: v.es_menor for v in cancion.versiones.all()}
        self.assertEqual(modos, {"B♭mi": True, "C": False})

    def test_las_facetas_traen_las_dos_tonalidades_y_los_dos_modos(self):
        facetas = Cancion.facetas({})
        self.assertEqual(
            sorted(f["valor"] for f in facetas["tonalidades"]), ["B♭mi", "C"]
        )
        self.assertEqual({m["valor"]: m["total"] for m in facetas["modos"]}, {"mayor": 1, "menor": 1})
