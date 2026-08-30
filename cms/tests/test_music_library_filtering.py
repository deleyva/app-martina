import datetime
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, Client, RequestFactory
from django.utils import timezone
from wagtail.models import Page
from taggit.models import Tag
from cms.models import (
    BlogIndexPage,
    BlogPage,
    DictadoPage,
    MusicLibraryIndexPage,
    ScorePage,
    MusicCategory
)
from wagtail.test.utils import WagtailPageTests


class MusicLibraryFilteringTest(WagtailPageTests):
    def setUp(self):
        # Find root page
        self.root_page = Page.objects.get(id=2)

        # Create Index Page
        self.index_page = MusicLibraryIndexPage(
            title="Biblioteca Musical",
            slug="biblioteca-musical",
            intro="Bienvenido a la biblioteca",
        )
        self.root_page.add_child(instance=self.index_page)
        self.index_page.save_revision().publish()

        # Create Tags
        # Desde C37b las páginas etiquetan con taggit facetado, no con MusicTag.
        self.tag_jazz = Tag.objects.create(name="estilo:jazz", slug="estilo-jazz")
        self.tag_piano = Tag.objects.create(
            name="instrumento:piano", slug="instrumento-piano"
        )

        # Create Categories
        self.cat_ejercicios = MusicCategory.objects.create(name="Ejercicios")
        self.cat_repertorio = MusicCategory.objects.create(name="Repertorio")

        # Create Score Pages
        # Score 1: Jazz, Ejercicios
        self.score1 = ScorePage(
            title="Jazz Etude 1",
            slug="jazz-etude-1",
        )
        self.index_page.add_child(instance=self.score1)
        self.score1.save_revision().publish()
        self.score1.faceted_tags.add(self.tag_jazz)
        self.score1.categories.add(self.cat_ejercicios)
        self.score1.save()

        # Score 2: Piano, Repertorio
        self.score2 = ScorePage(
            title="Piano Sonata",
            slug="piano-sonata",
        )
        self.index_page.add_child(instance=self.score2)
        self.score2.save_revision().publish()
        self.score2.faceted_tags.add(self.tag_piano)
        self.score2.categories.add(self.cat_repertorio)
        self.score2.save()

        # Score 3: Jazz, Repertorio
        self.score3 = ScorePage(
            title="Jazz Ballad",
            slug="jazz-ballad",
        )
        self.index_page.add_child(instance=self.score3)
        self.score3.save_revision().publish()
        self.score3.faceted_tags.add(self.tag_jazz)
        self.score3.categories.add(self.cat_repertorio)
        self.score3.save()

        self.factory = RequestFactory()

    def test_filter_by_tag(self):
        # Request filtering by "Jazz" tag
        request = self.factory.get(self.index_page.url, {'tags': 'estilo:jazz'})
        # RequestFactory no pasa por el middleware, asi que no trae `user`.
        # `_filter_visible_pages` lo lee y reventaba con AttributeError.
        request.user = AnonymousUser()
        context = self.index_page.get_context(request)
        
        # Should return Score1 and Score3 only
        scores = context['scores']
        self.assertEqual(scores.count(), 2)
        self.assertIn(self.score1, scores)
        self.assertIn(self.score3, scores)
        self.assertNotIn(self.score2, scores)

    def test_filter_by_category(self):
        # Request filtering by "Ejercicios" category
        request = self.factory.get(self.index_page.url, {'categories': 'Ejercicios'})
        # RequestFactory no pasa por el middleware, asi que no trae `user`.
        # `_filter_visible_pages` lo lee y reventaba con AttributeError.
        request.user = AnonymousUser()
        context = self.index_page.get_context(request)
        
        # Should return Score1 only
        scores = context['scores']
        self.assertEqual(scores.count(), 1)
        self.assertIn(self.score1, scores)
        self.assertNotIn(self.score2, scores)
        self.assertNotIn(self.score3, scores)

    def test_filter_combined(self):
        # Filter by tag "Jazz" AND category "Repertorio" -> Should return score3
        response = self.client.get(
            self.index_page.url, {"tags": "estilo:jazz", "categories": "Repertorio"}
        )
        self.assertEqual(response.status_code, 200)
        scores = response.context["scores"]
        self.assertEqual(scores.count(), 1)
        self.assertEqual(scores[0], self.score3)

    def test_search_by_text(self):
        # Search for "Sonata" -> Should return score2
        response = self.client.get(self.index_page.url, {"q": "Sonata"})
        self.assertEqual(response.status_code, 200)
        scores = response.context["scores"]
        self.assertEqual(scores.count(), 1)
        self.assertEqual(scores[0], self.score2)

        # Search for "Jazz" -> Should return score1 and score3
        response = self.client.get(self.index_page.url, {"q": "Jazz"})
        self.assertEqual(response.status_code, 200)
        scores = response.context["scores"]
        self.assertEqual(scores.count(), 2)
        self.assertIn(self.score1, scores)
        self.assertIn(self.score3, scores)
        self.assertNotIn(self.score2, scores)

    def test_no_filter(self):
        # No filters
        request = self.factory.get(self.index_page.url)
        # RequestFactory no pasa por el middleware, asi que no trae `user`.
        # `_filter_visible_pages` lo lee y reventaba con AttributeError.
        request.user = AnonymousUser()
        context = self.index_page.get_context(request)
        
        # Should return all 3 scores
        scores = context['scores']
        self.assertEqual(scores.count(), 3)


class MusicLibraryTypeFilterTest(WagtailPageTests):
    """El filtro por tipo de página y su combinación con el texto libre."""

    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.index_page = MusicLibraryIndexPage(
            title="Biblioteca Musical",
            slug="biblioteca-tipos",
            intro="Bienvenido a la biblioteca",
        )
        self.root_page.add_child(instance=self.index_page)
        self.index_page.save_revision().publish()

        # Un elemento de cada tipo, todos con "armonia" en el título salvo uno,
        # para poder cruzar texto y tipo.
        self.score = ScorePage(title="Armonia en partitura", slug="armonia-partitura")
        self.index_page.add_child(instance=self.score)
        self.score.save_revision().publish()

        self.dictado = DictadoPage(
            title="Armonia dictada", slug="armonia-dictada", intro="Dictado de armonia"
        )
        self.index_page.add_child(instance=self.dictado)
        self.dictado.save_revision().publish()

        self.articulo = BlogPage(
            title="Armonia explicada",
            slug="armonia-explicada",
            date=datetime.date.today(),
            intro="Articulo sobre armonia",
        )
        self.index_page.add_child(instance=self.articulo)
        self.articulo.save_revision().publish()

        self.libro = BlogIndexPage(
            title="Armonia el libro", slug="armonia-libro", intro="Libro de armonia"
        )
        self.index_page.add_child(instance=self.libro)
        self.libro.save_revision().publish()

        self.otro = ScorePage(title="Contrapunto", slug="contrapunto")
        self.index_page.add_child(instance=self.otro)
        self.otro.save_revision().publish()

    def _titulos(self, response, clave):
        return {entry["page"].title for entry in response.context[clave]}

    def test_sin_filtro_de_tipo_salen_todos(self):
        response = self.client.get(self.index_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Armonia en partitura", self._titulos(response, "music_content"))
        self.assertIn("Armonia dictada", self._titulos(response, "music_content"))
        self.assertIn("Armonia explicada", self._titulos(response, "blog_entries"))
        self.assertIn("Armonia el libro", self._titulos(response, "blog_entries"))

    def test_filtrar_por_un_tipo(self):
        response = self.client.get(self.index_page.url, {"types": "dictado"})
        self.assertEqual(
            self._titulos(response, "music_content"), {"Armonia dictada"}
        )
        self.assertEqual(self._titulos(response, "blog_entries"), set())

    def test_filtrar_por_varios_tipos(self):
        response = self.client.get(
            self.index_page.url, {"types": ["articulo", "libro"]}
        )
        self.assertEqual(
            self._titulos(response, "blog_entries"),
            {"Armonia explicada", "Armonia el libro"},
        )
        self.assertEqual(self._titulos(response, "music_content"), set())

    def test_tipos_separados_por_coma(self):
        """La forma `?types=a,b` de los enlaces compartidos equivale a repetir el parámetro."""
        response = self.client.get(self.index_page.url, {"types": "articulo,libro"})
        self.assertEqual(
            self._titulos(response, "blog_entries"),
            {"Armonia explicada", "Armonia el libro"},
        )

    def test_texto_y_tipo_se_combinan(self):
        """Buscar "armonia" y acotar a partituras deja una sola, no las dos partituras."""
        response = self.client.get(
            self.index_page.url, {"q": "Armonia", "types": "partitura"}
        )
        self.assertEqual(
            self._titulos(response, "music_content"), {"Armonia en partitura"}
        )
        self.assertNotIn("Contrapunto", self._titulos(response, "music_content"))

    def test_contadores_ignoran_el_filtro_de_tipo(self):
        """Las pastillas cuentan sobre el texto, no sobre el tipo marcado."""
        response = self.client.get(
            self.index_page.url, {"q": "Armonia", "types": "dictado"}
        )
        counts = {f["slug"]: f["count"] for f in response.context["type_facets"]}
        self.assertEqual(counts["partitura"], 1)
        self.assertEqual(counts["dictado"], 1)
        self.assertEqual(counts["articulo"], 1)
        self.assertEqual(counts["libro"], 1)
        self.assertEqual(response.context["total_matches"], 4)

    def test_tipo_desconocido_se_ignora(self):
        response = self.client.get(self.index_page.url, {"types": "chorizo"})
        self.assertEqual(response.context["selected_types"], [])
        self.assertIn("Armonia dictada", self._titulos(response, "music_content"))

    def test_seleccion_marcada_en_las_pastillas(self):
        response = self.client.get(self.index_page.url, {"types": "test"})
        seleccionadas = [f["slug"] for f in response.context["type_facets"] if f["selected"]]
        self.assertEqual(seleccionadas, ["test"])
        self.assertEqual(response.context["types_query"], "test")


class MusicLibraryUnaccentSearchTest(WagtailPageTests):
    """El buscador ignora las tildes en ambos sentidos."""

    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.index_page = MusicLibraryIndexPage(
            title="Biblioteca Musical", slug="biblioteca-tildes", intro="Bienvenido"
        )
        self.root_page.add_child(instance=self.index_page)
        self.index_page.save_revision().publish()

        self.con_tilde = ScorePage(title="Armonía moderna", slug="armonia-moderna")
        self.index_page.add_child(instance=self.con_tilde)
        self.con_tilde.save_revision().publish()

        self.sin_tilde = ScorePage(title="Interpretacion basica", slug="interpretacion")
        self.index_page.add_child(instance=self.sin_tilde)
        self.sin_tilde.save_revision().publish()

    def test_buscar_sin_tilde_encuentra_con_tilde(self):
        response = self.client.get(self.index_page.url, {"q": "armonia"})
        self.assertIn(self.con_tilde, response.context["scores"])

    def test_buscar_con_tilde_encuentra_sin_tilde(self):
        response = self.client.get(self.index_page.url, {"q": "interpretación"})
        self.assertIn(self.sin_tilde, response.context["scores"])

    def test_la_busqueda_sigue_discriminando(self):
        """Ignorar tildes no puede convertir el buscador en un comodín."""
        response = self.client.get(self.index_page.url, {"q": "armonia"})
        self.assertNotIn(self.sin_tilde, response.context["scores"])

    def test_etiquetas_tambien_ignoran_tildes(self):
        tag = Tag.objects.create(name="concepto:educacion-auditiva", slug="ea")
        self.con_tilde.faceted_tags.add(tag)
        self.con_tilde.save()
        response = self.client.get(self.index_page.url, {"q": "educación"})
        self.assertIn(self.con_tilde, response.context["scores"])
