import pytest
from django.db import IntegrityError

from ..models import DispositivoWifi
from .factories import DispositivoWifiFactory
from .factories import PersonalFactory


@pytest.mark.django_db
class TestUnicidad:
    def test_la_misma_mac_no_se_registra_dos_veces_mientras_este_activa(self):
        DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B")
        with pytest.raises(IntegrityError):
            DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B", usuario=PersonalFactory())

    def test_tras_darse_de_baja_se_puede_volver_a_registrar(self):
        d = DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B")
        d.marcar_anadida()
        d.marcar_para_baja()
        d.marcar_dada_de_baja()

        nuevo = DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B", usuario=PersonalFactory())
        assert nuevo.estado == DispositivoWifi.Estado.PENDIENTE


@pytest.mark.django_db
class TestMaquinaDeEstados:
    def test_el_ciclo_completo(self):
        d = DispositivoWifiFactory()
        assert d.estado == DispositivoWifi.Estado.PENDIENTE

        assert d.marcar_anadida() is True
        assert d.estado == DispositivoWifi.Estado.ANADIDA
        assert d.anadida_at is not None

        assert d.marcar_para_baja() is True
        assert d.estado == DispositivoWifi.Estado.BAJA_PENDIENTE

        assert d.marcar_dada_de_baja() is True
        assert d.estado == DispositivoWifi.Estado.DADA_DE_BAJA
        assert d.baja_at is not None

    def test_marcar_anadida_dos_veces_solo_cuenta_una(self):
        d = DispositivoWifiFactory()
        assert d.marcar_anadida() is True
        assert d.marcar_anadida() is False

    def test_no_se_puede_dar_de_baja_lo_que_ya_esta_de_baja(self):
        d = DispositivoWifiFactory()
        d.marcar_anadida()
        d.marcar_para_baja()
        d.marcar_dada_de_baja()
        assert d.marcar_dada_de_baja() is False
        assert d.marcar_para_baja() is False

    def test_no_se_cierra_una_baja_que_nadie_ha_abierto(self):
        d = DispositivoWifiFactory()
        d.marcar_anadida()
        assert d.marcar_dada_de_baja() is False
        assert d.estado == DispositivoWifi.Estado.ANADIDA
