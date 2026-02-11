# ruff: noqa: ERA001, E501
import pytest

from ..forms import AdjuntoForm
from ..forms import ComentarioForm
from ..forms import IncidenciaForm
from .factories import EtiquetaFactory
from .factories import UbicacionFactory


@pytest.mark.django_db
class TestIncidenciaForm:
    def test_valid_data(self):
        ubi = UbicacionFactory()
        form = IncidenciaForm(data={
            "titulo": "Test incidencia",
            "descripcion": "Descripción",
            "urgencia": "media",
            "reportero_nombre": "Prof. Test",
            "ubicacion": ubi.pk,
            "es_privada": False,
            "etiquetas_ids": "",
        })
        assert form.is_valid(), form.errors

    def test_required_fields(self):
        form = IncidenciaForm(data={})
        assert not form.is_valid()
        assert "titulo" in form.errors
        assert "reportero_nombre" in form.errors

    def test_etiquetas_ids_parsing(self):
        ubi = UbicacionFactory()
        et1 = EtiquetaFactory()
        et2 = EtiquetaFactory()
        form = IncidenciaForm(data={
            "titulo": "Con etiquetas",
            "descripcion": "",
            "urgencia": "baja",
            "reportero_nombre": "Prof. X",
            "ubicacion": ubi.pk,
            "es_privada": False,
            "etiquetas_ids": f"{et1.pk},{et2.pk}",
        })
        assert form.is_valid()
        instance = form.save()
        assert instance.etiquetas.count() == 2

    def test_etiquetas_ids_empty(self):
        ubi = UbicacionFactory()
        form = IncidenciaForm(data={
            "titulo": "Sin etiquetas",
            "descripcion": "",
            "urgencia": "media",
            "reportero_nombre": "Prof. Y",
            "ubicacion": ubi.pk,
            "es_privada": False,
            "etiquetas_ids": "",
        })
        assert form.is_valid()
        instance = form.save()
        assert instance.etiquetas.count() == 0

    def test_without_ubicacion(self):
        form = IncidenciaForm(data={
            "titulo": "Sin ubicación",
            "descripcion": "",
            "urgencia": "media",
            "reportero_nombre": "Prof. Z",
            "ubicacion": "",
            "es_privada": False,
            "etiquetas_ids": "",
        })
        assert form.is_valid()


@pytest.mark.django_db
class TestComentarioForm:
    def test_valid_data(self):
        form = ComentarioForm(data={
            "autor_nombre": "María",
            "texto": "Un comentario de test",
        })
        assert form.is_valid()

    def test_required_fields(self):
        form = ComentarioForm(data={})
        assert not form.is_valid()
        assert "autor_nombre" in form.errors
        assert "texto" in form.errors

    def test_empty_texto(self):
        form = ComentarioForm(data={
            "autor_nombre": "Alguien",
            "texto": "",
        })
        assert not form.is_valid()


@pytest.mark.django_db
class TestAdjuntoForm:
    def test_valid_empty(self):
        """AdjuntoForm with no file is not valid (archivo is required)."""
        form = AdjuntoForm(data={})
        assert not form.is_valid()
