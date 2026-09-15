"""La misma ficha en dos lenguas, una sola página (fase 33, 2026-09-15).

Lo que estos tests defienden no es «que se traduzca», sino las tres cosas que
harían que la solución dejara de merecer la pena: que la página siga siendo
UNA (una URL, una ficha musical), que una lengua que falta no rompa nada, y
que el alumno de la bilingüe no tenga que pulsar un botón para leer en inglés.
"""

import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from wagtail.models import Page, Site

from blogs.models import ArticuloPage, BlogIndexPage
from clases.models import Enrollment, Group, Subject, idioma_del_alumno
from musica.models import MusicLibraryIndexPage, RecursoPage, RecursoTraduccion

User = get_user_model()


class TraduccionesBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="trad@example.com", password="testpassword123"
        )
        self.client.force_login(self.user)
        # Bajo `depth=1` la página no pertenece a ningún Site y `page.url` es
        # None: estos tests piden URLs de verdad, así que cuelgan del sitio.
        self.root_page = Site.objects.get(is_default_site=True).root_page
        self.biblioteca = MusicLibraryIndexPage(
            title="Biblioteca", slug="biblioteca-trad"
        )
        self.root_page.add_child(instance=self.biblioteca)
        self.biblioteca.save_revision().publish()

    def _recurso(self, slug="paseo", idioma="es", intro="Estopa en 2005", body="<p>Rumba.</p>"):
        page = RecursoPage(
            title="Paseo",
            slug=slug,
            date="2026-09-15",
            intro=intro,
            body=body,
            idioma=idioma,
        )
        self.biblioteca.add_child(instance=page)
        page.save_revision().publish()
        return page


class ModeloTraduccionTest(TraduccionesBase):
    """C185, C187, C189 — el modelo, sin pasar por HTTP."""

    def test_una_traduccion_no_crea_otra_pagina(self):
        """C185: la traducción es una fila hija, no un segundo árbol."""
        page = self._recurso()
        RecursoTraduccion.objects.create(
            page=page, idioma="en", intro="Estopa in 2005", body="<p>Rumba.</p>"
        )
        self.assertEqual(Page.objects.filter(slug="paseo").count(), 1)
        self.assertEqual(page.traducciones.count(), 1)

    def test_la_lengua_pedida_gana(self):
        page = self._recurso()
        RecursoTraduccion.objects.create(
            page=page, idioma="en", intro="Estopa in 2005", body="<p>Rumba EN.</p>"
        )
        page = RecursoPage.objects.get(pk=page.pk)
        self.assertEqual(page.texto("en")["intro"], "Estopa in 2005")
        self.assertFalse(page.texto("en")["es_respaldo"])
        self.assertEqual(page.texto("es")["intro"], "Estopa en 2005")

    def test_sin_traduccion_cae_al_texto_base_y_lo_dice(self):
        """C187: falta el inglés — ni 404 ni cuerpo vacío."""
        page = self._recurso()
        texto = page.texto("en")
        self.assertEqual(texto["idioma"], "es")
        self.assertEqual(texto["intro"], "Estopa en 2005")
        self.assertTrue(texto["es_respaldo"])

    def test_solo_asoma_el_selector_con_mas_de_una_lengua(self):
        page = self._recurso()
        self.assertEqual(page.idiomas_disponibles, [("es", "Español")])
        RecursoTraduccion.objects.create(page=page, idioma="en", intro="x")
        page = RecursoPage.objects.get(pk=page.pk)
        self.assertEqual(
            page.idiomas_disponibles, [("es", "Español"), ("en", "English")]
        )

    def test_la_base_de_datos_prohibe_dos_veces_la_misma_lengua(self):
        """C189: el falsador es la restricción, no una comprobación en Python."""
        page = self._recurso()
        RecursoTraduccion.objects.create(page=page, idioma="en", intro="a")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RecursoTraduccion.objects.create(page=page, idioma="en", intro="b")


class VistaTraduccionTest(TraduccionesBase):
    """C184, C186, C188 — lo que llega al navegador."""

    def _grupo(self, nombre, idioma):
        asignatura, _ = Subject.objects.get_or_create(
            name="Música", defaults={"code": "MUS"}
        )
        return Group.objects.create(
            name=nombre, subject=asignatura, academic_year="2026-2027", idioma=idioma
        )

    def test_una_pagina_sin_traducciones_se_ve_igual_que_siempre(self):
        """C184: ni selector ni aviso donde solo hay una lengua."""
        page = self._recurso(slug="sin-traducir")
        resp = self.client.get(page.url)
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.content.decode()
        self.assertIn("Estopa en 2005", cuerpo)
        self.assertNotIn('aria-label="Lengua del artículo"', cuerpo)

    def test_la_misma_url_responde_en_las_dos_lenguas(self):
        """C186."""
        page = self._recurso(slug="dos-lenguas")
        RecursoTraduccion.objects.create(
            page=page, idioma="en", intro="Estopa in 2005", body="<p>Rumba EN.</p>"
        )
        es = self.client.get(page.url + "?lang=es").content.decode()
        en = self.client.get(page.url + "?lang=en").content.decode()
        self.assertIn("Estopa en 2005", es)
        self.assertNotIn("Estopa in 2005", es)
        self.assertIn("Estopa in 2005", en)
        self.assertIn('aria-label="Lengua del artículo"', en)

    def test_el_aviso_de_respaldo_solo_sale_si_la_lengua_se_pidio(self):
        """Un cartel permanente se aprende a no leer.

        Con los 147 artículos que hoy están en inglés etiquetados como tales,
        avisar por defecto pondría el aviso en todas las páginas del alumnado
        ordinario. Solo se avisa a quien pidió la lengua por la URL.
        """
        page = self._recurso(slug="aviso", idioma="en", intro="Coldplay in 2008")
        alumno = User.objects.create_user(
            email="alumno4@example.com", password="testpassword123"
        )
        Enrollment.objects.create(user=alumno, group=self._grupo("3D", "es"))
        self.client.force_login(alumno)

        sin_pedir = self.client.get(page.url).content.decode()
        self.assertNotIn("todavía no está escrita", sin_pedir)
        self.assertIn("Coldplay in 2008", sin_pedir)

        pidiendo = self.client.get(page.url + "?lang=es").content.decode()
        self.assertIn("todavía no está escrita", pidiendo)

    def test_una_lengua_inventada_no_rompe_la_pagina(self):
        page = self._recurso(slug="lengua-rara")
        resp = self.client.get(page.url + "?lang=klingon")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Estopa en 2005", resp.content.decode())

    def test_el_alumno_de_la_bilingue_lee_en_ingles_sin_tocar_nada(self):
        """C188: el defecto sale del grupo, no del navegador."""
        page = self._recurso(slug="bilingue")
        RecursoTraduccion.objects.create(
            page=page, idioma="en", intro="Estopa in 2005", body="<p>Rumba EN.</p>"
        )
        alumno = User.objects.create_user(
            email="alumna@example.com", password="testpassword123"
        )
        Enrollment.objects.create(user=alumno, group=self._grupo("3A bil", "en"))
        self.client.force_login(alumno)
        self.assertIn("Estopa in 2005", self.client.get(page.url).content.decode())

    def test_el_alumno_de_un_grupo_ordinario_lee_en_castellano(self):
        page = self._recurso(slug="ordinario")
        RecursoTraduccion.objects.create(
            page=page, idioma="en", intro="Estopa in 2005", body="<p>Rumba EN.</p>"
        )
        alumno = User.objects.create_user(
            email="alumno2@example.com", password="testpassword123"
        )
        Enrollment.objects.create(user=alumno, group=self._grupo("3B", "es"))
        self.client.force_login(alumno)
        self.assertIn("Estopa en 2005", self.client.get(page.url).content.decode())

    def test_la_url_manda_sobre_el_grupo(self):
        """El profesor de la bilingüe quiere ver la versión castellana."""
        page = self._recurso(slug="url-manda")
        RecursoTraduccion.objects.create(
            page=page, idioma="en", intro="Estopa in 2005", body="<p>Rumba EN.</p>"
        )
        alumno = User.objects.create_user(
            email="alumno3@example.com", password="testpassword123"
        )
        Enrollment.objects.create(user=alumno, group=self._grupo("3C bil", "en"))
        self.client.force_login(alumno)
        cuerpo = self.client.get(page.url + "?lang=es").content.decode()
        self.assertIn("Estopa en 2005", cuerpo)

    def test_sin_matricula_no_hay_lengua_de_grupo(self):
        self.assertIsNone(idioma_del_alumno(self.user))


class ApiTraduccionesTest(TraduccionesBase):
    """C190, C191 — las dos versiones en una sola pasada."""

    URL = "/api/cms/blog-pages"

    def _post(self, payload):
        return self.client.post(
            self.URL, data=json.dumps(payload), content_type="application/json"
        )

    def _payload(self, **extra):
        base = {
            "title": "Viva la Vida",
            "date": "2026-09-15",
            "intro": "Coldplay en 2008",
            "body": "<p>Cuerda y timbal.</p>",
            "parent_page_id": self.biblioteca.id,
            "publish_immediately": True,
            "idioma": "es",
            "traducciones": [
                {
                    "idioma": "en",
                    "intro": "Coldplay in 2008",
                    "body": "<p>Strings and timpani.</p>",
                }
            ],
        }
        base.update(extra)
        return base

    def test_una_llamada_publica_las_dos_lenguas(self):
        """C190."""
        resp = self._post(self._payload())
        self.assertEqual(resp.status_code, 200, resp.content)
        datos = resp.json()
        self.assertEqual(datos["idioma"], "es")
        self.assertEqual(len(datos["traducciones"]), 1)

        page = RecursoPage.objects.get(id=datos["id"])
        self.assertEqual(page.texto("en")["intro"], "Coldplay in 2008")
        self.assertEqual(page.texto("es")["intro"], "Coldplay en 2008")
        self.assertEqual(Page.objects.filter(id=page.id).count(), 1)

    def test_un_articulo_de_departamento_no_lleva_traducciones(self):
        """C191."""
        departamento = BlogIndexPage(title="Filosofía", slug="filosofia-trad")
        self.root_page.add_child(instance=departamento)
        departamento.save_revision().publish()

        resp = self._post(self._payload(parent_page_id=departamento.id, idioma=""))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ArticuloPage.objects.filter(title="Viva la Vida").count(), 0)

    def test_dos_traducciones_en_la_misma_lengua_dan_400(self):
        resp = self._post(
            self._payload(
                traducciones=[
                    {"idioma": "en", "intro": "a"},
                    {"idioma": "en", "intro": "b"},
                ]
            )
        )
        self.assertEqual(resp.status_code, 400)

    def test_una_traduccion_en_la_lengua_base_da_400(self):
        resp = self._post(
            self._payload(traducciones=[{"idioma": "es", "intro": "a"}])
        )
        self.assertEqual(resp.status_code, 400)

    def test_una_lengua_desconocida_da_400(self):
        resp = self._post(self._payload(idioma="klingon", traducciones=[]))
        self.assertEqual(resp.status_code, 400)

    def test_actualizar_reemplaza_el_juego_de_traducciones(self):
        page_id = self._post(self._payload()).json()["id"]
        resp = self.client.put(
            f"{self.URL}/{page_id}",
            data=json.dumps({"traducciones": [], "publish_immediately": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        page = RecursoPage.objects.get(id=page_id)
        self.assertEqual(page.traducciones.count(), 0)
        self.assertEqual(page.texto("en")["idioma"], "es")


class DeteccionIdiomaTest(TestCase):
    """C193 — la lengua de lo ya publicado se mide, no se supone."""

    def test_distingue_castellano_de_ingles(self):
        from musica.management.commands.detectar_idioma_recursos import clasificar

        castellano = (
            "<p>La canción empieza con una guitarra sola y el bajo que entra "
            "en el segundo compás, porque lo que se busca es que el oído "
            "espere algo más.</p>"
        )
        ingles = (
            "<p>The song opens with a single guitar and the bass that comes in "
            "on the second bar, because what they are after is the feeling "
            "that there is something else coming.</p>"
        )
        self.assertEqual(clasificar(castellano)[0], "es")
        self.assertEqual(clasificar(ingles)[0], "en")

    def test_un_texto_corto_queda_en_duda(self):
        from musica.management.commands.detectar_idioma_recursos import clasificar

        self.assertEqual(clasificar("<p>Estopa, 2005.</p>")[0], "duda")
