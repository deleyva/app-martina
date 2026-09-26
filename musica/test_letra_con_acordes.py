"""La letra con acordes (ChordPro) como material de sesión (2026-09-25).

Fija tres cosas:

- `LetraConAcordes` es solo un asa: una fila por canción, que nace al pedirla y
  no existe si la canción no tiene ChordPro.
- En el artículo, la letra completa solo viaja a quien tiene sesión iniciada. Es
  material con derechos y la página es pública.
- El visor de sesión lee el texto de la canción, así que corregir la letra en la
  canción la corrige en todas las sesiones que ya la tienen.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from wagtail.models import Site

from musica.models import LetraConAcordes, MusicLibraryIndexPage, RecursoPage
from my_library.models import LibraryItem

User = get_user_model()

CHORDPRO = "{start_of_verse}\n[G]I found a [Em]love, for [C]me\n{end_of_verse}"


@override_settings(ALLOWED_HOSTS=["*"])
class LetraConAcordesTest(TestCase):
    def setUp(self):
        self.sitio = Site.objects.get(is_default_site=True)
        biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-cho")
        self.sitio.root_page.add_child(instance=biblioteca)
        biblioteca.save_revision().publish()

        self.cancion = RecursoPage(
            title="Perfect", slug="perfect-cho", date="2026-09-25",
            intro="x", body="<p>Cuerpo.</p>", chordpro=CHORDPRO,
        )
        biblioteca.add_child(instance=self.cancion)
        self.cancion.save_revision().publish()

        self.sin_letra = RecursoPage(
            title="Sin letra", slug="sin-letra-cho", date="2026-09-25",
            intro="x", body="<p>Cuerpo.</p>",
        )
        biblioteca.add_child(instance=self.sin_letra)
        self.sin_letra.save_revision().publish()

        self.alumna = User.objects.create_user(
            email="alumna-cho@example.com", password="x123456789"
        )

    # --- El asa ---

    def test_sin_chordpro_no_hay_letra_ni_fila(self):
        self.assertIsNone(self.sin_letra.obtener_letra_con_acordes())
        self.assertFalse(LetraConAcordes.objects.filter(page=self.sin_letra).exists())

    def test_con_chordpro_siempre_la_misma_fila(self):
        primera = self.cancion.obtener_letra_con_acordes()
        segunda = self.cancion.obtener_letra_con_acordes()
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(LetraConAcordes.objects.filter(page=self.cancion).count(), 1)
        self.assertEqual(primera.chordpro, CHORDPRO)

    # --- El artículo ---

    def _html(self, user=None):
        if user:
            self.client.force_login(user)
        respuesta = self.client.get(
            self.cancion.url, follow=True, HTTP_HOST=self.sitio.hostname
        )
        # Sin esto, una página de error pasaría el test del anónimo: tampoco
        # lleva la letra.
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Perfect", respuesta.content.decode())
        return respuesta.content.decode()

    def test_un_anonimo_no_recibe_la_letra(self):
        html = self._html()
        self.assertNotIn("cp-source", html)
        self.assertNotIn("I found a", html)

    def test_con_sesion_la_letra_viaja_y_se_pinta_con_el_bundle(self):
        html = self._html(self.alumna)
        self.assertIn('id="cp-source"', html)
        self.assertIn("I found a", html)
        # Con el almacenamiento de estáticos con manifiesto, el nombre lleva hash.
        self.assertRegex(html, r"/static/js/chordpro(\.[0-9a-f]+)?\.js")
        self.assertNotIn("cdn.jsdelivr.net/npm/chordsheetjs", html)
        # Va en Resources, detrás del cuerpo, no al principio del artículo.
        self.assertLess(html.index(">Resources</h2>"), html.index('id="chordpro"'))
        self.assertLess(html.index("Cuerpo."), html.index('id="chordpro"'))
        self.assertIn("Pantalla completa", html)
        # Diagramas de acordes: selector de instrumento y tira con las bases.
        self.assertIn('id="cp-instrumento"', html)
        self.assertIn("vendor/chords-db/guitar", html)
        self.assertIn("vendor/chords-db/ukulele", html)

    # --- El visor de sesión ---

    def test_el_visor_de_estudio_lee_el_texto_vivo_de_la_cancion(self):
        letra = self.cancion.obtener_letra_con_acordes()
        item = LibraryItem.objects.create(
            user=self.alumna,
            content_type=ContentType.objects.get_for_model(letra),
            object_id=letra.pk,
        )
        self.assertEqual(item.get_documents()["chordpro"], [letra])

        self.cancion.chordpro = "[D]Letra corregida"
        self.cancion.save_revision().publish()

        self.client.force_login(self.alumna)
        from django.urls import reverse

        html = self.client.get(
            reverse("my_library:study_item_content", args=[item.pk])
        ).content.decode()
        self.assertIn("data-chordpro-visor", html)
        self.assertIn("Letra corregida", html)
        self.assertIn("data-diagramas", html)
        self.assertIn("data-instrumento", html)
        self.assertNotIn("I found a", html)

    def test_si_se_vacia_el_chordpro_el_visor_lo_dice(self):
        letra = self.cancion.obtener_letra_con_acordes()
        item = LibraryItem.objects.create(
            user=self.alumna,
            content_type=ContentType.objects.get_for_model(letra),
            object_id=letra.pk,
        )
        self.cancion.chordpro = ""
        self.cancion.save_revision().publish()

        self.client.force_login(self.alumna)
        from django.urls import reverse

        html = self.client.get(
            reverse("my_library:study_item_content", args=[item.pk])
        ).content.decode()
        self.assertIn("ya no tiene letra con acordes", html)

    def test_el_json_de_la_letra_no_rompe_el_script(self):
        """`json_script` escapa `<`: una letra con `</script>` no cierra el
        bloque antes de tiempo. El escape de HTML al pintar lo hace el JS."""
        self.cancion.chordpro = "[G]hola </script><img src=x onerror=alert(1)>"
        self.cancion.save_revision().publish()
        html = self._html(self.alumna)
        self.assertNotIn("<img src=x onerror", html)


@override_settings(ALLOWED_HOSTS=["*"])
class GuardarChordProTest(TestCase):
    """El ✎ guarda la letra con el permiso de Wagtail sobre la página."""

    def setUp(self):
        from django.urls import reverse

        sitio = Site.objects.get(is_default_site=True)
        biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-ed")
        sitio.root_page.add_child(instance=biblioteca)
        biblioteca.save_revision().publish()
        self.cancion = RecursoPage(
            title="Perfect", slug="perfect-ed", date="2026-09-26",
            intro="x", body="<p>Cuerpo.</p>", chordpro=CHORDPRO,
        )
        biblioteca.add_child(instance=self.cancion)
        self.cancion.save_revision().publish()
        self.url = reverse("musica:guardar_chordpro", args=[self.cancion.pk])
        self.admin = User.objects.create_superuser(email="admin-ed@example.com", password="x123456789")
        self.alumna = User.objects.create_user(email="alumna-ed@example.com", password="x123456789")

    def _post(self, cuerpo):
        import json

        return self.client.post(self.url, data=json.dumps(cuerpo), content_type="application/json")

    def test_quien_puede_editar_la_pagina_guarda_y_publica(self):
        self.client.force_login(self.admin)
        r = self._post({"chordpro": "[A]Nueva\r\nlinea"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["publicada"])
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.chordpro, "[A]Nueva\nlinea")
        self.assertFalse(self.cancion.has_unpublished_changes)

    def test_sin_permiso_de_edicion_no_se_toca(self):
        self.client.force_login(self.alumna)
        self.assertEqual(self._post({"chordpro": "[A]Hackeo"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self._post({"chordpro": "[A]Hackeo"}).status_code, 403)
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.chordpro, CHORDPRO)

    def test_datos_malos_dan_400(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url, data="no json", content_type="application/json").status_code, 400)
        self.assertEqual(self._post({"otra": 1}).status_code, 400)
        self.assertEqual(self._post({"chordpro": "x" * 50_001}).status_code, 400)

    def test_el_boton_solo_sale_a_quien_puede_editar(self):
        sitio = Site.objects.get(is_default_site=True)
        self.client.force_login(self.alumna)
        html = self.client.get(self.cancion.url, follow=True, HTTP_HOST=sitio.hostname).content.decode()
        self.assertNotIn("cp-editar-flotante", html)
        self.client.force_login(self.admin)
        html = self.client.get(self.cancion.url, follow=True, HTTP_HOST=sitio.hostname).content.decode()
        self.assertIn("cp-editar-flotante", html)
