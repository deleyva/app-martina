# ruff: noqa: E501, PLR2004, S106
"""La API de lectura de incidencias.

Lo que importa aquí no es que devuelva 200: es que una clave de API que no sea
de un técnico NO vea las incidencias privadas, y que los filtros devuelvan
exactamente lo que dicen.
"""

import json

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


# --- Escritura -------------------------------------------------------------------

from unittest.mock import patch  # noqa: E402

from incidencias.models import Derivacion  # noqa: E402
from incidencias.models import HistorialAsignacion  # noqa: E402
from incidencias.tests.factories import DerivacionFactory  # noqa: E402
from incidencias.tests.factories import ServicioFactory  # noqa: E402


def _post(client, path, clave, datos=None):
    return client.post(
        f"{BASE}{path}",
        data=json.dumps(datos or {}),
        content_type="application/json",
        HTTP_X_API_KEY=str(clave.key),
    )


def _patch(client, path, clave, datos):
    return client.patch(
        f"{BASE}{path}",
        data=json.dumps(datos),
        content_type="application/json",
        HTTP_X_API_KEY=str(clave.key),
    )


@pytest.fixture
def servicio(db):
    # slug propio: la semilla (0007) ya crea «hardware-software-4100» en la base de test
    return ServicioFactory(slug="servicio-de-prueba", nombre="Servicio de prueba")


@pytest.mark.django_db
def test_clave_de_profe_no_puede_escribir(client, clave_profe, servicio, tecnico):
    inc = IncidenciaFactory(estado="pendiente", titulo="Intacta")
    d = DerivacionFactory(incidencia=inc, servicio=servicio, asunto="Asunto intacto")
    intentos = [
        _post(client, f"{inc.id}/asignar", clave_profe, {"tecnico": "tecnica"}),
        _post(client, f"{inc.id}/comentar", clave_profe, {"texto": "hola"}),
        _post(client, f"{inc.id}/estado", clave_profe, {"estado": "resuelta"}),
        _patch(client, f"{inc.id}", clave_profe, {"ambito": "gestion"}),
        _post(client, f"{inc.id}/derivar", clave_profe, {"servicio": servicio.slug}),
        _patch(client, f"derivaciones/{d.id}", clave_profe, {"asunto": "cambiado"}),
        _post(client, f"derivaciones/{d.id}/enviada", clave_profe),
        _post(client, f"derivaciones/{d.id}/respuesta", clave_profe, {"texto": "r"}),
        _post(client, f"derivaciones/{d.id}/cerrar", clave_profe, {"resultado": "duplicada"}),
    ]
    assert [r.status_code for r in intentos] == [403] * 9
    inc.refresh_from_db()
    d.refresh_from_db()
    assert inc.estado == "pendiente"
    assert inc.asignado_a is None
    assert inc.ambito == "informatica"
    assert inc.comentarios.count() == 0
    assert d.estado == "borrador"
    assert d.asunto == "Asunto intacto"
    assert Derivacion.objects.count() == 1


@pytest.mark.django_db
def test_asignar_por_api_crea_historial_igual_que_la_vista(client, tecnico, clave_tecnico):
    otro = TecnicoFactory(user__email="secretaria@iesmartinabescos.es", nombre_display="secretaria")
    inc = IncidenciaFactory()

    r = _post(client, f"{inc.id}/asignar", clave_tecnico, {"tecnico": "secretaria"})
    assert r.status_code == 200, r.content
    assert r.json()["asignado_a"]["usuario"] == "secretaria"
    h = HistorialAsignacion.objects.get(incidencia=inc)
    assert (h.asignado_por, h.asignado_a, h.nota) == (tecnico, otro, "Asignada a secretaria")

    r = _post(client, f"{inc.id}/asignar", clave_tecnico, {"tecnico": None})
    assert r.json()["asignado_a"] is None
    assert HistorialAsignacion.objects.filter(incidencia=inc).count() == 2
    assert HistorialAsignacion.objects.filter(incidencia=inc).order_by("-id").first().nota.startswith("Desasignada")

    assert _post(client, f"{inc.id}/asignar", clave_tecnico, {"tecnico": "nadie"}).status_code == 404


@pytest.mark.django_db
def test_estado_por_api_notifica_una_vez(client, clave_tecnico):
    inc = IncidenciaFactory(estado="pendiente")
    with patch("incidencias.services.acciones.IncidenciaNotificationService.notify_estado_changed") as notify:
        assert _post(client, f"{inc.id}/estado", clave_tecnico, {"estado": "resuelta"}).status_code == 200
        assert _post(client, f"{inc.id}/estado", clave_tecnico, {"estado": "resuelta"}).status_code == 200
    notify.assert_called_once_with(inc.pk, "pendiente", "resuelta")
    assert _post(client, f"{inc.id}/estado", clave_tecnico, {"estado": "volando"}).status_code == 422


@pytest.mark.django_db
def test_comentar_por_api_notifica_y_autor_por_defecto_es_la_clave(client, clave_tecnico):
    inc = IncidenciaFactory()
    with patch("incidencias.services.acciones.IncidenciaNotificationService.notify_new_comment") as notify:
        r = _post(client, f"{inc.id}/comentar", clave_tecnico, {"texto": "Repartida por Illa"})
    assert r.status_code == 200
    c = inc.comentarios.get()
    assert (c.autor_nombre, c.texto) == ("tecnica", "Repartida por Illa")
    notify.assert_called_once_with(inc.pk, c.pk)
    assert _post(client, f"{inc.id}/comentar", clave_tecnico, {"texto": "   "}).status_code == 422


@pytest.mark.django_db
def test_patch_solo_toca_lo_enviado(client, clave_tecnico):
    aula = UbicacionFactory(nombre="Aula 9", planta="P1")
    wifi = EtiquetaFactory(nombre="WiFi", slug="wifi")
    inc = IncidenciaFactory(urgencia="alta", ubicacion=aula, etiquetas=[wifi], es_privada=True)

    r = _patch(client, f"{inc.id}", clave_tecnico, {"ambito": "mantenimiento"})
    assert r.status_code == 200, r.content
    inc.refresh_from_db()
    assert inc.ambito == "mantenimiento"
    assert inc.urgencia == "alta"
    assert inc.ubicacion == aula
    assert inc.es_privada is True
    assert list(inc.etiquetas.all()) == [wifi]

    r = _patch(client, f"{inc.id}", clave_tecnico, {"ubicacion_id": None, "etiquetas": [], "es_privada": False})
    inc.refresh_from_db()
    assert inc.ubicacion is None
    assert inc.etiquetas.count() == 0
    assert inc.es_privada is False
    assert _patch(client, f"{inc.id}", clave_tecnico, {"ambito": "cosmos"}).status_code == 422
    assert _patch(client, f"{inc.id}", clave_tecnico, {"ubicacion_id": 999999}).status_code == 404


@pytest.mark.django_db
def test_patch_etiqueta_desconocida_422(client, clave_tecnico):
    EtiquetaFactory(nombre="WiFi", slug="wifi")
    inc = IncidenciaFactory()
    r = _patch(client, f"{inc.id}", clave_tecnico, {"etiquetas": ["wifi", "no-existe"]})
    assert r.status_code == 422
    assert "no-existe" in r.json()["detail"]
    assert inc.etiquetas.count() == 0


@pytest.mark.django_db
def test_derivar_devuelve_asunto_y_cuerpo_generados(client, tecnico, clave_tecnico, servicio):
    aula = UbicacionFactory(nombre="Aula N6", planta="PB")
    inc = IncidenciaFactory(titulo="Cable HDMI roto", ubicacion=aula, estado="pendiente")
    r = _post(client, f"{inc.id}/derivar", clave_tecnico, {"servicio": servicio.slug})
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["asunto"] == f"[INC-{inc.id}] Aula N6 — Cable HDMI roto"
    assert servicio.url_publica in d["cuerpo"]
    assert d["texto_correo"] == f"{d['asunto']}\n\n{d['cuerpo']}"
    assert d["estado"] == "borrador"
    assert d["creada_por"] == "Técnica"
    inc.refresh_from_db()
    assert inc.estado == "en_progreso"
    assert _post(client, f"{inc.id}/derivar", clave_tecnico, {"servicio": "inventado"}).status_code == 404

    r = _post(client, f"{inc.id}/derivar", clave_tecnico, {"servicio": servicio.slug, "cuerpo": "Mi propio cuerpo"})
    assert r.json()["cuerpo"] == "Mi propio cuerpo"


@pytest.mark.django_db
def test_transicion_ilegal_409(client, tecnico, clave_tecnico, servicio):
    d = DerivacionFactory(servicio=servicio)
    assert _post(client, f"derivaciones/{d.id}/respuesta", clave_tecnico, {"texto": "aún no"}).status_code == 409
    r = _post(client, f"derivaciones/{d.id}/enviada", clave_tecnico)
    assert r.status_code == 200
    assert r.json()["estado"] == "enviada"
    assert r.json()["enviada_por"] == "Técnica"
    assert _post(client, f"derivaciones/{d.id}/enviada", clave_tecnico).status_code == 409
    assert _patch(client, f"derivaciones/{d.id}", clave_tecnico, {"cuerpo": "tarde"}).status_code == 409
    r = _patch(client, f"derivaciones/{d.id}", clave_tecnico, {"ticket_externo": "T-7"})
    assert r.status_code == 200
    assert r.json()["ticket_externo"] == "T-7"
    r = _post(client, f"derivaciones/{d.id}/respuesta", clave_tecnico, {"texto": "Vienen el lunes", "canal": "telefono"})
    assert r.json()["estado"] == "respondida"
    assert [c["sentido"] for c in r.json()["comunicaciones"]] == ["enviada", "recibida"]
    assert _post(client, f"derivaciones/{d.id}/respuesta", clave_tecnico, {"texto": "x", "canal": "paloma"}).status_code == 422
    r = _post(client, f"derivaciones/{d.id}/cerrar", clave_tecnico, {"resultado": "resuelta", "nota": "Hecho"})
    assert r.json()["estado"] == "cerrada"
    assert r.json()["resultado"] == "resuelta"
    assert _post(client, f"derivaciones/{d.id}/cerrar", clave_tecnico, {"resultado": "resuelta"}).status_code == 409


@pytest.mark.django_db
def test_servicios_incluye_url_publica(client, tecnico, clave_tecnico, servicio):
    inactivo = ServicioFactory(slug="muerto", activo=False)
    d = DerivacionFactory(servicio=servicio)
    d.marcar_enviada(tecnico)
    r = _get(client, "servicios", clave_tecnico)
    assert r.status_code == 200
    por_slug = {s["slug"]: s for s in r.json()}
    assert por_slug[servicio.slug]["url_publica"] == servicio.url_publica
    assert por_slug[servicio.slug]["abiertas"] == 1
    assert por_slug[servicio.slug]["correos"] == ["uno@example.com", "dos@example.com"]
    assert inactivo.slug in por_slug
    activos = [s["slug"] for s in _get(client, "servicios", clave_tecnico, activos="true").json()]
    assert servicio.slug in activos
    assert inactivo.slug not in activos


@pytest.mark.django_db
def test_lista_trae_ambito_y_derivaciones(client, tecnico, clave_tecnico, servicio):
    inc = IncidenciaFactory(ambito="mantenimiento")
    abierta = DerivacionFactory(incidencia=inc, servicio=servicio)
    cerrada = DerivacionFactory(incidencia=inc, servicio=servicio)
    cerrada.cerrar(resultado="duplicada")

    item = _get(client, "", clave_tecnico).json()["items"][0]
    assert item["ambito"] == "mantenimiento"
    assert [d["id"] for d in item["derivaciones"]] == [abierta.id]
    assert item["derivaciones"][0]["servicio"] == servicio.slug

    todas = _get(client, "derivaciones", clave_tecnico, incidencia=inc.id).json()
    assert {d["id"] for d in todas} == {abierta.id, cerrada.id}
    abiertas = _get(client, "derivaciones", clave_tecnico, estado="abiertas", servicio=servicio.slug).json()
    assert [d["id"] for d in abiertas] == [abierta.id]
    assert _get(client, f"derivaciones/{abierta.id}", clave_tecnico).json()["incidencia_id"] == inc.id
