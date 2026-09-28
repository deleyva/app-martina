# ruff: noqa: E501, PLR2004, S106
"""La API de lectura de incidencias.

Lo que importa aquí no es que devuelva 200: es que una clave de API que no sea
de un técnico NO vea las incidencias privadas, y que los filtros devuelvan
exactamente lo que dicen.
"""

import pytest
from django.contrib.auth import get_user_model

from api_keys.models import APIKey

from incidencias.models import Incidencia
from .factories import ComentarioFactory
from .factories import EtiquetaFactory
from .factories import HistorialAsignacionFactory
from .factories import IncidenciaFactory
from .factories import ProcessedEmailFactory
from .factories import TecnicoFactory
from .factories import UbicacionFactory

User = get_user_model()
BASE = "/api/incidencias/"


@pytest.fixture
def tecnico(db):
    return TecnicoFactory(
        user__email="tecnica@iesmartinabescos.es", nombre_display="Técnica",
    )


@pytest.fixture
def clave_tecnico(tecnico):
    return APIKey.objects.create(name="skill", user=tecnico.user)


@pytest.fixture
def clave_profe(db):
    profe = User.objects.create_user(email="profe@iesmartinabescos.es", password="x")
    return APIKey.objects.create(name="profe", user=profe)


def _get(client, path, clave, **params):
    return client.get(f"{BASE}{path}", params, HTTP_X_API_KEY=str(clave.key))


# --- Permisos -----------------------------------------------------------------


@pytest.mark.django_db
def test_sin_clave_es_401(client):
    assert client.get(BASE).status_code == 401


@pytest.mark.django_db
def test_una_clave_que_no_es_de_tecnico_no_ve_nada(client, clave_profe):
    IncidenciaFactory(es_privada=True, titulo="Secreto")
    r = _get(client, "", clave_profe)
    assert r.status_code == 403
    assert "Secreto" not in r.content.decode()
    assert _get(client, "resumen", clave_profe).status_code == 403
    assert _get(client, "tecnicos", clave_profe).status_code == 403


@pytest.mark.django_db
def test_un_tecnico_dado_de_baja_tampoco(client, tecnico, clave_tecnico):
    tecnico.activo = False
    tecnico.save()
    assert _get(client, "", clave_tecnico).status_code == 403


@pytest.mark.django_db
def test_un_superusuario_sin_perfil_entra(client):
    admin = User.objects.create_superuser(
        email="admin@iesmartinabescos.es", password="x",
    )
    clave = APIKey.objects.create(name="admin", user=admin)
    assert _get(client, "", clave).status_code == 200


# --- Lista y filtros ------------------------------------------------------------


@pytest.mark.django_db
def test_la_lista_trae_privadas_y_lo_que_hace_falta_para_repartir(
    client, tecnico, clave_tecnico,
):
    etiqueta = EtiquetaFactory(nombre="Proyectar", slug="proyectar")
    aula = UbicacionFactory(nombre="Aula N6", planta="PB")
    inc = IncidenciaFactory(
        titulo="Cable HDMI roto",
        es_privada=True,
        urgencia="alta",
        ubicacion=aula,
        asignado_a=tecnico,
        etiquetas=[etiqueta],
    )
    ComentarioFactory(incidencia=inc)
    ComentarioFactory(incidencia=inc)

    r = _get(client, "", clave_tecnico)
    assert r.status_code == 200
    datos = r.json()
    assert datos["total"] == 1
    item = datos["items"][0]
    assert item["titulo"] == "Cable HDMI roto"
    assert item["es_privada"] is True
    assert item["urgencia"] == "alta"
    assert item["ubicacion"]["nombre"] == "Aula N6"
    assert item["ubicacion"]["planta_nombre"] == "Planta Baja"
    assert [e["slug"] for e in item["etiquetas"]] == ["proyectar"]
    assert item["asignado_a"]["usuario"] == "tecnica"
    assert item["asignado_a"]["abiertas"] == 1
    assert item["n_comentarios"] == 2
    assert item["url"].endswith(f"/incidencias/{inc.id}/")


@pytest.mark.django_db
def test_los_filtros_devuelven_exactamente_lo_que_dicen(client, tecnico, clave_tecnico):
    otro = TecnicoFactory(user__email="otro@iesmartinabescos.es")
    pb = UbicacionFactory(nombre="Aula 1", planta="PB")
    p2 = UbicacionFactory(nombre="Aula 2", planta="P2")
    wifi = EtiquetaFactory(nombre="WiFi", slug="wifi")
    pendiente = IncidenciaFactory(
        estado="pendiente",
        ubicacion=pb,
        asignado_a=tecnico,
        etiquetas=[wifi],
        titulo="Sin wifi en el aula",
    )
    progreso = IncidenciaFactory(
        estado="en_progreso", ubicacion=p2, asignado_a=None, urgencia="alta",
    )
    resuelta = IncidenciaFactory(estado="resuelta", ubicacion=None, asignado_a=otro)

    def ids(**params):
        r = _get(client, "", clave_tecnico, **params)
        assert r.status_code == 200, r.content
        return sorted(i["id"] for i in r.json()["items"])

    assert ids() == sorted([pendiente.id, progreso.id, resuelta.id])
    assert ids(estado="abiertas") == sorted([pendiente.id, progreso.id])
    assert ids(estado="pendiente,resuelta") == sorted([pendiente.id, resuelta.id])
    assert ids(urgencia="alta") == [progreso.id]
    assert ids(tecnico="sin_asignar") == [progreso.id]
    assert ids(tecnico=str(tecnico.id)) == [pendiente.id]
    assert ids(tecnico="otro") == [resuelta.id]
    assert ids(etiqueta="wifi") == [pendiente.id]
    assert ids(planta="P2") == [progreso.id]
    assert ids(ubicacion=pb.id) == [pendiente.id]
    assert ids(sin_ubicacion="true") == [resuelta.id]
    assert ids(q="WIFI") == [pendiente.id]


@pytest.mark.django_db
def test_fechas_y_paginacion(client, clave_tecnico):
    incs = IncidenciaFactory.create_batch(5)
    Incidencia.objects.filter(pk=incs[0].pk).update(created_at="2026-02-01T10:00:00Z")

    r = _get(client, "", clave_tecnico, desde="2026-03-01")
    assert r.json()["total"] == 4
    r = _get(client, "", clave_tecnico, hasta="2026-02-28")
    assert [i["id"] for i in r.json()["items"]] == [incs[0].id]

    r = _get(client, "", clave_tecnico, limit=2, page=2, orden="created_at")
    datos = r.json()
    assert datos["total"] == 5
    assert datos["page"] == 2
    assert len(datos["items"]) == 2

    assert _get(client, "", clave_tecnico, orden="titulo").status_code == 422


# --- Detalle ---------------------------------------------------------------------


@pytest.mark.django_db
def test_el_detalle_trae_la_conversacion_entera(client, tecnico, clave_tecnico):
    inc = IncidenciaFactory(descripcion="El cable no llega")
    ComentarioFactory(
        incidencia=inc, autor_nombre="secretaria", texto="Enviado al 4100",
    )
    HistorialAsignacionFactory(
        incidencia=inc, asignado_por=tecnico, asignado_a=tecnico, nota="Me la quedo",
    )
    ProcessedEmailFactory(
        incidencia=inc, raw_subject="Fwd: cable", raw_sender="profe@iesmartinabescos.es",
    )

    r = _get(client, str(inc.id), clave_tecnico)
    assert r.status_code == 200
    d = r.json()
    assert d["descripcion"] == "El cable no llega"
    assert [c["autor"] for c in d["comentarios"]] == ["secretaria"]
    assert d["comentarios"][0]["texto"] == "Enviado al 4100"
    assert d["historial_asignaciones"][0]["nota"] == "Me la quedo"
    assert d["historial_asignaciones"][0]["asignado_a"] == "Técnica"
    assert d["emails_origen"][0]["asunto"] == "Fwd: cable"

    assert _get(client, "999999", clave_tecnico).status_code == 404


# --- Catálogos y resumen -----------------------------------------------------------


@pytest.mark.django_db
def test_tecnicos_etiquetas_ubicaciones(client, tecnico, clave_tecnico):
    TecnicoFactory(user__email="baja@iesmartinabescos.es", activo=False)
    IncidenciaFactory(asignado_a=tecnico, estado="pendiente")
    IncidenciaFactory(asignado_a=tecnico, estado="resuelta")
    EtiquetaFactory(nombre="Ratón", slug="raton")
    UbicacionFactory(nombre="Aula 9", planta="P1")

    tecnicos = _get(client, "tecnicos", clave_tecnico).json()
    por_usuario = {t["usuario"]: t for t in tecnicos}
    assert por_usuario["tecnica"]["abiertas"] == 1
    assert por_usuario["baja"]["activo"] is False
    assert [
        t["usuario"]
        for t in _get(client, "tecnicos", clave_tecnico, activos="true").json()
    ] == ["tecnica"]

    assert {e["slug"] for e in _get(client, "etiquetas", clave_tecnico).json()} >= {
        "raton",
    }
    assert {u["nombre"] for u in _get(client, "ubicaciones", clave_tecnico).json()} >= {
        "Aula 9",
    }


@pytest.mark.django_db
def test_el_resumen_cuenta_bien_y_senala_los_huecos(client, tecnico, clave_tecnico):
    IncidenciaFactory(estado="pendiente", asignado_a=None, ubicacion=None)
    IncidenciaFactory(estado="en_progreso", asignado_a=tecnico, urgencia="alta")
    IncidenciaFactory(estado="resuelta", asignado_a=None, ubicacion=None)

    r = _get(client, "resumen", clave_tecnico)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 3
    assert d["abiertas"] == 2
    assert {x["clave"]: x["n"] for x in d["por_estado"]} == {
        "pendiente": 1,
        "en_progreso": 1,
        "resuelta": 1,
    }
    assert d["abiertas_sin_asignar"] == 1
    assert d["abiertas_sin_ubicacion"] == 1
    assert {x["nombre"]: x["n"] for x in d["por_tecnico"]} == {
        "Sin asignar": 1,
        "Técnica": 1,
    }
    assert d["abierta_mas_antigua"] is not None
