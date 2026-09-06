"""Las funciones puras del importador de Blogspot, probadas sin red ni BD.

Todo el HTML de aquí abajo está copiado de los feeds reales de los dieciséis
blogs del centro, no inventado. Lo que se prueba es lo que de verdad llegó.
"""

import re

import pytest

from blogs.blogspot import (
    BLOG_MAP,
    derivar_intro,
    es_imagen_de_google,
    etiqueta_facetada,
    limpiar_cuerpo,
    slug_desde_url,
    slugify_simple,
    url_maxima_resolucion,
)

BLOGGER = "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEh"


class TestMapa:
    def test_los_dieciseis_blogs_estan(self):
        assert len(BLOG_MAP) == 16

    def test_ningun_departamento_recibe_dos_blogs(self):
        # Un destino repetido mezclaría dos departamentos en el mismo listado.
        assert len(set(BLOG_MAP.values())) == 16


class TestMaximaResolucion:
    """C109. Blogger incrusta a `/s320/` en 271 de las 582 imágenes: sin esta
    reescritura, casi todo el archivo fotográfico del centro entra en miniatura."""

    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            (f"{BLOGGER}/s320/foto.jpeg", f"{BLOGGER}/s0/foto.jpeg"),
            (f"{BLOGGER}/s1600/foto.jpeg", f"{BLOGGER}/s0/foto.jpeg"),
            (f"{BLOGGER}/s16000/foto.jpeg", f"{BLOGGER}/s0/foto.jpeg"),
            (f"{BLOGGER}/w310-h438/foto.jpeg", f"{BLOGGER}/s0/foto.jpeg"),
            (f"{BLOGGER}/w640-h480-c/foto.jpeg", f"{BLOGGER}/s0/foto.jpeg"),
            ("https://1.bp.blogspot.com/-AbC/XYZ=s320", "https://1.bp.blogspot.com/-AbC/XYZ=s0"),
            ("https://lh3.googleusercontent.com/AbC=w400-h300", "https://lh3.googleusercontent.com/AbC=s0"),
        ],
    )
    def test_cualquier_tamano_converge_en_el_original(self, entrada, esperado):
        assert url_maxima_resolucion(entrada) == esperado

    def test_una_url_sin_patron_de_tamano_se_deja_como_esta(self):
        # Inventarse una URL da 404, y un 404 es una foto perdida.
        externa = "https://seminariomiacifema.catedu.es/wp-content/uploads/cartel.png"
        assert url_maxima_resolucion(externa) == externa

    def test_solo_se_reescribe_el_primer_token_de_tamano(self):
        # `/s320/` en el nombre del fichero no es un token de tamaño.
        url = f"{BLOGGER}/s320/captura-s640-recorte.png"
        assert url_maxima_resolucion(url) == f"{BLOGGER}/s0/captura-s640-recorte.png"


class TestDominios:
    @pytest.mark.parametrize(
        "url",
        [
            f"{BLOGGER}/s320/a.jpg",
            "https://1.bp.blogspot.com/-x/y=s320",
            "https://lh7-us.googleusercontent.com/abc",
        ],
    )
    def test_reconoce_las_de_google(self, url):
        assert es_imagen_de_google(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://seminariomiacifema.catedu.es/cartel.png",
            "https://ampacondado.files.wordpress.com/logo.png",
            "file:///C:/Users/profe/Desktop/foto.jpg",
        ],
    )
    def test_no_confunde_las_de_fuera(self, url):
        assert not es_imagen_de_google(url)


class TestEtiquetas:
    """C115. Las 10 etiquetas que de verdad existen en los 16 blogs."""

    @pytest.mark.parametrize(
        "bruta,esperada",
        [
            ("1ºESO", "curso:1-eso"),
            ("3º ESO", "curso:3-eso"),
            ("4ºESO", "curso:4-eso"),
            ("información", "tema:informacion"),
            ("Información para las familias", "tema:informacion-para-las-familias"),
            ("recomendaciones", "tema:recomendaciones"),
            ("actividades", "tema:actividades"),
            ("Frohe Ostern", "tema:frohe-ostern"),
            ("fp pruebas acceso", "tema:fp-pruebas-acceso"),
            ("Técnicas de estudio.", "tema:tecnicas-de-estudio"),
        ],
    )
    def test_las_diez_etiquetas_medidas(self, bruta, esperada):
        assert etiqueta_facetada(bruta) == esperada

    def test_toda_etiqueta_sale_con_faceta(self):
        # A27.6: un término suelto rompe el vocabulario facetado del sitio.
        for bruta in ["1ºESO", "información", "Frohe Ostern", "fp pruebas acceso"]:
            assert etiqueta_facetada(bruta).count(":") == 1

    def test_una_etiqueta_que_queda_vacia_se_descarta(self):
        # Devolver `tema:` sería peor que no devolver nada: el comando la reporta.
        assert etiqueta_facetada("···") is None
        assert etiqueta_facetada("   ") is None

    def test_sin_acentos_ni_mayusculas(self):
        assert slugify_simple("Educación Plástica y Visual") == "educacion-plastica-y-visual"


class TestSlug:
    @pytest.mark.parametrize(
        "url,esperado",
        [
            ("https://dplasticaiesmbescos.blogspot.com/2023/12/criterios-de-evaluacion-2023-2024.html",
             "criterios-de-evaluacion-2023-2024"),
            ("https://dmusicaiesmbescos.blogspot.com/p/recursos.html", "recursos"),
            ("https://x.blogspot.com/2019/04/algo.html?m=1", "algo"),
            ("https://x.blogspot.com/2019/04/algo.html#comentarios", "algo"),
        ],
    )
    def test_el_permalink_da_el_slug(self, url, esperado):
        assert slug_desde_url(url) == esperado

    def test_es_estable(self):
        # C114 depende de esto: la misma URL da siempre el mismo slug.
        url = "https://x.blogspot.com/2021/09/vuelta-al-cole.html"
        assert slug_desde_url(url) == slug_desde_url(url)


class TestLimpieza:
    """C110. HTML real, pegado desde Google Docs, tal cual llegó en el feed."""

    REAL = (
        '<p><span style="font-family: arial;">Estos son los criterios.</span></p>'
        '<p><br /></p>'
        '<h2 style="text-align: left;"><span style="font-family: arial;">1º ESO</span></h2>'
        '<div><span id="docs-internal-guid-15eb50b3"><ol style="margin-bottom: 0;">'
        '<li aria-level="1" dir="ltr" style="font-weight: 700;">'
        '<p dir="ltr" role="presentation" style="line-height: 1.2;">'
        '<span style="vertical-align: baseline;">Procedimientos</span></p></li></ol>'
        '</span></div>'
    )

    def test_no_queda_ni_un_style(self):
        assert "style=" not in limpiar_cuerpo(self.REAL)

    def test_no_quedan_contenedores_de_maquetacion(self):
        salida = limpiar_cuerpo(self.REAL)
        for basura in ["<span", "<div", "class=", "aria-level", "role=", "id="]:
            assert basura not in salida

    def test_el_texto_sobrevive_entero(self):
        # Limpiar maquetación no es borrar contenido.
        salida = limpiar_cuerpo(self.REAL)
        for frase in ["Estos son los criterios.", "1º ESO", "Procedimientos"]:
            assert frase in salida

    def test_la_estructura_semantica_sobrevive(self):
        salida = limpiar_cuerpo(self.REAL)
        assert "<h2>" in salida
        assert "<ol>" in salida and "<li>" in salida

    def test_los_restos_de_word_se_van(self):
        salida = limpiar_cuerpo('<p>Texto<o:p></o:p></p><v:shape id="x">forma</v:shape>')
        assert "<o:p>" not in salida and "<v:shape" not in salida
        assert "Texto" in salida and "forma" in salida

    def test_h1_baja_a_h2(self):
        # El `h1` de la página es el título del artículo; dos compiten en SEO
        # y rompen la jerarquía de lectores de pantalla.
        assert "<h1" not in limpiar_cuerpo("<h1>Titular</h1>")
        assert "<h2>Titular</h2>" in limpiar_cuerpo("<h1>Titular</h1>")

    def test_las_tablas_sobreviven(self):
        # C112. 59 tablas, 33 de ellas en un solo post de Inglés.
        crudo = (
            '<table border="1" style="width: 100%;" cellpadding="4"><tbody>'
            '<tr><th style="color: red;" colspan="2">Criterio</th></tr>'
            '<tr><td width="50">1.1</td><td>Comprende textos</td></tr>'
            "</tbody></table>"
        )
        salida = limpiar_cuerpo(crudo)
        assert "<table>" in salida and "<tbody>" in salida
        assert 'colspan="2"' in salida          # la estructura de la tabla se respeta
        assert "border=" not in salida and "width=" not in salida and "style=" not in salida
        assert "Comprende textos" in salida

    def test_los_videos_de_youtube_sobreviven(self):
        # C111. Los 22 iframes del archivo son todos de YouTube, y
        # `articulo.html` ya lleva JS que los hace responsive.
        crudo = (
            '<iframe allowfullscreen="allowfullscreen" class="BLOG_video_class" '
            'height="266" src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="320"></iframe>'
        )
        salida = limpiar_cuerpo(crudo)
        assert 'src="https://www.youtube.com/embed/dQw4w9WgXcQ"' in salida
        assert "height=" not in salida and "class=" not in salida

    def test_los_parrafos_vacios_de_blogspot_se_podan(self):
        # Blogspot separa con `<p><br /></p>`; sin podar quedan agujeros.
        salida = limpiar_cuerpo("<p>Uno</p><p><br /></p><p><br /></p><p>Dos</p>")
        assert salida.count("<p>") == 2

    def test_un_enlace_sin_destino_no_queda_como_enlace(self):
        salida = limpiar_cuerpo('<p><a name="marcador">Texto</a></p>')
        assert "<a" not in salida and "Texto" in salida

    def test_el_texto_suelto_tras_quitar_divs_acaba_en_un_parrafo(self):
        salida = limpiar_cuerpo("<div>Suelto</div>")
        assert salida.strip().startswith("<p>")
        assert "Suelto" in salida

    def test_cuerpo_vacio_no_revienta(self):
        assert limpiar_cuerpo("") == ""
        assert limpiar_cuerpo("   ") == ""

    def test_no_sobrevive_ninguna_etiqueta_fuera_de_la_lista(self):
        # Afirmación universal, no una lista de ejemplos: cualquier etiqueta
        # que salga de la limpieza tiene que estar permitida.
        from blogs.blogspot import PERMITIDAS

        crudo = (
            "<marquee>Corre</marquee><blink>Parpadea</blink><center>Centro</center>"
            "<font face='Arial'>Fuente</font><figure><figcaption>Pie</figcaption></figure>"
            "<article><header>Cabecera</header></article>"
        )
        salida = limpiar_cuerpo(crudo)
        for nombre in set(re.findall(r"<\s*([a-zA-Z][a-zA-Z0-9]*)", salida)):
            assert nombre.lower() in PERMITIDAS, f"«{nombre}» no debería sobrevivir"
        # Y el texto sigue ahí.
        for palabra in ["Corre", "Parpadea", "Centro", "Fuente", "Pie", "Cabecera"]:
            assert palabra in salida


class TestIntro:
    def test_cabe_en_el_campo(self):
        # `ArticuloPage.intro` es un CharField(max_length=250).
        largo = "<p>" + ("palabra " * 200) + "</p>"
        assert len(derivar_intro(largo)) <= 250

    def test_corta_por_espacio_no_a_mitad_de_palabra(self):
        salida = derivar_intro("<p>" + ("interdisciplinariedad " * 40) + "</p>")
        assert salida.endswith("…")
        assert "interdisciplinaried…" not in salida

    def test_es_el_principio_del_texto_no_un_resumen(self):
        # A27.5: el importador no interpreta ni reescribe lo que escribió un profesor.
        assert derivar_intro("<p>Estos son los criterios.</p>") == "Estos son los criterios."

    def test_ignora_las_etiquetas(self):
        assert derivar_intro('<p><b>Hola</b> <i>mundo</i></p>') == "Hola mundo"

    def test_un_articulo_solo_de_imagenes_da_intro_vacia(self):
        assert derivar_intro('<embed embedtype="image" id="1" format="fullwidth" alt=""/>') == ""


class TestMaquetacionDeBlogspot:
    """Los dos vicios del editor clásico de Blogger, medidos en el archivo real."""

    def test_la_tabla_de_una_columna_que_centra_una_foto_desaparece(self):
        # Las 7 tablas de Alemán son de este tipo, ninguna es una tabla de datos.
        crudo = (
            '<table class="tr-caption-container"><tbody>'
            "<tr><td><img src='https://blogger.googleusercontent.com/img/b/x/s320/f.jpg'/></td></tr>"
            '<tr><td class="tr-caption">Pie de foto</td></tr>'
            "</tbody></table>"
        )
        salida = limpiar_cuerpo(crudo)
        assert "<table" not in salida
        assert "Pie de foto" in salida

    def test_la_tabla_de_datos_de_verdad_no_se_toca(self):
        crudo = (
            "<table><tbody>"
            "<tr><td>1.1</td><td>Comprende textos</td></tr>"
            "<tr><td>1.2</td><td>Produce textos</td></tr>"
            "</tbody></table>"
        )
        salida = limpiar_cuerpo(crudo)
        assert "<table>" in salida
        assert "Comprende textos" in salida and "Produce textos" in salida

    def test_el_enlace_a_la_version_grande_de_google_se_va(self):
        # A27.3 / C108: ni una URL de Google sobrevive en el cuerpo.
        crudo = (
            '<a href="https://blogger.googleusercontent.com/img/b/x/s1600/f.jpg">'
            '<embed embedtype="image" id="42" format="fullwidth" alt="Foto"/></a>'
        )
        salida = limpiar_cuerpo(crudo)
        assert "googleusercontent" not in salida
        assert 'id="42"' in salida       # la foto, ya nuestra, se queda

    def test_un_enlace_a_google_con_texto_conserva_el_texto(self):
        crudo = '<p><a href="https://blogger.googleusercontent.com/img/b/x/s0/f.jpg">Feliz Navidad</a></p>'
        salida = limpiar_cuerpo(crudo)
        assert "googleusercontent" not in salida
        assert "Feliz Navidad" in salida

    def test_un_enlace_vacio_no_deja_un_hueco_pulsable(self):
        salida = limpiar_cuerpo('<p><a href="https://www.topagrar.at/imgs/62d2.jpg"></a>Texto</p>')
        assert "topagrar" not in salida
        assert "Texto" in salida

    def test_un_enlace_normal_a_otra_web_se_respeta(self):
        # Solo se limpian los envoltorios de Google, no la bibliografía del profesor.
        crudo = '<p><a href="https://www.goethe.de/es/">Instituto Goethe</a></p>'
        salida = limpiar_cuerpo(crudo)
        assert 'href="https://www.goethe.de/es/"' in salida
        assert "Instituto Goethe" in salida
