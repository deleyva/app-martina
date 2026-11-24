"""Patrones de piano en las fichas (fase 114).

Fija:

- La progresión se escribe de tres maneras y se guarda de una; lo que no es una
  tríada de la escala mayor se rechaza diciendo cuál y por qué.
- El catálogo de patrones es un solo fichero para el servidor y para el
  navegador, y el bundle lo lleva dentro.
- Un patrón guarda cuatro datos y ninguna nota. Solo quien puede editar la
  página lo añade o lo cambia, y cada cambio deja una revisión.
- Lo que no vale no se guarda a medias, y la ficha vuelve con el motivo.
- En la página, en clase y en las listas es un patrón de piano, no un ejercicio
  de audición.
"""

import json
import random
from importlib import import_module
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from wagtail.models import Site

from musica.models import (
    DictadoPage,
    EjercicioDeFicha,
    LibroPage,
    MusicLibraryIndexPage,
    PatronPianoBlock,
)
from musica.services import audicion, patrones
from my_library.libros import material_de

User = get_user_model()

RAIZ = Path(patrones.__file__).resolve().parents[2]
FUENTE_JS = RAIZ / "martina_bescos_app/static/js/src/patron_piano.js"
BUNDLE_JS = RAIZ / "martina_bescos_app/static/js/patron_piano.js"

PATRON = {"titulo": "", "progresion": "I V V I", "patron": "bajo-acorde", "tonalidad": "C", "tempo": 80}


class ProgresionTest(SimpleTestCase):
    def test_se_escribe_de_tres_maneras_y_se_guarda_de_una(self):
        for texto in ("I V V I", "I – V – V – I", "1 5 5 1", " I, V | V - I ", "I→V→V→I"):
            self.assertEqual(patrones.leer_progresion(texto), [1, 5, 5, 1], texto)
        self.assertEqual(patrones.leer_progresion("I vi IV V"), [1, 6, 4, 5])
        self.assertEqual(patrones.leer_progresion("ii iii vii°"), [2, 3, 7])
        # El círculo del disminuido, como salga del teclado, o sin él.
        self.assertEqual(patrones.leer_progresion("vii° viiº viio viidim vii"), [7] * 5)
        self.assertEqual(patrones.escribir_progresion([1, 6, 4, 5]), "I vi IV V")
        self.assertEqual(patrones.escribir_progresion([1, 5, 5, 1], " – "), "I – V – V – I")

    def test_lo_que_no_es_de_la_escala_mayor_se_rechaza_diciendo_por_que(self):
        casos = {
            "I V7": ("«V7»", "tríadas de la escala mayor"),
            "i v": ("primer grado es mayor", "«I»"),
            "I II": ("segundo grado es menor", "«ii»"),
            "I VII": ("séptimo grado es disminuido", "«vii°»"),
            "I V/V V": ("«V/V»",),
            "I bVII": ("«bVII»",),
            "I°": ("«I°»",),
            "1 8": ("«8»", "del 1 al 7"),
            "1 55": ("«55»",),
            "": ("Escribe la progresión",),
            "   ": ("Escribe la progresión",),
            " ".join(["I"] * 17): ("17 compases", "16"),
        }
        for texto, trozos in casos.items():
            with self.assertRaises(patrones.PatronNoValido, msg=texto) as cm:
                patrones.leer_progresion(texto)
            for trozo in trozos:
                self.assertIn(trozo, str(cm.exception), texto)

    def test_el_catalogo_es_un_solo_fichero_y_el_bundle_lo_lleva_dentro(self):
        catalogo = json.loads(patrones.RUTA_DEL_CATALOGO.read_text(encoding="utf-8"))
        self.assertEqual([c for c, _ in patrones.patrones()], [p["id"] for p in catalogo["patrones"]])
        self.assertEqual([c for c, _ in patrones.tonalidades()], [t["id"] for t in catalogo["tonalidades"]])
        self.assertEqual(len(patrones.tonalidades()), 12)
        self.assertEqual(patrones.nombre_del_patron("bajo-acorde"), "Bajo y acorde")
        self.assertEqual(patrones.nombre_de_la_tonalidad("Bb"), "Si♭ mayor")
        self.assertEqual(patrones.nombre_del_patron("vals"), "")

        # El navegador lee ESE fichero, no una copia…
        self.assertIn("musica/patrones_piano.json", FUENTE_JS.read_text(encoding="utf-8"))
        # …y el bundle que se sirve se construyó con el catálogo de hoy. Si
        # falla: `npm run build-js` y confirmar el bundle.
        bundle = BUNDLE_JS.read_text(encoding="utf-8")
        for clave, _ in patrones.patrones():
            self.assertIn(f'"{clave}"', bundle, f"El bundle no conoce el patrón {clave}: hay que reconstruirlo.")
        self.assertNotIn("sourceMappingURL", bundle)

    def test_el_valor_que_se_guarda_son_cuatro_datos_y_ninguna_nota(self):
        valor = patrones.valor_de_patron({"progresion": "1 5 5 1", "patron": "alberti", "tonalidad": "G", "tempo": "96"})
        self.assertEqual(
            valor,
            {"titulo": "", "progresion": "I V V I", "patron": "alberti", "tonalidad": "G", "tempo": 96},
        )
        # Sin nada, lo de partida: I–V en do, el patrón más fácil.
        self.assertEqual(
            patrones.valor_de_patron({}),
            {"titulo": "", "progresion": "I V V I", "patron": "redondas", "tonalidad": "C", "tempo": 80},
        )
        # El tempo se acota; lo ilegible se queda como estaba.
        self.assertEqual(patrones.valor_de_patron({"tempo": "5"})["tempo"], 40)
        self.assertEqual(patrones.valor_de_patron({"tempo": "999"})["tempo"], 200)
        self.assertEqual(patrones.valor_de_patron({"tempo": "rápido"}, {"tempo": 72})["tempo"], 72)
        self.assertEqual(len(patrones.valor_de_patron({"titulo": "x" * 300})["titulo"]), 120)

    def test_al_editar_lo_que_no_viaja_se_queda_como_estaba(self):
        anterior = {"titulo": "Balada", "progresion": "I vi IV V", "patron": "negras", "tonalidad": "F", "tempo": 66}
        self.assertEqual(patrones.valor_de_patron({}, anterior), anterior)
        self.assertEqual(patrones.valor_de_patron({"tonalidad": "D"}, anterior)["tonalidad"], "D")
        self.assertEqual(patrones.valor_de_patron({"tonalidad": "D"}, anterior)["progresion"], "I vi IV V")

    def test_un_patron_o_una_tonalidad_que_no_estan_en_el_catalogo_no_se_guardan(self):
        with self.assertRaises(patrones.PatronNoValido) as cm:
            patrones.valor_de_patron({"patron": "vals"})
        self.assertIn("«vals»", str(cm.exception))
        with self.assertRaises(patrones.PatronNoValido) as cm:
            patrones.valor_de_patron({"tonalidad": "H"})
        self.assertIn("«H»", str(cm.exception))

    def test_el_bloque_valida_tambien_en_el_administrador(self):
        bloque = PatronPianoBlock()
        limpio = bloque.clean(bloque.to_python({**PATRON, "progresion": "1 4 5 1"}))
        self.assertEqual(limpio["progresion"], "I IV V I")
        for mal in ({"progresion": "I V7"}, {"patron": "vals"}, {"tonalidad": "H"}):
            with self.assertRaises(ValidationError, msg=mal):
                bloque.clean(bloque.to_python({**PATRON, **mal}))

    def test_lo_que_va_al_navegador_son_grados(self):
        self.assertEqual(
            patrones.para_el_navegador({**PATRON, "tonalidad": "Bb", "tempo": 72}),
            {"grados": [1, 5, 5, 1], "patron": "bajo-acorde", "tonalidad": "Bb", "tempo": 72},
        )
        # Una progresión guardada que ya no se entiende no revienta la página.
        self.assertEqual(patrones.para_el_navegador({**PATRON, "progresion": "I V7"})["grados"], [])
        self.assertEqual(patrones.titulo_de(PATRON), "I – V – V – I")
        self.assertEqual(patrones.titulo_de({**PATRON, "titulo": "Balada"}), "Balada")

    def test_la_migracion_solo_cambia_la_definicion_del_contenido(self):
        migracion = import_module("musica.migrations.0016_fase_114").Migration
        self.assertEqual(migracion.dependencies, [("musica", "0015_fase_112")])
        self.assertEqual([type(o).__name__ for o in migracion.operations], ["AlterField"])
        self.assertEqual((migracion.operations[0].model_name, migracion.operations[0].name), ("dictadopage", "content"))


@override_settings(ALLOWED_HOSTS=["*"])
class FichaDePianoTest(TestCase):
    def setUp(self):
        self.sitio = Site.objects.get(is_default_site=True)
        biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-piano")
        self.sitio.root_page.add_child(instance=biblioteca)
        biblioteca.save_revision().publish()

        self.libro = LibroPage(title="Piano por progresiones", slug="piano-progresiones")
        biblioteca.add_child(instance=self.libro)
        self.libro.save_revision().publish()

        self.profe = User.objects.create_superuser(email="profe-piano@example.com", password="x123456789")
        self.alumna = User.objects.create_user(email="alumna-piano@example.com", password="x123456789")

    def _ficha(self, titulo="I – V", *valores):
        ficha = DictadoPage(title=titulo, slug=f"ficha-{random.randint(0, 10**9)}")
        self.libro.add_child(instance=ficha)
        for tipo, valor in valores:
            audicion.anadir(ficha, tipo, valor)
        ficha.save_revision().publish()
        return DictadoPage.objects.get(pk=ficha.pk)

    def _con_patron(self, **cambios):
        return self._ficha("I – V", ("patron_piano", {**PATRON, **cambios}))

    def _get(self, url, user=None):
        if user:
            self.client.force_login(user)
        r = self.client.get(url, follow=True, HTTP_HOST=self.sitio.hostname)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def _proyectar(self, objeto):
        from clases.models import ClassSessionItem
        from clases.views import render_item_content

        item = ClassSessionItem(content_type=ContentType.objects.get_for_model(type(objeto)), object_id=objeto.pk)
        request = RequestFactory().get("/")
        request.user = self.profe
        request.session = self.client.session
        return render_item_content(request, item).content.decode()

    # --- C810: solo quien puede editar, y con revisión ---

    def test_anadir_un_patron_publica_deja_revision_y_no_guarda_notas(self):
        ficha = self._ficha()
        revisiones = ficha.revisions.count()
        self.client.force_login(self.profe)
        r = self.client.post(
            reverse("musica:anadir_patron", args=[ficha.pk]),
            {"progresion": "1 5 5 1", "patron": "bajo-acorde", "tonalidad": "G"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("fa-ficha", html)
        self.assertIn("data-patron-piano=", html)
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(ficha.revisions.count(), revisiones + 1)
        self.assertEqual([b.block_type for b in ficha.content], ["patron_piano"])
        self.assertEqual(
            dict(ficha.content[0].value),
            {"titulo": "", "progresion": "I V V I", "patron": "bajo-acorde", "tonalidad": "G", "tempo": 80},
        )
        self.assertFalse(ficha.es_antigua)
        self.assertEqual([n for _, n in ficha.ejercicios()], [1])

    def test_la_alumna_y_quien_no_ha_entrado_no_tocan_nada(self):
        ficha = self._con_patron()
        bloque_id = ficha.content[0].id
        urls = (
            reverse("musica:anadir_patron", args=[ficha.pk]),
            reverse("musica:editar_patron", args=[ficha.pk, bloque_id]),
        )
        self.client.force_login(self.alumna)
        for url in urls:
            self.assertEqual(self.client.post(url, {"progresion": "I IV", "tonalidad": "D"}).status_code, 403, url)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.post(url, {"progresion": "I IV", "tonalidad": "D"}).status_code, 403, url)
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(len(ficha.content), 1)
        self.assertEqual(dict(ficha.content[0].value), PATRON)

    def test_editar_cambia_los_datos_y_conserva_el_bloque(self):
        ficha = self._con_patron()
        bloque_id = ficha.content[0].id
        revisiones = ficha.revisions.count()
        self.client.force_login(self.profe)
        r = self.client.post(
            reverse("musica:editar_patron", args=[ficha.pk, bloque_id]),
            {"progresion": "I – vi – IV – V", "patron": "alberti", "tonalidad": "F", "tempo": "66", "titulo": "Balada"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(r.status_code, 200)
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(ficha.revisions.count(), revisiones + 1)
        self.assertEqual(ficha.content[0].id, bloque_id)
        self.assertEqual(ficha.content[0].block_type, "patron_piano")
        self.assertEqual(
            dict(ficha.content[0].value),
            {"titulo": "Balada", "progresion": "I vi IV V", "patron": "alberti", "tonalidad": "F", "tempo": 66},
        )

    # --- C809: lo que no vale no se guarda, y se dice por qué ---

    def test_una_progresion_que_no_vale_no_se_guarda_y_la_ficha_dice_por_que(self):
        ficha = self._con_patron()
        bloque_id = ficha.content[0].id
        revisiones = ficha.revisions.count()
        self.client.force_login(self.profe)

        # Al añadir: el aviso va en el formulario de añadir, con lo tecleado.
        r = self.client.post(
            reverse("musica:anadir_patron", args=[ficha.pk]),
            {"progresion": "I V7", "patron": "alberti", "tonalidad": "D"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("No entiendo «V7»", html)
        self.assertIn('value="I V7"', html)
        self.assertNotIn("{#", html)

        # Al editar: el aviso va en ese ejercicio, con su editor abierto.
        r = self.client.post(
            reverse("musica:editar_patron", args=[ficha.pk, bloque_id]),
            {"progresion": "I II", "patron": "alberti", "tonalidad": "D"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("segundo grado es menor", html)
        self.assertIn('value="I II"', html)
        self.assertIn('<details class="fa-editar" open>', html)

        # Sin HTMX, un 400 con el motivo.
        r = self.client.post(reverse("musica:anadir_patron", args=[ficha.pk]), {"progresion": "I V7"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("V7", r.content.decode())

        # Y nada ha cambiado: ni un ejercicio más, ni una revisión, ni un dato.
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(ficha.revisions.count(), revisiones)
        self.assertEqual(len(ficha.content), 1)
        self.assertEqual(dict(ficha.content[0].value), PATRON)

    def test_el_editor_de_patrones_no_toca_un_dictado(self):
        abc = "X:1\nL:1/4\nK:C\nC D E F|"
        ficha = self._ficha("Mezclada", ("dictado_abc", {"tipo": "melodico", "abc": abc, "tempo": 60}))
        dictado = ficha.content[0].id
        self.client.force_login(self.profe)
        r = self.client.post(reverse("musica:editar_patron", args=[ficha.pk, dictado]), {"progresion": "I V"})
        self.assertEqual(r.status_code, 404)
        r = self.client.post(reverse("musica:editar_patron", args=[ficha.pk, "no-existe"]), {"progresion": "I V"})
        self.assertEqual(r.status_code, 404)
        ficha = DictadoPage.objects.get(pk=ficha.pk)
        self.assertEqual(ficha.content[0].value["abc"], abc)
        self.assertNotIn("progresion", dict(ficha.content[0].value))

    # --- C811: la página ---

    def test_la_pagina_pinta_el_patron_con_sus_grados_y_carga_su_reproductor(self):
        ficha = self._con_patron(tonalidad="Bb", tempo=72)
        html = self._get(ficha.url, self.profe)
        self.assertIn('data-patron-piano="{&quot;grados&quot;: [1, 5, 5, 1], &quot;patron&quot;: &quot;bajo-acorde&quot;', html)
        self.assertIn("&quot;tonalidad&quot;: &quot;Bb&quot;, &quot;tempo&quot;: 72}", html)
        self.assertIn("I – V – V – I · Bajo y acorde", html)
        self.assertIn('<option value="Bb" selected>Si♭ mayor</option>', html)
        self.assertIn("data-pp-partitura", html)
        # La partitura va a la vista, no dentro de un desplegable de solución.
        self.assertNotIn("Ver solución", html)
        # Primero el motor de los dictados y después el del patrón.
        self.assertLess(html.rindex("js/dictado."), html.rindex("js/patron_piano."))
        self.assertIn("＋ Patrón de piano", html)
        self.assertIn("✎ Editar el patrón", html)
        self.assertNotIn("{#", html)
        # La ficha de piano no carga el CSS ni el reproductor de las antiguas.
        self.assertNotIn("daisyui@3.9.4", html)

        self.client.logout()
        html = self._get(ficha.url, self.alumna)
        self.assertIn("data-patron-piano=", html)
        self.assertIn("data-pp-tonalidad", html)  # transportar es de quien mira
        self.assertNotIn("＋ Patrón de piano", html)
        self.assertNotIn("✎ Editar el patrón", html)
        self.assertNotIn("musica/fichas/", html)

    # --- C815: en clase ---

    def test_en_clase_se_pinta_ese_patron_solo_y_sin_editor(self):
        ficha = self._ficha(
            "I – V",
            ("patron_piano", PATRON),
            ("patron_piano", {**PATRON, "patron": "alberti"}),
        )
        uno, dos = material_de(ficha)
        self.assertEqual([type(m).__name__ for m in (uno, dos)], ["EjercicioDeFicha"] * 2)
        html = self._proyectar(dos)
        self.assertIn("fa-clase fa-suelto", html)
        self.assertEqual(html.count("data-patron-piano="), 1)
        self.assertIn("&quot;patron&quot;: &quot;alberti&quot;", html)
        self.assertIn(f'id="ej-{dos.bloque_id}"', html)
        self.assertNotIn(f'id="ej-{uno.bloque_id}"', html)
        self.assertIn('<span class="fa-numero">2</span>', html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("Editar el patrón", html)
        self.assertNotIn("＋ Patrón de piano", html)
        self.assertNotIn("{#", html)

    # --- C816: en las listas ---

    def test_en_las_listas_es_un_patron_de_piano_y_no_un_ejercicio_de_audicion(self):
        from clases.libros_de_grupo import describir
        from clases.models import ClassSessionItem
        from my_library.models import LibraryItem

        ficha = self._ficha(
            "I – V",
            ("patron_piano", PATRON),
            ("patron_piano", {**PATRON, "titulo": "Balada", "patron": "negras"}),
            ("audiometrico", audicion.generar_audiometrico(50)),
        )
        patron, balada, test = material_de(ficha)
        self.assertEqual(patron.describir(), ("🎹", "I – V · 1 · I – V – V – I", "Patrón de piano · Bajo y acorde"))
        self.assertEqual(balada.describir(), ("🎹", "I – V · 2 · Balada", "Patrón de piano · Acordes a negras"))
        self.assertEqual(patron.title, "I – V · 1 · I – V – V – I")
        self.assertEqual(patron.tipo_e_icono(), ("Patrón de piano", "🎹"))
        # Los de audición, como estaban.
        self.assertEqual(test.describir()[0], "🎧")
        self.assertEqual(test.tipo_e_icono(), ("Ejercicio de audición", "🎧"))

        tipo = ContentType.objects.get_for_model(EjercicioDeFicha)
        self.assertEqual(describir(patron), ("🎹", "I – V · 1 · I – V – V – I", "Patrón de piano · Bajo y acorde"))
        for modelo in (ClassSessionItem, LibraryItem):
            de_piano = modelo(content_type=tipo, object_id=patron.pk)
            self.assertEqual((de_piano.get_content_type_name(), de_piano.get_icon()), ("Patrón de piano", "🎹"), modelo)
            de_audicion = modelo(content_type=tipo, object_id=test.pk)
            self.assertEqual(
                (de_audicion.get_content_type_name(), de_audicion.get_icon()), ("Ejercicio de audición", "🎧"), modelo
            )
            # Un ejercicio que ya no existe no revienta la lista.
            huerfano = modelo(content_type=tipo, object_id=0)
            self.assertEqual((huerfano.get_content_type_name(), huerfano.get_icon()), ("Ejercicio de audición", "🎧"))

    def test_el_indice_del_libro_la_llama_ficha_de_piano(self):
        de_piano = self._con_patron()
        de_audicion = self._ficha("Tests de ¼ de tono", ("audiometrico", audicion.generar_audiometrico(50)))
        mezclada = self._ficha("De todo", ("patron_piano", PATRON), ("audiometrico", audicion.generar_audiometrico(50)))
        vacia = self._ficha("Sin nada")
        self.assertTrue(de_piano.es_ficha_de_piano)
        for otra in (de_audicion, mezclada, vacia):
            self.assertFalse(otra.es_ficha_de_piano, otra.title)

        html = self._get(self.libro.url, self.profe)
        self.assertEqual(html.count("Ficha de piano"), 1)
        self.assertEqual(html.count("Ficha de audición\n"), 3)
        self.assertIn("🎹", html)
        # El botón de siempre, que ahora sirve también para esto.
        self.assertIn("＋ Ficha de audición o de piano", html)
        self.assertNotIn("{#", html)
