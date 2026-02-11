# ruff: noqa: ERA001, E501
import pytest

from ..models import Adjunto
from ..models import Comentario
from ..models import Etiqueta
from ..models import HistorialAsignacion
from ..models import Incidencia
from ..models import Tecnico
from ..models import Ubicacion
from ..models import adjunto_upload_path
from .factories import AdjuntoFactory
from .factories import ComentarioFactory
from .factories import EtiquetaFactory
from .factories import HistorialAsignacionFactory
from .factories import IncidenciaFactory
from .factories import TecnicoFactory
from .factories import UbicacionFactory


# =============================================================================
# Ubicacion
# =============================================================================


@pytest.mark.django_db
class TestUbicacion:
    def test_str_without_grupo(self):
        ubi = UbicacionFactory(nombre="Aula 101", grupo="", planta="PB")
        assert "Aula 101" in str(ubi)
        assert "Planta Baja" in str(ubi)

    def test_str_with_grupo(self):
        ubi = UbicacionFactory(nombre="Aula 102", grupo="1ESO-A", planta="P1")
        result = str(ubi)
        assert "Aula 102" in result
        assert "1ESO-A" in result
        assert "Primera Planta" in result

    def test_unique_together(self):
        Ubicacion.objects.create(nombre="UniqueTest", planta="PB")
        with pytest.raises(Exception):  # noqa: B017
            Ubicacion.objects.create(nombre="UniqueTest", planta="PB")

    def test_ordering(self):
        """Ordering is by planta ascending then nombre ascending."""
        ubi_p2 = UbicacionFactory(nombre="Z-Order-Aula", planta="P2")
        ubi_p1 = UbicacionFactory(nombre="A-Order-Aula", planta="P1")
        pks = [ubi_p1.pk, ubi_p2.pk]
        ubicaciones = list(Ubicacion.objects.filter(pk__in=pks))
        # P1 < P2 alphabetically
        assert ubicaciones[0] == ubi_p1
        assert ubicaciones[1] == ubi_p2

    def test_planta_choices(self):
        assert len(Ubicacion.Planta.choices) == 3
        values = [c[0] for c in Ubicacion.Planta.choices]
        assert "PB" in values
        assert "P1" in values
        assert "P2" in values


# =============================================================================
# Etiqueta
# =============================================================================


@pytest.mark.django_db
class TestEtiqueta:
    def test_str(self):
        et = EtiquetaFactory(nombre="Internet")
        assert str(et) == "Internet"

    def test_slug_unique(self):
        Etiqueta.objects.create(nombre="Red WiFi Unique", slug="red-wifi-unique")
        with pytest.raises(Exception):  # noqa: B017
            Etiqueta.objects.create(nombre="Red WiFi 2 Unique", slug="red-wifi-unique")

    def test_ordering(self):
        et_z = EtiquetaFactory(nombre="Zzz etiqueta")
        et_a = EtiquetaFactory(nombre="Aaa etiqueta")
        etiquetas = list(Etiqueta.objects.all())
        assert etiquetas.index(et_a) < etiquetas.index(et_z)


# =============================================================================
# Incidencia
# =============================================================================


@pytest.mark.django_db
class TestIncidencia:
    def test_str(self):
        inc = IncidenciaFactory(titulo="Proyector roto", urgencia=Incidencia.Urgencia.ALTA)
        result = str(inc)
        assert "Proyector roto" in result
        assert "Alta" in result

    def test_default_estado(self):
        inc = IncidenciaFactory()
        assert inc.estado == Incidencia.Estado.PENDIENTE

    def test_default_urgencia(self):
        inc = IncidenciaFactory()
        assert inc.urgencia == Incidencia.Urgencia.MEDIA

    def test_estado_choices(self):
        values = [c[0] for c in Incidencia.Estado.choices]
        assert "pendiente" in values
        assert "en_progreso" in values
        assert "resuelta" in values

    def test_urgencia_choices(self):
        values = [c[0] for c in Incidencia.Urgencia.choices]
        assert "baja" in values
        assert "media" in values
        assert "alta" in values
        assert "critica" in values

    def test_with_etiquetas(self):
        et1 = EtiquetaFactory(nombre="Internet", slug="internet")
        et2 = EtiquetaFactory(nombre="WiFi", slug="wifi")
        inc = IncidenciaFactory(etiquetas=[et1, et2])
        assert inc.etiquetas.count() == 2

    def test_es_privada(self):
        inc = IncidenciaFactory(es_privada=True)
        assert inc.es_privada is True

    def test_ordering(self):
        """Most recent first."""
        inc1 = IncidenciaFactory()
        inc2 = IncidenciaFactory()
        incidencias = list(Incidencia.objects.all())
        assert incidencias.index(inc2) < incidencias.index(inc1)

    def test_asignado_a_nullable(self):
        inc = IncidenciaFactory(asignado_a=None)
        assert inc.asignado_a is None

    def test_ubicacion_nullable(self):
        inc = IncidenciaFactory(ubicacion=None)
        assert inc.ubicacion is None


# =============================================================================
# Comentario
# =============================================================================


@pytest.mark.django_db
class TestComentario:
    def test_str(self):
        com = ComentarioFactory(autor_nombre="Pedro", texto="Esto está fatal")
        result = str(com)
        assert "Pedro" in result
        assert "Esto está fatal" in result

    def test_ordering(self):
        """Oldest first."""
        inc = IncidenciaFactory()
        com1 = ComentarioFactory(incidencia=inc)
        com2 = ComentarioFactory(incidencia=inc)
        comentarios = list(inc.comentarios.all())
        assert comentarios.index(com1) < comentarios.index(com2)

    def test_cascade_delete(self):
        com = ComentarioFactory()
        inc_pk = com.incidencia.pk
        Incidencia.objects.get(pk=inc_pk).delete()
        assert Comentario.objects.filter(pk=com.pk).count() == 0

    def test_related_name(self):
        inc = IncidenciaFactory()
        ComentarioFactory(incidencia=inc)
        ComentarioFactory(incidencia=inc)
        assert inc.comentarios.count() == 2


# =============================================================================
# Adjunto
# =============================================================================


@pytest.mark.django_db
class TestAdjunto:
    def test_str(self):
        adj = AdjuntoFactory()
        assert "Adjunto para" in str(adj)

    def test_is_image_true(self):
        adj = AdjuntoFactory(archivo__filename="photo.jpg")
        assert adj.is_image is True
        assert adj.is_video is False

    def test_is_image_png(self):
        adj = AdjuntoFactory(archivo__filename="photo.png")
        assert adj.is_image is True

    def test_is_video_true(self):
        adj = AdjuntoFactory(archivo__filename="clip.mp4")
        assert adj.is_video is True
        assert adj.is_image is False

    def test_is_video_mov(self):
        adj = AdjuntoFactory(archivo__filename="clip.mov")
        assert adj.is_video is True

    def test_upload_path(self):
        adj = AdjuntoFactory()
        # Test the upload path function directly
        path = adjunto_upload_path(adj, "test.jpg")
        assert f"incidencias/{adj.incidencia_id}/test.jpg" == path

    def test_cascade_delete(self):
        adj = AdjuntoFactory()
        inc_pk = adj.incidencia.pk
        Incidencia.objects.get(pk=inc_pk).delete()
        assert Adjunto.objects.filter(pk=adj.pk).count() == 0


# =============================================================================
# Tecnico
# =============================================================================


@pytest.mark.django_db
class TestTecnico:
    def test_str_with_nombre_display(self):
        tecnico = TecnicoFactory(nombre_display="Juan Técnico")
        assert str(tecnico) == "Juan Técnico"

    def test_str_without_nombre_display(self):
        tecnico = TecnicoFactory(nombre_display="")
        fallback = str(tecnico)
        # Should fallback to email or user string
        assert fallback  # not empty

    def test_activo_default(self):
        tecnico = TecnicoFactory()
        assert tecnico.activo is True

    def test_related_name(self):
        tecnico = TecnicoFactory()
        inc = IncidenciaFactory(asignado_a=tecnico)
        assert inc in tecnico.incidencias_asignadas.all()


# =============================================================================
# HistorialAsignacion
# =============================================================================


@pytest.mark.django_db
class TestHistorialAsignacion:
    def test_str(self):
        hist = HistorialAsignacionFactory()
        result = str(hist)
        assert "→" in result

    def test_ordering(self):
        """Newest first."""
        inc = IncidenciaFactory()
        h1 = HistorialAsignacionFactory(incidencia=inc)
        h2 = HistorialAsignacionFactory(incidencia=inc)
        historial = list(inc.historial_asignaciones.all())
        assert historial.index(h2) < historial.index(h1)

    def test_cascade_delete(self):
        hist = HistorialAsignacionFactory()
        inc_pk = hist.incidencia.pk
        Incidencia.objects.get(pk=inc_pk).delete()
        assert HistorialAsignacion.objects.filter(pk=hist.pk).count() == 0

    def test_asignado_por_nullable(self):
        hist = HistorialAsignacionFactory(asignado_por=None)
        assert hist.asignado_por is None
        assert "Sistema" in str(hist)
