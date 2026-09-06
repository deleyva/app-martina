"""La validación de MACs, que es donde vive el valor de esta app."""

import pytest

from ..services.mac import MacInvalida
from ..services.mac import es_aleatoria
from ..services.mac import exportar
from ..services.mac import formatear_mac
from ..services.mac import normalizar_mac
from ..services.mac import validar_mac

CANONICA = "A4:83:E7:1C:90:2B"


class TestNormalizar:
    @pytest.mark.parametrize(
        "entrada",
        [
            "A4:83:E7:1C:90:2B",
            "a4:83:e7:1c:90:2b",
            "A4-83-E7-1C-90-2B",
            "a483.e71c.902b",
            "A483E71C902B",
            "a4 83 e7 1c 90 2b",
            "  A4:83:E7:1C:90:2B  ",
        ],
    )
    def test_todos_los_formatos_dan_la_misma_forma(self, entrada):
        assert normalizar_mac(entrada) == CANONICA

    @pytest.mark.parametrize(
        "basura",
        ["", "   ", "A4:83:E7:1C:90", "A4:83:E7:1C:90:2B:CD", "ZZ:83:E7:1C:90:2B", "hola"],
    )
    def test_lo_que_no_es_una_mac_se_rechaza(self, basura):
        with pytest.raises(MacInvalida):
            normalizar_mac(basura)


class TestAleatorias:
    """Afirmación universal: el bit localmente administrado es el bit 1 del primer octeto.

    Eso son exactamente los segundos nibbles 2, 6, A y E. No es una lista de
    ejemplos: es el conjunto completo de los que activan ese bit.
    """

    NIBBLES_ALEATORIOS = "26AE"
    NIBBLES_FABRICA = "014589CD"  # los pares (unicast) que NO tienen el bit puesto

    def test_todos_los_nibbles_locales_se_detectan(self):
        for alto in "0123456789ABCDEF":
            for bajo in self.NIBBLES_ALEATORIOS:
                mac = f"{alto}{bajo}:11:22:33:44:55"
                assert es_aleatoria(mac), f"{mac} debería detectarse como aleatoria"

    def test_ninguna_mac_de_fabrica_se_marca_como_aleatoria(self):
        for alto in "0123456789ABCDEF":
            for bajo in self.NIBBLES_FABRICA:
                mac = f"{alto}{bajo}:11:22:33:44:55"
                assert not es_aleatoria(mac), f"{mac} es de fábrica y no debería marcarse"

    @pytest.mark.parametrize("mac", ["02:11:22:33:44:55", "0A:BB:CC:DD:EE:F0", "AE:11:22:33:44:55"])
    def test_validar_las_rechaza_explicando_por_que(self, mac):
        with pytest.raises(MacInvalida, match="aleatoria"):
            validar_mac(mac)


class TestValidar:
    @pytest.mark.parametrize("mac", ["A4:83:E7:1C:90:2B", "00:1B:44:11:3A:B7", "F8:E4:3B:00:11:22"])
    def test_las_de_fabrica_pasan(self, mac):
        assert validar_mac(mac) == mac

    def test_la_nula_y_la_de_difusion_se_rechazan(self):
        with pytest.raises(MacInvalida):
            validar_mac("00:00:00:00:00:00")
        with pytest.raises(MacInvalida):
            validar_mac("FF:FF:FF:FF:FF:FF")

    @pytest.mark.parametrize("mac", ["01:11:22:33:44:55", "03:11:22:33:44:55", "FD:11:22:33:44:55"])
    def test_el_multicast_se_rechaza(self, mac):
        with pytest.raises(MacInvalida):
            validar_mac(mac)

    def test_acepta_minusculas_y_devuelve_canonica(self):
        assert validar_mac("a4-83-e7-1c-90-2b") == CANONICA


class TestExportar:
    def test_cada_formato_de_salida(self):
        assert formatear_mac(CANONICA, "colon") == "A4:83:E7:1C:90:2B"
        assert formatear_mac(CANONICA, "hyphen") == "A4-83-E7-1C-90-2B"
        assert formatear_mac(CANONICA, "plain") == "A483E71C902B"
        assert formatear_mac(CANONICA, "cisco") == "A483.E71C.902B"

    def test_separadores(self):
        macs = ["A4:83:E7:1C:90:2B", "00:1B:44:11:3A:B7"]
        assert exportar(macs, "colon", "coma") == "A4:83:E7:1C:90:2B, 00:1B:44:11:3A:B7"
        assert exportar(macs, "colon", "linea") == "A4:83:E7:1C:90:2B\n00:1B:44:11:3A:B7"
        assert exportar(macs, "plain", "coma") == "A483E71C902B, 001B44113AB7"

    def test_lista_vacia(self):
        assert exportar([], "colon", "coma") == ""
