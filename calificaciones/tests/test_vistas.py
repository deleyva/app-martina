"""C211, C214, C215, C217, C218, C219, C220 por HTTP."""

from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from calificaciones.models import CambioNota, Criterio, Evidencia, MarcoEvaluacion, Nota, Plan, Prueba
from martina_bescos_app.users.tests.factories import UserFactory

D = Decimal


def _prueba(plan, nombre):
    return Prueba.objects.get(instrumento__plan=plan, instrumento__nombre=nombre)


# ----- permisos (C218) -------------------------------------------------------


@pytest.mark.django_db
def test_un_alumno_no_entra(client, alumnos, plan):
    client.force_login(alumnos[0])
    respuesta = client.get(reverse("calificaciones:index"))
    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith("/accounts/login/")
    respuesta = client.get(reverse("calificaciones:cuadro", args=[plan.groups.first().pk]))
    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith("/accounts/login/")


@pytest.mark.django_db
def test_el_profesor_ve_su_cuadro(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    respuesta = client.get(reverse("calificaciones:cuadro", args=[group.pk]) + "?t=1")
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert "{#" not in html
    assert "Alumno 0" in html
    assert "L.rít" in html


@pytest.mark.django_db
def test_otro_profesor_recibe_404_en_todo(client, otro_profesor, otro_group, group, alumnos, plan):
    client.force_login(otro_profesor)
    prueba = _prueba(plan, "Teoría")
    assert client.get(reverse("calificaciones:cuadro", args=[group.pk])).status_code == 404
    assert client.get(reverse("calificaciones:plan", args=[plan.pk])).status_code == 404
    assert client.get(reverse("calificaciones:clase", args=[group.pk])).status_code == 404
    assert client.get(reverse("calificaciones:historial", args=[group.pk])).status_code == 404
    r = client.post(
        reverse("calificaciones:nota_guardar", args=[group.pk]),
        {"prueba": prueba.pk, "alumno": alumnos[0].pk, "valor": "7"},
    )
    assert r.status_code == 404
    assert Nota.objects.count() == 0
    r = client.post(
        reverse("calificaciones:evidencia_subir", args=[group.pk]),
        {"prueba": prueba.pk, "alumno": alumnos[0].pk, "tipo": "texto", "texto": "hola"},
    )
    assert r.status_code == 404
    assert Evidencia.objects.count() == 0


@pytest.mark.django_db
def test_el_menu_solo_lo_ve_el_profesorado(client, profesor, alumnos, group, plan):
    client.force_login(profesor)
    html = client.get("/calificaciones/").content.decode()
    assert "{#" not in html
    assert html.count("/calificaciones/") >= 3  # barra, drawer y dock
    client.force_login(alumnos[0])
    html = client.get(reverse("my_library:index")).content.decode()
    assert "Calificaciones" not in html


# ----- notas e historial (C215, C219) ------------------------------------------


@pytest.mark.django_db
def test_guardar_nota_devuelve_la_fila_y_deja_historial(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    alumno = alumnos[0]
    r = client.post(url, {"prueba": _prueba(plan, "Teoría").pk, "alumno": alumno.pk, "valor": "8"})
    assert r.status_code == 200
    datos = r.json()
    assert datos["valor"] == "8"
    assert datos["trimestre"] == "8"  # único instrumento con nota: renormalizado
    assert datos["cualitativa"] == "NT"
    assert datos["faltan"] == 3

    client.post(url, {"prueba": _prueba(plan, "Lectura rítmica").pk, "alumno": alumno.pk, "valor": "6,5"})
    client.post(url, {"prueba": _prueba(plan, "Dictado").pk, "alumno": alumno.pk, "valor": "5"})
    r = client.post(url, {"prueba": _prueba(plan, "Cuaderno").pk, "alumno": alumno.pk, "valor": "10"})
    # Por criterios: 1.1 6.8 · 1.2 8.8 · 2.1 8.6 · 3.1 5.6 → 7.45. Por columnas:
    # (30·8 + 20·6.5 + 25·5 + 25·10) / 100 = 7.45. La misma cifra, porque cuadra.
    assert r.json()["trimestre"] == "7.45"
    assert r.json()["faltan"] == 0

    # Vacío = sin nota, no cero.
    r = client.post(url, {"prueba": _prueba(plan, "Teoría").pk, "alumno": alumno.pk, "valor": ""})
    assert r.json()["valor"] == ""
    assert Nota.objects.get(prueba__instrumento__nombre="Teoría", alumno=alumno).valor is None
    assert r.json()["faltan"] == 1

    # Fuera de rango o basura: 400 y nada cambia.
    assert client.post(url, {"prueba": _prueba(plan, "Teoría").pk, "alumno": alumno.pk, "valor": "11"}).status_code == 400
    assert client.post(url, {"prueba": _prueba(plan, "Teoría").pk, "alumno": alumno.pk, "valor": "abc"}).status_code == 400

    cambios = CambioNota.objects.filter(nota__alumno=alumno, nota__prueba__instrumento__nombre="Teoría")
    assert [(c.antes, c.despues) for c in cambios.order_by("ts", "pk")] == [("", "8"), ("8", "")]


@pytest.mark.django_db
def test_deshacer_escribe_el_valor_anterior_y_no_borra(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    prueba = _prueba(plan, "Teoría")
    client.post(url, {"prueba": prueba.pk, "alumno": alumnos[0].pk, "valor": "4"})
    client.post(url, {"prueba": prueba.pk, "alumno": alumnos[0].pk, "valor": "9"})
    ultimo = CambioNota.objects.filter(nota__alumno=alumnos[0]).order_by("-ts", "-pk").first()
    assert (ultimo.antes, ultimo.despues) == ("4", "9")

    r = client.post(reverse("calificaciones:cambio_revertir", args=[ultimo.pk]), {"next": "/calificaciones/"})
    assert r.status_code == 302
    assert Nota.objects.get(prueba=prueba, alumno=alumnos[0]).valor == D(4)
    assert CambioNota.objects.filter(nota__alumno=alumnos[0]).count() == 3
    reversion = CambioNota.objects.filter(revertido_de=ultimo).get()
    assert (reversion.antes, reversion.despues) == ("9", "4")

    html = client.get(reverse("calificaciones:historial", args=[group.pk])).content.decode()
    assert "{#" not in html
    assert "deshacer" in html


@pytest.mark.django_db
def test_el_cuadro_con_varias_pruebas_agrega(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    instrumento = plan.instrumentos.get(nombre="Lectura rítmica")
    segunda = Prueba.objects.create(instrumento=instrumento, nombre="Lectura rítmica 2")
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    client.post(url, {"prueba": instrumento.pruebas.first().pk, "alumno": alumnos[1].pk, "valor": "4"})
    client.post(url, {"prueba": segunda.pk, "alumno": alumnos[1].pk, "valor": "8"})
    resultado = plan.resultado_de(alumnos[1])
    assert resultado.instrumentos[instrumento.pk] == D(6)
    html = client.get(reverse("calificaciones:cuadro", args=[group.pk])).content.decode()
    assert "nota-agregada" in html  # con dos pruebas, la celda no es editable en línea


# ----- evidencias (C217) ---------------------------------------------------------


@pytest.mark.django_db
def test_evidencia_se_sube_y_solo_la_ve_su_profesor(client, profesor, otro_profesor, otro_group, group, alumnos, plan):
    client.force_login(profesor)
    prueba = _prueba(plan, "Lectura rítmica")
    foto = SimpleUploadedFile("foto.jpg", b"\xff\xd8\xff\xe0fake", content_type="image/jpeg")
    r = client.post(
        reverse("calificaciones:evidencia_subir", args=[group.pk]),
        {"prueba": prueba.pk, "alumno": alumnos[0].pk, "tipo": "foto", "archivo": foto},
    )
    assert r.status_code == 200, r.content
    evidencia = Evidencia.objects.get()
    assert evidencia.archivo.name.startswith(f"calificaciones/{plan.pk}/{alumnos[0].pk}/")
    assert "foto.jpg" not in evidencia.archivo.name  # nombre no adivinable
    assert evidencia.archivo.storage.exists(evidencia.archivo.name)

    r = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert r.status_code == 200
    assert r["Content-Type"] == "image/jpeg"
    assert b"".join(r.streaming_content) == b"\xff\xd8\xff\xe0fake"

    r = client.post(
        reverse("calificaciones:evidencia_subir", args=[group.pk]),
        {"prueba": prueba.pk, "alumno": alumnos[0].pk, "tipo": "texto", "texto": "Lee bien la negra con puntillo"},
    )
    assert r.json()["total"] == 2

    client.force_login(otro_profesor)
    assert client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk])).status_code == 404
    assert client.post(reverse("calificaciones:evidencia_borrar", args=[evidencia.pk])).status_code == 404
    assert Evidencia.objects.count() == 2

    client.force_login(alumnos[0])
    r = client.get(reverse("calificaciones:evidencia_ver", args=[evidencia.pk]))
    assert r.status_code in (302, 403)


def test_nginx_cierra_la_ruta_de_media():
    from pathlib import Path

    conf = Path(__file__).resolve().parents[2] / "compose" / "production" / "nginx" / "default.conf"
    texto = conf.read_text()
    assert "location ^~ /media/calificaciones/" in texto
    bloque = texto.split("location ^~ /media/calificaciones/")[1].split("}")[0]
    assert "return 404" in bloque


# ----- plan y reparto (C213) ----------------------------------------------------


@pytest.mark.django_db
def test_reparto_se_guarda_y_cuadra(client, profesor, group, plan):
    client.force_login(profesor)
    html = client.get(reverse("calificaciones:plan", args=[plan.pk])).content.decode()
    assert "{#" not in html
    assert "Cuadra" in html or "cuadre" in html
    criterios = {c.codigo: c for c in plan.marco.criterios.all()}
    instrumentos = {i.nombre: i for i in plan.instrumentos.all()}
    datos = {
        f"celda-{criterios['1.1'].pk}-{instrumentos['Teoría'].pk}": "25",
        f"celda-{criterios['1.2'].pk}-{instrumentos['Lectura rítmica'].pk}": "25",
        f"celda-{criterios['2.1'].pk}-{instrumentos['Dictado'].pk}": "25",
        f"celda-{criterios['3.1'].pk}-{instrumentos['Cuaderno'].pk}": "20",  # no cuadra: 20 ≠ 25
        f"celda-{criterios['3.1'].pk}-{instrumentos['Teoría'].pk}": "0",  # cero = celda vacía
    }
    r = client.post(reverse("calificaciones:reparto_guardar", args=[plan.pk]), datos)
    assert r.status_code == 302
    cuadre = plan.cuadre()
    assert cuadre["total"] == D(95)
    assert cuadre["cuadra"] is False
    assert [f["cuadra"] for f in cuadre["filas"]] == [True, True, True, False]
    assert instrumentos["Teoría"].peso == D(25)


@pytest.mark.django_db
def test_copiar_plan_para_otro_trimestre(client, profesor, group, plan):
    client.force_login(profesor)
    r = client.post(
        reverse("calificaciones:plan_adoptar", args=[group.pk]) + "?t=2",
        {"copiar_de": plan.pk, "nombre": "Segunda"},
    )
    assert r.status_code == 302
    nuevo = Plan.para_grupo(group, 2)
    assert nuevo.nombre == "Segunda"
    assert nuevo.instrumentos.count() == 4
    assert nuevo.cuadre()["cuadra"] is True
    assert nuevo.instrumentos.first().pruebas.count() == 1  # cada instrumento nace con su prueba


# ----- la siembra (C214) ----------------------------------------------------------


@pytest.mark.django_db
def test_cargar_marcos_musica_cuadra_y_es_idempotente(subject):
    call_command("cargar_marcos_musica", curso="2026-2027")
    call_command("cargar_marcos_musica", curso="2026-2027")
    assert MarcoEvaluacion.objects.count() == 3
    for marco in MarcoEvaluacion.objects.all():
        assert marco.peso_total == D(100)
        plan = marco.planes.get()
        assert plan.instrumentos.count() == 9
        assert plan.instrumentos.filter(nombre="Sensorialidad").exists()
        assert plan.cuadre()["cuadra"] is True, str(marco)
    assert Criterio.objects.count() == 10 + 10 + 9
    tercero = MarcoEvaluacion.objects.get(nivel="3º ESO")
    assert tercero.pesos_trimestre() == {1: D(20), 2: D(30), 3: D(50)}


# ----- exportar --------------------------------------------------------------------


@pytest.mark.django_db
def test_exportar_csv_por_criterio(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    for nombre in ("Teoría", "Lectura rítmica", "Dictado", "Cuaderno"):
        client.post(url, {"prueba": _prueba(plan, nombre).pk, "alumno": alumnos[0].pk, "valor": "8"})
    r = client.get(reverse("calificaciones:exportar", args=[group.pk]) + "?t=1&por=criterio")
    assert r.status_code == 200
    texto = r.content.decode("utf-8-sig")
    lineas = texto.strip().splitlines()
    assert lineas[0] == "Alumno;1.1;1.2;2.1;3.1;Nota;Calificación"
    assert lineas[1].startswith("Alumno 0;8,00;8,00;8,00;8,00;8,00;NT")
