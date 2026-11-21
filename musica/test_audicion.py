"""Fichas de audición (fase 111): el libro, los tests audiométricos y la clase.

Fija:

- El generador: frecuencias entre 240 y 600 Hz, el segundo sonido a la distancia
  exacta, las dos direcciones, y las distancias en fracciones de TONO.
- Un `LibroPage` admite fichas y las lista; `capitulos_de` y `material_de` las
  entregan enteras, así que llegan a una sesión por el flujo de siempre.
- Solo quien puede editar la página la edita desde la web, y cada cambio deja
  una revisión.
- En clase y en el visor de estudio la ficha se pinta con su parcial, no en un
  iframe con la web alrededor.
- La ficha antigua de bloques sueltos se sigue viendo como antes.
"""

import random

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from wagtail.documents import get_document_model
from wagtail.models import Site

from musica.models import DictadoPage, LibroPage, MusicLibraryIndexPage, RecursoPage
from musica.services import audicion
from my_library.libros import capitulos_de, material_de
from my_library.medios import clasificar

User = get_user_model()


class GeneradorTest(TestCase):
    def test_distancias_en_fracciones_de_tono_desde_el_cuarto(self):
        cents = [c for _, c, _ in audicion.DISTANCIAS]
        self.assertEqual(cents[0], 50.0)  # ¼ de tono, no ¼ de semitono
        self.assertEqual([round(c, 3) for c in cents], [50.0, 25.0, 12.5, 8.333, 4.0, 2.0, 1.0])
        for clave, c, _ in audicion.DISTANCIAS:
            n = int(clave.split("/")[1])
            self.assertAlmostEqual(c, 200 / n)

    def test_pares_en_rango_y_con_las_dos_direcciones(self):
        valor = audicion.generar_audiometrico(50, n=200, rng=random.Random(7))
        self.assertEqual(len(valor["pares"]), 200)
        self.assertEqual(valor["cents"], 50.0)
        fs = [p["f"] for p in valor["pares"]]
        self.assertTrue(all(240 <= f <= 600 for f in fs))
        direcciones = {p["sube"] for p in valor["pares"]}
        self.assertEqual(direcciones, {True, False})

    def test_el_segundo_sonido_a_la_distancia_exacta(self):
        self.assertAlmostEqual(audicion.segundo_sonido(400, 1200), 800)
        self.assertAlmostEqual(audicion.segundo_sonido(440, 50) / 440, 2 ** (50 / 1200))

    def test_etiquetas_legibles(self):
        self.assertEqual(audicion.etiqueta_de_cents(50), "¼ de tono · 50 cents")
        self.assertEqual(audicion.etiqueta_de_cents(12.5), "1/16 de tono · 12,5 cents")
        self.assertEqual(audicion.etiqueta_de_cents(200 / 24), "1/24 de tono · 8,3 cents")

    def test_cents_no_positivos_no_valen(self):
        with self.assertRaises(ValueError):
            audicion.generar_audiometrico(0)


@override_settings(ALLOWED_HOSTS=["*"])
class FichaTest(TestCase):
    def setUp(self):
        self.sitio = Site.objects.get(is_default_site=True)
        biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-aud")
        self.sitio.root_page.add_child(instance=biblioteca)
        biblioteca.save_revision().publish()

        self.libro = LibroPage(title="Entrenamiento auditivo", slug="entrenamiento-aud")
        biblioteca.add_child(instance=self.libro)
        self.libro.save_revision().publish()

        self.profe = User.objects.create_superuser(email="profe-aud@example.com", password="x123456789")
        self.alumna = User.objects.create_user(email="alumna-aud@example.com", password="x123456789")

    def _ficha(self, titulo="Tests de ¼ de tono", n_tests=0):
        ficha = DictadoPage(title=titulo, slug=f"ficha-{random.randint(0, 10**9)}")
        self.libro.add_child(instance=ficha)
        for _ in range(n_tests):
            audicion.anadir(ficha, "audiometrico", audicion.generar_audiometrico(50))
        ficha.save_revision().publish()
        ficha.refresh_from_db()
        return ficha

    def _get(self, url, user=None):
        if user:
            self.client.force_login(user)
        r = self.client.get(url, follow=True, HTTP_HOST=self.sitio.hostname)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    # --- C771: el libro admite y lista fichas ---

    def test_un_libro_admite_fichas(self):
        self.assertIn(DictadoPage, LibroPage.allowed_subpage_models())
        self.assertIn(LibroPage, DictadoPage.allowed_parent_page_models())

    def test_el_indice_del_libro_lista_la_ficha_en_orden_de_arbol(self):
        cancion = RecursoPage(title="Capítulo uno", slug="cap-uno-aud", date="2026-11-18", intro="x", body="<p>x</p>")
        self.libro.add_child(instance=cancion)
        cancion.save_revision().publish()
        self._ficha("Tests de ¼ de tono")
        html = self._get(self.libro.url)
        self.assertIn("Capítulo uno", html)
        self.assertIn("Tests de ¼ de tono", html)
        self.assertIn("Ficha de audición", html)
        self.assertLess(html.index("Capítulo uno"), html.index("Tests de ¼ de tono"))
        self.assertNotIn("{#", html)

    def test_boton_de_nueva_ficha_solo_para_quien_puede_y_en_libros_de_audicion(self):
        self.assertIn("＋ Ficha de audición", self._get(self.libro.url, self.profe))
        self.client.logout()
        self.assertNotIn("＋ Ficha de audición", self._get(self.libro.url, self.alumna))

    # --- C772: tres tipos de ejercicio, y la ficha antigua intacta ---

    def test_los_tres_tipos_de_ejercicio_caben_en_una_ficha(self):
        ficha = self._ficha()
        audicion.anadir(ficha, "audiometrico", audicion.generar_audiometrico(25))
        audicion.anadir(ficha, "dictado_abc", {"tipo": "ritmico", "abc": "X:1\nL:1/4\nK:C\nC C C C|", "tempo": 60})
        audicion.anadir(ficha, "dictado_imagen", {"titulo": "Dictado 1"})
        ficha.save_revision().publish()
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        tipos = [b.block_type for b in ficha.content]
        self.assertEqual(tipos, ["audiometrico", "dictado_abc", "dictado_imagen"])
        self.assertEqual([n for _, n in ficha.ejercicios()], [1, 2, 3])
        self.assertFalse(ficha.es_antigua)

    def test_la_ficha_antigua_se_pinta_como_siempre(self):
        Documento = get_document_model()
        audio = Documento(title="dictado 1")
        audio.file.save("dictado1.mp3", ContentFile(b"ID3"), save=True)
        antigua = DictadoPage(title="Dictado antiguo", slug="dictado-antiguo-aud")
        self.libro.add_child(instance=antigua)
        antigua.content = [{"type": "audio", "value": {"title": "Dictado 1", "audio_file": audio.pk}}]
        antigua.save_revision().publish()
        antigua = DictadoPage.objects.get(pk=antigua.pk)
        self.assertTrue(antigua.es_antigua)
        # En clase, la antigua sigue en su iframe, como antes de la fase 111.
        from clases.models import ClassSessionItem
        from clases.views import render_item_content

        item = ClassSessionItem(content_type=ContentType.objects.get_for_model(DictadoPage), object_id=antigua.pk)
        request = RequestFactory().get("/")
        request.user = self.profe
        request.session = self.client.session
        self.assertIn("<iframe", render_item_content(request, item).content.decode())

        html = self._get(antigua.url, self.profe)
        self.assertIn("dictado-content", html)
        self.assertIn("daisyui@3.9.4", html)  # la antigua, como siempre
        self.assertNotIn("fa-ficha", html)
        self.assertNotIn("＋ Test audiométrico", html)

    # --- C774: solo quien puede editar, y con revisión ---

    def test_la_alumna_no_puede_anadir_ni_borrar(self):
        ficha = self._ficha(n_tests=1)
        bloque_id = ficha.content[0].id
        self.client.force_login(self.alumna)
        for url, datos in (
            (reverse("musica:anadir_audiometrico", args=[ficha.pk]), {"distancia": "1/4", "cuantos": 1}),
            (reverse("musica:borrar_ejercicio", args=[ficha.pk, bloque_id]), {}),
            (reverse("musica:regenerar_ejercicio", args=[ficha.pk, bloque_id]), {}),
            (reverse("musica:mover_ejercicio", args=[ficha.pk, bloque_id]), {"hacia": "abajo"}),
            (reverse("musica:crear_ficha", args=[self.libro.pk]), {"titulo": "x"}),
        ):
            self.assertEqual(self.client.post(url, datos).status_code, 403, url)
        self.client.logout()
        r = self.client.post(reverse("musica:anadir_audiometrico", args=[ficha.pk]), {"distancia": "1/4"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(DictadoPage.objects.get(pk=ficha.pk).content), 1)

    def test_anadir_tests_publica_y_deja_revision(self):
        ficha = self._ficha()
        revisiones = ficha.revisions.count()
        self.client.force_login(self.profe)
        r = self.client.post(
            reverse("musica:anadir_audiometrico", args=[ficha.pk]),
            {"distancia": "1/8", "cuantos": 3},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("fa-ficha", r.content.decode())
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(ficha.revisions.count(), revisiones + 1)
        self.assertEqual([b.block_type for b in ficha.content], ["audiometrico"] * 3)
        self.assertTrue(all(b.value["cents"] == 25.0 for b in ficha.content))
        self.assertTrue(all(len(b.value["pares"]) == 10 for b in ficha.content))

    def test_mover_regenerar_y_borrar(self):
        ficha = self._ficha(n_tests=2)
        primero, segundo = [b.id for b in ficha.content]
        pares_antes = [dict(p) for p in ficha.content[1].value["pares"]]
        self.client.force_login(self.profe)

        self.client.post(reverse("musica:mover_ejercicio", args=[ficha.pk, segundo]), {"hacia": "arriba"})
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual([b.id for b in ficha.content], [segundo, primero])

        self.client.post(reverse("musica:regenerar_ejercicio", args=[ficha.pk, segundo]))
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(ficha.content[0].id, segundo)
        self.assertNotEqual([dict(p) for p in ficha.content[0].value["pares"]], pares_antes)

        self.client.post(reverse("musica:borrar_ejercicio", args=[ficha.pk, primero]))
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual([b.id for b in ficha.content], [segundo])

        r = self.client.post(reverse("musica:borrar_ejercicio", args=[ficha.pk, "no-existe"]))
        self.assertEqual(r.status_code, 404)

    def test_crear_ficha_desde_el_libro(self):
        self.client.force_login(self.profe)
        r = self.client.post(reverse("musica:crear_ficha", args=[self.libro.pk]), {"titulo": "Dictado rítmico 3"})
        self.assertEqual(r.status_code, 302)
        ficha = DictadoPage.objects.child_of(self.libro).get(title="Dictado rítmico 3")
        self.assertTrue(ficha.live)
        # Relativa al host de la petición: nunca a otro sitio.
        self.assertFalse(r["Location"].startswith("http"), r["Location"])
        self.assertTrue(ficha.url.endswith(r["Location"]))
        # El mismo título otra vez no choca con el slug.
        self.client.post(reverse("musica:crear_ficha", args=[self.libro.pk]), {"titulo": "Dictado rítmico 3"})
        self.assertEqual(DictadoPage.objects.child_of(self.libro).filter(title="Dictado rítmico 3").count(), 2)

    # --- La página de la ficha ---

    def test_la_pagina_lleva_los_pares_la_solucion_y_el_editor_solo_para_el_profe(self):
        ficha = self._ficha(n_tests=1)
        pares = ficha.content[0].value["pares"]
        html = self._get(ficha.url, self.profe)
        self.assertIn("data-audiometrico", html)
        self.assertIn("Ver solución", html)
        self.assertEqual(html.count('class="fa-par"'), 10)
        flechas = "".join("↑" if p["sube"] else "↓" for p in pares)
        self.assertEqual("".join(c for c in html.split("fa-flechas", 1)[1].split("</ol>", 1)[0] if c in "↑↓"), flechas)
        self.assertIn("＋ Test audiométrico", html)
        self.assertNotIn("{#", html)
        # Sin el DaisyUI viejo del CDN, que rompía la cabecera en el móvil.
        self.assertNotIn("daisyui@3.9.4", html)
        self.assertNotIn("wavesurfer", html)
        self.client.logout()
        html = self._get(ficha.url, self.alumna)
        self.assertIn("data-audiometrico", html)
        self.assertNotIn("＋ Test audiométrico", html)
        self.assertNotIn("Regenerar", html)

    # --- C779, C780: dictados en ABC ---

    def test_anadir_un_dictado_con_su_plantilla_y_editarlo(self):
        ficha = self._ficha()
        self.client.force_login(self.profe)
        self.client.post(reverse("musica:anadir_dictado", args=[ficha.pk]), {"tipo": "ritmico"})
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        bloque = ficha.content[0]
        self.assertEqual(bloque.block_type, "dictado_abc")
        self.assertEqual(bloque.value["tipo"], "ritmico")
        self.assertIn("clef=perc", bloque.value["abc"])
        self.assertEqual(bloque.value["abc"].count("|"), 8)  # 8 compases
        self.assertEqual((bloque.value["tempo"], bloque.value["repeticiones"], bloque.value["silencio"]), (60, 2, 10))
        self.assertTrue(bloque.value["cuenta_previa"])

        abc = "X:1\nM:3/4\nL:1/4\nK:G\nG A B|c2 B|A G F|G3|B c d|e2 d|c B A|G3|"
        self.client.post(
            reverse("musica:editar_dictado", args=[ficha.pk, bloque.id]),
            {"abc": abc, "tipo": "melodico", "tempo": "72", "timbre": "flauta", "repeticiones": "3", "silencio": "15", "titulo": "Dictado 1"},
        )
        valor = DictadoPage.objects.get(pk=ficha.pk).content[0].value
        self.assertEqual(valor["abc"], abc)
        self.assertEqual((valor["tipo"], valor["tempo"], valor["timbre"]), ("melodico", 72, "flauta"))
        self.assertEqual((valor["repeticiones"], valor["silencio"], valor["titulo"]), (3, 15, "Dictado 1"))
        # El checkbox desmarcado no viaja: es «sin cuenta previa».
        self.assertFalse(valor["cuenta_previa"])

    def test_el_dictado_se_limita_y_no_lo_edita_la_alumna(self):
        ficha = self._ficha()
        self.client.force_login(self.profe)
        self.client.post(reverse("musica:anadir_dictado", args=[ficha.pk]), {"tipo": "melodico"})
        bloque_id = DictadoPage.objects.get(pk=ficha.pk).content[0].id
        url = reverse("musica:editar_dictado", args=[ficha.pk, bloque_id])
        self.client.post(url, {"abc": "X:1\nK:C\nC|", "tempo": "999", "repeticiones": "9", "silencio": "-3", "timbre": "rarito"})
        valor = DictadoPage.objects.get(pk=ficha.pk).content[0].value
        self.assertEqual((valor["tempo"], valor["repeticiones"], valor["silencio"], valor["timbre"]), (200, 4, 0, ""))
        self.assertEqual(self.client.post(url, {"abc": "x" * 6000}).status_code, 400)
        self.client.force_login(self.alumna)
        self.assertEqual(self.client.post(url, {"abc": "X:1\nK:C\nD|"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("musica:anadir_dictado", args=[ficha.pk]), {}).status_code, 403)

    def test_la_pagina_lleva_el_reproductor_y_el_editor_del_dictado(self):
        ficha = self._ficha()
        audicion.anadir(ficha, "dictado_abc", {"tipo": "melodico", "abc": "X:1\nK:C\nC D E F|", "tempo": 60, "repeticiones": 2, "silencio": 10, "cuenta_previa": True})
        ficha.save_revision().publish()
        html = self._get(ficha.url, self.profe)
        self.assertIn("data-dictado=", html)
        self.assertIn("▶ Dictado", html)
        self.assertIn("Lo toco yo", html)
        self.assertIn("data-editor-abc", html)
        self.assertIn("vendor/abcjs/abcjs-basic-min.js", html)
        self.assertIn("js/motor_midi.js", html)
        self.assertNotIn("{#", html)
        self.client.logout()
        html = self._get(ficha.url, self.alumna)
        self.assertIn("▶ Dictado", html)
        self.assertNotIn("data-editor-abc", html)

    # --- C785-C787: grabar y dictados con imagen ---

    def _png(self):
        import io

        from PIL import Image as PILImage

        b = io.BytesIO()
        PILImage.new("RGB", (40, 20), "white").save(b, "PNG")
        return SimpleUploadedFile("respuesta.png", b.getvalue(), content_type="image/png")

    def test_dictado_con_imagen(self):
        ficha = self._ficha()
        self.client.force_login(self.profe)
        r = self.client.post(
            reverse("musica:anadir_dictado_imagen", args=[ficha.pk]),
            {"titulo": "Dictado 1", "imagen": self._png()},
        )
        self.assertEqual(r.status_code, 302)
        bloque = DictadoPage.objects.get(pk=ficha.pk).content[0]
        self.assertEqual(bloque.block_type, "dictado_imagen")
        self.assertEqual(bloque.value["titulo"], "Dictado 1")
        self.assertIsNotNone(bloque.value["imagen"])
        html = self._get(ficha.url, self.profe)
        self.assertIn("Sin grabación: lo toca el profesor en clase.", html)
        self.assertIn("data-grabacion", html)
        self.assertIn("<img", html.split("fa-imagen-respuesta", 1)[1][:400])
        # Una imagen que no lo es se rechaza.
        falsa = SimpleUploadedFile("x.exe", b"MZ", content_type="application/octet-stream")
        r = self.client.post(reverse("musica:anadir_dictado_imagen", args=[ficha.pk]), {"imagen": falsa})
        self.assertEqual(r.status_code, 400)

    def test_subir_la_grabacion_es_idempotente_y_suena_en_lugar_del_sintetizador(self):
        from wagtail.documents import get_document_model

        ficha = self._ficha()
        self.client.force_login(self.profe)
        self.client.post(reverse("musica:anadir_dictado", args=[ficha.pk]), {"tipo": "melodico"})
        bloque_id = DictadoPage.objects.get(pk=ficha.pk).content[0].id
        url = reverse("musica:subir_audio", args=[ficha.pk, bloque_id])
        clave = "3f2b8c1e-1111-4222-8333-944455556666"
        Documento = get_document_model()
        antes = Documento.objects.count()
        for _ in range(2):  # el reintento tras perder la respuesta
            r = self.client.post(url, {"clave": clave, "archivo": SimpleUploadedFile("grabacion.webm", b"\x1aE\xdf\xa3webm", content_type="audio/webm")}, HTTP_HX_REQUEST="true")
            self.assertEqual(r.status_code, 200)
        self.assertEqual(Documento.objects.count(), antes + 1)
        valor = DictadoPage.objects.get(pk=ficha.pk).content[0].value
        self.assertEqual(valor["audio"].title, f"Grabación de audición {clave}")
        html = self._get(ficha.url, self.profe)
        self.assertIn("<audio", html)
        self.assertIn("Suena la grabación del profesor.", html)
        self.assertNotIn("data-tocar>", html)
        # Editar el ABC no se lleva la grabación por delante.
        self.client.post(reverse("musica:editar_dictado", args=[ficha.pk, bloque_id]), {"abc": "X:1\nK:C\nC D|"})
        self.assertIsNotNone(DictadoPage.objects.get(pk=ficha.pk).content[0].value["audio"])
        # Quitarla devuelve el sintetizador.
        self.client.post(reverse("musica:quitar_audio", args=[ficha.pk, bloque_id]))
        self.assertIsNone(DictadoPage.objects.get(pk=ficha.pk).content[0].value["audio"])
        self.assertIn("data-tocar>", self._get(ficha.url, self.profe))

    def test_la_subida_se_limita_y_no_la_hace_la_alumna(self):
        ficha = self._ficha()
        self.client.force_login(self.profe)
        self.client.post(reverse("musica:anadir_dictado", args=[ficha.pk]), {"tipo": "melodico"})
        bloque_id = DictadoPage.objects.get(pk=ficha.pk).content[0].id
        url = reverse("musica:subir_audio", args=[ficha.pk, bloque_id])
        audio = lambda nombre="g.webm": SimpleUploadedFile(nombre, b"x", content_type="audio/webm")
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        self.assertEqual(self.client.post(url, {"archivo": audio("g.pdf")}).status_code, 400)
        self.assertEqual(self.client.post(url, {"archivo": audio(), "clave": "../../x"}).status_code, 400)
        self.client.force_login(self.alumna)
        self.assertEqual(self.client.post(url, {"archivo": audio()}).status_code, 403)
        self.assertEqual(self.client.post(reverse("musica:quitar_audio", args=[ficha.pk, bloque_id])).status_code, 403)
        self.assertEqual(self.client.post(reverse("musica:anadir_dictado_imagen", args=[ficha.pk]), {}).status_code, 403)

    # --- C776, C777: en clase y en el visor de estudio ---

    def test_el_libro_entrega_la_ficha_por_ejercicios(self):
        # Hasta la fase 111 el libro entregaba la ficha entera; desde la 112,
        # un ejercicio por test (C794). La ficha sigue siendo capítulo.
        ficha = self._ficha(n_tests=1)
        capitulos = capitulos_de(self.libro)
        self.assertIn(ficha.pk, [c.pk for c in capitulos])
        capitulo = next(c for c in capitulos if c.pk == ficha.pk)
        material = material_de(capitulo)
        self.assertEqual([type(m).__name__ for m in material], ["EjercicioDeFicha"])
        self.assertEqual(clasificar(capitulo, "dictadopage")["fichas"], [capitulo])
        self.assertEqual(clasificar(material[0], "ejerciciodeficha")["ejercicios"], material)

    def test_en_clase_se_pinta_la_ficha_y_no_un_iframe(self):
        from clases.models import ClassSessionItem
        from clases.views import render_item_content

        ficha = self._ficha(n_tests=1)
        item = ClassSessionItem(
            content_type=ContentType.objects.get_for_model(DictadoPage),
            object_id=ficha.pk,
        )
        request = RequestFactory().get("/")
        request.user = self.profe
        request.session = self.client.session
        html = render_item_content(request, item).content.decode()
        self.assertNotIn("<iframe", html)
        self.assertIn("fa-ficha fa-clase", html)
        self.assertIn("data-audiometrico", html)
        self.assertIn("Ver solución", html)
        # En clase no se edita.
        self.assertNotIn("＋ Test audiométrico", html)
        self.assertNotIn("{#", html)
        # C783: los dictados suenan con el MuseScore General recortado, no con sonivox.
        self.assertIn("vendor/musescore/MuseScore_General_fichas.sf3", html)
        self.assertNotIn("sonivox", html)


@override_settings(ALLOWED_HOSTS=["*"])
class EjercicioSueltoTest(TestCase):
    """Fase 112: un test suelto en cada clase, en vez de la ficha entera."""

    setUp = FichaTest.setUp
    _ficha = FichaTest._ficha
    _get = FichaTest._get

    def _ids(self, ficha):
        return [b.id for b, n in ficha.ejercicios() if n]

    def _render(self, objeto):
        from clases.models import ClassSessionItem
        from clases.views import render_item_content

        item = ClassSessionItem(
            content_type=ContentType.objects.get_for_model(objeto), object_id=objeto.pk
        )
        request = RequestFactory().get("/")
        request.user = self.profe
        request.session = self.client.session
        respuesta = render_item_content(request, item)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def _guardar(self, ficha):
        ficha.save_revision().publish()
        return DictadoPage.objects.get(pk=ficha.pk)

    # --- C794 ---

    def test_un_ejercicio_por_test_en_orden_y_sin_duplicar(self):
        from musica.models import EjercicioDeFicha

        ficha = self._ficha(n_tests=3)
        primera = material_de(ficha)
        self.assertEqual([e.bloque_id for e in primera], self._ids(ficha))
        segunda = material_de(DictadoPage.objects.get(pk=ficha.pk))
        self.assertEqual([e.pk for e in segunda], [e.pk for e in primera])
        self.assertEqual(EjercicioDeFicha.objects.filter(ficha=ficha).count(), 3)

    def test_los_dictados_tambien_van_sueltos(self):
        ficha = self._ficha(n_tests=1)
        audicion.anadir(ficha, "dictado_abc", {"abc": "X:1\nK:C\nCDEF|", "tipo": "ritmico"})
        ficha = self._guardar(ficha)
        material = material_de(ficha)
        self.assertEqual(len(material), 2)
        self.assertEqual(material[1].describir()[2], "Dictado rítmico")

    def test_enumerar_de_nuevo_no_consulta_por_ejercicio(self):
        # Anti-C: con las filas ya creadas, una consulta por ficha.
        ficha = self._ficha(n_tests=10)
        material_de(ficha)
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        with self.assertNumQueries(1):
            self.assertEqual(len(material_de(ficha)), 10)

    # --- C795 ---

    def test_en_la_sesion_un_test_por_clase_y_el_siguiente_al_darlo_por_visto(self):
        from django.utils import timezone

        from clases import libros_de_grupo
        from clases.models import ClassSession, Group, GroupBook, Subject

        ficha = self._ficha(n_tests=3)
        asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
        grupo = Group.objects.create(name="1º A aud", subject=asignatura, academic_year="2026-2027")
        libro = GroupBook.objects.create(group=grupo, libro=self.libro, seccion="dictado")

        filas = libros_de_grupo.enumerar(libro)
        self.assertEqual([f["tipo"].model for f in filas], ["ejerciciodeficha"] * 3)
        self.assertEqual(filas[2]["titulo"], "Tests de ¼ de tono · 3 · ¿Sube o baja?")
        self.assertEqual(filas[0]["tipo_legible"], "Test audiométrico · ¼ de tono · 50 cents")
        self.assertEqual(filas[0]["icono"], "🎧")

        def clase():
            return ClassSession.objects.create(
                teacher=self.profe, group=grupo, date=timezone.now().date(), title="Clase"
            )

        hoy = libros_de_grupo.preparar_sesion(clase(), por_libro=1)
        self.assertEqual(len(hoy), 1)
        self.assertEqual(hoy[0].content_object.bloque_id, self._ids(ficha)[0])
        self.assertEqual(hoy[0].source_page_id, ficha.pk)
        self.assertEqual(hoy[0].get_icon(), "🎧")
        libros_de_grupo.marcar_visto(hoy[0])
        manana = libros_de_grupo.preparar_sesion(clase(), por_libro=1)
        self.assertEqual(manana[0].content_object.bloque_id, self._ids(ficha)[1])

        # Elegido a mano: solo el que se elige.
        a_mano = clase()
        tercero = filas[2]["objeto"]
        creados = libros_de_grupo.anadir_elementos(a_mano, [(libro.pk, filas[2]["tipo"].pk, tercero.pk)])
        self.assertEqual([c.object_id for c in creados], [tercero.pk])
        self.assertEqual(a_mano.items.count(), 1)

    # --- C796 ---

    def test_en_clase_solo_se_pinta_ese_test(self):
        ficha = self._ficha(n_tests=3)
        uno, dos, tres = material_de(ficha)
        html = self._render(dos)
        self.assertIn(f'id="ej-{dos.bloque_id}"', html)
        self.assertNotIn(f'id="ej-{uno.bloque_id}"', html)
        self.assertNotIn(f'id="ej-{tres.bloque_id}"', html)
        self.assertEqual(html.count("data-audiometrico "), 1)
        self.assertIn('<span class="fa-numero">2</span>', html)
        self.assertIn("Tests de ¼ de tono", html)
        self.assertIn("Ver solución", html)
        self.assertIn("fa-clase fa-suelto", html)
        self.assertIn(f"ficha-{ficha.pk}-{dos.bloque_id}", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("＋ Test audiométrico", html)
        self.assertNotIn("↻ Regenerar", html)
        self.assertNotIn("{#", html)

    # --- C798 ---

    def test_sigue_al_ejercicio_al_reordenar_y_avisa_si_se_borra(self):
        ficha = self._ficha(n_tests=3)
        uno, dos, _ = material_de(ficha)
        audicion.mover(ficha, uno.bloque_id, +1)
        ficha = self._guardar(ficha)
        uno.refresh_from_db()
        self.assertEqual(uno.bloque_y_numero()[1], 2)
        html = self._render(uno)
        self.assertIn(f'id="ej-{uno.bloque_id}"', html)
        self.assertIn('<span class="fa-numero">2</span>', html)

        audicion.borrar(ficha, dos.bloque_id)
        ficha = self._guardar(ficha)
        dos.refresh_from_db()
        html = self._render(dos)
        self.assertIn("Este ejercicio ya no está en la ficha", html)
        self.assertNotIn("data-audiometrico ", html)
        self.assertIn("ejercicio borrado", dos.title)
        self.assertNotIn(dos.pk, [e.pk for e in material_de(ficha)])

    # --- C797 / Anti-A ---

    def test_la_ficha_antigua_sigue_entrando_entera(self):
        Documento = get_document_model()
        audio = Documento(title="dictado 1")
        audio.file.save("dictado1-112.mp3", ContentFile(b"ID3"), save=True)
        antigua = DictadoPage(title="Dictado antiguo 112", slug="dictado-antiguo-112")
        self.libro.add_child(instance=antigua)
        antigua.content = [{"type": "audio", "value": {"title": "Dictado 1", "audio_file": audio.pk}}]
        antigua = self._guardar(antigua)
        self.assertEqual(material_de(antigua), [antigua])

    # --- C799 ---

    def test_el_visor_suelto_de_la_sesion_pinta_el_ejercicio(self):
        from django.utils import timezone

        from clases.models import ClassSession, ClassSessionItem, Group, Subject

        ficha = self._ficha(n_tests=2)
        _, dos = material_de(ficha)
        asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
        grupo = Group.objects.create(name="1º B aud", subject=asignatura, academic_year="2026-2027")
        sesion = ClassSession.objects.create(
            teacher=self.profe, group=grupo, date=timezone.now().date(), title="Clase"
        )
        item = ClassSessionItem.objects.create(
            session=sesion,
            content_type=ContentType.objects.get_for_model(dos),
            object_id=dos.pk,
            source_page=ficha,
        )
        html = self._get(reverse("clases:class_session_item_viewer", args=[sesion.pk, item.pk]), self.profe)
        self.assertIn(f'id="ej-{dos.bloque_id}"', html)
        self.assertEqual(html.count("data-audiometrico "), 1)

    def test_la_miniatura_dice_que_es_audicion(self):
        from my_library.previsualizacion import datos_de_miniatura

        ficha = self._ficha(n_tests=1)
        (ejercicio,) = material_de(ficha)
        self.assertEqual(datos_de_miniatura(ejercicio)["tipo"], "audicion")
        self.assertEqual(datos_de_miniatura(ficha, "dictadopage")["tipo"], "audicion")

    # --- C793 ---

    @override_settings(LANGUAGE_CODE="es")
    def test_los_cents_llegan_con_punto(self):
        from django.template.loader import render_to_string
        from django.utils import translation

        valor = audicion.generar_audiometrico(12.5, n=2)
        with translation.override("es"):
            html = render_to_string("musica/partials/ejercicio_audiometrico.html", {"b": valor})
        self.assertIn('data-cents="12.5"', html)


class BundleTest(TestCase):
    """El bundle de esbuild se confirma en git: producción no lo construye."""

    def test_el_bundle_esta_sin_source_map_y_con_el_reproductor(self):
        from pathlib import Path

        from django.conf import settings

        bundle = Path(settings.APPS_DIR) / "static" / "js" / "audicion.js"
        self.assertTrue(bundle.exists(), "falta static/js/audicion.js: bunx esbuild (ver package.json, build-js)")
        texto = bundle.read_text(encoding="utf-8")
        # Con el almacenamiento con manifiesto, esa línea sin su `.map` tumba
        # `collectstatic` (2026-10-29).
        self.assertNotIn("sourceMappingURL", texto)
        for marca in ("[data-audiometrico]", "Audicion", "fa-sonando"):
            self.assertIn(marca, texto)

        dictado = Path(settings.APPS_DIR) / "static" / "js" / "dictado.js"
        self.assertTrue(dictado.exists(), "falta static/js/dictado.js")
        texto = dictado.read_text(encoding="utf-8")
        self.assertNotIn("sourceMappingURL", texto)
        for marca in ("[data-dictado]", "[data-editor-abc]", "MotorMidi", "los de clase tienen 8"):
            self.assertIn(marca, texto)

        grabadora = Path(settings.APPS_DIR) / "static" / "js" / "grabadora.js"
        self.assertTrue(grabadora.exists(), "falta static/js/grabadora.js")
        texto = grabadora.read_text(encoding="utf-8")
        self.assertNotIn("sourceMappingURL", texto)
        for marca in ("audicion-grabaciones", "[data-grabacion]", "Grabadora", "X-CSRFToken"):
            self.assertIn(marca, texto)

    def test_el_banco_de_las_fichas_va_con_su_licencia_mit(self):
        from pathlib import Path

        from django.conf import settings

        carpeta = Path(settings.APPS_DIR) / "static" / "vendor" / "musescore"
        banco = carpeta / "MuseScore_General_fichas.sf3"
        self.assertTrue(banco.exists(), "falta el banco: bun scripts/recortar_banco.ts (ver LEEME.txt)")
        self.assertEqual(banco.read_bytes()[:4], b"RIFF")
        self.assertLessEqual(banco.stat().st_size, 3_000_000)
        # La licencia MIT de MuseScore General pide sus avisos en toda obra derivada.
        self.assertIn("MIT license", (carpeta / "LICENSE.md").read_text(encoding="utf-8"))
        self.assertTrue((carpeta / "LEEME.txt").exists())

    def test_abcjs_se_sirve_desde_el_sitio_con_licencia(self):
        from pathlib import Path

        from django.conf import settings

        carpeta = Path(settings.APPS_DIR) / "static" / "vendor" / "abcjs"
        self.assertTrue((carpeta / "abcjs-basic-min.js").exists())
        self.assertTrue((carpeta / "LICENSE.md").exists())
        self.assertIn("abcjs_basic v6.7.2", (carpeta / "abcjs-basic-min.js").read_text(encoding="utf-8")[:200])
        self.assertNotIn("sourceMappingURL", (carpeta / "abcjs-basic-min.js").read_text(encoding="utf-8"))
