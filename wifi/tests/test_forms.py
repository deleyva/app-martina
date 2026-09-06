import pytest

from ..forms import DispositivoWifiForm
from .factories import DispositivoWifiFactory


@pytest.mark.django_db
class TestDispositivoWifiForm:
    def test_normaliza_la_mac_al_guardarla(self):
        form = DispositivoWifiForm(data={"mac": "a4-83-e7-1c-90-2b", "descripcion": "Móvil"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["mac"] == "A4:83:E7:1C:90:2B"

    def test_rechaza_una_mac_aleatoria_diciendo_por_que(self):
        form = DispositivoWifiForm(data={"mac": "02:11:22:33:44:55", "descripcion": ""})
        assert not form.is_valid()
        assert "aleatoria" in " ".join(form.errors["mac"]).lower()

    def test_rechaza_basura(self):
        form = DispositivoWifiForm(data={"mac": "no soy una mac", "descripcion": ""})
        assert not form.is_valid()
        assert "mac" in form.errors

    def test_rechaza_un_duplicado_activo(self):
        DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B")
        form = DispositivoWifiForm(data={"mac": "a4:83:e7:1c:90:2b", "descripcion": ""})
        assert not form.is_valid()
        assert "ya está registrada" in " ".join(form.errors["mac"])

    def test_admite_un_duplicado_si_el_anterior_se_dio_de_baja(self):
        d = DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B")
        d.marcar_anadida()
        d.marcar_para_baja()
        d.marcar_dada_de_baja()

        form = DispositivoWifiForm(data={"mac": "A4:83:E7:1C:90:2B", "descripcion": ""})
        assert form.is_valid(), form.errors

    def test_la_descripcion_es_opcional(self):
        form = DispositivoWifiForm(data={"mac": "F8:E4:3B:00:11:22"})
        assert form.is_valid(), form.errors
