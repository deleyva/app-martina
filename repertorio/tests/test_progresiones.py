"""Normalización de progresiones: los giros, los inventarios y el texto libre."""

from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from repertorio import progresiones
from repertorio.models import Cancion
from repertorio.tests.test_importador import DOC, RUTA


class FamiliaTest(SimpleTestCase):
    def test_los_giros_caen_en_la_misma_familia(self):
        """Es la misma progresión empezada en otro sitio."""
        for giro in ["I-V-vi-IV", "V-vi-IV-I", "vi-IV-I-V", "IV-I-V-vi"]:
            with self.subTest(giro=giro):
                self.assertEqual(progresiones.familia(giro), "I-V-vi-IV")

    def test_progresiones_distintas_no_se_mezclan(self):
        """La de los cuatro acordes y el doo-wop de los 50 no son la misma."""
        self.assertNotEqual(
            progresiones.familia("I-V-vi-IV"), progresiones.familia("I-vi-IV-V")
        )

    def test_el_inventario_de_acordes_no_es_una_progresion(self):
        """«Beat It» trae esto y solo tiene tres acordes."""
        for inventario in [
            "I-ii-iii-IV-V-vi",
            "I-ii-iii-IV-V-vi-vv",
            "i-ii*-III-iv-v-VI",
            "I-ii-III-IV-V-vi",
        ]:
            with self.subTest(inventario=inventario):
                self.assertEqual(progresiones.familia(inventario), "")

    def test_cuatro_grados_ascendentes_si_son_progresion(self):
        """El corte está en cinco: I-ii-iii-IV es corta y puede ser música."""
        self.assertEqual(progresiones.familia("I-ii-iii-IV"), "I-ii-iii-IV")

    def test_las_etiquetas_se_respetan(self):
        self.assertEqual(progresiones.familia("12 Bar Blues"), "12 Bar Blues")
        self.assertEqual(progresiones.familia("I-V/V-IV-iv"), "I-V/V-IV-iv")

    def test_los_destrozos_del_origen_se_deshacen(self):
        """En Sanity el vii° viaja como `vv` y el ii° como `ii*`."""
        self.assertEqual(progresiones.tokens("I-vv"), ["I", "vii°"])
        self.assertEqual(progresiones.tokens("i-ii*"), ["i", "ii°"])

    def test_vacio(self):
        self.assertEqual(progresiones.familia(""), "")
        self.assertEqual(progresiones.familia(None), "")
        self.assertEqual(progresiones.familia("---"), "")

    def test_nombre_amistoso_solo_cuando_existe(self):
        self.assertIn("cuatro acordes", progresiones.etiqueta("I-V-vi-IV"))
        self.assertEqual(progresiones.etiqueta("I-ii-vi-IV"), "I-ii-vi-IV")


class DesdeTextoTest(SimpleTestCase):
    def test_reconoce_una_progresion_escrita(self):
        self.assertEqual(progresiones.desde_texto("con la progresión I-V-vi-IV")[0], "I-V-vi-IV")

    def test_acepta_guiones_largos(self):
        self.assertEqual(progresiones.desde_texto("canciones I–V–vi–IV")[0], "I-V-vi-IV")

    def test_un_giro_escrito_a_mano_tambien_se_pliega(self):
        self.assertEqual(progresiones.desde_texto("vi-IV-I-V al ukelele")[0], "I-V-vi-IV")

    def test_IV_no_se_lee_como_I(self):
        """Con `I` antes que `IV` en el patrón, esto daba «I-V-vi-I»."""
        self.assertEqual(progresiones.desde_texto("I-V-vi-IV")[0], "I-V-vi-IV")

    def test_el_blues_de_doce_compases_por_su_nombre(self):
        for frase in ["blues de 12 compases", "12 bar blues", "blues de doce compases"]:
            with self.subTest(frase=frase):
                self.assertEqual(progresiones.desde_texto(frase)[0], "12 Bar Blues")

    def test_no_dispara_con_texto_normal(self):
        self.assertEqual(progresiones.desde_texto("yo vi una canción")[0], None)
        self.assertEqual(progresiones.desde_texto("de los 70 con 3 acordes")[0], None)

    def test_un_inventario_escrito_no_cuenta(self):
        self.assertEqual(progresiones.desde_texto("I-ii-iii-IV-V-vi")[0], None)


class FiltroDeProgresionTest(TestCase):
    def setUp(self):
        docs = [
            dict(DOC, _id="p1", title="Cuatro acordes", slug="a", chordProgression="I-V-vi-IV"),
            dict(DOC, _id="p2", title="El mismo giro", slug="b", chordProgression="vi-IV-I-V"),
            dict(DOC, _id="p3", title="Doo-wop", slug="c", chordProgression="I-vi-IV-V"),
            dict(DOC, _id="p4", title="Inventario", slug="d", chordProgression="I-ii-iii-IV-V-vi"),
        ]
        with patch(RUTA, return_value=docs):
            call_command("importar_jamzone")

    def test_la_familia_se_calcula_al_importar(self):
        self.assertEqual(
            Cancion.objects.get(fuente_id="p2").progresion_familia, "I-V-vi-IV"
        )

    def test_filtrar_por_familia_trae_los_giros(self):
        titulos = sorted(c.titulo for c in Cancion.buscar(progresion=["I-V-vi-IV"]))
        self.assertEqual(titulos, ["Cuatro acordes", "El mismo giro"])

    def test_el_inventario_se_queda_fuera(self):
        self.assertEqual(Cancion.objects.get(fuente_id="p4").progresion_familia, "")
        familias = [f["valor"] for f in Cancion.facetas({})["progresiones"]]
        self.assertNotIn("I-ii-iii-IV-V-vi", familias)

    def test_la_faceta_cuenta_los_giros_juntos(self):
        facetas = {f["valor"]: f["total"] for f in Cancion.facetas({})["progresiones"]}
        self.assertEqual(facetas["I-V-vi-IV"], 2)
        self.assertEqual(facetas["I-vi-IV-V"], 1)
