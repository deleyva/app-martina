from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import DispositivoWifi
from .permissions import correo_puede_solicitar
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

    def titular(self, quien_lo_rellena):
        """A nombre de quién queda el dispositivo. Aquí, siempre de quien lo envía."""
        return quien_lo_rellena


class AltaEnNombreDeForm(DispositivoWifiForm):
    """El mismo formulario, más «¿para quién es?». Solo lo ve quien gestiona.

    Es para el compañero que viene a la mesa de administración con el móvil en
    la mano: el gestor teclea la MAC y el correo del compañero, y el dispositivo
    queda a nombre de él, que es quien recibirá la clave. Nadie le obliga a
    entrar con Google para copiar y pegar doce dígitos.
    """

    para_correo = forms.EmailField(
        label=_("¿Para quién es?"),
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "eromero@iesmartinabescos.es",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
    )

    def clean_para_correo(self):
        correo = (self.cleaned_data.get("para_correo") or "").strip().lower()
        if not correo:
            return ""
        if not correo_puede_solicitar(correo):
            msg = _(
                "Ese correo no es de personal del centro, así que no puede tener "
                "dispositivos en la WiFi. Si es una excepción, hay que autorizar "
                "la cuenta a mano en el panel de administración."
            )
            raise ValidationError(msg)
        return correo

    def titular(self, quien_lo_rellena):
        """El compañero del correo, o quien rellena el formulario si lo dejó vacío.

        Si el compañero aún no tiene cuenta, se crea aquí, sin contraseña: el
        día que entre con Google, `SocialAccountAdapter.pre_social_login` la
        enlaza por correo y ve sus dispositivos sin que nadie haga nada más.
        """
        correo = self.cleaned_data.get("para_correo")
        if not correo:
            return quien_lo_rellena
        usuarios = get_user_model().objects
        usuario = usuarios.filter(email__iexact=correo).first()
        if usuario is None:
            usuario = usuarios.create_user(email=correo)
        return usuario
