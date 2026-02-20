from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Adjunto
from .models import Comentario
from .models import Etiqueta
from .models import Incidencia
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
