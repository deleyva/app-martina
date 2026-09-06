"""El comando `import_blogspot` contra base de datos, sin tocar la red.

Los feeds se sustituyen por diccionarios con la forma exacta que devuelve
Blogger, y `_descargar_imagen` por una imagen de un píxel: lo que se prueba
aquí es lo que el comando escribe en la BD, no si Google contesta.
"""

from io import BytesIO
from unittest import mock

from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from wagtail.images import get_image_model
from wagtail.models import Collection, Page

from blogs.blogspot import BLOG_MAP
from blogs.models import ArticuloPage, BlogIndexPage

# PNG de 1x1 válido: basta para que Willow calcule ancho y alto.
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def _entrada(titulo, slug, publicado, cuerpo, categorias=()):
    """La forma exacta de una entrada del feed JSON de Blogger."""
    return {
        "id": {"$t": f"tag:blogger.com,1999:blog-1.post-{abs(hash(slug))}"},
        "title": {"$t": titulo},
        "published": {"$t": publicado},
        "content": {"$t": cuerpo},
        "category": [{"term": c} for c in categorias],
        "link": [
            {"rel": "alternate", "href": f"https://dmusicaiesmbescos.blogspot.com/2023/05/{slug}.html"}
        ],
    }


class ImportBlogspotTest(TestCase):
    def setUp(self):
        root = Page.objects.filter(depth=1).first()
        self.musica = BlogIndexPage(title="Música", slug="musica")
        root.add_child(instance=self.musica)
        self.musica.save_revision().publish()

    def _importar(self, entradas, **opciones):
        def feed_falso(host, tipo="posts"):
            return entradas if tipo == "posts" else []

        def imagen_falsa(self_cmd, url, titulo, coleccion, informe):
            imagen = get_image_model()(title=titulo[:255], collection=coleccion)
            imagen.file = ImageFile(BytesIO(PNG_1PX), name="falsa.png")
            imagen.save()
            informe.imagenes_ok += 1
            return imagen

        with mock.patch("blogs.management.commands.import_blogspot.leer_feed", feed_falso), \
             mock.patch(
                 "blogs.management.commands.import_blogspot.Command._descargar_imagen",
                 imagen_falsa,
             ):
            call_command("import_blogspot", blog=["dmusicaiesmbescos"], verbosity=0, **opciones)

    # -- C107: el mapa se valida antes de escribir nada -------------------

    def test_un_blog_desconocido_falla_sin_escribir_nada(self):
        with self.assertRaises(CommandError):
            call_command("import_blogspot", blog=["blogdeunprofe"], verbosity=0)
        self.assertEqual(ArticuloPage.objects.count(), 0)

    def test_un_departamento_que_no_existe_aborta_antes_de_importar(self):
        # Mejor no importar nada que importar la mitad y dejar huérfanos.
        self.musica.slug = "musica-renombrada"
        self.musica.save()
        with self.assertRaises(CommandError) as cm:
            call_command("import_blogspot", blog=["dmusicaiesmbescos"], verbosity=0)
        self.assertIn("musica", str(cm.exception))
        self.assertEqual(ArticuloPage.objects.count(), 0)

    def test_los_dieciseis_destinos_del_mapa_son_distintos(self):
        self.assertEqual(len(set(BLOG_MAP.values())), len(BLOG_MAP))

    # -- lo que se escribe ------------------------------------------------

    def test_un_post_se_convierte_en_articulo_publicado(self):
        self._importar([_entrada("Concierto de Navidad", "concierto", "2023-12-20T10:00:00.000-08:00",
                                 "<p><span style='color:red'>Fue estupendo.</span></p>")])
        articulo = ArticuloPage.objects.get(slug="concierto")
        self.assertTrue(articulo.live)
        self.assertEqual(articulo.title, "Concierto de Navidad")
        self.assertEqual(articulo.intro, "Fue estupendo.")
        self.assertNotIn("style=", articulo.body)
        self.assertEqual(articulo.get_parent().specific, self.musica)

    def test_se_conserva_la_fecha_original_no_la_de_hoy(self):
        # C113. Un archivo importado con la fecha del import no es un archivo.
        self._importar([_entrada("Viejo", "viejo", "2019-03-19T08:00:00.000-08:00", "<p>Texto</p>")])
        articulo = ArticuloPage.objects.get(slug="viejo")
        self.assertEqual(articulo.date.year, 2019)
        self.assertEqual(articulo.first_published_at.year, 2019)

    def test_con_draft_no_se_publica(self):
        self._importar([_entrada("Borrador", "borrador", "2023-05-01T10:00:00.000-08:00", "<p>x</p>")],
                       draft=True)
        self.assertFalse(ArticuloPage.objects.get(slug="borrador").live)

    def test_las_etiquetas_entran_facetadas(self):
        # C115 / A27.6.
        self._importar([_entrada("Con etiquetas", "etiquetado", "2023-05-01T10:00:00.000-08:00",
                                 "<p>x</p>", categorias=["1ºESO", "información"])])
        nombres = set(ArticuloPage.objects.get(slug="etiquetado").faceted_tags.names())
        self.assertEqual(nombres, {"curso:1-eso", "tema:informacion"})

    def test_la_primera_imagen_se_promociona_a_portada(self):
        self._importar([_entrada("Con foto", "con-foto", "2023-05-01T10:00:00.000-08:00",
                                 "<p>Texto</p><img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/>")])
        articulo = ArticuloPage.objects.get(slug="con-foto")
        self.assertIsNotNone(articulo.featured_image)

    def test_no_queda_ni_una_url_de_google_en_el_cuerpo(self):
        # C108 / A27.3, comprobado sobre TODOS los cuerpos, no una muestra.
        self._importar([
            _entrada("A", "a", "2023-05-01T10:00:00.000-08:00",
                     "<a href='https://blogger.googleusercontent.com/img/b/x/s1600/f.jpg'>"
                     "<img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/></a>"),
            _entrada("B", "b", "2023-05-02T10:00:00.000-08:00",
                     "<img src='https://1.bp.blogspot.com/-x/y=s320'/>"),
        ])
        for articulo in ArticuloPage.objects.exclude(source_url=""):
            self.assertNotIn("googleusercontent", articulo.body)
            self.assertNotIn("bp.blogspot", articulo.body)

    def test_una_imagen_que_no_se_puede_bajar_no_deja_el_src_apuntando_a_google(self):
        # A27.3: preferimos perder la foto a dejar un enlace que se romperá.
        def feed_falso(host, tipo="posts"):
            return [_entrada("Rota", "rota", "2023-05-01T10:00:00.000-08:00",
                             "<p>Texto</p><img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/>")] \
                if tipo == "posts" else []

        with mock.patch("blogs.management.commands.import_blogspot.leer_feed", feed_falso), \
             mock.patch(
                 "blogs.management.commands.import_blogspot.Command._descargar_imagen",
                 lambda *a, **k: None,
             ):
            call_command("import_blogspot", blog=["dmusicaiesmbescos"], verbosity=0)
        articulo = ArticuloPage.objects.get(slug="rota")
        self.assertNotIn("googleusercontent", articulo.body)
        self.assertIn("Texto", articulo.body)

    def test_un_post_sin_texto_usa_el_titulo_de_entradilla(self):
        # `intro` es obligatorio; hay posts que son solo un cartel escaneado.
        self._importar([_entrada("Solo un cartel", "cartel", "2023-05-01T10:00:00.000-08:00",
                                 "<img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/>")])
        self.assertEqual(ArticuloPage.objects.get(slug="cartel").intro, "Solo un cartel")

    # -- C114: relanzar no duplica ---------------------------------------

    def test_relanzar_el_comando_no_duplica_nada(self):
        entradas = [
            _entrada("Uno", "uno", "2023-05-01T10:00:00.000-08:00", "<p>a</p>"),
            _entrada("Dos", "dos", "2023-05-02T10:00:00.000-08:00", "<p>b</p>"),
        ]
        self._importar(entradas)
        self.assertEqual(ArticuloPage.objects.count(), 2)
        self._importar(entradas)
        self.assertEqual(ArticuloPage.objects.count(), 2)

    def test_relanzar_tampoco_vuelve_a_bajar_las_imagenes(self):
        entradas = [_entrada("Foto", "foto", "2023-05-01T10:00:00.000-08:00",
                             "<img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/>")]
        self._importar(entradas)
        antes = get_image_model().objects.count()
        self._importar(entradas)
        self.assertEqual(get_image_model().objects.count(), antes)

    # -- A27.2: lo escrito a mano no se toca ------------------------------

    def test_un_articulo_escrito_a_mano_sobrevive_intacto(self):
        a_mano = ArticuloPage(title="Escrito por un profe", slug="a-mano",
                              date="2026-01-01", intro="Mío", body="<p>No me toques</p>")
        self.musica.add_child(instance=a_mano)
        a_mano.save_revision().publish()

        self._importar([_entrada("Importado", "importado", "2023-05-01T10:00:00.000-08:00", "<p>x</p>")])

        a_mano.refresh_from_db()
        self.assertEqual(a_mano.body, "<p>No me toques</p>")
        self.assertEqual(a_mano.intro, "Mío")
        self.assertEqual(a_mano.source_url, "")

    def test_un_slug_que_choca_con_uno_a_mano_no_lo_pisa(self):
        a_mano = ArticuloPage(title="Concierto", slug="concierto",
                              date="2026-01-01", intro="Mío", body="<p>Original</p>")
        self.musica.add_child(instance=a_mano)
        a_mano.save_revision().publish()

        self._importar([_entrada("Concierto", "concierto", "2023-05-01T10:00:00.000-08:00", "<p>Importado</p>")])

        a_mano.refresh_from_db()
        self.assertEqual(a_mano.body, "<p>Original</p>")
        self.assertEqual(ArticuloPage.objects.filter(slug="concierto-2").count(), 1)

    def test_las_imagenes_van_a_su_propia_coleccion(self):
        self._importar([_entrada("Foto", "foto", "2023-05-01T10:00:00.000-08:00",
                                 "<img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/>")])
        self.assertTrue(Collection.objects.filter(name__startswith="Blogspot —").exists())
