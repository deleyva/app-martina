from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Adjunto
from .models import Comentario
from .models import Comunicacion
from .models import Derivacion
from .models import Etiqueta
from .models import Incidencia
from .models import Servicio
from .models import Ubicacion


class IncidenciaForm(forms.ModelForm):
    """Formulario para crear una incidencia."""

    etiquetas_ids = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text=_("IDs de etiquetas separados por coma"),
    )

    class Meta:
        model = Incidencia
        fields = [
            "titulo",
            "descripcion",
            "urgencia",
            "ambito",
            "reportero_nombre",
            "ubicacion",
            "es_privada",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Describe brevemente la incidencia...",
                "autocomplete": "off",
            }),
            "descripcion": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 4,
                "placeholder": "Describe con más detalle qué ha ocurrido...",
            }),
            "urgencia": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "ambito": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "reportero_nombre": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Tu usuario del IES sin @iesmartinabescos. Por ejemplo eromero o 0125eromero",
            }),
            "ubicacion": forms.Select(attrs={
                "class": "hidden",  # Hidden, replaced by autocomplete
            }),
            "es_privada": forms.CheckboxInput(attrs={
                "class": "checkbox checkbox-primary",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ubicacion"].queryset = Ubicacion.objects.all()
        self.fields["ubicacion"].empty_label = "Selecciona ubicación..."
        self.fields["reportero_nombre"].label = "¿Quién eres?"
        # Sin ámbito en el POST (formularios antiguos, correo) → informática.
        self.fields["ambito"].required = False

    def clean_ambito(self):
        return self.cleaned_data.get("ambito") or Incidencia.Ambito.INFORMATICA

        if self.instance and self.instance.pk:
            etiquetas = self.instance.etiquetas.all()
            if etiquetas:
                self.fields["etiquetas_ids"].initial = ",".join(str(e.id) for e in etiquetas)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            # Handle etiquetas from hidden field
            etiquetas_ids = self.cleaned_data.get("etiquetas_ids", "")
            if etiquetas_ids:
                ids = [
                    int(x.strip())
                    for x in etiquetas_ids.split(",")
                    if x.strip().isdigit()
                ]
                etiquetas = Etiqueta.objects.filter(id__in=ids)
                instance.etiquetas.set(etiquetas)
            else:
                instance.etiquetas.clear()
        return instance


class ComentarioForm(forms.ModelForm):
    """Formulario para añadir un comentario."""

    class Meta:
        model = Comentario
        fields = ["autor_nombre", "texto"]
        widgets = {
            "autor_nombre": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Tu usuario del IES sin @iesmartinabescos. Por ejemplo eromero o 0125eromero",
            }),
            "texto": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": "Escribe tu comentario...",
            }),
        }


class AdjuntoForm(forms.ModelForm):
    """Formulario para adjuntar archivos."""

    class Meta:
        model = Adjunto
        fields = ["archivo"]
        widgets = {
            "archivo": forms.ClearableFileInput(attrs={
                "class": "file-input file-input-bordered w-full",
                "accept": "image/*,video/*",
            }),
        }

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if archivo and archivo.size > Adjunto.MAX_FILE_SIZE:
            msg = _("El archivo no puede superar los 10 MB.")
            raise ValidationError(msg)
        return archivo


# =============================================================================
# Derivaciones
# =============================================================================


class _ServicioChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"📞 {obj.nombre}" if obj.es_por_visita else obj.nombre


class DerivacionForm(forms.Form):
    """Elegir a qué servicio se deriva."""

    servicio = _ServicioChoiceField(
        queryset=Servicio.objects.filter(activo=True),
        empty_label="Elige un servicio…",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )


class DerivacionEditarForm(forms.ModelForm):
    """Asunto y cuerpo (solo en borrador) y ticket (siempre)."""

    class Meta:
        model = Derivacion
        fields = ["asunto", "cuerpo", "ticket_externo"]
        widgets = {
            "asunto": forms.TextInput(attrs={"class": "input input-bordered w-full font-mono text-sm"}),
            "cuerpo": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full font-mono text-sm", "rows": 14}),
            "ticket_externo": forms.TextInput(attrs={"class": "input input-bordered input-sm w-full", "placeholder": "Nº de ticket, si lo hay"}),
        }


class RespuestaForm(forms.Form):
    """Lo que ha contestado el servicio, apuntado a mano."""

    texto = forms.CharField(
        widget=forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 4, "placeholder": "Qué han contestado…"}),
    )
    fecha = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input input-bordered input-sm w-full"}),
        help_text=_("Cuándo contestaron; en blanco, ahora"),
    )
    canal = forms.ChoiceField(
        choices=Comunicacion.Canal.choices,
        initial=Comunicacion.Canal.CORREO,
        widget=forms.Select(attrs={"class": "select select-bordered select-sm w-full"}),
    )
    ticket_externo = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "input input-bordered input-sm w-full", "placeholder": "Nº de ticket, si lo dan"}),
    )


class CerrarDerivacionForm(forms.Form):
    resultado = forms.ChoiceField(
        choices=Derivacion.Resultado.choices,
        widget=forms.Select(attrs={"class": "select select-bordered select-sm w-full"}),
    )
    nota = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 2, "placeholder": "Cómo ha quedado (opcional)"}),
    )


class ServicioForm(forms.ModelForm):
    """Alta y edición de un servicio desde el panel, sin admin. El slug sale del nombre."""

    class Meta:
        model = Servicio
        fields = ["nombre", "modo", "que_va_aqui", "telefono", "correos", "url_formulario", "activo", "orden"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "input input-bordered w-full", "placeholder": "Electricista, Fontanería…"}),
            "modo": forms.RadioSelect(attrs={"class": "radio radio-sm"}),
            "que_va_aqui": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 3}),
            "telefono": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "correos": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "url_formulario": forms.URLInput(attrs={"class": "input input-bordered w-full"}),
            "activo": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "orden": forms.NumberInput(attrs={"class": "input input-bordered input-sm w-24"}),
        }
