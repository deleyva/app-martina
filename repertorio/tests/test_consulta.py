"""La caja de texto: qué entiende y qué deja pasar como texto libre."""

from django.test import SimpleTestCase

from repertorio.consulta import interpretar_consulta


class InterpretarConsultaTest(SimpleTestCase):
    def test_decada_y_acordes(self):
        filtros, chips, resto = interpretar_consulta("de los 70 con 3 acordes")
        self.assertEqual(filtros["decada"], [1970])
        self.assertEqual(filtros["num_acordes"], [3])
        self.assertEqual(resto, "")

    def test_el_relleno_no_acaba_en_la_busqueda_de_texto(self):
        """«dame una canción de…» no puede buscarse literalmente."""
        _, _, resto = interpretar_consulta("dame una canción de los 70 con 3 acordes")
        self.assertEqual(resto, "")

    def test_tres_acordes_no_se_lee_como_año(self):
        filtros, _, _ = interpretar_consulta("3 acordes")
        self.assertNotIn("decada", filtros)
        self.assertEqual(filtros["num_acordes"], [3])

    def test_numeros_en_palabra(self):
        filtros, _, _ = interpretar_consulta("dos acordes")
        self.assertEqual(filtros["num_acordes"], [2])

    def test_comparadores(self):
        self.assertEqual(interpretar_consulta("menos de 4 acordes")[0]["num_acordes_max"], 3)
        self.assertEqual(interpretar_consulta("hasta 3 acordes")[0]["num_acordes_max"], 3)
        self.assertEqual(interpretar_consulta("al menos 4 acordes")[0]["num_acordes_min"], 4)
        self.assertEqual(interpretar_consulta("más de 4 acordes")[0]["num_acordes_min"], 5)

    def test_formas_de_escribir_la_decada(self):
        for frase in ["años 90", "los 90", "90s", "1990", "1995", "década de los 90"]:
            with self.subTest(frase=frase):
                self.assertEqual(interpretar_consulta(frase)[0]["decada"], [1990])

    def test_dos_cifras_del_siglo_XXI(self):
        """«los 20» es 2020, no 1920: es la lectura natural hoy."""
        self.assertEqual(interpretar_consulta("los 20")[0]["decada"], [2020])
        self.assertEqual(interpretar_consulta("los 10")[0]["decada"], [2010])

    def test_instrumento_idioma_y_nivel(self):
        filtros, _, resto = interpretar_consulta("ukelele fácil en español")
        self.assertEqual(filtros["instrumento"], ["Ukulele"])
        self.assertEqual(filtros["idioma"], ["spanish"])
        self.assertEqual(filtros["nivel"], ["Beginner"])
        self.assertEqual(resto, "")

    def test_sin_tildes_tambien(self):
        filtros, _, _ = interpretar_consulta("facil en ingles con bateria")
        self.assertEqual(filtros["nivel"], ["Beginner"])
        self.assertEqual(filtros["idioma"], ["english"])
        self.assertEqual(filtros["instrumento"], ["Drums"])

    def test_curso_y_favoritas(self):
        filtros, _, _ = interpretar_consulta("para 1º ESO favoritas")
        self.assertEqual(filtros["curso"], ["1eso"])
        self.assertTrue(filtros["favorito"])

    def test_lo_que_no_entiende_va_a_texto_libre(self):
        filtros, chips, resto = interpretar_consulta("bamba")
        self.assertEqual(filtros, {})
        self.assertEqual(chips, [])
        self.assertEqual(resto, "bamba")

    def test_vacio(self):
        self.assertEqual(interpretar_consulta(""), ({}, [], ""))
        self.assertEqual(interpretar_consulta("   "), ({}, [], ""))

    def test_cada_filtro_deja_su_chip(self):
        _, chips, _ = interpretar_consulta("de los 70 con 3 acordes al ukelele")
        claves = {c["clave"] for c in chips}
        self.assertEqual(claves, {"decada", "num_acordes", "instrumento"})


class ProgresionEnLaCajaTest(SimpleTestCase):
    """La progresión escrita en la caja, conviviendo con los demás filtros."""

    def test_sola(self):
        filtros, chips, resto = interpretar_consulta("progresión I-V-vi-IV")
        self.assertEqual(filtros["progresion"], ["I-V-vi-IV"])
        self.assertEqual(resto, "")

    def test_junto_a_decada_e_instrumento(self):
        filtros, _, resto = interpretar_consulta("I-V-vi-IV de los 90 al ukelele")
        self.assertEqual(filtros["progresion"], ["I-V-vi-IV"])
        self.assertEqual(filtros["decada"], [1990])
        self.assertEqual(filtros["instrumento"], ["Ukulele"])
        self.assertEqual(resto, "")

    def test_el_blues_de_12_compases_no_se_come_la_decada(self):
        """El 12 del blues no puede leerse como una década."""
        filtros, _, _ = interpretar_consulta("blues de 12 compases de los 60")
        self.assertEqual(filtros["progresion"], ["12 Bar Blues"])
        self.assertEqual(filtros["decada"], [1960])

    def test_los_numeros_de_acordes_siguen_funcionando(self):
        filtros, _, _ = interpretar_consulta("I-IV-V con 3 acordes")
        self.assertEqual(filtros["progresion"], ["I-IV-V"])
        self.assertEqual(filtros["num_acordes"], [3])


class TonalidadEnLaCajaTest(SimpleTestCase):
    def test_nota_en_castellano(self):
        filtros, _, resto = interpretar_consulta("en sol")
        self.assertEqual(filtros["tonalidad"], ["G"])
        self.assertEqual(resto, "")

    def test_junto_a_otros_filtros(self):
        filtros, _, _ = interpretar_consulta("de los 80 al ukelele en la menor")
        self.assertEqual(filtros["tonalidad"], ["Ami"])
        self.assertEqual(filtros["decada"], [1980])
        self.assertEqual(filtros["instrumento"], ["Ukulele"])

    def test_modo_suelto(self):
        filtros, _, _ = interpretar_consulta("algo fácil en menor")
        self.assertEqual(filtros["modo"], ["menor"])
        self.assertEqual(filtros["nivel"], ["Beginner"])

    def test_la_bamba_sigue_siendo_una_busqueda_de_texto(self):
        filtros, _, resto = interpretar_consulta("la bamba")
        self.assertNotIn("tonalidad", filtros)
        self.assertEqual(resto, "bamba")
