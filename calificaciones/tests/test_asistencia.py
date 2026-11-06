"""Fase 102 — las faltas y las notas de clase, en calificaciones y en el informe.

Los falsadores de C688, C690, C693 y C694.
"""

import itertools
import json
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from calificaciones import asistencia
from clases import plano as planos
from clases.models import Asistencia, ClassSession, Enrollment

pytestmark = pytest.mark.django_db


def _sesion(group, profesor, dia, titulo="Clase"):
    return ClassSession.objects.create(teacher=profesor, group=group, date=dia, title=titulo)


# ----- C688: escribir la marca -------------------------------------------------


def test_marcar_guarda_la_marca_y_lo_que_no_llega_no_cambia(group, profesor, alumnos):
    s = _sesion(group, profesor, date(2026, 10, 7))
    a = alumnos[0].pk
    planos.marcar(s, a, nota="No trae el ukelele por tercera vez")
    assert Asistencia.objects.get(session=s, alumno_id=a).nota_en_informe is False

    planos.marcar(s, a, nota_en_informe=True)
    fila = Asistencia.objects.get(session=s, alumno_id=a)
    assert fila.nota_en_informe is True
    assert fila.nota == "No trae el ukelele por tercera vez"

    # Otro toque (material) no quita la marca.
    planos.marcar(s, a, sin_material=["ukelele"])
    assert Asistencia.objects.get(session=s, alumno_id=a).nota_en_informe is True


def test_vaciar_la_nota_quita_la_marca(group, profesor, alumnos):
    s = _sesion(group, profesor, date(2026, 10, 7))
    a = alumnos[0].pk
    planos.marcar(s, a, estado=Asistencia.FALTA, nota="Avisó su madre", nota_en_informe=True)
    planos.marcar(s, a, nota="")
    fila = Asistencia.objects.get(session=s, alumno_id=a)
    assert fila.nota_en_informe is False
    assert fila.estado == Asistencia.FALTA


@pytest.mark.parametrize("valor", ["si", 1, 0, "true", []])
def test_la_marca_tiene_que_ser_booleana(group, profesor, alumnos, valor):
    s = _sesion(group, profesor, date(2026, 10, 7))
    with pytest.raises(ValidationError):
        planos.marcar(s, alumnos[0].pk, nota="x", nota_en_informe=valor)
    assert not Asistencia.objects.filter(session=s).exists()


def test_lista_marcar_acepta_la_marca_por_http(client, group, profesor, alumnos):
    s = _sesion(group, profesor, date(2026, 10, 7))
    a = alumnos[0].pk
    client.force_login(profesor)
    url = reverse("clases:lista_marcar", args=[s.pk])
    r = client.post(url, json.dumps({"alumno": a, "nota": "Muy bien hoy"}), content_type="application/json")
    assert r.status_code == 200, r.content
    assert r.json()["asistencia"]["nota_en_informe"] is False
    r = client.post(url, json.dumps({"alumno": a, "nota_en_informe": True}), content_type="application/json")
    assert r.json()["asistencia"]["nota_en_informe"] is True
    r = client.post(url, json.dumps({"alumno": a, "nota_en_informe": "sí"}), content_type="application/json")
    assert r.status_code == 422


# ----- C690: lo que lee calificaciones -------------------------------------------


def test_el_resumen_cuenta_por_trimestre(group, profesor, alumnos):
    ana, bruno, _ = alumnos
    octubre = _sesion(group, profesor, date(2026, 10, 7), "Ritmo")
    noviembre = _sesion(group, profesor, date(2026, 11, 4), "Escalas")
    febrero = _sesion(group, profesor, date(2027, 2, 10), "Dictado")
    _sesion(group, profesor, date(2026, 11, 5), "Sin lista")  # ni pasada ni marcas: no cuenta

    planos.marcar(octubre, ana.pk, estado=Asistencia.FALTA)
    planos.marcar(noviembre, ana.pk, estado=Asistencia.RETRASO, sin_material=["ukelele"], nota="Llega sin ukelele")
    planos.marcar(noviembre, bruno.pk, sin_material=["ukelele", "libreta"])
    planos.marcar(febrero, ana.pk, estado=Asistencia.FALTA)
    planos.dar_por_pasada(febrero)

    r = asistencia.resumen(group, profesor)
    assert r["clases"] == {"1": 2, "2": 1, "3": 0}
    assert [m["clave"] for m in r["materiales"]] == ["ukelele", "libreta"]

    t1 = r["alumnos"][str(ana.pk)]["1"]
    assert (t1["faltas"], t1["retrasos"]) == (1, 1)
    assert t1["sin_material"] == {"ukelele": 1, "libreta": 0}
    assert [m["fecha"] for m in t1["marcas"]] == ["2026-10-07", "2026-11-04"]
    assert t1["marcas"][1]["nota"] == "Llega sin ukelele"
    assert t1["marcas"][1]["nota_en_informe"] is False
    assert t1["informe"]["faltas"] == ["2026-10-07"]
    assert t1["informe"]["retrasos"][0]["fecha"] == "2026-11-04"
    assert t1["informe"]["sin_material"]["ukelele"] == ["2026-11-04"]

    assert r["alumnos"][str(ana.pk)]["2"]["faltas"] == 1
    assert r["alumnos"][str(bruno.pk)]["1"]["sin_material"] == {"ukelele": 1, "libreta": 1}
    assert r["alumnos"][str(bruno.pk)]["1"]["faltas"] == 0


def test_la_vista_devuelve_el_resumen(client, group, profesor, alumnos):
    s = _sesion(group, profesor, date(2026, 10, 7))
    planos.marcar(s, alumnos[0].pk, estado=Asistencia.FALTA)
    client.force_login(profesor)
    r = client.get(reverse("calificaciones:asistencia_json", args=[group.pk]))
    assert r.status_code == 200
    assert r["Cache-Control"] == "no-store"
    assert r.json()["alumnos"][str(alumnos[0].pk)]["1"]["faltas"] == 1


# ----- C693: ninguna nota sin marcar llega al informe ----------------------------


def test_solo_las_notas_marcadas_llegan_al_informe(group, profesor, alumnos):
    """Todas las combinaciones de nota (vacía, espacios, texto) × marca (sí, no), en un mismo alumno."""
    ana = alumnos[0]
    combinaciones = list(itertools.product(["", "   ", "Nota de clase"], [False, True]))
    esperadas = []
    for i, (texto, marcada) in enumerate(combinaciones):
        s = _sesion(group, profesor, date(2026, 10, 1 + i))
        # Una falta para que la fila exista aunque la nota esté vacía.
        planos.marcar(s, ana.pk, estado=Asistencia.FALTA, nota=f"{texto} {i}" if texto.strip() else texto)
        planos.marcar(s, ana.pk, nota_en_informe=marcada)
        if texto.strip() and marcada:
            esperadas.append({"fecha": s.date.isoformat(), "texto": f"{texto} {i}"})

    bloque = asistencia.resumen(group, profesor)["alumnos"][str(ana.pk)]["1"]
    assert bloque["informe"]["notas"] == esperadas
    assert len(esperadas) == 1
    # La pestaña sí las ve todas (las que tienen texto).
    assert sum(1 for m in bloque["marcas"] if m["nota"]) == 2
    # Y el texto de una nota sin marcar no aparece en ningún rincón del informe.
    sin_marcar = next(m["nota"] for m in bloque["marcas"] if m["nota"] and not m["nota_en_informe"])
    assert sin_marcar not in json.dumps(bloque["informe"])


# ----- C694: de quién son las sesiones, y quién entra ---------------------------


def test_no_cuentan_las_sesiones_de_otro_profesor_ni_las_bajas(group, profesor, otro_profesor, alumnos):
    group.teachers.add(otro_profesor)
    ana, bruno, _ = alumnos
    mia = _sesion(group, profesor, date(2026, 10, 7))
    suya = _sesion(group, otro_profesor, date(2026, 10, 8))
    planos.marcar(mia, ana.pk, estado=Asistencia.FALTA)
    planos.marcar(suya, ana.pk, estado=Asistencia.FALTA, nota="Del cotitular", nota_en_informe=True)
    planos.marcar(mia, bruno.pk, estado=Asistencia.FALTA)
    Enrollment.objects.filter(user=bruno, group=group).update(is_active=False)

    r = asistencia.resumen(group, profesor)
    assert r["alumnos"][str(ana.pk)]["1"]["faltas"] == 1
    assert r["alumnos"][str(ana.pk)]["1"]["informe"]["notas"] == []
    assert str(bruno.pk) not in r["alumnos"]
    assert r["clases"]["1"] == 1


def test_un_profesor_de_otro_grupo_recibe_404(client, group, otro_profesor, otro_group, alumnos):
    client.force_login(otro_profesor)
    r = client.get(reverse("calificaciones:asistencia_json", args=[group.pk]))
    assert r.status_code == 404


def test_un_alumno_no_entra(client, group, alumnos):
    client.force_login(alumnos[0])
    r = client.get(reverse("calificaciones:asistencia_json", args=[group.pk]))
    assert r.status_code == 302
