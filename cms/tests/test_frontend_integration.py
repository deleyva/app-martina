from django.test import TestCase, Client
from cms.models import MusicLibraryIndexPage, ScorePage, MusicTag, MusicCategory, DictadoPage
from wagtail.models import Page

class FrontendIntegrationTest(TestCase):
    def setUp(self):
        # En Wagtail, la página raíz suele tener id=2 (creada por migración inicial)
        # Si no existe, la creamos o buscamos otra.
        # Asumimos que Page id=2 existe para simplificar, como en otros tests.
        self.root_page = Page.objects.filter(id=2).first()
        if not self.root_page:
             self.root_page = Page.objects.create(title="Root", slug="root", depth=1, path="0001")

        self.index_page = MusicLibraryIndexPage(title="Music Library", slug="music-library")
        self.root_page.add_child(instance=self.index_page)
        self.index_page.save_revision().publish()
        
        self.tag1 = MusicTag.objects.create(name="Jazz", color="#123456")
        self.tag2 = MusicTag.objects.create(name="Classical")
        
        self.score1 = ScorePage(title="Jazz Tune", slug="jazz-tune")
        self.index_page.add_child(instance=self.score1)
        self.score1.tags.add(self.tag1)
        self.score1.save_revision().publish()

        self.dictado1 = DictadoPage(title="Rhythmic Dictation", slug="rhythmic-dictation")
        self.index_page.add_child(instance=self.dictado1)
        self.dictado1.tags.add(self.tag1)
        self.dictado1.save_revision().publish()

    def test_search_form_presence(self):
        """Verifica que el formulario de búsqueda esté presente en el HTML response."""
        response = self.client.get(self.index_page.url)
        self.assertEqual(response.status_code, 200)
        # Buscamos partes clave del formulario
        self.assertContains(response, '<input type="text"', count=1) # Search input
        self.assertContains(response, 'name="q"')
        
    def test_tag_filter_links(self):
        """Verifica que los enlaces de filtrado por tags se generen correctamente."""
        response = self.client.get(self.index_page.url)
        self.assertEqual(response.status_code, 200)
        # Check for tag links
        self.assertContains(response, f'?tags={self.tag1.name}')
        self.assertContains(response, f'?tags={self.tag2.name}')
        
    def test_pagination_logic_js_loading(self):
        """Verifica que el JS de paginación se incluye y el viejo se ha ido."""
        response = self.client.get(self.index_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'const ITEMS_PER_PAGE = 5;')
        self.assertNotContains(response, 'function filterScores()')

    def test_regression_fixes(self):
        """
        Verifica correcciones de regresión:
        1. Tags son enlaces (<a>) y no <span>.
        2. Tags tienen estilos inline para colores.
        3. Iconos correctos para dictados.
        4. Texto del botón de filtro activo no splitteado.
        """
        response = self.client.get(self.index_page.url, {'tags': [self.tag1.name]})
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()

        # 1. Tags son enlaces
        self.assertIn(f'<a href="?tags={self.tag1.name}"', content)
        
        # 2. Estilos de color (Jazz tiene color #123456)
        self.assertIn('style="color: #123456; border-color: #123456;"', content)

        # 3. Icono de dictado (buscar parte del SVG path unico o la clase)
        # El SVG de dictado tiene una path específica
        self.assertIn('M15.536 8.464a5 5 0 010 7.072', content)

        # 4. Texto del filtro activo
        # Si el filtro está activo, debe mostrar "Jazz" y no "J, a, z, z"
        # Buscamos en el botón del dropdown
        self.assertIn(f'{self.tag1.name}', content)
        self.assertNotIn('J, a, z, z', content)
