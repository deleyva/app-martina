"""Fase 70 — Plano de clase y pasar lista. Los falsadores de C423 a C432."""

import json
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from api_keys.models import APIKey
from clases import plano as planos
from clases.models import Asistencia
from clases.models import ClassSession
from clases.models import ClassSessionItem
from clases.models import Enrollment
from clases.models import Group
from clases.models import PaseDeLista
from clases.models import PlanoDeClase
from clases.models import PlanoVersion
from clases.models import SessionNote
from clases.models import Subject
from martina_bescos_app.users.tests.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_hosts")]


@pytest.fixture
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.APPS_CANDADO = False


def _grupo(nombre, profesor=None):
    asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
    grupo = Group.objects.create(name=nombre, subject=asignatura, academic_year="2026-2027")
    if profesor:
        grupo.teachers.add(profesor)
    return grupo


@pytest.fixture
def profesor():
    return UserFactory(name="Profe")


@pytest.fixture
def grupo(profesor):
    return _grupo("3-EG-BIL", profesor)


@pytest.fixture
def alumnos(grupo):
    lista = [UserFactory(name=n) for n in ("ANA PEREZ GIL", "BRUNO SANZ ROS", "CARLA DIAZ PAZ")]
    for a in lista:
        Enrollment.objects.create(user=a, group=grupo)
    return lista


@pytest.fixture
def sesion(grupo, profesor):
    return ClassSession.objects.create(teacher=profesor, group=grupo, date=date(2026, 10, 7), title="Ritmo")


def _mesa(ocupantes, plazas=2, x=100, y=200, **extra):
    return {"id": "m1", "x": x, "y": y, "plazas": plazas, "giro": 0, "ocupantes": ocupantes, **extra}


def _disp(*mesas):
    return {"referencia": {"x": 440, "y": 20}, "mesas": list(mesas)}


# === C423 — un plano por grupo y aula ===


def test_dos_planos_por_grupo_y_no_mas(grupo):
    planos.plano_de(grupo, "referencia")
    planos.plano_de(grupo, "musica")
    planos.plano_de(grupo, "musica")
    assert PlanoDeClase.objects.filter(group=grupo).count() == 2
    with pytest.raises(IntegrityError):
        PlanoDeClase.objects.create(group=grupo, aula="musica")


def test_aula_desconocida_se_rechaza(grupo):
    with pytest.raises(ValidationError):
        planos.plano_de(grupo, "gimnasio")


# === C424 — validación: entero o nada ===


def test_disposicion_valida_se_normaliza(grupo, alumnos):
    limpia = planos.validar(_disp(_mesa([alumnos[0].pk])), grupo)
    assert limpia["mesas"][0]["ocupantes"] == [alumnos[0].pk, None]


@pytest.mark.parametrize(
    "caso",
    ["duplicado", "ajeno", "de_baja", "fuera", "plazas", "sobran"],
)
def test_disposicion_invalida_se_rechaza(grupo, alumnos, caso):
    ana, bruno, _ = alumnos
    if caso == "duplicado":
        disp = _disp(_mesa([ana.pk, None]), {**_mesa([ana.pk]), "id": "m2"})
    elif caso == "ajeno":
        disp = _disp(_mesa([UserFactory().pk]))
    elif caso == "de_baja":
        Enrollment.objects.filter(user=bruno).update(is_active=False)
        disp = _disp(_mesa([bruno.pk]))
    elif caso == "fuera":
        disp = _disp(_mesa([], x=5000))
    elif caso == "plazas":
        disp = _disp(_mesa([], plazas=9))
    else:
        disp = _disp(_mesa([ana.pk, bruno.pk, alumnos[2].pk], plazas=2))
    with pytest.raises(ValidationError):
        planos.validar(disp, grupo)


def test_lo_invalido_no_toca_el_plano(grupo, alumnos):
    plano = planos.plano_de(grupo, "referencia")
    planos.guardar(plano, _disp(_mesa([alumnos[0].pk])))
    with pytest.raises(ValidationError):
        planos.guardar(plano, _disp(_mesa([UserFactory().pk])))
    plano.refresh_from_db()
    assert plano.disposicion["mesas"][0]["ocupantes"][0] == alumnos[0].pk
    assert plano.versiones.count() == 1


def test_quien_no_tiene_plaza_sale_en_sin_sitio(grupo, alumnos):
    plano = planos.plano_de(grupo, "referencia")
    planos.guardar(plano, _disp(_mesa([alumnos[0].pk])))
    assert [u.pk for u in planos.sin_sitio(plano)] == [alumnos[1].pk, alumnos[2].pk]


# === C425 — versiones y restaurar ===


def test_restaurar_es_otro_guardado(grupo, alumnos, profesor):
    plano = planos.plano_de(grupo, "referencia")
    v1 = planos.guardar(plano, _disp(_mesa([alumnos[0].pk])), autor=profesor, motivo="primero")
    planos.guardar(plano, _disp(_mesa([alumnos[1].pk])), autor=profesor)
    planos.restaurar(v1, autor=profesor)
    plano.refresh_from_db()
    assert plano.disposicion["mesas"][0]["ocupantes"][0] == alumnos[0].pk
    assert plano.versiones.count() == 3
    assert plano.versiones.first().origen == PlanoVersion.RESTAURAR


def test_restaurar_no_sienta_a_quien_se_dio_de_baja(grupo, alumnos):
    plano = planos.plano_de(grupo, "referencia")
    v1 = planos.guardar(plano, _disp(_mesa([alumnos[0].pk])))
    Enrollment.objects.filter(user=alumnos[0]).update(is_active=False)
    planos.restaurar(v1)
    plano.refresh_from_db()
    assert plano.disposicion["mesas"][0]["ocupantes"] == [None, None]


# === C426 — editor ===


def test_editor_abre_para_el_profesor(client, profesor, grupo, alumnos):
    client.force_login(profesor)
    r = client.get(reverse("clases:plano_editor", args=[grupo.pk, "musica"]))
    assert r.status_code == 200
    assert b"plano-datos" in r.content


def test_editor_cerrado_a_otro_profesor(client, grupo):
    otro = UserFactory()
    _grupo("1-G-BIL", otro)
    client.force_login(otro)
    assert client.get(reverse("clases:plano_editor", args=[grupo.pk, "musica"])).status_code == 404


def test_guardar_desde_el_editor_deja_version(client, profesor, grupo, alumnos):
    client.force_login(profesor)
    r = client.post(
        reverse("clases:plano_guardar", args=[grupo.pk, "referencia"]),
        data=json.dumps({"disposicion": _disp(_mesa([alumnos[2].pk])), "motivo": "prueba"}),
        content_type="application/json",
    )
    assert r.status_code == 200, r.content
    assert r.json()["versiones"][0]["motivo"] == "prueba"
    assert PlanoVersion.objects.get().origen == PlanoVersion.PANTALLA


def test_guardar_invalido_da_422(client, profesor, grupo, alumnos):
    client.force_login(profesor)
    r = client.post(
        reverse("clases:plano_guardar", args=[grupo.pk, "referencia"]),
        data=json.dumps({"disposicion": _disp(_mesa([alumnos[0].pk, alumnos[0].pk]))}),
        content_type="application/json",
    )
    assert r.status_code == 422
    assert r.json()["errores"]


# === C427 — la clase empieza por la lista ===


def test_la_clase_sin_lista_pasada_lo_dice(client, profesor, sesion):
    client.force_login(profesor)
    r = client.get(reverse("clases:class_session_present", args=[sesion.pk]))
    assert r.context["lista_pasada"] is False
    assert b'id="panel-lista"' in r.content
    assert b'id="fab-lista"' in r.content


def test_el_alumnado_no_ve_el_plano(client, sesion, alumnos):
    client.force_login(alumnos[0])
    r = client.get(reverse("clases:class_session_present", args=[sesion.pk]))
    assert r.status_code == 200
    assert b'id="panel-lista"' not in r.content
    assert b'id="fab-lista"' not in r.content


def test_en_clase_se_pueden_cambiar_sitios(client, profesor, sesion):
    """Fase 71: el editor del plano dentro de la clase, con las URL del grupo."""
    client.force_login(profesor)
    r = client.get(reverse("clases:class_session_present", args=[sesion.pk]))
    html = r.content.decode()
    assert 'data-modo="editar"' in html
    assert 'id="lista-edicion"' in html
    assert "clases/plano_edicion.js" in html
    grupo = sesion.group_id
    assert reverse("clases:plano_guardar", args=[grupo, "AULA"]) in html
    assert reverse("clases:plano_restaurar", args=[grupo, "AULA", 0]) in html


def test_el_alumnado_no_ve_cambiar_sitios(client, sesion, alumnos):
    client.force_login(alumnos[0])
    html = client.get(reverse("clases:class_session_present", args=[sesion.pk])).content.decode()
    assert 'data-modo="editar"' not in html
    assert 'id="lista-edicion"' not in html


def test_el_alumnado_no_puede_leer_la_lista(client, sesion, alumnos):
    client.force_login(alumnos[0])
    assert client.get(reverse("clases:lista_datos", args=[sesion.pk])).status_code in (302, 403, 404)


def test_dar_por_pasada(client, profesor, sesion):
    client.force_login(profesor)
    assert client.post(reverse("clases:lista_pasada", args=[sesion.pk])).status_code == 200
    r = client.get(reverse("clases:class_session_present", args=[sesion.pk]))
    assert r.context["lista_pasada"] is True


def test_el_aula_por_defecto_es_la_ultima_usada(profesor, grupo, sesion):
    pase = planos.pase_de(sesion)
    assert pase.aula == "referencia"
    pase.aula = "musica"
    pase.save()
    otra = ClassSession.objects.create(teacher=profesor, group=grupo, date=date(2026, 10, 8), title="Otra")
    assert planos.pase_de(otra).aula == "musica"


def test_cambiar_de_aula_en_la_lista(client, profesor, sesion, alumnos):
    client.force_login(profesor)
    r = client.get(reverse("clases:lista_datos", args=[sesion.pk]) + "?aula=musica")
    assert r.json()["aula"] == "musica"
    assert PaseDeLista.objects.get(session=sesion).aula == "musica"


# === C429 — marcar ===


def _marcar(client, sesion, **cuerpo):
    return client.post(
        reverse("clases:lista_marcar", args=[sesion.pk]),
        data=json.dumps(cuerpo), content_type="application/json",
    )


def test_marcar_falta_retraso_material_y_nota(client, profesor, sesion, alumnos):
    client.force_login(profesor)
    ana = alumnos[0].pk
    assert _marcar(client, sesion, alumno=ana, estado="retraso").json()["asistencia"]["hora"]
    _marcar(client, sesion, alumno=ana, sin_material=["libreta", "ukelele"])
    r = _marcar(client, sesion, alumno=ana, nota="  Llega sin justificante ")
    fila = Asistencia.objects.get(session=sesion, alumno_id=ana)
    assert fila.estado == "retraso" and fila.hora_llegada is not None
    assert fila.sin_material == ["ukelele", "libreta"]
    assert fila.nota == "Llega sin justificante"
    assert r.json()["asistencia"]["estado"] == "retraso"


def test_volver_a_presente_sin_nada_borra_la_fila(client, profesor, sesion, alumnos):
    client.force_login(profesor)
    _marcar(client, sesion, alumno=alumnos[0].pk, estado="falta")
    r = _marcar(client, sesion, alumno=alumnos[0].pk, estado="presente")
    assert r.json()["asistencia"] is None
    assert not Asistencia.objects.exists()


def test_falta_borra_la_hora_del_retraso(sesion, alumnos):
    planos.marcar(sesion, alumnos[0].pk, estado="retraso")
    fila = planos.marcar(sesion, alumnos[0].pk, estado="falta")
    assert fila.hora_llegada is None


def test_no_se_marca_a_quien_no_es_del_grupo(client, profesor, sesion, alumnos):
    client.force_login(profesor)
    assert _marcar(client, sesion, alumno=UserFactory().pk, estado="falta").status_code == 422
    assert _marcar(client, sesion, alumno=alumnos[0].pk, sin_material=["flauta"]).status_code == 422


# === C430 — resumen para SIGAD ===


def test_resumen_sigad(sesion, alumnos):
    planos.marcar(sesion, alumnos[1].pk, estado="falta")
    fila = planos.marcar(sesion, alumnos[0].pk, estado="retraso")
    planos.marcar(sesion, alumnos[2].pk, sin_material=["ukelele"])
    texto = planos.resumen_sigad(sesion)
    hora = fila.hora_llegada.strftime("%H:%M")
    assert texto == f"3-EG-BIL · 07/10/2026\nFaltas: BRUNO SANZ ROS\nRetrasos: ANA PEREZ GIL ({hora})"


def test_resumen_sin_incidencias(sesion):
    assert planos.resumen_sigad(sesion).endswith("Faltas: ninguna\nRetrasos: ninguno")


# === C431 — Evaluar al azar salta a quien falta ===


def test_al_azar_no_elige_a_quien_falta(client, profesor, sesion, alumnos, monkeypatch):
    from calificaciones import evaluar

    item = ClassSessionItem(session=sesion, order=0)
    item.pk = 1
    capturado = {}

    def falso_al_azar(group, instrumento, excluir=(), azar=None):
        capturado["excluir"] = set(int(x) for x in excluir)

    monkeypatch.setattr("clases.views_evaluar._elemento", lambda request, pk: (item, sesion.group))
    monkeypatch.setattr("clases.views_evaluar._instrumento_de", lambda item, group: None)
    monkeypatch.setattr(evaluar, "al_azar", falso_al_azar)
    monkeypatch.setattr(evaluar, "sin_nota", lambda group, instrumento: [])
    planos.marcar(sesion, alumnos[1].pk, estado="falta")
    planos.marcar(sesion, alumnos[0].pk, estado="retraso")
    client.force_login(profesor)
    client.get(reverse("clases:evaluar_azar", args=[1]) + "?excluir=" + str(alumnos[2].pk))
    assert capturado["excluir"] == {alumnos[1].pk, alumnos[2].pk}


# === C432 — API ===


@pytest.fixture
def clave(profesor):
    return str(APIKey.objects.create(user=profesor, name="illa").key)


def _api(client, metodo, ruta, clave, **kw):
    return getattr(client, metodo)(
        "/api/clases" + ruta, HTTP_X_API_KEY=clave, content_type="application/json", **kw
    )


def test_api_lista_mis_grupos(client, grupo, alumnos, clave):
    _grupo("1-G-BIL", UserFactory())
    r = _api(client, "get", "/grupos", clave)
    assert r.status_code == 200
    assert [g["nombre"] for g in r.json()] == ["3-EG-BIL"]
    assert r.json()[0]["alumnado"] == 3


def test_api_escribe_con_motivo_y_deja_version(client, grupo, alumnos, clave):
    cuerpo = {"disposicion": _disp(_mesa([alumnos[0].pk, alumnos[1].pk])), "motivo": "Separar a A de C"}
    r = _api(client, "put", f"/grupos/{grupo.pk}/planos/musica", clave, data=json.dumps(cuerpo))
    assert r.status_code == 200, r.content
    version = PlanoVersion.objects.get()
    assert (version.origen, version.motivo) == (PlanoVersion.API, "Separar a A de C")
    assert r.json()["sin_sitio"] == [alumnos[2].pk]


def test_api_sin_motivo_no_escribe(client, grupo, alumnos, clave):
    cuerpo = {"disposicion": _disp(_mesa([alumnos[0].pk])), "motivo": "  "}
    r = _api(client, "put", f"/grupos/{grupo.pk}/planos/musica", clave, data=json.dumps(cuerpo))
    assert r.status_code == 422
    assert not PlanoVersion.objects.exists()


def test_api_invalido_da_422(client, grupo, alumnos, clave):
    cuerpo = {"disposicion": _disp(_mesa([UserFactory().pk])), "motivo": "x"}
    r = _api(client, "put", f"/grupos/{grupo.pk}/planos/musica", clave, data=json.dumps(cuerpo))
    assert r.status_code == 422


def test_api_grupo_ajeno_da_404(client, clave):
    ajeno = _grupo("4-AC-BIL", UserFactory())
    assert _api(client, "get", f"/grupos/{ajeno.pk}/planos/musica", clave).status_code == 404
    assert _api(client, "get", f"/grupos/{ajeno.pk}/asistencia", clave).status_code == 404


def test_api_sin_clave_da_401(client, grupo):
    assert client.get(f"/api/clases/grupos/{grupo.pk}/planos/musica").status_code == 401


def test_api_asistencia_y_sesiones(client, grupo, sesion, alumnos, clave):
    planos.marcar(sesion, alumnos[1].pk, estado="falta", nota="Enfermo")
    sesion.reflection = "Ha ido bien"
    sesion.save()
    SessionNote.objects.create(session=sesion, estado=SessionNote.TRANSCRITA, transcripcion="Bruno distraído")
    SessionNote.objects.create(session=sesion)  # pendiente: no sale
    r = _api(client, "get", f"/grupos/{grupo.pk}/asistencia?desde=2026-10-01", clave).json()
    assert r[0]["marcas"] == [
        {"alumno": alumnos[1].pk, "nombre": "BRUNO SANZ ROS", "estado": "falta", "hora": "", "sin_material": [], "nota": "Enfermo"}
    ]
    s = _api(client, "get", f"/grupos/{grupo.pk}/sesiones?hasta=2026-10-31", clave).json()
    assert s[0]["reflexion"] == "Ha ido bien"
    assert [n["transcripcion"] for n in s[0]["notas"]] == ["Bruno distraído"]
    assert _api(client, "get", f"/grupos/{grupo.pk}/sesiones?desde=2026-11-01", clave).json() == []


# === Revisión independiente (2026-10-07) ===


def test_una_baja_no_bloquea_el_siguiente_guardado(client, profesor, grupo, alumnos):
    plano = planos.plano_de(grupo, "referencia")
    planos.guardar(plano, _disp(_mesa([alumnos[0].pk, alumnos[1].pk])))
    Enrollment.objects.filter(user=alumnos[1]).update(is_active=False)
    client.force_login(profesor)
    servido = client.get(reverse("clases:plano_datos", args=[grupo.pk, "referencia"])).json()
    assert servido["disposicion"]["mesas"][0]["ocupantes"] == [alumnos[0].pk, None]
    r = client.post(
        reverse("clases:plano_guardar", args=[grupo.pk, "referencia"]),
        data=json.dumps({"disposicion": servido["disposicion"]}), content_type="application/json",
    )
    assert r.status_code == 200, r.content


def test_cotitular_no_pasa_lista_en_la_sesion_de_otro(client, grupo, sesion, alumnos):
    cotitular = UserFactory()
    grupo.teachers.add(cotitular)
    client.force_login(cotitular)
    assert client.get(reverse("clases:lista_datos", args=[sesion.pk])).status_code == 404
    assert _marcar(client, sesion, alumno=alumnos[0].pk, estado="falta").status_code == 404
    assert not Asistencia.objects.exists()


def test_api_no_ensena_sesiones_de_otro_profesor(client, grupo, alumnos, clave):
    otro = UserFactory()
    grupo.teachers.add(otro)
    ClassSession.objects.create(teacher=otro, group=grupo, date=date(2026, 10, 7), title="Suya", reflection="privada")
    assert _api(client, "get", f"/grupos/{grupo.pk}/sesiones", clave).json() == []
    assert _api(client, "get", f"/grupos/{grupo.pk}/asistencia", clave).json() == []


def test_api_grupos_solo_los_mios_aunque_sea_staff(client, profesor, grupo, clave):
    profesor.is_staff = True
    profesor.save()
    _grupo("1-G-BIL", UserFactory())
    assert [g["nombre"] for g in _api(client, "get", "/grupos", clave).json()] == ["3-EG-BIL"]


@pytest.mark.parametrize(
    "disposicion",
    [
        {"referencia": [1, 2], "mesas": []},
        {"referencia": "x", "mesas": []},
        {"mesas": [{"plazas": 2, "ocupantes": 5}]},
        {"mesas": [{"plazas": 2, "ocupantes": True}]},
    ],
)
def test_api_formas_malas_dan_422_y_no_500(client, grupo, alumnos, clave, disposicion):
    cuerpo = {"disposicion": disposicion, "motivo": "x"}
    r = _api(client, "put", f"/grupos/{grupo.pk}/planos/musica", clave, data=json.dumps(cuerpo))
    assert r.status_code == 422, r.content


@pytest.mark.parametrize(
    "cuerpo",
    [{"estado": ["falta"]}, {"estado": {"a": 1}}, {"sin_material": 5}, {"sin_material": [1]}, {"nota": 3}],
)
def test_marcar_con_formas_malas_da_422_y_no_deja_fila(client, profesor, sesion, alumnos, cuerpo):
    client.force_login(profesor)
    assert _marcar(client, sesion, alumno=alumnos[0].pk, **cuerpo).status_code == 422
    assert not Asistencia.objects.exists()
