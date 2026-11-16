"""C475: la pantalla de revisión del banco."""

import pytest
from django.urls import reverse

from preguntas.models import Pregunta

from .conftest import pregunta


@pytest.mark.django_db
class TestPermisos:
    @pytest.mark.parametrize("nombre", ["banco", "nueva"])
    def test_sin_sesion_al_login(self, client, nombre):
        r = client.get(reverse(f"preguntas:{nombre}"))
        assert r.status_code == 302 and "login" in r["Location"]

    def test_un_alumno_no_entra(self, client, alumno):
        client.force_login(alumno)
        p = pregunta()
        assert client.get(reverse("preguntas:banco")).status_code == 302
        assert client.post(reverse("preguntas:estado", args=[p.pk]), {"estado": "archivada"}).status_code == 302
        assert Pregunta.objects.get(pk=p.pk).estado == "activa"


@pytest.mark.django_db
class TestBanco:
    def test_lista_por_concepto_con_filtro_sin_revisar(self, client, profesor):
        client.force_login(profesor)
        pregunta(enunciado="Figuras activa", etiquetas=("concepto:figuras",))
        pregunta(enunciado="Intervalos nueva", etiquetas=("concepto:intervalos",), estado="sin_revisar")
        r = client.get(reverse("preguntas:banco"))
        html = r.content.decode()
        assert r.status_code == 200
        assert html.index("concepto: figuras") < html.index("concepto: intervalos")
        r = client.get(reverse("preguntas:banco") + "?estado=sin_revisar")
        html = r.content.decode()
        assert "Intervalos nueva" in html and "Figuras activa" not in html

    def test_veces_preguntada_y_acierto(self, client, profesor, grupo, alumno, hoy):
        from preguntas import composicion
        from preguntas.models import Respuesta

        client.force_login(profesor)
        p = pregunta(correcta=1)
        pase = composicion.crear_pase(grupo, hoy, [p])
        Respuesta.objects.create(pase=pase, pregunta=p, alumno=alumno, opcion=1)
        Respuesta.objects.create(pase=pase, pregunta=p, alumno=profesor, opcion=0)
        html = client.get(reverse("preguntas:banco")).content.decode()
        assert "Preguntada <b>1</b> vez" in html
        assert "50 %" in html

    def test_sin_respuestas_el_acierto_es_guion(self, client, profesor):
        client.force_login(profesor)
        pregunta()
        html = client.get(reverse("preguntas:banco")).content.decode()
        assert "Preguntada <b>0</b> veces" in html and "<b>—</b>" in html

    def test_activar_y_archivar(self, client, profesor):
        client.force_login(profesor)
        p = pregunta(estado="sin_revisar")
        r = client.post(reverse("preguntas:estado", args=[p.pk]), {"estado": "activa", "volver": "/preguntas/?estado=sin_revisar"})
        assert r.status_code == 302 and r["Location"] == "/preguntas/?estado=sin_revisar"
        assert Pregunta.objects.get(pk=p.pk).estado == "activa"
        client.post(reverse("preguntas:estado", args=[p.pk]), {"estado": "archivada"})
        assert Pregunta.objects.get(pk=p.pk).estado == "archivada"
        assert client.post(reverse("preguntas:estado", args=[p.pk]), {"estado": "rota"}).status_code == 400

    def test_con_htmx_devuelve_solo_la_tarjeta_y_los_contadores(self, client, profesor):
        """Activar o archivar no recarga la página: vuelve la tarjeta y los totales."""
        client.force_login(profesor)
        p = pregunta(enunciado="Pregunta del banco", estado="sin_revisar")
        pregunta(enunciado="Otra que no toca", estado="activa")
        r = client.post(
            reverse("preguntas:estado", args=[p.pk]),
            {"estado": "activa", "volver": "/preguntas/?estado=sin_revisar"},
            HTTP_HX_REQUEST="true",
        )
        html = r.content.decode()
        assert r.status_code == 200
        assert Pregunta.objects.get(pk=p.pk).estado == "activa"
        assert "<html" not in html and "Otra que no toca" not in html
        assert f'id="pregunta-{p.pk}"' in html and "Pregunta del banco" in html
        # La tarjeta nueva ya no ofrece «Activar», sí «Archivar», y recuerda la lista.
        assert ">Activar<" not in html and ">Archivar<" in html
        assert 'value="/preguntas/?estado=sin_revisar"' in html
        assert 'id="total-activa" hx-swap-oob="true">2<' in html
        assert 'id="total-sin_revisar" hx-swap-oob="true">0<' in html

    def test_volver_de_otro_sitio_no_se_sigue(self, client, profesor):
        client.force_login(profesor)
        p = pregunta(estado="sin_revisar")
        r = client.post(reverse("preguntas:estado", args=[p.pk]), {"estado": "activa", "volver": "https://ejemplo.com/"})
        assert r.status_code == 302 and r["Location"] == reverse("preguntas:banco")

    def test_las_tarjetas_llevan_htmx_y_la_lista_de_vuelta(self, client, profesor):
        client.force_login(profesor)
        p = pregunta(estado="sin_revisar")
        html = client.get(reverse("preguntas:banco") + "?estado=sin_revisar").content.decode()
        assert f'hx-post="{reverse("preguntas:estado", args=[p.pk])}"' in html
        assert f'hx-target="#pregunta-{p.pk}"' in html
        assert f'{reverse("preguntas:editar", args=[p.pk])}?volver=/preguntas/%3Festado%3Dsin_revisar' in html


@pytest.mark.django_db
class TestEditar:
    def _datos(self, **cambios):
        datos = {
            "enunciado": "¿Qué intervalo hay entre do y sol?",
            "opcion_0": "Tercera", "opcion_1": "Cuarta", "opcion_2": "Quinta", "opcion_3": "Octava",
            "correcta": "2",
            "explicacion": "Do-re-mi-fa-sol: cinco notas.",
            "etiquetas": "concepto:intervalos, curso:2eso",
        }
        datos.update(cambios)
        return datos

    def test_crear_desde_el_formulario(self, client, profesor):
        client.force_login(profesor)
        r = client.post(reverse("preguntas:nueva"), self._datos())
        assert r.status_code == 302
        p = Pregunta.objects.get()
        assert p.opciones == ["Tercera", "Cuarta", "Quinta", "Octava"]
        assert p.correcta == 2 and p.autor == profesor and p.estado == "sin_revisar"
        assert set(p.etiquetas.names()) == {"concepto:intervalos", "curso:2eso"}

    def test_al_guardar_vuelve_a_la_lista_y_a_la_pregunta(self, client, profesor):
        client.force_login(profesor)
        p = pregunta(estado="sin_revisar")
        url = reverse("preguntas:editar", args=[p.pk]) + "?volver=/preguntas/%3Festado%3Dsin_revisar%26q%3Ddo"
        html = client.get(url).content.decode()
        assert f'href="/preguntas/?estado=sin_revisar&amp;q=do#pregunta-{p.pk}"' in html
        r = client.post(url, self._datos(enunciado="Cambiado"))
        assert r.status_code == 302 and r["Location"] == f"/preguntas/?estado=sin_revisar&q=do#pregunta-{p.pk}"

    def test_editar_conserva_el_estado(self, client, profesor):
        client.force_login(profesor)
        p = pregunta(estado="activa")
        r = client.post(reverse("preguntas:editar", args=[p.pk]), self._datos(enunciado="Cambiado"))
        assert r.status_code == 302 and r["Location"].endswith("?estado=activa")
        p.refresh_from_db()
        assert p.enunciado == "Cambiado" and p.estado == "activa"

    @pytest.mark.parametrize(
        "cambio, campo",
        [
            ({"opcion_2": ""}, "opciones"),
            ({"correcta": ""}, "correcta"),
            ({"etiquetas": "curso:2eso"}, "etiquetas"),
            ({"etiquetas": "concepto:x, caracter:alegre"}, "etiquetas"),
        ],
    )
    def test_un_formulario_malo_no_guarda_y_reensena_lo_tecleado(self, client, profesor, cambio, campo):
        client.force_login(profesor)
        r = client.post(reverse("preguntas:nueva"), self._datos(**cambio))
        assert r.status_code == 200
        assert Pregunta.objects.count() == 0
        assert r.context["errores"].get(campo)
        assert "Tercera" in r.content.decode()

    def test_el_formulario_de_edicion_carga_con_sus_datos(self, client, profesor):
        client.force_login(profesor)
        p = pregunta(correcta=3)
        html = client.get(reverse("preguntas:editar", args=[p.pk])).content.decode()
        assert 'value="3" class="radio radio-success"\n          checked' in html or 'value="3"' in html
        assert "concepto:figuras" in html
