"""Los dos invariantes de la importación, que son donde esto se rompería en silencio."""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from repertorio.models import Cancion, Version

DOC = {
    "_id": "abc123",
    "title": "Jolene",
    "slug": "jolene",
    "releaseYear": 1973,
    "numberOfChords": 3,
    "tempo": 110,
    "chordProgression": "i-III-VII",
    "gRated": True,
    "spotifyId": "4DHcnVTT87F0zZhRPYmZ3B",
    "musicVideo": "Ixrje2rXLMA",
    "songLyrics": "https://example.org/letra",
    "forma": ["Verse", "Chorus"],
    "dato": "Un dato.",
    "artistas": ["Dolly Parton"],
    "generos": ["Country"],
    "idiomas": ["English"],
    "charts": [
        {
            "version": "original",
            "nivel": "Intermediate",
            "tonalidad": "Ami",
            "acordes": ["Ami", "C", "G"],
            "instrumentos": [{"nombre": "Guitar"}, {"nombre": "Ukulele"}],
        },
        {
            "version": "transposed",
            "nivel": "Beginner",
            "tonalidad": "Emi",
            "acordes": ["Emi", "G", "D"],
            "instrumentos": [{"nombre": "Ukulele"}],
        },
    ],
}

RUTA = "repertorio.management.commands.importar_jamzone.descargar"


class ImportadorTest(TestCase):
    def test_importa_y_es_idempotente(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.assertEqual(Cancion.objects.count(), 1)
        self.assertEqual(Version.objects.count(), 2)

        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.assertEqual(Cancion.objects.count(), 1, "reimportar no puede duplicar")
        self.assertEqual(Version.objects.count(), 2)

    def test_la_decada_se_deriva_del_año(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.assertEqual(Cancion.objects.get().decada, 1970)

    def test_reimportar_no_pisa_los_campos_propios(self):
        """El test que evita la pérdida silenciosa de las notas de clase."""
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")

        cancion = Cancion.objects.get()
        cancion.notas = "La monté con 3º y funcionó."
        cancion.cursos = ["3eso"]
        cancion.favorito = True
        cancion.save()

        cambiado = dict(DOC, tempo=120)
        with patch(RUTA, return_value=[cambiado]):
            call_command("importar_jamzone")

        cancion.refresh_from_db()
        self.assertEqual(cancion.tempo, 120, "lo de JamZone sí se actualiza")
        self.assertEqual(cancion.notas, "La monté con 3º y funcionó.")
        self.assertEqual(cancion.cursos, ["3eso"])
        self.assertTrue(cancion.favorito)

    def test_no_toca_las_canciones_propias(self):
        propia = Cancion.objects.create(
            origen=Cancion.PROPIO, titulo="La flaca", anio=1996, notas="mía"
        )
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        propia.refresh_from_db()
        self.assertEqual(propia.titulo, "La flaca")
        self.assertEqual(propia.notas, "mía")
        self.assertEqual(Cancion.objects.filter(origen=Cancion.PROPIO).count(), 1)

    def test_dry_run_no_escribe(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone", "--dry-run")
        self.assertEqual(Cancion.objects.count(), 0)


class BuscarTest(TestCase):
    def setUp(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")

    def test_la_consulta_de_aceptacion(self):
        """«de los 70 con 3 acordes» tiene que encontrar Jolene."""
        encontradas = Cancion.buscar(decada=[1970], num_acordes=[3])
        self.assertEqual([c.titulo for c in encontradas], ["Jolene"])

    def test_instrumento_y_nivel_van_contra_la_misma_version(self):
        """Ukelele + principiante existe (la transpuesta); guitarra + principiante no."""
        self.assertTrue(Cancion.buscar(instrumento=["Ukulele"], nivel=["Beginner"]).exists())
        self.assertFalse(Cancion.buscar(instrumento=["Guitar"], nivel=["Beginner"]).exists())

    def test_facetas_cuentan(self):
        facetas = Cancion.facetas({"decada": [1970]})
        acordes = {f["valor"]: f["total"] for f in facetas["acordes"]}
        self.assertEqual(acordes.get(3), 1)


class NormalizarIdentificadoresTest(TestCase):
    """Los datos de origen vienen sucios; la limpieza es parte del contrato."""

    def test_spotify(self):
        from repertorio.management.commands.importar_jamzone import _spotify_id

        self.assertEqual(
            _spotify_id("https://open.spotify.com/track/7ByxizhA4GgEf7Sxomxhze?si=45fc"),
            "7ByxizhA4GgEf7Sxomxhze",
        )
        self.assertEqual(
            _spotify_id("6KmPsYpaZzZBCXPmiVdiCB?si=b3ab1c99802142d7"),
            "6KmPsYpaZzZBCXPmiVdiCB",
        )
        self.assertEqual(_spotify_id("6XXxKsu3RJeN3ZvbMYrgQW"), "6XXxKsu3RJeN3ZvbMYrgQW")
        self.assertEqual(_spotify_id(None), "")
        self.assertEqual(_spotify_id("no-es-un-id"), "")

    def test_youtube(self):
        from repertorio.management.commands.importar_jamzone import _youtube_id

        self.assertEqual(_youtube_id("watch?v=2azy1D-yyWc"), "2azy1D-yyWc")
        self.assertEqual(_youtube_id("https://youtu.be/7V3jqsIe8c0"), "7V3jqsIe8c0")
        self.assertEqual(_youtube_id("hhKNjTb6U1Y"), "hhKNjTb6U1Y")
        self.assertEqual(
            _youtube_id("fEsqGblZQMXql3Tu"), "", "lo que no es un ID válido no se guarda"
        )
        self.assertEqual(_youtube_id(None), "")


class VariosValoresTest(TestCase):
    """Marcar dos instrumentos pide los dos, no cualquiera de los dos."""

    def setUp(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")

    def test_dos_instrumentos_es_una_Y(self):
        # La versión original tiene guitarra y ukelele; la fácil solo ukelele.
        self.assertTrue(
            Cancion.buscar(instrumento=["Guitar", "Ukulele"]).exists(),
            "la versión original tiene las dos",
        )
        self.assertFalse(
            Cancion.buscar(instrumento=["Guitar", "Bass"]).exists(),
            "ninguna versión tiene guitarra y bajo a la vez",
        )

    def test_dos_cursos_es_una_Y(self):
        cancion = Cancion.objects.get()
        cancion.cursos = ["3eso"]
        cancion.save()
        self.assertTrue(Cancion.buscar(curso=["3eso"]).exists())
        self.assertFalse(Cancion.buscar(curso=["3eso", "4eso"]).exists())


class EntidadesHtmlTest(TestCase):
    """Los datos de origen traen «&amp;» en crudo; no puede llegar a pantalla."""

    def test_se_deshacen_en_titulo_y_artista(self):
        doc = dict(
            DOC,
            _id="ent1",
            title="Jungle Boogie &amp; More",
            artistas=["Kool &amp; The Gang"],
            dato="Un &quot;dato&quot;.",
        )
        with patch(RUTA, return_value=[doc]):
            call_command("importar_jamzone")
        cancion = Cancion.objects.get(fuente_id="ent1")
        self.assertEqual(cancion.titulo, "Jungle Boogie & More")
        self.assertEqual(cancion.artistas.first().nombre, "Kool & The Gang")
        self.assertEqual(cancion.dato, 'Un "dato".')


class VocabularioHuerfanoTest(TestCase):
    def test_se_borra_el_artista_que_ya_no_cuelga_de_nada(self):
        from repertorio.models import Artista

        Artista.objects.create(nombre="Fantasma", slug="fantasma")
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.assertFalse(Artista.objects.filter(nombre="Fantasma").exists())
        self.assertTrue(Artista.objects.filter(nombre="Dolly Parton").exists())
