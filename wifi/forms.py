from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import DispositivoWifi
from .services.mac import MacInvalida
from .services.mac import validar_mac


class DispositivoWifiForm(forms.ModelForm):
    """Pide la MAC real del dispositivo y la deja en forma canónica."""

    class Meta:
        model = DispositivoWifi
        fields = ["mac", "descripcion"]
        labels = {
            "mac": _("Dirección MAC de tu WiFi"),
            "descripcion": _("¿Qué dispositivo es?"),
        }
        widgets = {
            "mac": forms.TextInput(attrs={
                "class": "input input-bordered w-full font-mono tracking-wider",
                "placeholder": "A4:83:E7:1C:90:2B",
                "autocomplete": "off",
                "autocapitalize": "characters",
                "spellcheck": "false",
            }),
            "descripcion": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Móvil personal, portátil del aula 12…",
                "autocomplete": "off",
            }),
        }

    def clean_mac(self):
        try:
            mac = validar_mac(self.cleaned_data.get("mac", ""))
        except MacInvalida as exc:
            raise ValidationError(str(exc)) from exc

        ya_registrada = DispositivoWifi.objects.filter(
            mac=mac,
            estado__in=DispositivoWifi.ESTADOS_ACTIVOS,
        ).exists()
        if ya_registrada:
            msg = _(
                "Esa MAC ya está registrada. Si crees que hay un error o el "
                "dispositivo ha cambiado de manos, dilo en administración."
            )
            raise ValidationError(msg)

        return mac
