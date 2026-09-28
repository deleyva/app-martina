# ruff: noqa: E501, PLR2004
"""Derivaciones: máquina de estados, correo generado y vistas de técnico."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from incidencias.models import Comunicacion
from incidencias.models import Derivacion
from incidencias.models import Incidencia
from incidencias.models import TransicionInvalida
from incidencias.services import acciones
from incidencias.tests.factories import ComentarioFactory
from incidencias.tests.factories import DerivacionFactory
from incidencias.tests.factories import IncidenciaFactory
from incidencias.tests.factories import ServicioFactory
from incidencias.tests.factories import TecnicoFactory
from incidencias.tests.factories import UbicacionFactory

User = get_user_model()


@pytest.fixture
def tecnico(db):
    return TecnicoFactory(user__email="tecnica@iesmartinabescos.es", nombre_display="Técnica")


@pytest.fixture
def tecnico_client(tecnico):
    c = Client()
    c.force_login(tecnico.user)
    return c


@pytest.fixture
def servicio(db):
    return ServicioFactory(slug="hardware-software-4100", nombre="Hardware y software (4100)")


# --- Correo generado ------------------------------------------------------------


@pytest.mark.django_db
def test_asunto_por_defecto_lleva_inc_y_aula(servicio, tecnico):
    aula = UbicacionFactory(nombre="Aula N6", planta="PB")
    con_aula = IncidenciaFactory(titulo="Cable HDMI roto", ubicacion=aula)
    sin_aula = IncidenciaFactory(titulo="PC estropeado", ubicacion=None)

    d1 = acciones.derivar(con_aula, servicio, tecnico)
    d2 = acciones.derivar(sin_aula, servicio, tecnico)

    assert d1.asunto == f"[INC-{con_aula.pk}] Aula N6 — Cable HDMI roto"
    assert d2.asunto == f"[INC-{sin_aula.pk}] Sin aula — PC estropeado"


@pytest.mark.django_db
def test_texto_correo_es_asunto_linea_en_blanco_cuerpo(servicio, tecnico, tecnico_client):
    inc = IncidenciaFactory()
    d = acciones.derivar(inc, servicio, tecnico)

    assert d.texto_correo == f"{d.asunto}\n\n{d.cuerpo}"

    html = tecnico_client.get(reverse("incidencias:detalle", args=[inc.pk])).content.decode()
    assert d.texto_correo in html


@pytest.mark.django_db
def test_cuerpo_no_escapa_html(servicio, tecnico):
    inc = IncidenciaFactory(descripcion="El cable 'HDMI' va & viene <mal>")
    d = acciones.derivar(inc, servicio, tecnico)
    assert "El cable 'HDMI' va & viene <mal>" in d.cuerpo
    assert "&#x27;" not in d.cuerpo
    assert "&amp;" not in d.cuerpo


@pytest.mark.django_db
def test_cuerpo_lleva_enlace_a_la_pagina_viva_y_lo_comprobado(servicio, tecnico):
    inc = IncidenciaFactory(titulo="Sin sonido")
    ComentarioFactory(incidencia=inc, autor_nombre="tecnica", texto="Probado otro cable, nada")
    ComentarioFactory(incidencia=inc, autor_nombre="unprofe", texto="A mí tampoco me va")
    d = acciones.derivar(inc, servicio, tecnico)
    assert servicio.url_publica in d.cuerpo
    assert "Probado otro cable, nada" in d.cuerpo
    assert "A mí tampoco me va" not in d.cuerpo


@pytest.mark.django_db
def test_crear_borrador_sube_pendiente_a_en_progreso_y_notifica(servicio, tecnico):
    inc = IncidenciaFactory(estado="pendiente")
    with patch("incidencias.services.acciones.IncidenciaNotificationService.notify_estado_changed") as notify:
        acciones.derivar(inc, servicio, tecnico)
    inc.refresh_from_db()
    assert inc.estado == Incidencia.Estado.EN_PROGRESO
    notify.assert_called_once_with(inc.pk, "pendiente", "en_progreso")

    ya_en_progreso = IncidenciaFactory(estado="en_progreso")
    with patch("incidencias.services.acciones.IncidenciaNotificationService.notify_estado_changed") as notify:
        acciones.derivar(ya_en_progreso, servicio, tecnico)
    notify.assert_not_called()


# --- Máquina de estados -----------------------------------------------------------


@pytest.mark.django_db
def test_marcar_enviada_crea_comunicacion_enviada_con_cuerpo(tecnico):
    d = DerivacionFactory(cuerpo="Hola 4100")
    com = d.marcar_enviada(tecnico)
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.ENVIADA
    assert d.enviada_por == tecnico
    assert d.enviada_at is not None
    assert com.sentido == Comunicacion.Sentido.ENVIADA
    assert com.texto == d.texto_correo
    assert "Hola 4100" in com.texto


@pytest.mark.django_db
def test_marcar_enviada_dos_veces_falla(tecnico):
    d = DerivacionFactory()
    d.marcar_enviada(tecnico)
    with pytest.raises(TransicionInvalida):
        d.marcar_enviada(tecnico)


@pytest.mark.django_db
def test_respuesta_en_borrador_falla():
    d = DerivacionFactory()
    with pytest.raises(TransicionInvalida):
        d.registrar_respuesta(autor="secretaria", texto="Vendrán el lunes")
    assert d.comunicaciones.count() == 0


@pytest.mark.django_db
def test_registrar_respuesta_guarda_ticket_y_pasa_a_respondida(tecnico):
    d = DerivacionFactory()
    d.marcar_enviada(tecnico)
    cuando = timezone.now()
    com = d.registrar_respuesta(autor="secretaria", texto="Ticket abierto", fecha=cuando, ticket_externo="INC0012345")
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.RESPONDIDA
    assert d.ticket_externo == "INC0012345"
    assert com.sentido == Comunicacion.Sentido.RECIBIDA
    assert com.fecha == cuando
    # una segunda respuesta sigue siendo válida
    d.registrar_respuesta(autor="secretaria", texto="Vienen el jueves")
    assert d.comunicaciones.count() == 3


@pytest.mark.django_db
def test_cerrar_sin_resultado_falla(tecnico):
    d = DerivacionFactory()
    d.marcar_enviada(tecnico)
    with pytest.raises(TransicionInvalida):
        d.cerrar(resultado="")
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.ENVIADA


@pytest.mark.django_db
def test_borrador_solo_se_cierra_como_duplicada():
    d = DerivacionFactory()
    with pytest.raises(TransicionInvalida):
        d.cerrar(resultado="resuelta")
    d.cerrar(resultado="duplicada")
    assert d.estado == Derivacion.Estado.CERRADA


@pytest.mark.django_db
def test_editar_cuerpo_tras_enviada_falla(tecnico):
    d = DerivacionFactory(cuerpo="original")
    d.marcar_enviada(tecnico)
    with pytest.raises(TransicionInvalida):
        d.editar(cuerpo="cambiado")
    d.editar(ticket_externo="T-1")  # el ticket sí
    d.refresh_from_db()
    assert d.cuerpo == "original"
    assert d.ticket_externo == "T-1"


@pytest.mark.django_db
def test_cerrada_no_admite_nada(tecnico):
    d = DerivacionFactory()
    d.marcar_enviada(tecnico)
    d.cerrar(resultado="resuelta", nota="Arreglado en la visita")
    assert d.comunicaciones.filter(sentido="nota").count() == 1
    for accion in (
        lambda: d.marcar_enviada(tecnico),
        lambda: d.registrar_respuesta(autor="x", texto="y"),
        lambda: d.cerrar(resultado="resuelta"),
        lambda: d.editar(cuerpo="z"),
        lambda: d.anotar(autor="x", texto="y"),
    ):
        with pytest.raises(TransicionInvalida):
            accion()


# --- Vistas de técnico ------------------------------------------------------------


@pytest.mark.django_db
def test_vistas_derivacion_exigen_tecnico(servicio):
    inc = IncidenciaFactory()
    d = DerivacionFactory(incidencia=inc, servicio=servicio)
    profe = User.objects.create_user(email="profe@iesmartinabescos.es", password="x")  # noqa: S106
    anonimo = Client()
    logueado = Client()
    logueado.force_login(profe)

    rutas = [
        (reverse("incidencias:derivar", args=[inc.pk]), {"servicio": servicio.pk}),
        (reverse("incidencias:derivacion_editar", args=[d.pk]), {"asunto": "x", "cuerpo": "y", "ticket_externo": ""}),
        (reverse("incidencias:derivacion_enviada", args=[d.pk]), {}),
        (reverse("incidencias:derivacion_respuesta", args=[d.pk]), {"texto": "r", "canal": "correo"}),
        (reverse("incidencias:derivacion_cerrar", args=[d.pk]), {"resultado": "duplicada"}),
    ]
    for url, datos in rutas:
        for cliente in (anonimo, logueado):
            r = cliente.post(url, datos)
            assert r.status_code in (302, 403), url
            if r.status_code == 302:
                assert "login" in r["Location"], url
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.BORRADOR
    assert d.asunto != "x"
    assert Derivacion.objects.count() == 1


@pytest.mark.django_db
def test_flujo_completo_por_las_vistas(servicio, tecnico, tecnico_client):
    inc = IncidenciaFactory(estado="pendiente")

    r = tecnico_client.post(reverse("incidencias:derivar", args=[inc.pk]), {"servicio": servicio.pk})
    assert r.status_code == 302
    d = Derivacion.objects.get(incidencia=inc)
    assert r["Location"].endswith(f"/incidencias/{inc.pk}/#derivacion-{d.pk}")

    tecnico_client.post(reverse("incidencias:derivacion_editar", args=[d.pk]), {"asunto": d.asunto, "cuerpo": "Cuerpo editado", "ticket_externo": ""})
    d.refresh_from_db()
    assert d.cuerpo == "Cuerpo editado"

    tecnico_client.post(reverse("incidencias:derivacion_enviada", args=[d.pk]))
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.ENVIADA
    assert d.enviada_por == tecnico

    tecnico_client.post(reverse("incidencias:derivacion_respuesta", args=[d.pk]), {"texto": "Vendrán el lunes", "canal": "telefono", "ticket_externo": "T-9"})
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.RESPONDIDA
    assert d.ticket_externo == "T-9"

    tecnico_client.post(reverse("incidencias:derivacion_cerrar", args=[d.pk]), {"resultado": "resuelta", "nota": "Cambiaron el cable"})
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.CERRADA
    assert [c.sentido for c in d.comunicaciones.all()] == ["enviada", "recibida", "nota"]


@pytest.mark.django_db
def test_transicion_ilegal_por_vista_no_rompe_y_avisa(servicio, tecnico, tecnico_client):
    d = DerivacionFactory(servicio=servicio)
    r = tecnico_client.post(reverse("incidencias:derivacion_respuesta", args=[d.pk]), {"texto": "x", "canal": "correo"}, follow=True)
    assert r.status_code == 200
    assert "No se puede registrar una respuesta" in r.content.decode()
    d.refresh_from_db()
    assert d.estado == Derivacion.Estado.BORRADOR


@pytest.mark.django_db
def test_regenerar_token_invalida_el_anterior(servicio):
    viejo = servicio.token
    otro = ServicioFactory()
    assert otro.token != viejo
    c = Client()
    assert c.get(reverse("incidencias:servicio_publico", args=[viejo])).status_code == 200
    servicio.regenerar_token()
    assert servicio.token != viejo
    assert c.get(reverse("incidencias:servicio_publico", args=[viejo])).status_code == 404
    assert c.get(reverse("incidencias:servicio_publico", args=[servicio.token])).status_code == 200
