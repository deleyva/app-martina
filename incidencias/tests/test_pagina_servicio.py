# ruff: noqa: E501, PLR2004
"""La página pública de un servicio: lo que ve el técnico externo, y lo que no."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from incidencias.models import Derivacion
from incidencias.tests.factories import ComentarioFactory
from incidencias.tests.factories import DerivacionFactory
from incidencias.tests.factories import IncidenciaFactory
from incidencias.tests.factories import ServicioFactory
from incidencias.tests.factories import TecnicoFactory
from incidencias.tests.factories import UbicacionFactory


@pytest.fixture
def servicio(db):
    return ServicioFactory(slug="redes", nombre="Redes y conectividad")


def _pagina(servicio):
    return Client().get(reverse("incidencias:servicio_publico", args=[servicio.token]))


@pytest.mark.django_db
def test_token_valido_200_sin_sesion(servicio):
    r = _pagina(servicio)
    assert r.status_code == 200
    assert "Redes y conectividad" in r.content.decode()


@pytest.mark.django_db
def test_token_inventado_404(servicio):
    assert Client().get(reverse("incidencias:servicio_publico", args=["no-existe"])).status_code == 404


@pytest.mark.django_db
def test_servicio_inactivo_404(servicio):
    servicio.activo = False
    servicio.save()
    assert _pagina(servicio).status_code == 404


@pytest.mark.django_db
def test_no_muestra_reportero_nunca(servicio):
    publica = IncidenciaFactory(reportero_nombre="profesorpublico", es_privada=False)
    privada = IncidenciaFactory(reportero_nombre="profesorprivado", es_privada=True)
    DerivacionFactory(incidencia=publica, servicio=servicio)
    DerivacionFactory(incidencia=privada, servicio=servicio)
    ComentarioFactory(incidencia=publica, autor_nombre="comentarista", texto="Comentario interno que no debe salir")
    html = _pagina(servicio).content.decode()
    assert "profesorpublico" not in html
    assert "profesorprivado" not in html
    assert "comentarista" not in html
    assert "Comentario interno que no debe salir" not in html


@pytest.mark.django_db
def test_privada_solo_id_aula_asunto(servicio):
    aula = UbicacionFactory(nombre="Aula N3", planta="PB")
    privada = IncidenciaFactory(titulo="Carpeta docentes", descripcion="Actas y exámenes a la vista", es_privada=True, ubicacion=aula)
    d = DerivacionFactory(incidencia=privada, servicio=servicio, cuerpo="Cuerpo con datos sensibles")
    d.marcar_enviada(TecnicoFactory())
    html = _pagina(servicio).content.decode()
    assert f"[INC-{privada.pk}]" in html
    assert "Aula N3" in html
    assert "Carpeta docentes" in html
    assert "Actas y exámenes a la vista" not in html
    assert "Cuerpo con datos sensibles" not in html


@pytest.mark.django_db
def test_publica_si_muestra_descripcion_y_correo_enviado(servicio):
    inc = IncidenciaFactory(titulo="Sin wifi", descripcion="El router parpadea", es_privada=False)
    d = DerivacionFactory(incidencia=inc, servicio=servicio, cuerpo="Texto del correo")
    d.marcar_enviada(TecnicoFactory())
    html = _pagina(servicio).content.decode()
    assert "El router parpadea" in html
    assert "Texto del correo" in html


@pytest.mark.django_db
def test_solo_derivaciones_de_ese_servicio(servicio):
    otro = ServicioFactory(slug="otro")
    DerivacionFactory(incidencia=IncidenciaFactory(titulo="Mía"), servicio=servicio)
    DerivacionFactory(incidencia=IncidenciaFactory(titulo="Ajena"), servicio=otro)
    html = _pagina(servicio).content.decode()
    assert "Mía" in html
    assert "Ajena" not in html


@pytest.mark.django_db
def test_cerradas_de_mas_de_60_dias_no_salen(servicio):
    tecnico = TecnicoFactory()
    reciente = DerivacionFactory(incidencia=IncidenciaFactory(titulo="Reciente"), servicio=servicio)
    reciente.marcar_enviada(tecnico)
    reciente.cerrar(resultado="resuelta")
    vieja = DerivacionFactory(incidencia=IncidenciaFactory(titulo="Antigua"), servicio=servicio)
    vieja.marcar_enviada(tecnico)
    vieja.cerrar(resultado="resuelta")
    Derivacion.objects.filter(pk=vieja.pk).update(updated_at=timezone.now() - timedelta(days=61))
    html = _pagina(servicio).content.decode()
    assert "Reciente" in html
    assert "Antigua" not in html


@pytest.mark.django_db
def test_agrupa_por_planta_y_aula(servicio):
    pb = UbicacionFactory(nombre="Aula N1", planta="PB")
    p2 = UbicacionFactory(nombre="Aula 17", planta="P2")
    DerivacionFactory(incidencia=IncidenciaFactory(titulo="Arriba", ubicacion=p2), servicio=servicio)
    DerivacionFactory(incidencia=IncidenciaFactory(titulo="Abajo", ubicacion=pb), servicio=servicio)
    DerivacionFactory(incidencia=IncidenciaFactory(titulo="Perdida", ubicacion=None), servicio=servicio)
    html = _pagina(servicio).content.decode()
    assert html.index("Planta Baja") < html.index("Abajo") < html.index("Segunda Planta") < html.index("Arriba") < html.index("Sin ubicación") < html.index("Perdida")


@pytest.mark.django_db
def test_historico_incluye_enviada_y_recibida_en_orden(servicio):
    d = DerivacionFactory(incidencia=IncidenciaFactory(es_privada=False), servicio=servicio, cuerpo="Primero el envío")
    d.marcar_enviada(TecnicoFactory())
    d.registrar_respuesta(autor="secretaria", texto="Luego la respuesta", ticket_externo="T-1")
    html = _pagina(servicio).content.decode()
    assert html.index("Primero el envío") < html.index("Luego la respuesta")
    assert "T-1" in html
