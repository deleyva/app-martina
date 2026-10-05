# ruff: noqa: E501, PLR2004
"""Oficios (modo «visita»): se apuntan en su lista, se les llama y se cierran sin correo (fase 65)."""

import pytest
from api_keys.models import APIKey
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from incidencias.models import Comunicacion
from incidencias.models import Derivacion
from incidencias.models import Servicio
from incidencias.models import TransicionInvalida
from incidencias.services import acciones
from incidencias.tests.factories import DerivacionFactory
from incidencias.tests.factories import IncidenciaFactory
from incidencias.tests.factories import ServicioFactory
from incidencias.tests.factories import TecnicoFactory
from incidencias.tests.factories import UbicacionFactory

User = get_user_model()
BASE = "/api/incidencias/"


@pytest.fixture
def tecnico(db):
    return TecnicoFactory(user__email="secretaria@iesmartinabescos.es", nombre_display="Secretaría")


@pytest.fixture
def tecnico_client(tecnico):
    c = Client()
    c.force_login(tecnico.user)
    return c


@pytest.fixture
def oficio(db):
    return ServicioFactory(slug="fontaneria", nombre="Fontanería", modo=Servicio.Modo.VISITA, correos="")


@pytest.fixture
def correo(db):
    return ServicioFactory(slug="hardware-software-4100", nombre="Hardware y software (4100)")


# --- Modelo --------------------------------------------------------------------


@pytest.mark.django_db
def test_modo_por_defecto_es_correo():
    assert Servicio(nombre="Nuevo").modo == Servicio.Modo.CORREO
    # Los nueve de la semilla de la fase 56 siguen en correo; los dos oficios sembrados, en visita.
    assert set(Servicio.objects.filter(modo="visita").values_list("slug", flat=True)) >= {"electricista", "carpinteria-y-ventanas"}
    assert not Servicio.objects.filter(slug="hardware-software-4100", modo="visita").exists()


@pytest.mark.django_db
def test_derivar_a_oficio_no_redacta_correo_y_queda_en_la_lista(oficio, correo, tecnico):
    inc = IncidenciaFactory(titulo="Enchufe suelto", ubicacion=UbicacionFactory(nombre="Aula N3", planta="P1"))
    d_oficio = acciones.derivar(inc, oficio, tecnico)
    d_correo = acciones.derivar(inc, correo, tecnico)
    assert d_oficio.cuerpo == ""
    assert d_oficio.estado_texto == "En la lista"
    assert d_correo.cuerpo.startswith("Buenos días")
    assert d_correo.estado_texto == "Borrador"


@pytest.mark.django_db
@pytest.mark.parametrize("resultado", ["resuelta", "sin_solucion", "duplicada"])
def test_oficio_se_cierra_desde_la_lista(oficio, resultado):
    d = DerivacionFactory(servicio=oficio)
    d.cerrar(resultado=resultado, autor="Secretaría", nota="Vino el martes")
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.CERRADA
    assert d.resultado == resultado


@pytest.mark.django_db
@pytest.mark.parametrize("resultado", ["resuelta", "sin_solucion"])
def test_correo_en_borrador_sigue_sin_poder_cerrarse(correo, resultado):
    d = DerivacionFactory(servicio=correo)
    with pytest.raises(TransicionInvalida):
        d.cerrar(resultado=resultado)


@pytest.mark.django_db
def test_avisar_a_oficio_deja_llamada_por_telefono(oficio, tecnico):
    d = DerivacionFactory(servicio=oficio, cuerpo="")
    c = d.marcar_enviada(tecnico)
    assert d.estado_texto == "Avisado"
    assert c.canal == Comunicacion.Canal.TELEFONO
    assert c.texto == f"Avisado para que venga: {d.asunto}"
    d.cerrar(resultado="resuelta")
    assert d.estado == Derivacion.Estado.CERRADA


@pytest.mark.django_db
def test_slug_sale_del_nombre_y_no_choca(db):
    a = Servicio.objects.create(nombre="Fontanería y calefacción")
    b = Servicio.objects.create(nombre="Fontanería y calefacción")
    assert a.slug == "fontaneria-y-calefaccion"
    assert b.slug == "fontaneria-y-calefaccion-2"
    assert a.token != b.token


# --- Vistas --------------------------------------------------------------------


@pytest.mark.django_db
def test_tecnico_da_de_alta_un_oficio_desde_el_panel(tecnico_client):
    r = tecnico_client.get(reverse("incidencias:panel_servicio_nuevo"))
    assert r.status_code == 200
    assert "{#" not in r.content.decode()
    r = tecnico_client.post(
        reverse("incidencias:panel_servicio_nuevo"),
        {"nombre": "Cerrajería", "modo": "visita", "telefono": "600 000 000", "activo": "on", "orden": 220},
    )
    assert r.status_code == 302
    s = Servicio.objects.get(slug="cerrajeria")
    assert s.es_por_visita
    assert s.telefono == "600 000 000"


@pytest.mark.django_db
def test_tecnico_edita_un_servicio(tecnico_client, oficio):
    r = tecnico_client.post(
        reverse("incidencias:panel_servicio_editar", args=[oficio.pk]),
        {"nombre": "Fontanería", "modo": "visita", "telefono": "976 111 222", "orden": 5},
    )
    assert r.status_code == 302
    oficio.refresh_from_db()
    assert oficio.telefono == "976 111 222"
    assert oficio.activo is False  # casilla sin marcar = baja
    assert oficio.slug == "fontaneria"  # editar no cambia el slug


@pytest.mark.django_db
def test_no_tecnico_no_crea_servicios(db):
    profe = User.objects.create_user(email="profe@iesmartinabescos.es", password="x")
    c = Client()
    c.force_login(profe)
    antes = Servicio.objects.count()
    r = c.post(reverse("incidencias:panel_servicio_nuevo"), {"nombre": "Intruso", "modo": "visita", "orden": 1})
    assert r.status_code in (302, 403)
    assert Servicio.objects.count() == antes
    anon = Client().post(reverse("incidencias:panel_servicio_nuevo"), {"nombre": "Intruso", "modo": "visita", "orden": 1})
    assert anon.status_code in (302, 403)
    assert Servicio.objects.count() == antes


@pytest.mark.django_db
def test_detalle_de_oficio_sin_correo_y_con_avisar(tecnico_client, oficio, tecnico):
    inc = IncidenciaFactory(titulo="Ventana que no cierra")
    d = acciones.derivar(inc, oficio, tecnico)
    html = tecnico_client.get(reverse("incidencias:detalle", args=[inc.pk])).content.decode()
    tarjeta = html.split(f'id="derivacion-{d.pk}"')[1]
    assert "Copiar correo" not in tarjeta
    assert "Marcar como avisado" in tarjeta
    assert "En la lista" in tarjeta
    assert "{#" not in html

    tecnico_client.post(reverse("incidencias:derivacion_enviada", args=[d.pk]))
    tecnico_client.post(reverse("incidencias:derivacion_cerrar", args=[d.pk]), {"resultado": "resuelta", "nota": "Arreglada"})
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.CERRADA


@pytest.mark.django_db
def test_detalle_de_correo_sigue_igual(tecnico_client, correo, tecnico):
    inc = IncidenciaFactory(titulo="Proyector")
    d = acciones.derivar(inc, correo, tecnico)
    html = tecnico_client.get(reverse("incidencias:detalle", args=[inc.pk])).content.decode()
    tarjeta = html.split(f'id="derivacion-{d.pk}"')[1]
    assert "Copiar correo" in tarjeta
    assert "Marcar como avisado" not in tarjeta


@pytest.mark.django_db
def test_pagina_publica_de_oficio_dice_en_la_lista_y_avisado(oficio, tecnico):
    privada = IncidenciaFactory(titulo="Persiana", descripcion="Lo cuenta un alumno", es_privada=True, reportero_nombre="Fulanito")
    publica = IncidenciaFactory(titulo="Enchufe", descripcion="Chispea al enchufar", reportero_nombre="Menganita")
    acciones.derivar(privada, oficio, tecnico)
    avisada = acciones.derivar(publica, oficio, tecnico)
    avisada.marcar_enviada(tecnico)
    html = Client().get(f"/incidencias/servicio/{oficio.token}/").content.decode()
    assert "En la lista" in html
    assert "Avisado" in html
    assert "Borrador" not in html
    assert "Chispea al enchufar" in html
    assert "Lo cuenta un alumno" not in html
    assert "Fulanito" not in html
    assert "Menganita" not in html
    assert "Imprimir" in html


@pytest.mark.django_db
def test_api_servicios_trae_modo(oficio, tecnico):
    clave = APIKey.objects.create(name="skill", user=tecnico.user)
    r = Client().get(f"{BASE}servicios", HTTP_X_API_KEY=str(clave.key))
    assert r.status_code == 200
    por_slug = {s["slug"]: s for s in r.json()}
    assert por_slug["fontaneria"]["modo"] == "visita"
