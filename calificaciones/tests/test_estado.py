"""C340–C342: el estado que pinta la pantalla, las letras y quién puede verlo."""

import csv
import io
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse

from calificaciones import estado, plantillas
from calificaciones.models import CambioNota, Instrumento, Nota, NotaManual, Plan, Prueba

D = Decimal


@pytest.fixture
def marcos(subject):
    call_command("cargar_marcos_musica", curso="2026-2027")


@pytest.fixture
def plan_letras(client, profesor, group, alumnos, marcos):
    """El grupo estrena plan desde la plantilla de 3º: nueve instrumentos en A-D."""
    client.force_login(profesor)
    client.post(reverse("calificaciones:plan_adoptar", args=[group.pk]) + "?t=1", {"plantilla": "3eso"})
    return Plan.para_grupo(group, 1)


def _guardar(client, group, prueba, alumno, valor):
    return client.post(
        reverse("calificaciones:nota_guardar", args=[group.pk]),
        {"prueba": prueba.pk, "alumno": alumno.pk, "valor": valor},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )


# ----- letras (C340) ---------------------------------------------------------------


@pytest.mark.django_db
def test_las_plantillas_nacen_con_la_escala_cualitativa(marcos, group):
    for plantilla in plantillas.PLANTILLAS:
        plan = plantilla.crear_plan(plantilla.marco_de(group), 1, plantilla.clave)
        for instrumento in plan.instrumentos.all():
            assert instrumento.escala == Instrumento.ESCALA_OPCIONES, instrumento.nombre
            assert [(o["etiqueta"], o["valor"]) for o in instrumento.opciones_normalizadas()] == [
                ("SB", D("9.5")),
                ("NT", D(8)),
                ("BI", D("6.5")),
                ("SU", D("5.5")),
                ("IN", D(4)),
            ]


@pytest.mark.django_db
def test_los_instrumentos_de_una_plantilla_no_comparten_la_lista(marcos, group):
    """Editar las opciones de un instrumento no puede cambiar las de otro ni las de la plantilla."""
    plan = plantillas.POR_CLAVE["3eso"].crear_plan(plantillas.POR_CLAVE["3eso"].marco_de(group), 1, "x")
    primero = plan.instrumentos.first()
    primero.opciones[0]["valor"] = 9
    primero.save()
    assert plantillas.ESCALA[0]["valor"] == 9.5
    assert plan.instrumentos.last().opciones[0]["valor"] == 9.5


@pytest.mark.django_db
def test_letra_que_no_es_opcion_da_400(client, group, alumnos, plan_letras):
    teoria = Prueba.objects.get(instrumento__plan=plan_letras, instrumento__nombre="Teoría")
    r = _guardar(client, group, teoria, alumnos[0], "7")
    assert r.status_code == 400
    assert "SB, NT, BI, SU, IN" in r.json()["error"]
    assert not Nota.objects.filter(valor__isnull=False).exists()
    assert not CambioNota.objects.exists()


@pytest.mark.django_db
def test_una_letra_se_guarda_como_su_valor_y_se_lee_como_letra(client, group, alumnos, plan_letras):
    teoria = Prueba.objects.get(instrumento__plan=plan_letras, instrumento__nombre="Teoría")
    r = _guardar(client, group, teoria, alumnos[0], "8")
    assert r.status_code == 200
    assert r.json()["etiqueta"] == "NT"
    celda = r.json()["alumno"]["trimestres"]["1"]["notas"][str(teoria.pk)]
    assert celda == {"valor": "8", "etiqueta": "NT"}
    assert Nota.objects.get(prueba=teoria, alumno=alumnos[0]).valor == D(8)
    # Teoría pesa 15 de 100 en 3º y lo demás está vacío: 8 · 0,15 = 1,2.
    assert r.json()["alumno"]["trimestres"]["1"]["nota"] == "1.2"
    # Vaciar la celda sigue valiendo.
    assert _guardar(client, group, teoria, alumnos[0], "").status_code == 200
    assert Nota.objects.get(prueba=teoria, alumno=alumnos[0]).valor is None


@pytest.mark.django_db
def test_una_nota_antigua_que_no_es_opcion_se_lee_como_numero(profesor, alumnos, plan):
    teoria = Instrumento.objects.get(plan=plan, nombre="Teoría")
    Nota.poner(teoria.pruebas.get(), alumnos[0], D(7), profesor)
    plan.pasar_a_letras(plantillas.ESCALA)
    teoria.refresh_from_db()
    assert teoria.etiqueta_de(D(7)) == "7"
    assert teoria.etiqueta_de(D(8)) == "NT"
    assert plan.resultado_de(alumnos[0]).instrumentos[teoria.pk] == D(7)


@pytest.mark.django_db
def test_pasar_a_letras_desde_el_plan(client, profesor, group, plan):
    client.force_login(profesor)
    r = client.post(reverse("calificaciones:plan_ajustes", args=[plan.pk]), {"a_letras": "1"})
    assert r.status_code == 302
    assert set(plan.instrumentos.values_list("escala", flat=True)) == {"opciones"}
    plan.refresh_from_db()
    assert plan.hueco_cuenta_cero is True  # pasar a letras no toca la regla


@pytest.mark.parametrize(
    ("opciones", "error"),
    [
        ([{"etiqueta": "A", "valor": 10}, {"etiqueta": "a", "valor": 8}], "repetida"),
        ([{"etiqueta": "Á", "valor": 10}, {"etiqueta": "A", "valor": 8}], "repetida"),
        ([{"etiqueta": "A", "valor": 10}, {"etiqueta": "B", "valor": 10}], "valen 10"),
        ([{"etiqueta": "A", "valor": 11}], "entre 0 y 10"),
        ([{"etiqueta": " ", "valor": 5}], "etiqueta"),
    ],
)
def test_opciones_que_se_pisan_no_se_guardan(opciones, error):
    with pytest.raises(ValueError, match=error):
        Instrumento.limpiar_opciones(opciones)


@pytest.mark.django_db
def test_una_fila_entera_en_un_viaje_o_todo_o_nada(client, group, alumnos, plan_letras):
    pruebas = list(Prueba.objects.filter(instrumento__plan=plan_letras).order_by("pk"))
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    r = client.post(
        url,
        {"alumno": alumnos[0].pk, "prueba": [p.pk for p in pruebas], "valor": ["9.5", "8", "9.5", "9.5", "6.5", "8", "9.5", "8", "9.5"]},
    )
    assert r.status_code == 200
    # 15·9,5 + 10·8 + 10·9,5 + 10·9,5 + 10·6,5 + 10·8 + 10·9,5 + 15·8 + 10·9,5 = 867,5 → 8,675 → 8,7
    assert r.json()["alumno"]["trimestres"]["1"]["nota"] == "8.7"
    assert r.json()["alumno"]["trimestres"]["1"]["nota2"] == "8.68"
    assert Nota.objects.filter(alumno=alumnos[0], valor__isnull=False).count() == 9
    assert CambioNota.objects.count() == 9

    # Una que no vale en medio: no se guarda ninguna.
    r = client.post(url, {"alumno": alumnos[1].pk, "prueba": [p.pk for p in pruebas[:3]], "valor": ["9.5", "7", "8"]})
    assert r.status_code == 400
    assert not Nota.objects.filter(alumno=alumnos[1]).exists()
    # Y si las listas no casan, tampoco.
    assert client.post(url, {"alumno": alumnos[1].pk, "prueba": [pruebas[0].pk], "valor": ["9.5", "8"]}).status_code == 400
    assert client.post(url, {"alumno": alumnos[1].pk}).status_code == 400


# ----- un solo cálculo (C341) ----------------------------------------------------------


@pytest.mark.django_db
def test_guardar_devuelve_el_mismo_bloque_que_estado(client, profesor, group, alumnos, plan_letras):
    pruebas = list(Prueba.objects.filter(instrumento__plan=plan_letras).order_by("pk"))
    for prueba, valor in zip(pruebas, ["9.5", "8", "6.5", "5.5", "9.5", "8"]):
        r = _guardar(client, group, prueba, alumnos[0], valor)
    NotaManual.objects.create(group=group, alumno=alumnos[0], ambito="1", calificacion="NT")
    r = _guardar(client, group, pruebas[6], alumnos[0], "4")
    leido = client.get(reverse("calificaciones:estado", args=[group.pk])).json()
    del_estado = next(a for a in leido["alumnos"] if a["id"] == alumnos[0].pk)
    assert r.json()["alumno"] == del_estado
    assert del_estado["trimestres"]["1"]["manual"] == "NT"
    assert estado.bloque_alumno(group, alumnos[0]) == del_estado


@pytest.mark.django_db
def test_los_numeros_del_estado_son_los_del_csv(client, profesor, group, alumnos, plan_letras):
    pruebas = list(Prueba.objects.filter(instrumento__plan=plan_letras).order_by("pk"))
    for alumno, valores in zip(alumnos, [["9.5", "8", "6.5"], ["4"], []]):
        for prueba, valor in zip(pruebas, valores):
            _guardar(client, group, prueba, alumno, valor)
    leido = client.get(reverse("calificaciones:estado", args=[group.pk])).json()
    fichero = client.get(reverse("calificaciones:exportar", args=[group.pk]) + "?t=1&por=instrumento")
    filas = list(csv.reader(io.StringIO(fichero.content.decode("utf-8-sig")), delimiter=";"))
    por_nombre = {fila[0]: fila for fila in filas[1:]}
    assert len(por_nombre) == 3
    for alumno in leido["alumnos"]:
        fila = por_nombre[alumno["nombre"]]
        nota_csv = D(fila[-2].replace(",", "."))
        assert alumno["trimestres"]["1"]["nota2"] == CambioNota.texto(nota_csv)
        assert alumno["trimestres"]["1"]["cualitativa"] == fila[-1]


@pytest.mark.django_db
def test_el_estado_trae_columnas_competencias_y_curso(client, profesor, group, alumnos, plan_letras):
    leido = client.get(reverse("calificaciones:estado", args=[group.pk])).json()
    primero = leido["trimestres"]["1"]
    assert [c["corto"] for c in primero["columnas"]][:3] == ["Teoría", "Sensor.", "D. rít."]
    assert {c["tipo"] for c in primero["columnas"]} == {"opciones"}
    assert [c["codigo"] for c in primero["competencias"]] == ["CE.MU.1", "CE.MU.2", "CE.MU.3", "CE.MU.4"]
    assert [c["peso"] for c in primero["competencias"]] == ["30", "20", "30", "20"]
    assert [p["encaja"] for p in leido["trimestres"]["2"]["empezar"]["plantillas"]] == [True, False, False]
    assert sum(D(c["peso"]) for c in primero["competencias"]) == D(100)
    assert primero["plan"]["cuadra"] is True
    # La 2ª no tiene plan: ofrece seguir con lo de la 1ª y las plantillas.
    segundo = leido["trimestres"]["2"]
    assert segundo["plan"] is None
    assert segundo["empezar"]["anterior"]["id"] == plan_letras.pk
    assert [p["clave"] for p in segundo["empezar"]["plantillas"]][0] == "3eso"
    assert leido["pesos_trimestre"] == {"1": "20", "2": "30", "3": "50"}
    assert leido["grupos"] == [{"id": group.pk, "nombre": group.name}]


@pytest.mark.django_db
def test_una_segunda_prueba_es_una_segunda_columna(client, profesor, group, alumnos, plan_letras):
    teoria = Instrumento.objects.get(plan=plan_letras, nombre="Teoría")
    Prueba.objects.create(instrumento=teoria, nombre="Teoría de octubre")
    oculta = Prueba.objects.create(instrumento=teoria, nombre="Teoría oculta", activa=False)
    columnas = client.get(reverse("calificaciones:estado", args=[group.pk])).json()["trimestres"]["1"]["columnas"]
    assert [c["corto"] for c in columnas][:3] == ["Teoría 1", "Teoría 2", "Sensor."]
    assert oculta.pk not in [c["prueba"] for c in columnas]


@pytest.mark.django_db
def test_el_curso_solo_cuenta_las_evaluaciones_con_notas(client, profesor, group, alumnos, plan_letras):
    client.post(
        reverse("calificaciones:plan_adoptar", args=[group.pk]) + "?t=2", {"copiar_de": plan_letras.pk}
    )
    for prueba in Prueba.objects.filter(instrumento__plan=plan_letras):
        _guardar(client, group, prueba, alumnos[0], "8")
    bloque = estado.bloque_alumno(group, alumnos[0])
    assert bloque["trimestres"]["1"]["nota"] == "8.0"
    assert bloque["trimestres"]["2"]["nota"] == "0.0"  # con plan y sin tocar
    assert bloque["trimestres"]["2"]["con_datos"] is False
    assert bloque["curso"]["nota"] == "8.0"  # la 2ª no ha empezado: no baja el curso
    assert bloque["curso"]["cualitativa"] == "NT"
    # El alumno que no tiene nada no tiene nota de curso.
    assert estado.bloque_alumno(group, alumnos[1])["curso"]["nota"] == ""


@pytest.mark.django_db
def test_estado_consultas_acotadas(client, profesor, group, alumnos, plan_letras, django_assert_max_num_queries):
    from clases.models import Enrollment
    from martina_bescos_app.users.tests.factories import UserFactory

    client.get(reverse("calificaciones:estado", args=[group.pk]))
    with django_assert_max_num_queries(60) as con_tres:
        client.get(reverse("calificaciones:estado", args=[group.pk]))
    for n in range(20):
        Enrollment.objects.create(user=UserFactory(name=f"Otro {n}"), group=group)
    with django_assert_max_num_queries(len(con_tres.captured_queries) + 2):
        client.get(reverse("calificaciones:estado", args=[group.pk]))


# ----- permisos (C342) --------------------------------------------------------------------


@pytest.mark.django_db
def test_estado_exige_profesor_del_grupo(client, otro_profesor, otro_group, group, alumnos, plan):
    client.force_login(otro_profesor)
    for nombre in ("registro", "estado", "historial_json"):
        assert client.get(reverse(f"calificaciones:{nombre}", args=[group.pk])).status_code == 404, nombre
    assert client.post(reverse("calificaciones:plan_ajustes", args=[plan.pk]), {"a_letras": "1"}).status_code == 404
    assert set(plan.instrumentos.values_list("escala", flat=True)) == {"numerica"}

    client.force_login(alumnos[0])
    for nombre in ("registro", "estado", "historial_json"):
        r = client.get(reverse(f"calificaciones:{nombre}", args=[group.pk]))
        assert r.status_code == 302, nombre
        assert r["Location"].startswith("/accounts/login/")


# ----- historial --------------------------------------------------------------------------


@pytest.mark.django_db
def test_historial_en_letras_y_deshacer_por_json(client, group, alumnos, plan_letras):
    teoria = Prueba.objects.get(instrumento__plan=plan_letras, instrumento__nombre="Teoría")
    _guardar(client, group, teoria, alumnos[0], "9.5")
    _guardar(client, group, teoria, alumnos[0], "6.5")
    cambios = client.get(reverse("calificaciones:historial_json", args=[group.pk])).json()["cambios"]
    assert [(c["antes"], c["despues"]) for c in cambios] == [("SB", "BI"), ("", "SB")]
    assert cambios[0]["trimestre"] == 1
    assert cambios[0]["columna"] == "Teoría"

    r = client.post(
        reverse("calificaciones:cambio_revertir", args=[cambios[0]["id"]]),
        {"grupo": group.pk},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert r.status_code == 200
    assert r.json()["alumno"]["trimestres"]["1"]["notas"][str(teoria.pk)]["etiqueta"] == "SB"
    cambios = client.get(reverse("calificaciones:historial_json", args=[group.pk])).json()["cambios"]
    assert [(c["antes"], c["despues"], c["es_deshacer"]) for c in cambios][0] == ("BI", "SB", True)


# ----- la página ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_registro_no_hereda_de_base(client, profesor, group, plan):
    client.force_login(profesor)
    r = client.get(reverse("calificaciones:registro", args=[group.pk]) + "?t=2")
    html = r.content.decode()
    assert r.status_code == 200
    assert r["Cache-Control"] == "no-store"
    assert "{#" not in html
    assert 'id="root"' in html
    assert "calificaciones/registro" in html
    assert "csrfmiddlewaretoken" in html or 'name="csrf"' in html
    for resto in ('class="dock', "drawer", "Martina Bescós Music App", "theme-toggle"):
        assert resto not in html, resto
    assert '"trimestre": 2' in html


@pytest.mark.django_db
def test_los_mensajes_no_se_quedan_en_cola(client, profesor, group, alumnos, marcos):
    client.force_login(profesor)
    client.post(reverse("calificaciones:plan_adoptar", args=[group.pk]) + "?t=1", {"plantilla": "3eso"})
    html = client.get(reverse("calificaciones:registro", args=[group.pk])).content.decode()
    assert "ya puedes poner notas" in html
    assert "ya puedes poner notas" not in client.get(reverse("calificaciones:index")).content.decode()


@pytest.mark.django_db
def test_empezar_desde_la_pantalla_no_deja_mensajes(client, profesor, group, alumnos, marcos):
    """La pantalla pide por JSON y no recarga: un mensaje encolado saldría después, en otra página."""
    client.force_login(profesor)
    r = client.post(
        reverse("calificaciones:plan_adoptar", args=[group.pk]) + "?t=1",
        {"plantilla": "3eso"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert r.status_code == 200
    assert r.json()["plan"] == Plan.para_grupo(group, 1).pk
    assert "ya puedes poner notas" not in client.get(reverse("calificaciones:index")).content.decode()


@pytest.mark.django_db
def test_las_pantallas_viejas_ya_no_existen(client, profesor, group, plan):
    """C355: ni el cuadro, ni el panel, ni el historial en HTML, ni el modo clase."""
    from pathlib import Path

    client.force_login(profesor)
    for ruta in ("clase/", "historial/", "registro/", "instrumento/1/alumno/1/"):
        assert client.get(f"/calificaciones/grupo/{group.pk}/{ruta}").status_code == 404, ruta
    app = Path(__file__).parents[1]
    plantillas = {p.name for p in (app / "templates").rglob("*.html")}
    assert plantillas == {"index.html", "plan.html", "registro.html", "resumen.html"}
    for fichero in list((app / "templates").rglob("*.html")) + [app / "views.py", app / "urls.py"]:
        texto = fichero.read_text(encoding="utf-8")
        for nombre in ("calificaciones:cuadro", "calificaciones:clase", "calificaciones:panel", "calificaciones:historial'"):
            assert nombre not in texto, f"{fichero.name}: {nombre}"
    inicio = client.get(reverse("calificaciones:index")).content.decode()
    assert "Modo clase" not in inicio
    assert f"/calificaciones/grupo/{group.pk}/?t=1" in inicio


@pytest.mark.django_db
def test_el_plan_deja_cambiar_la_regla_y_pasar_a_letras(client, profesor, group, plan):
    client.force_login(profesor)
    html = client.get(reverse("calificaciones:plan", args=[plan.pk])).content.decode()
    assert "{#" not in html
    assert "Una celda vacía cuenta como 0" in html
    assert 'name="hueco_cuenta_cero" class="checkbox checkbox-sm" checked' in html
    assert "Calificar todo con SB · NT · BI · SU · IN" in html
    assert f"/calificaciones/grupo/{group.pk}/?t=1#info" in html
