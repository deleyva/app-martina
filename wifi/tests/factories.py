import factory
from factory.django import DjangoModelFactory

from martina_bescos_app.users.tests.factories import UserFactory

from ..models import DispositivoWifi

DOMINIO = "iesmartinabescos.es"


class PersonalFactory(UserFactory):
    """Cuenta de profesorado: la parte local empieza por letra."""

    email = factory.Sequence(lambda n: f"eromero{n}@{DOMINIO}")


class AlumnadoFactory(UserFactory):
    """Cuenta de alumnado: prefijo numérico de promoción."""

    email = factory.Sequence(lambda n: f"0125eromero{n}@{DOMINIO}")


class DispositivoWifiFactory(DjangoModelFactory):
    usuario = factory.SubFactory(PersonalFactory)
    mac = factory.Sequence(lambda n: f"A4:83:E7:{n // 65536 % 256:02X}:{n // 256 % 256:02X}:{n % 256:02X}")
    descripcion = factory.Sequence(lambda n: f"Dispositivo {n}")

    class Meta:
        model = DispositivoWifi
