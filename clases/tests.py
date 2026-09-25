from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from clases.models import ClassSessionItem, GroupLibraryItem, Group, Student, Enrollment
from my_library.models import LibraryItem
from wagtail.documents.models import Document

User = get_user_model()


class MediaMethodsTest(TestCase):
    def test_group_library_item_get_related_scorepage_media_no_score(self):
        item = GroupLibraryItem()
        item.get_related_scorepage = lambda: None

        media = item.get_related_scorepage_media()
        assert media == {
            "score": None,
            "audios": [],
            "embeds": [],
        }

    def test_group_library_item_get_related_scorepage_media_with_score(self):
        class DummyScore:
            def get_audios(self):
                return ["a1"]

            def get_embeds(self):
                return ["e1"]

        item = GroupLibraryItem()
        item.get_related_scorepage = lambda: DummyScore()

        media = item.get_related_scorepage_media()
        assert media["score"] is not None
        assert media["audios"] == ["a1"]
        assert media["embeds"] == ["e1"]

    def test_class_session_item_get_related_scorepage_media_no_score(self):
        item = ClassSessionItem()
        item.get_related_scorepage = lambda: None

        media = item.get_related_scorepage_media()
        assert media == {
            "score": None,
            "audios": [],
            "embeds": [],
        }

    def test_class_session_item_get_related_scorepage_media_with_score(self):
        class DummyScore:
            def get_audios(self):
                return ["a1"]

            def get_embeds(self):
                return ["e1"]

        item = ClassSessionItem()
        item.get_related_scorepage = lambda: DummyScore()

        media = item.get_related_scorepage_media()
        assert media["score"] is not None
        assert media["audios"] == ["a1"]
        assert media["embeds"] == ["e1"]


class LibraryAdditionReproductionTest(TestCase):
    def setUp(self):
        # Create a teacher
        self.teacher = User.objects.create_user(
            email='teacher@example.com',
            password='password',
            is_staff=True
        )

        # Create a student user
        self.student_user = User.objects.create_user(
            email='student@example.com',
            password='password'
        )

        # Create a group
        from clases.models import Subject
        subject = Subject.objects.create(name="Test Subject", code="TEST")
        self.group = Group.objects.create(name="Test Group", subject=subject)
        self.group.teachers.add(self.teacher)

        # Create Enrollment (new way)
        Enrollment.objects.create(user=self.student_user, group=self.group)

        # Create a content item (Document)
        self.document = Document.objects.create(title="Test Document")
        self.content_type = ContentType.objects.get_for_model(Document)

        # Client setup
        self.client = Client()
        self.client.login(email='teacher@example.com', password='password')

    def test_add_to_multiple_libraries_student(self):
        """
        Test adding an item to a student's personal library.
        """
        url = '/clases/libraries/add-multiple/'
        
        # Data for POST request
        data = {
            'content_type_id': self.content_type.id,
            'object_id': self.document.id,
            'student_ids': [self.student_user.id],  # Sending User ID (not Student ID)
        }

        response = self.client.post(url, data)

        # Check response
        self.assertEqual(response.status_code, 200)
        
        # Check if item was added to student's library
        is_in_library = LibraryItem.objects.filter(
            user=self.student_user,
            content_type=self.content_type,
            object_id=self.document.id
        ).exists()
        
        self.assertTrue(is_in_library, "Item should be in student's library")

    def test_add_to_multiple_libraries_group(self):
        """
        Test adding an item to a group library.
        """
        from clases.models import GroupLibraryItem
        url = '/clases/libraries/add-multiple/'
        
        data = {
            'content_type_id': self.content_type.id,
            'object_id': self.document.id,
            'group_ids': [self.group.id],
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

        is_in_group_library = GroupLibraryItem.objects.filter(
            group=self.group,
            content_type=self.content_type,
            object_id=self.document.id
        ).exists()
        self.assertTrue(is_in_group_library, "Item should be in group library")


class ClassSessionItemViewerPaginaTest(TestCase):
    """Una canción o un dictado abiertos desde una sesión redirigen al artículo.

    `from_view` se leía después de usarse en esa redirección, así que la rama
    daba siempre `UnboundLocalError` (un 500) y ningún test pasaba por ella.
    """

    def setUp(self):
        from datetime import date

        from wagtail.models import Site

        from clases.models import ClassSession, Subject
        from musica.models import MusicLibraryIndexPage, RecursoPage

        User = get_user_model()
        sitio = Site.objects.get(is_default_site=True)
        biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-visor")
        sitio.root_page.add_child(instance=biblioteca)
        biblioteca.save_revision().publish()
        self.cancion = RecursoPage(
            title="Una canción", slug="una-cancion-visor",
            date="2026-09-25", intro="x", body="<p>Cuerpo.</p>",
        )
        biblioteca.add_child(instance=self.cancion)
        self.cancion.save_revision().publish()

        asignatura, _ = Subject.objects.get_or_create(
            name="Música", defaults={"code": "MUS-VIS"}
        )
        grupo = Group.objects.create(
            name="1A-vis", subject=asignatura, academic_year="2026-2027"
        )
        self.profe = User.objects.create_user(
            email="profe-vis@example.com", password="x123456789", is_staff=True
        )
        grupo.teachers.add(self.profe)
        self.sesion = ClassSession.objects.create(
            teacher=self.profe, group=grupo, date=date(2026, 9, 25), title="Sesión"
        )
        self.item = ClassSessionItem.objects.create(
            session=self.sesion,
            content_type=ContentType.objects.get_for_model(RecursoPage),
            object_id=self.cancion.pk,
        )

    def _url(self, desde):
        from django.urls import reverse

        url = reverse(
            "clases:class_session_item_viewer", args=[self.sesion.pk, self.item.pk]
        )
        return f"{url}?from={desde}"

    def test_redirige_al_articulo_con_el_contexto_de_la_sesion(self):
        self.client.force_login(self.profe)
        for desde, cola in (
            ("view", f"?from_session={self.sesion.pk}"),
            ("edit", f"?from_session={self.sesion.pk}&from=edit"),
        ):
            with self.subTest(desde=desde):
                respuesta = self.client.get(self._url(desde))
                self.assertEqual(respuesta.status_code, 302)
                self.assertTrue(respuesta["Location"].endswith(cola))
                self.assertIn("una-cancion-visor", respuesta["Location"])
