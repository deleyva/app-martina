"""El volcado del índice a Markdown (fase 77).

Fija tres cosas: qué páginas entran (publicadas; privadas fuera, y con ellas lo
que cuelga de un libro privado), qué lleva la ficha de una canción (todo lo que
se pregunta en voz alta: tono, compás, tempo, acordes, tablatura), y que el
comando no crea nada.
"""

import io
import tempfile

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from wagtail.models import Site

from musica.exportacion import exportar_indice, texto_plano
from musica.models import (
    LetraConAcordes,
    LibroPage,
    MusicLibraryIndexPage,
    RecursoPage,
    RecursoTraduccion,
)

CHORDPRO = "{start_of_verse}\n[G]I found a [Em]love, for [C]me\n{end_of_verse}"


# --- texto_plano: puro, sin base de datos ---


@pytest.mark.parametrize(
    "html, esperado",
    [
        ("<p>Hola</p><p>Adiós</p>", "Hola\n\nAdiós"),
        ("<p>Una<br>dos</p>", "Una\ndos"),
        ("<p>Tom &amp; Jerry &eacute;</p>", "Tom & Jerry é"),
        ("<ul><li>a</li><li>b</li></ul>", "a\n\nb"),
        ('<p>Antes</p><embed embedtype="image" id="3"/><p>Después</p>', "Antes\n\nDespués"),
        ("<p>  espacios   </p>", "espacios"),
        ("", ""),
        (None, ""),
    ],
)
def test_texto_plano(html, esperado):
    assert texto_plano(html) == esperado


# --- El árbol sembrado ---


def _publicar(padre, pagina):
    padre.add_child(instance=pagina)
    pagina.save_revision().publish()
    return pagina


@override_settings(ALLOWED_HOSTS=["*"])
class ExportarIndiceTest(TestCase):
    def setUp(self):
        self.sitio = Site.objects.get(is_default_site=True)
        self.indice = _publicar(
            self.sitio.root_page,
            MusicLibraryIndexPage(title="Índice", slug="indice-exp", intro="<p>Bienvenido</p>"),
        )
        self.cancion = _publicar(
            self.indice,
            RecursoPage(
                title="Perfect",
                slug="perfect-exp",
                date="2026-09-25",
                intro="Una balada",
                body="<p>Cuerpo en castellano.</p>",
                idioma="es",
                artist="Ed Sheeran",
                key_fifths=-1,
                key_mode="major",
                time_signature_beats=6,
                time_signature_beat_type=8,
                tempo_bpm=95,
                duration_seconds=263,
                reference="vers. original",
                songsterr_url="https://www.songsterr.com/a/wsa/ed-sheeran-perfect-tab-s123",
                chordpro=CHORDPRO,
            ),
        )
        self.cancion.faceted_tags.add("concepto:acordes-basicos", "curso:3eso")
        RecursoTraduccion.objects.create(
            page=self.cancion, idioma="en", intro="A ballad", body="<p>Body in English.</p>"
        )
        self.cancion.save_revision().publish()

        self.suelto = _publicar(
            self.indice,
            RecursoPage(title="Artículo suelto", slug="suelto-exp", date="2026-09-25", intro="x", body=""),
        )
        self.privado = _publicar(
            self.indice,
            RecursoPage(title="Secreto", slug="secreto-exp", date="2026-09-25", intro="x", is_private=True),
        )
        borrador = RecursoPage(title="Borrador", slug="borrador-exp", date="2026-09-25", intro="x", live=False)
        self.indice.add_child(instance=borrador)

        self.libro = _publicar(self.indice, LibroPage(title="Libro abierto", slug="libro-exp", intro="<p>Un libro</p>"))
        self.capitulo = _publicar(
            self.libro,
            RecursoPage(title="Capítulo 1", slug="cap1-exp", date="2026-09-25", intro="x"),
        )
        libro_privado = _publicar(self.indice, LibroPage(title="Libro privado", slug="libro-priv-exp", is_private=True))
        _publicar(
            libro_privado,
            RecursoPage(title="Capítulo oculto", slug="cap-oculto-exp", date="2026-09-25", intro="x"),
        )

    def _exportar(self, **kwargs):
        markdown, recuentos = exportar_indice(self.indice, **kwargs)
        return markdown, recuentos

    # --- C489: qué entra ---

    def test_entran_las_publicadas_en_orden_de_arbol_y_salen_privadas_y_borradores(self):
        markdown, recuentos = self._exportar()
        secciones = [l for l in markdown.splitlines() if l.startswith("- **URL:** ")]
        urls = [l.removeprefix("- **URL:** ") for l in secciones]
        assert urls == [
            self.cancion.full_url,
            self.suelto.full_url,
            self.libro.full_url,
            self.capitulo.full_url,
        ]
        assert "Secreto" not in markdown
        assert "Borrador" not in markdown
        assert "Capítulo oculto" not in markdown
        assert recuentos == {"Recurso musical": 3, "Libro de la biblioteca": 1}

    def test_el_capitulo_anida_bajo_su_libro(self):
        markdown, _ = self._exportar()
        assert "\n## Libro abierto\n" in markdown
        assert "\n### Capítulo 1\n" in markdown
        assert "- **Dentro de:** Libro abierto" in markdown

    def test_incluir_privadas(self):
        markdown, _ = self._exportar(incluir_privadas=True)
        assert "Secreto" in markdown
        assert "Capítulo oculto" in markdown
        assert "Borrador" not in markdown

    # --- C490: la ficha de una canción ---

    def test_la_ficha_lleva_todo_lo_que_se_pregunta_en_voz_alta(self):
        markdown, _ = self._exportar()
        ficha = markdown.split("\n## Perfect\n")[1].split("\n---\n")[0]
        for dato in [
            "- **Artista / compositor:** Ed Sheeran",
            "- **Tonalidad:** F",
            "- **Compás:** 6/8",
            "- **Tempo:** 95 BPM",
            "- **Duración:** 4:23",
            "- **Referencia:** vers. original",
            "- **Tablatura (Songsterr):** https://www.songsterr.com/a/wsa/ed-sheeran-perfect-tab-s123",
            "- **Etiquetas:** concepto:acordes-basicos, curso:3eso",
            "#### Texto (Español)",
            "*Una balada*",
            "Cuerpo en castellano.",
            "#### Texto (English)",
            f"{self.cancion.full_url}?lang=en",
            "*A ballad*",
            "Body in English.",
            "```chordpro",
            "[G]I found a [Em]love, for [C]me",
        ]:
            assert dato in ficha, dato
        assert "<p>" not in ficha

    def test_el_indice_de_arriba_tiene_una_fila_por_pagina(self):
        markdown, _ = self._exportar()
        tabla = markdown.split("## Índice\n")[1].split("## Fichas\n")[0]
        filas = [l for l in tabla.splitlines() if l.startswith("| ") and "Título" not in l and "---" not in l]
        assert len(filas) == 4
        assert f"| Perfect | Recurso musical | Ed Sheeran | {self.cancion.full_url} |" in filas

    def test_solo_canciones(self):
        markdown, recuentos = self._exportar(solo_canciones=True)
        assert sum(recuentos.values()) == 1
        assert "\n## Perfect\n" in markdown
        assert "Artículo suelto" not in markdown.split("## Fichas\n")[1]

    # --- Anti-A: no escribe ---

    def test_no_crea_la_fila_de_letra_con_acordes(self):
        self._exportar()
        assert not LetraConAcordes.objects.filter(page=self.cancion).exists()

    # --- C492: el comando ---

    def test_comando_a_fichero_y_resumen_por_stderr(self):
        fichero = f"{tempfile.mkdtemp()}/indice.md"
        err = io.StringIO()
        call_command("exportar_indice_markdown", salida=fichero, stderr=err)
        with open(fichero, encoding="utf-8") as f:
            contenido = f.read()
        assert contenido.startswith("# Índice\n")
        assert "4 páginas" in err.getvalue()
        assert "KB → " in err.getvalue()

    def test_comando_por_stdout_y_eleccion_de_indice(self):
        out = io.StringIO()
        call_command("exportar_indice_markdown", indice="indice-exp", stdout=out, stderr=io.StringIO())
        assert out.getvalue().startswith("# Índice\n")
        out = io.StringIO()
        call_command("exportar_indice_markdown", indice=str(self.indice.pk), stdout=out, stderr=io.StringIO())
        assert out.getvalue().startswith("# Índice\n")

    def test_comando_con_varios_indices_exige_elegir(self):
        _publicar(self.sitio.root_page, MusicLibraryIndexPage(title="Otro", slug="otro-indice-exp"))
        with pytest.raises(CommandError, match="--indice"):
            call_command("exportar_indice_markdown", stdout=io.StringIO(), stderr=io.StringIO())
        with pytest.raises(CommandError, match="no-existe"):
            call_command("exportar_indice_markdown", indice="no-existe", stdout=io.StringIO())
