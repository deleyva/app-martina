"""Tests para el endpoint POST /api/cms/blog-pages."""

import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from wagtail.models import Page

from blogs.models import ArticuloPage, BlogIndexPage
from musica.models import MusicCategory, MusicLibraryIndexPage, RecursoPage

User = get_user_model()


class BlogPageAPITest(TestCase):
    """POST /api/cms/blog-pages contra un blog de departamento.

    Usa django_auth (sesión de Django), siguiendo el patrón del proyecto.

    Desde la fase 25 la ruta sirve a dos modelos y elige por el padre: bajo un
    `BlogIndexPage` crea un `ArticuloPage`, bajo la biblioteca musical un
    `RecursoPage`. Esta clase cubre el primer lado y `BlogPageMetadatosMusicales`
    hereda sus casos para cubrir el segundo, cambiando solo `PADRE` y `MODELO`.
    """

    MODELO = ArticuloPage

    def _crear_padre(self):
        padre = BlogIndexPage(title="Blog Test", slug="blog-test-api")
        self.root_page.add_child(instance=padre)
        return padre

    def setUp(self):
        # Usuario admin para autenticación
        self.user = User.objects.create_superuser(
            email="testadmin@example.com",
            password="testpassword123",
        )
        self.client.force_login(self.user)

        # Página raíz de Wagtail (depth=1)
        self.root_page = Page.objects.filter(depth=1).first()

        # El padre decide qué modelo crea el endpoint.
        self.blog_index = self._crear_padre()
        self.blog_index.save_revision().publish()

        # Snippets auxiliares
        self.cat = MusicCategory.objects.create(name="Teoría Musical")
        # Desde C37b las páginas etiquetan con nombres facetados de taggit.
        self.etiqueta = "dificultad:facil"

        self.url = "/api/cms/blog-pages"

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    # ------------------------------------------------------------------
    # Casos de éxito
    # ------------------------------------------------------------------

    def test_crear_blogpage_minima_como_borrador(self):
        """Debe crear una BlogPage como borrador con los campos mínimos."""
        response = self._post(
            {
                "title": "Mi primer artículo",
                "date": "2024-09-01",
                "intro": "Este es un resumen del artículo.",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["title"], "Mi primer artículo")
        self.assertFalse(data["live"])
        self.assertIn("/cms/pages/", data["edit_url"])
        self.assertIn("view_draft", data["preview_url"])

        page = self.MODELO.objects.get(id=data["id"])
        self.assertEqual(page.intro, "Este es un resumen del artículo.")
        self.assertFalse(page.live)

    def test_crear_blogpage_completa_y_publicar(self):
        """Debe crear una BlogPage completa y publicarla inmediatamente."""
        response = self._post(
            {
                "title": "Artículo completo",
                "date": "2024-10-15",
                "intro": "Resumen completo del artículo.",
                "body": "<p>Cuerpo del artículo en <strong>HTML</strong>.</p>",
                # Las categorías son musicales, así que solo van cuando el padre
                # es la biblioteca. En un departamento la respuesta es 400, y eso
                # lo comprueba `test_las_categorias_musicales_no_valen_en_un_departamento`.
                **({"category_ids": [self.cat.id]} if self.MODELO is RecursoPage else {}),
                "tags": [self.etiqueta],
                "parent_page_id": self.blog_index.id,
                "publish_immediately": True,
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["live"])

        page = self.MODELO.objects.get(id=data["id"])
        self.assertEqual(page.body, "<p>Cuerpo del artículo en <strong>HTML</strong>.</p>")
        if self.MODELO is RecursoPage:
            self.assertIn(self.cat, page.categories.all())
        else:
            self.assertFalse(
                hasattr(page, "categories"),
                "un artículo de departamento no tiene categorías musicales",
            )
        self.assertIn(self.etiqueta, [t.name for t in page.faceted_tags.all()])

    def test_sin_parent_usa_primer_blogindexpage(self):
        """Sin parent_page_id debe autodetectar la primera BlogIndexPage."""
        response = self._post(
            {
                "title": "Sin padre explícito",
                "date": "2024-11-01",
                "intro": "Test autodetección de padre.",
            }
        )
        self.assertEqual(response.status_code, 200)
        page = self.MODELO.objects.get(id=response.json()["id"])
        self.assertEqual(page.get_parent().specific, self.blog_index)

    # ------------------------------------------------------------------
    # Validaciones / errores
    # ------------------------------------------------------------------

    def test_parent_page_id_invalido_devuelve_400(self):
        """Un parent_page_id inexistente debe devolver 400."""
        response = self._post(
            {
                "title": "Artículo huérfano",
                "date": "2024-09-01",
                "intro": "Padre inexistente.",
                "parent_page_id": 99999,
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_category_id_invalido_devuelve_400(self):
        """Un category_id inexistente debe devolver 400."""
        response = self._post(
            {
                "title": "Categoría rota",
                "date": "2024-09-01",
                "intro": "Resumen.",
                "category_ids": [99999],
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_tag_ids_se_rechaza_con_400(self):
        """`tag_ids` se retiró con MusicTag (C37b). Falla alto en vez de
        ignorarse: un cliente viejo publicaría sin etiquetas y nadie se
        enteraría hasta buscarlas meses después."""
        response = self._post(
            {
                "title": "Cliente viejo",
                "date": "2024-09-01",
                "intro": "Resumen.",
                "tag_ids": [99999],
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("tag_ids", response.json()["detail"])

    def test_una_faceta_inventada_devuelve_400(self):
        """`caracter` no existe en facets.FACETAS: la etiqueta se crearía pero
        no agruparía ni filtraría."""
        response = self._post(
            {
                "title": "Faceta rara",
                "date": "2024-09-01",
                "intro": "Resumen.",
                "tags": ["caracter:melancolico"],
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_borrador_no_live(self):
        """Una página creada sin publish_immediately debe quedar como borrador."""
        response = self._post(
            {
                "title": "Borrador",
                "date": "2024-09-01",
                "intro": "Este es un borrador.",
                "publish_immediately": False,
                "parent_page_id": self.blog_index.id,
            }
        )
        self.assertEqual(response.status_code, 200)
        page = self.MODELO.objects.get(id=response.json()["id"])
        self.assertFalse(page.live)

    def test_las_categorias_musicales_no_valen_en_un_departamento(self):
        """La frontera de la fase 25, comprobada por su lado feo.

        `MusicCategory` es un vocabulario de la biblioteca. Antes se le podía
        colgar a un artículo de departamento porque los dos eran el mismo
        modelo, y de hecho había una fila haciéndolo: la categoría «COFOTAP»
        pegada a un artículo del blog de COFOTAP. Ahora se rechaza, y con un
        mensaje que dice qué hacer.
        """
        if self.MODELO is RecursoPage:
            self.skipTest("bajo la biblioteca musical las categorías sí valen")
        resp = self._post({
            "title": "Salida al Moncayo",
            "date": "2026-09-04",
            "intro": "Crónica de la excursión.",
            "parent_page_id": self.blog_index.id,
            "category_ids": [self.cat.id],
        })
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("categorías musicales", resp.json()["detail"])

    def test_la_ficha_musical_no_vale_en_un_departamento(self):
        """Lo que pidió Jesús, comprobado: nada de fichas en los blogs."""
        if self.MODELO is RecursoPage:
            self.skipTest("bajo la biblioteca musical la ficha sí vale")
        resp = self._post({
            "title": "Salida al Moncayo",
            "date": "2026-09-04",
            "intro": "Crónica de la excursión.",
            "parent_page_id": self.blog_index.id,
            "artist": "Fito & Fitipaldis",
            "tempo_bpm": 151,
        })
        self.assertEqual(resp.status_code, 400, resp.content)
        detalle = resp.json()["detail"]
        self.assertIn("no tiene ficha musical", detalle)
        self.assertIn("artist", detalle)
        self.assertIn("tempo_bpm", detalle)

    def test_sin_autenticar_devuelve_401(self):
        """Sin sesión activa debe devolver 401 o 403."""
        self.client.logout()
        response = self._post(
            {
                "title": "Sin auth",
                "date": "2024-09-01",
                "intro": "Intento sin autenticar.",
            }
        )
        self.assertIn(response.status_code, [401, 403])


class BlogPageMetadatosMusicalesTest(BlogPageAPITest):
    """Ficha musical, guardada como manda el estándar (2026-08-29).

    Cuelga de la biblioteca musical, no de un departamento: desde la fase 25 la
    ficha musical solo existe en `RecursoPage`, y mandarla a un artículo de
    departamento devuelve 400 a propósito. Al heredar de la clase de arriba,
    estos mismos casos comprueban además que el endpoint elige bien el modelo
    según el padre.

    Tonalidad como `fifths` + `mode` (MusicXML 4.0; el meta-evento MIDI FF 59
    guarda exactamente lo mismo en `sf`/`mi`). Compás como dos enteros
    (`beats`/`beat-type`, FF 58 `nn`/`dd`). Tempo numérico. Nada de texto.
    """

    MODELO = RecursoPage

    def _crear_padre(self):
        padre = MusicLibraryIndexPage(title="Biblioteca", slug="biblioteca-api")
        self.root_page.add_child(instance=padre)
        return padre

    # Por la boca vive el pez, Fito & Fitipaldis: Si menor = 2 sostenidos.
    FICHA = {
        "artist": "Fito & Fitipaldis",
        "key_fifths": 2,
        "key_mode": "minor",
        "time_signature_beats": 4,
        "time_signature_beat_type": 4,
        "tempo_bpm": 151,
        "duration_seconds": 204,
        "reference": "vers. directo",
    }

    def test_crear_con_ficha_persiste_todos_los_campos(self):
        resp = self._post({
            "title": "Por la boca vive el pez",
            "date": "2026-08-29",
            "intro": "Repertorio de El Grupo Luciérnaga.",
            "parent_page_id": self.blog_index.id,
            **self.FICHA,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        page = self.MODELO.objects.get(id=resp.json()["id"])
        for campo, esperado in self.FICHA.items():
            self.assertEqual(getattr(page, campo), esperado, f"campo {campo}")

    def test_la_respuesta_devuelve_dato_y_presentacion(self):
        resp = self._post({
            "title": "Uptown Funk",
            "date": "2026-08-29",
            "intro": "Repertorio.",
            "parent_page_id": self.blog_index.id,
            **self.FICHA,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        cuerpo = resp.json()
        self.assertEqual(cuerpo["key_fifths"], 2)
        self.assertEqual(cuerpo["key_display"], "Bm")
        self.assertEqual(cuerpo["time_signature_display"], "4/4")
        self.assertEqual(cuerpo["duration_display"], "3:24")

    def test_circulo_de_quintas_en_los_dos_sentidos(self):
        """La conversión es la razón de ser del formato numérico."""
        page = RecursoPage(title="x", slug="x", date="2026-08-29", intro="x")
        casos_mayor = {-7: "Cb", -4: "Ab", -1: "F", 0: "C", 2: "D", 5: "B", 7: "C#"}
        for fifths, esperado in casos_mayor.items():
            page.key_fifths, page.key_mode = fifths, "major"
            self.assertEqual(page.key_display, esperado, f"mayor {fifths}")
        casos_menor = {0: "Am", 1: "Em", 2: "Bm", -1: "Dm", 3: "F#m", -3: "Cm"}
        for fifths, esperado in casos_menor.items():
            page.key_fifths, page.key_mode = fifths, "minor"
            self.assertEqual(page.key_display, esperado, f"menor {fifths}")

    def test_modo_modal_no_inventa_tonica(self):
        """Con un modo que no es mayor ni menor, la tónica no se deduce sola."""
        page = RecursoPage(title="x", slug="x", date="2026-08-29", intro="x")
        page.key_fifths, page.key_mode = 1, "mixolydian"
        self.assertIn("mixolidio", page.key_display)

    def test_sin_armadura_no_pinta_tonalidad(self):
        page = RecursoPage(title="x", slug="x", date="2026-08-29", intro="x")
        self.assertEqual(page.key_display, "")
        self.assertEqual(page.time_signature_display, "")
        self.assertEqual(page.duration_display, "")
        self.assertFalse(page.tiene_ficha_musical)

    def test_do_mayor_es_cero_no_vacio(self):
        """Trampa clásica: fifths=0 es Do mayor, no 'sin dato'."""
        page = RecursoPage(title="x", slug="x", date="2026-08-29", intro="x")
        page.key_fifths, page.key_mode = 0, "major"
        self.assertEqual(page.key_display, "C")
        self.assertTrue(page.tiene_ficha_musical)

    def test_una_blogpage_normal_sigue_creandose_sin_ficha(self):
        """Anti-criterio: los artículos que no son canciones no se rompen."""
        resp = self._post({
            "title": "Artículo sin música",
            "date": "2026-08-29",
            "intro": "Un artículo normal y corriente.",
            "parent_page_id": self.blog_index.id,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        page = self.MODELO.objects.get(id=resp.json()["id"])
        self.assertIsNone(page.key_fifths)
        self.assertFalse(page.tiene_ficha_musical)

    def test_la_ficha_se_pinta_en_la_pagina(self):
        """Existir en la base no es verse: la plantilla tiene que pintarla."""
        resp = self._post({
            "title": "Entre dos tierras",
            "date": "2026-08-29",
            "intro": "Repertorio.",
            "parent_page_id": self.blog_index.id,
            "publish_immediately": True,
            **self.FICHA,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        page = self.MODELO.objects.get(id=resp.json()["id"])
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}  # lo pide el context processor de impersonación
        html = page.serve(request).render().content.decode()
        self.assertIn("Ficha musical", html)
        self.assertIn("Bm", html)          # no "2"
        self.assertIn("4/4", html)
        self.assertIn("151 BPM", html)
        self.assertIn("3:24", html)
        # {# ... #} en Django es de UNA linea: uno multilinea se imprime tal
        # cual en la pagina. Los asserts de arriba pasaban con el comentario
        # visible encima de la tarjeta; esto lo pillo el navegador, no el test.
        self.assertNotIn("{#", html)
        self.assertNotIn("MusicXML/MIDI", html)
