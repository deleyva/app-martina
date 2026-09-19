"""Lo corregido a mano manda sobre lo que traiga JamZone."""

from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage

from repertorio.admin import CancionAdmin
from repertorio.models import Cancion, Sincronizacion
from repertorio.tests.test_importador import DOC, RUTA

Usuario = get_user_model()


class FormaFalsa:
    """Un formulario de mentira. `save_model` ya no lo mira: compara contra la
    base. Se mantiene para probar que da igual lo que diga `changed_data`."""

    def __init__(self, changed_data):
        self.changed_data = changed_data


class CorreccionesTest(TestCase):
    def setUp(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.cancion = Cancion.objects.get()

    def test_un_campo_corregido_sobrevive_a_la_reimportacion(self):
        """El caso real: un vídeo que en origen viene ilegible."""
        self.cancion.youtube_id = "aaaaaaaaaaa"
        self.cancion.bloquear(["youtube_id"])
        self.cancion.save()

        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")

        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.youtube_id, "aaaaaaaaaaa")

    def test_lo_no_corregido_sigue_actualizandose(self):
        self.cancion.youtube_id = "aaaaaaaaaaa"
        self.cancion.bloquear(["youtube_id"])
        self.cancion.save()

        with patch(RUTA, return_value=[dict(DOC, tempo=99)]):
            call_command("importar_jamzone")

        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.youtube_id, "aaaaaaaaaaa", "lo bloqueado se respeta")
        self.assertEqual(self.cancion.tempo, 99, "lo demás se sigue actualizando")

    def test_soltar_la_correccion_devuelve_el_mando_a_jamzone(self):
        self.cancion.youtube_id = "aaaaaaaaaaa"
        self.cancion.bloquear(["youtube_id"])
        self.cancion.save()

        Cancion.objects.update(bloqueados=[])
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")

        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.youtube_id, DOC["musicVideo"])

    def test_solo_se_pueden_bloquear_campos_importados(self):
        nuevos = self.cancion.bloquear(["youtube_id", "notas", "inventado"])
        self.assertEqual(nuevos, ["youtube_id"])

    def test_el_informe_cuenta_los_campos_respetados(self):
        self.cancion.bloquear(["youtube_id", "tempo"])
        self.cancion.save()
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.assertEqual(Sincronizacion.ultima().campos_respetados, 2)


class AdminBloqueaSoloTest(TestCase):
    """Editar en el admin tiene que bloquear sin que haya que marcar nada."""

    def setUp(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.cancion = Cancion.objects.get()
        self.admin = CancionAdmin(Cancion, AdminSite())
        self.peticion = RequestFactory().post("/")
        self.peticion.user = Usuario.objects.create_user(
            email="a@local.test", password="x", is_staff=True, is_superuser=True
        )
        self.peticion.session = {}
        self.peticion._messages = FallbackStorage(self.peticion)

    def test_editar_un_id_lo_bloquea(self):
        self.cancion.youtube_id = "bbbbbbbbbbb"
        self.admin.save_model(self.peticion, self.cancion, FormaFalsa([]), change=True)
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.bloqueados, ["youtube_id"])

    def test_editar_las_notas_no_bloquea_nada(self):
        """Las notas ya están siempre protegidas; no hace falta marcarlas."""
        self.cancion.notas = "hola"
        self.admin.save_model(self.peticion, self.cancion, FormaFalsa([]), change=True)
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.bloqueados, [])

    def test_crear_una_cancion_propia_no_bloquea_nada(self):
        nueva = Cancion(origen=Cancion.PROPIO, titulo="Mía")
        self.admin.save_model(self.peticion, nueva, FormaFalsa([]), change=False)
        self.assertEqual(nueva.bloqueados, [])


class RegistroDeSincronizacionTest(TestCase):
    def test_se_registra_cada_importacion(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        registro = Sincronizacion.ultima()
        self.assertEqual(registro.recibidas, 1)
        self.assertEqual(registro.creadas, 1)
        self.assertFalse(registro.automatica)
        self.assertTrue(registro.ok)

    def test_el_simulacro_no_registra_nada(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone", "--dry-run")
        self.assertIsNone(Sincronizacion.ultima())

    def test_la_tarea_mensual_marca_la_sincronizacion_como_automatica(self):
        from repertorio.tasks import sincronizar_jamzone

        with patch(RUTA, return_value=[DOC]):
            sincronizar_jamzone.call_local()
        self.assertTrue(Sincronizacion.ultima().automatica)

    def test_si_la_descarga_falla_queda_registrado(self):
        from repertorio.tasks import sincronizar_jamzone

        with patch(RUTA, side_effect=RuntimeError("sin red")):
            sincronizar_jamzone.call_local()
        registro = Sincronizacion.ultima()
        self.assertEqual(registro.fallos, 1)
        self.assertFalse(registro.ok)


class AdminDeVerdadTest(TestCase):
    """Un POST real al formulario del admin, no un doble de pruebas."""

    def setUp(self):
        with patch(RUTA, return_value=[DOC]):
            call_command("importar_jamzone")
        self.cancion = Cancion.objects.get()
        self.jefe = Usuario.objects.create_superuser(email="jefe@local.test", password="x")
        self.client.force_login(self.jefe)
        self.url = f"/admin/repertorio/cancion/{self.cancion.pk}/change/"

    def _datos(self, **cambios):
        datos = {
            "origen": self.cancion.origen,
            "slug_externo": self.cancion.slug_externo,
            "titulo": self.cancion.titulo,
            "anio": self.cancion.anio,
            "num_acordes": self.cancion.num_acordes,
            "tempo": self.cancion.tempo,
            "progresion_romana": self.cancion.progresion_romana,
            "spotify_id": self.cancion.spotify_id,
            "youtube_id": self.cancion.youtube_id,
            "lyrics_url": self.cancion.lyrics_url,
            "forma": '["Verse", "Chorus"]',
            "dato": self.cancion.dato,
            "notas": self.cancion.notas,
            "cursos": "[]",
            "artistas": [a.pk for a in self.cancion.artistas.all()],
            "generos": [g.pk for g in self.cancion.generos.all()],
            "idiomas": [i.pk for i in self.cancion.idiomas.all()],
            "versiones-TOTAL_FORMS": "0",
            "versiones-INITIAL_FORMS": "0",
            "versiones-MIN_NUM_FORMS": "0",
            "versiones-MAX_NUM_FORMS": "1000",
        }
        if self.cancion.g_rated:
            datos["g_rated"] = "on"
        datos.update(cambios)
        return datos

    def test_guardar_un_id_corregido_lo_bloquea(self):
        respuesta = self.client.post(self.url, self._datos(youtube_id="dQw4w9WgXcQ"))
        self.assertEqual(respuesta.status_code, 302, "el admin debería redirigir tras guardar")
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.youtube_id, "dQw4w9WgXcQ")
        self.assertEqual(self.cancion.bloqueados, ["youtube_id"])

    def test_y_sobrevive_a_la_siguiente_importacion(self):
        """El recorrido entero: lo arreglo en el admin, reimporto, sigue arreglado."""
        self.client.post(self.url, self._datos(youtube_id="dQw4w9WgXcQ"))
        with patch(RUTA, return_value=[dict(DOC, musicVideo="")]):
            call_command("importar_jamzone")
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.youtube_id, "dQw4w9WgXcQ")

    def test_guardar_sin_cambiar_nada_no_bloquea(self):
        self.client.post(self.url, self._datos())
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.bloqueados, [])
