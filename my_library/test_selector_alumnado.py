"""El alumnado sale del HTML de los artículos (2026-09-16).

El diálogo de «añadir a bibliotecas» se incluye una vez por cada botón de
biblioteca de la página, y cada copia llevaba dentro la lista entera del
alumnado con sus correos. Medido en producción sobre un artículo con vídeos:
**28 copias y 591 correos**, 736 KB frente a los 80 KB que recibe un visitante,
sin que nadie hubiera abierto el diálogo.

Ni un alumno ni un visitante llegaron a recibir esa lista; lo que estos tests
fijan es que tampoco viaje por adelantado al navegador del profesor, y que la
URL que ahora la sirve tenga la misma cerradura que tenía el diálogo.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Site

from clases.models import Enrollment, Group, Subject
from musica.models import MusicLibraryIndexPage, RecursoPage

User = get_user_model()


class SelectorAlumnadoTest(TestCase):
    def setUp(self):
        self.sitio = Site.objects.get(is_default_site=True)
        self.biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-sel")
        self.sitio.root_page.add_child(instance=self.biblioteca)
        self.biblioteca.save_revision().publish()

        self.cancion = RecursoPage(
            title="Una canción", slug="una-cancion-sel",
            date="2026-09-16", intro="x", body="<p>Cuerpo.</p>",
        )
        self.biblioteca.add_child(instance=self.cancion)
        self.cancion.save_revision().publish()

        asignatura, _ = Subject.objects.get_or_create(
            name="Música", defaults={"code": "MUS-SEL"}
        )
        self.grupo = Group.objects.create(
            name="3A-sel", subject=asignatura, academic_year="2026-2027"
        )
        self.profe = User.objects.create_user(
            email="profe-sel@example.com", password="x123456789", is_staff=True
        )
        self.grupo.teachers.add(self.profe)
        self.alumna = User.objects.create_user(
            email="alumna-sel@example.com", password="x123456789"
        )
        Enrollment.objects.create(user=self.alumna, group=self.grupo)

    def _html(self, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get(
            self.cancion.url, follow=True, HTTP_HOST=self.sitio.hostname
        ).content.decode()

    # ---- lo que NO viaja en el artículo -------------------------------

    def test_el_articulo_no_lleva_correos_del_alumnado(self):
        """El caso que motivó todo: la página vista por un profesor."""
        self.assertNotIn(self.alumna.email, self._html(self.profe))

    def test_un_alumno_tampoco_los_recibe(self):
        self.assertNotIn(self.alumna.email, self._html(self.alumna))

    def test_un_visitante_sin_sesion_tampoco(self):
        self.assertNotIn(self.alumna.email, self._html())

    # ---- la puerta nueva ----------------------------------------------

    def test_el_profesor_recibe_su_alumnado_al_pedirlo(self):
        self.client.force_login(self.profe)
        respuesta = self.client.get(reverse("my_library:students_picker"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.alumna.email, respuesta.content.decode())

    def test_un_alumno_no_puede_pedir_la_lista(self):
        """La cerradura está en la vista, no en la plantilla."""
        self.client.force_login(self.alumna)
        self.assertEqual(
            self.client.get(reverse("my_library:students_picker")).status_code, 403
        )

    def test_un_profesor_sin_grupos_no_recibe_a_nadie(self):
        otro = User.objects.create_user(
            email="otro-profe@example.com", password="x123456789", is_staff=True
        )
        self.client.force_login(otro)
        respuesta = self.client.get(reverse("my_library:students_picker"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn(self.alumna.email, respuesta.content.decode())

    def test_un_profesor_no_ve_alumnado_de_grupos_ajenos(self):
        """Lo que impide que la URL sea un listado del centro entero."""
        ajeno = Group.objects.create(
            name="4B-ajeno", subject=Subject.objects.first(), academic_year="2026-2027"
        )
        intruso = User.objects.create_user(
            email="intruso-sel@example.com", password="x123456789"
        )
        Enrollment.objects.create(user=intruso, group=ajeno)

        self.client.force_login(self.profe)
        html = self.client.get(reverse("my_library:students_picker")).content.decode()
        self.assertIn(self.alumna.email, html)
        self.assertNotIn(intruso.email, html)

    def test_sin_sesion_la_url_no_sirve_nada(self):
        respuesta = self.client.get(reverse("my_library:students_picker"))
        self.assertIn(respuesta.status_code, (302, 403))
