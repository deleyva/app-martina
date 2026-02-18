# ruff: noqa: ERA001, E501
import factory
from factory.django import DjangoModelFactory

from martina_bescos_app.users.tests.factories import UserFactory

from ..models import Adjunto
from ..models import Comentario
from ..models import Etiqueta
from ..models import HistorialAsignacion
from ..models import Incidencia
from ..models import Tecnico
from ..models import Ubicacion


class UbicacionFactory(DjangoModelFactory):
    nombre = factory.Sequence(lambda n: f"Aula {n}")
    grupo = factory.LazyAttribute(lambda o: f"Grupo {o.nombre[-1]}")
    planta = factory.Iterator(["PB", "P1", "P2"])

    class Meta:
        model = Ubicacion
        django_get_or_create = ["nombre", "planta"]


class EtiquetaFactory(DjangoModelFactory):
    nombre = factory.Sequence(lambda n: f"Etiqueta {n}")
    slug = factory.LazyAttribute(lambda o: o.nombre.lower().replace(" ", "-"))

    class Meta:
        model = Etiqueta
        django_get_or_create = ["slug"]


class TecnicoFactory(DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    nombre_display = factory.LazyAttribute(lambda o: o.user.name)
    activo = True

    class Meta:
        model = Tecnico
        django_get_or_create = ["user"]


class IncidenciaFactory(DjangoModelFactory):
    titulo = factory.Sequence(lambda n: f"Incidencia {n}")
    descripcion = factory.Faker("paragraph", locale="es_ES")
    urgencia = Incidencia.Urgencia.MEDIA
    estado = Incidencia.Estado.PENDIENTE
    es_privada = False
    reportero_nombre = factory.Faker("name", locale="es_ES")
    ubicacion = factory.SubFactory(UbicacionFactory)

    class Meta:
        model = Incidencia

    @factory.post_generation
    def etiquetas(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for etiqueta in extracted:
                self.etiquetas.add(etiqueta)


class ComentarioFactory(DjangoModelFactory):
    incidencia = factory.SubFactory(IncidenciaFactory)
    autor_nombre = factory.Faker("name", locale="es_ES")
    texto = factory.Faker("paragraph", locale="es_ES")

    class Meta:
        model = Comentario


class AdjuntoFactory(DjangoModelFactory):
    incidencia = factory.SubFactory(IncidenciaFactory)
    archivo = factory.django.FileField(filename="test_image.jpg")

    class Meta:
        model = Adjunto


class HistorialAsignacionFactory(DjangoModelFactory):
    incidencia = factory.SubFactory(IncidenciaFactory)
    asignado_por = factory.SubFactory(TecnicoFactory)
    asignado_a = factory.SubFactory(TecnicoFactory)
    nota = factory.LazyAttribute(lambda o: f"Asignada a {o.asignado_a}")

    class Meta:
        model = HistorialAsignacion


class GeminiAPIUsageFactory(DjangoModelFactory):
    caller = "email_parser"
    tokens_used = factory.Faker("random_int", min=50, max=500)
    success = True
    error_message = ""

    class Meta:
        model = "incidencias.GeminiAPIUsage"


class ProcessedEmailFactory(DjangoModelFactory):
    message_id = factory.Sequence(lambda n: f"<msg-{n}@gmail.com>")
    incidencia = factory.SubFactory(IncidenciaFactory)
    raw_subject = factory.Faker("sentence", locale="es_ES")
    raw_sender = factory.Faker("email")
    skipped = False
    skip_reason = ""

    class Meta:
        model = "incidencias.ProcessedEmail"

