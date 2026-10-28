"""Pistas de práctica del visor ChordPro (fase 82).

Fija cuatro cosas:

- El audio solo sale con sesión iniciada, por la vista, nunca por `/media/`
  (nginx cierra `/media/pistas_practica/`). Son grabaciones comerciales.
- Subir, cambiar y borrar es de quien puede editar la canción, como el ✎.
- Las marcas se validan en el modelo y se guardan ordenadas por tiempo.
- El alumno de una canción sin pistas no ve nada nuevo en el visor.
"""

import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.models import Site

from musica.models import MusicLibraryIndexPage, PistaDePractica, RecursoPage
from my_library.models import LibraryItem

User = get_user_model()

CHORDPRO = "{start_of_verse}\n[G]I found a [Em]love, for [C]me\n{end_of_verse}"
AUDIO = b"ID3\x03\x00\x00\x00" + b"\x00" * 64

MEDIA = tempfile.mkdtemp(prefix="pistas-test-")
# El elemento, no el texto: el JavaScript del visor también nombra el selector.
BOTON = '<button type="button" data-accion="practica"'


def mp3(nombre="cancion.mp3", contenido=AUDIO):
    return SimpleUploadedFile(nombre, contenido, content_type="audio/mpeg")


@override_settings(ALLOWED_HOSTS=["*"], MEDIA_ROOT=MEDIA)
class PistasTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        sitio = Site.objects.get(is_default_site=True)
        biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-pistas")
        sitio.root_page.add_child(instance=biblioteca)
        biblioteca.save_revision().publish()
        self.cancion = RecursoPage(
            title="Perfect", slug="perfect-pistas", date="2026-10-28",
            intro="x", body="<p>Cuerpo.</p>", chordpro=CHORDPRO,
        )
        biblioteca.add_child(instance=self.cancion)
        self.cancion.save_revision().publish()

        self.alumna = User.objects.create_user(email="alumna-pis@example.com", password="x123456789")
        self.profe = User.objects.create_superuser(email="profe-pis@example.com", password="x123456789")

    def pista(self, **extra):
        return PistaDePractica.crear(self.cancion, mp3(), extra.pop("nombre", "Original"), **extra)

    # --- El modelo ---

    def test_el_fichero_va_a_la_carpeta_cerrada_con_nombre_aleatorio(self):
        pista = self.pista()
        self.assertTrue(pista.archivo.name.startswith("pistas_practica/"))
        self.assertTrue(pista.archivo.name.endswith(".mp3"))
        self.assertNotIn("cancion", pista.archivo.name)
        self.assertTrue(Path(pista.archivo.path).exists())
        self.assertEqual(self.pista(nombre="Backing").orden, 1)

    def test_solo_audio_y_no_mas_de_40_mb(self):
        with self.assertRaises(ValueError):
            PistaDePractica.crear(self.cancion, mp3("partitura.pdf"), "x")
        grande = mp3()
        grande.size = PistaDePractica.TAMANO_MAXIMO + 1
        with self.assertRaises(ValueError):
            PistaDePractica.crear(self.cancion, grande, "x")
        with self.assertRaises(ValueError):
            PistaDePractica.crear(self.cancion, None, "x")
        with self.assertRaises(ValueError):
            PistaDePractica.crear(self.cancion, mp3(), "   ")
        self.assertFalse(PistaDePractica.objects.exists())

    def test_el_desfase_es_un_entero_dentro_de_una_octava(self):
        self.assertEqual(PistaDePractica.limpiar_semitonos("-3"), -3)
        self.assertEqual(PistaDePractica.limpiar_semitonos(""), 0)
        for malo in ("12", "-12", "dos", "1.5"):
            with self.assertRaises(ValueError):
                PistaDePractica.limpiar_semitonos(malo)

    def test_las_marcas_se_guardan_ordenadas_y_una_por_parrafo(self):
        limpias = PistaDePractica.limpiar_marcas([
            {"p": 2, "t": 40, "ancla": "estribillo"},
            {"p": 0, "t": 0.004},
            {"p": 1, "t": 12.345, "ancla": "verso"},
            {"p": 2, "t": 41.5, "ancla": "estribillo"},
        ])
        self.assertEqual([m["p"] for m in limpias], [0, 1, 2])
        self.assertEqual([m["t"] for m in limpias], [0.0, 12.35, 41.5])
        self.assertEqual(limpias[0]["ancla"], "")

    def test_marcas_invalidas(self):
        malas = [
            "no es lista",
            [{"p": -1, "t": 3}],
            [{"p": True, "t": 3}],
            [{"p": "1", "t": 3}],
            [{"p": 1, "t": 3601}],
            [{"p": 1, "t": -0.5}],
            [{"p": 1, "t": "3"}],
            [{"p": 1, "t": 3, "ancla": 7}],
            [1, 2],
            [{"p": i, "t": i} for i in range(PistaDePractica.MAX_MARCAS + 1)],
        ]
        for marcas in malas:
            with self.subTest(marcas=str(marcas)[:40]), self.assertRaises(ValueError):
                PistaDePractica.limpiar_marcas(marcas)

    def test_borrar_la_pista_o_la_cancion_borra_el_fichero(self):
        una = self.pista()
        otra = self.pista(nombre="Backing")
        ruta_una, ruta_otra = Path(una.archivo.path), Path(otra.archivo.path)
        una.delete()
        self.assertFalse(ruta_una.exists())
        self.cancion.delete()
        self.assertFalse(ruta_otra.exists())
        self.assertFalse(PistaDePractica.objects.exists())

    # --- Oír ---

    def test_sin_sesion_no_hay_audio(self):
        pista = self.pista()
        r = self.client.get(reverse("musica:pista_audio", args=[pista.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse(settings.LOGIN_URL)))
        self.assertNotIn(b"ID3", r.content)

    def test_con_sesion_cualquiera_lo_oye_entero(self):
        pista = self.pista()
        self.client.force_login(self.alumna)
        r = self.client.get(reverse("musica:pista_audio", args=[pista.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), AUDIO)
        self.assertEqual(r["Cache-Control"], "private, max-age=604800")

    def test_una_pista_que_no_existe_da_404(self):
        self.client.force_login(self.alumna)
        self.assertEqual(self.client.get(reverse("musica:pista_audio", args=[999])).status_code, 404)

    def test_nginx_cierra_la_carpeta(self):
        conf = (Path(settings.BASE_DIR) / "compose/production/nginx/default.conf").read_text()
        bloque = conf.split("location ^~ /media/pistas_practica/", 1)
        self.assertEqual(len(bloque), 2, "falta la regla de nginx")
        self.assertIn("return 404;", bloque[1].split("}", 1)[0])

    # --- Subir, cambiar, borrar ---

    def test_subir_pide_poder_editar_la_cancion(self):
        url = reverse("musica:pista_subir", args=[self.cancion.pk])
        self.client.force_login(self.alumna)
        r = self.client.post(url, {"archivo": mp3(), "nombre": "Original"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(PistaDePractica.objects.exists())

        self.client.force_login(self.profe)
        r = self.client.post(url, {"archivo": mp3(), "nombre": "Backing track", "semitonos": "2"})
        self.assertEqual(r.status_code, 201)
        datos = r.json()
        self.assertEqual(datos["nombre"], "Backing track")
        self.assertEqual(datos["semitonos"], 2)
        self.assertEqual(datos["audio"], reverse("musica:pista_audio", args=[datos["id"]]))

    def test_subir_algo_que_no_es_audio_da_400(self):
        self.client.force_login(self.profe)
        r = self.client.post(
            reverse("musica:pista_subir", args=[self.cancion.pk]),
            {"archivo": mp3("virus.exe"), "nombre": "x"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("Solo audio", r.json()["error"])

    def test_guardar_marcas_y_desfase(self):
        pista = self.pista()
        url = reverse("musica:pista_guardar", args=[pista.pk])
        cuerpo = json.dumps({"semitonos": -2, "marcas": [{"p": 1, "t": 9}, {"p": 0, "t": 1}]})

        self.client.force_login(self.alumna)
        self.assertEqual(self.client.post(url, cuerpo, content_type="application/json").status_code, 403)

        self.client.force_login(self.profe)
        r = self.client.post(url, cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        pista.refresh_from_db()
        self.assertEqual(pista.semitonos, -2)
        self.assertEqual([m["p"] for m in pista.marcas], [0, 1])

        r = self.client.post(url, json.dumps({"marcas": [{"p": 0, "t": 9999}]}), content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.post(url, "{no", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(url, "[1]", content_type="application/json").status_code, 400)
        pista.refresh_from_db()
        self.assertEqual(len(pista.marcas), 2)

    def test_borrar_pide_poder_editar(self):
        pista = self.pista()
        ruta = Path(pista.archivo.path)
        url = reverse("musica:pista_borrar", args=[pista.pk])
        self.client.force_login(self.alumna)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(ruta.exists())
        self.client.force_login(self.profe)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertFalse(PistaDePractica.objects.exists())
        self.assertFalse(ruta.exists())

    # --- El visor ---

    def _visor(self, user):
        letra = self.cancion.obtener_letra_con_acordes()
        item = LibraryItem.objects.create(
            user=user, content_type=ContentType.objects.get_for_model(letra), object_id=letra.pk,
        )
        self.client.force_login(user)
        html = self.client.get(reverse("my_library:study_item_content", args=[item.pk])).content.decode()
        self.assertIn("data-chordpro-visor", html)
        self.assertNotIn("{#", html)
        return html

    def test_el_alumno_sin_pistas_no_ve_nada_nuevo(self):
        html = self._visor(self.alumna)
        self.assertNotIn(BOTON, html)
        self.assertNotIn("cpv-pistas", html)

    def test_el_profe_sin_pistas_ve_el_boton_para_subir(self):
        html = self._visor(self.profe)
        self.assertIn(BOTON, html)
        self.assertIn(reverse("musica:pista_subir", args=[self.cancion.pk]), html)
        self.assertIn("SignalsmithStretch-1.3.2.js", html)

    def test_el_alumno_con_pistas_las_oye_pero_no_las_edita(self):
        pista = self.pista()
        html = self._visor(self.alumna)
        self.assertIn("🎧 Práctica (1)", html)
        self.assertIn(reverse("musica:pista_audio", args=[pista.pk]), html)
        self.assertIn('"puedeEditar": false', html)
        self.assertNotIn(pista.archivo.name, html)
