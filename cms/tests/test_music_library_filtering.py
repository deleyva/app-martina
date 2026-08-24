import datetime
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, Client, RequestFactory
from django.utils import timezone
from wagtail.models import Page
from taggit.models import Tag
from cms.models import (
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
