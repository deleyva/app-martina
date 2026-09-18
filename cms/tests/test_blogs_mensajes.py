"""Los mensajes de Django, en el subdominio de blogs (2026-09-18).

`blogs/base.html` era el unico de los cinco `base` del proyecto que no
recorria `messages`. Un mensaje que no se recorre no se marca como leido: se
queda en la sesion y sale entero la proxima vez que esa persona abre una
plantilla que si los pinta —el admin de Wagtail—, de golpe y descolocado.

El dano no era el amontonamiento, era lo que tapaba. Wagtail, cuando te echa
de `/cms/`, encola el motivo ("no tienes permiso para acceder al admin"). En
blogs ese motivo no se pintaba nunca: veias la pantalla de acceso otra vez,
sin explicacion, volvias a entrar, y cada vuelta dejaba dos mensajes mas.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Site

from blogs.models import ArticuloPage, BlogIndexPage

User = get_user_model()


class MensajesEnBlogsTest(TestCase):
    def setUp(self):
        root = Site.objects.get(is_default_site=True).root_page
        self.index = BlogIndexPage(title="Blogs", slug="blogs-mensajes")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()

        self.articulo = ArticuloPage(
            title="Otro articulo", slug="otro-articulo", date="2026-09-18", intro="x"
        )
        self.index.add_child(instance=self.articulo)
        self.articulo.save_revision().publish()

        # Sin `wagtailadmin.access_admin`: el caso real, un profesor al que
        # alguien ha pasado el enlace de /cms/ y todavia no tiene permiso.
        self.profesor = User.objects.create_user(
            email="profesor@example.com", password="x123456789"
        )

    def test_el_motivo_del_rechazo_se_ve_en_blogs(self):
        """El criterio de verdad: por que te ha echado de /cms/, escrito."""
        self.client.force_login(self.profesor)
        self.client.get("/cms/")  # encola "no tienes permiso..."
        html = self.client.get(self.articulo.url).content.decode()
        self.assertIn("permission to access the admin", html)

    def test_no_queda_nada_en_la_cola_despues_de_pintarlos(self):
        """Lo que producia el amontonamiento: no consumirlos.

        Las dos mitades importan. Sin la primera el test pasa tambien con la
        plantilla rota, porque entonces el mensaje no sale nunca y "no sale la
        segunda vez" se cumple por el motivo equivocado.
        """
        self.client.force_login(self.profesor)
        self.client.get("/cms/")
        primera = self.client.get(self.articulo.url).content.decode()
        self.assertIn("permission to access the admin", primera)
        segunda = self.client.get(self.articulo.url).content.decode()
        self.assertNotIn("permission to access the admin", segunda)

    def test_sin_mensajes_no_pinta_el_hueco(self):
        html = self.client.get(self.articulo.url).content.decode()
        self.assertNotIn("border-l-2 border-black bg-gray-50", html)
