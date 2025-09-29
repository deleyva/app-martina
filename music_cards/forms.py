from django import forms
from .models import MusicItem, Text, Category, Tag, File, Embed


class MusicItemForm(forms.ModelForm):
    class Meta:
        model = MusicItem
        fields = ["title", "visibility", "is_template"]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Nombre del elemento musical'
            }),
            'visibility': forms.Select(attrs={
                'class': 'select select-bordered w-full'
            }),
            'is_template': forms.CheckboxInput(attrs={
                'class': 'checkbox checkbox-primary'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['visibility'].required = True


class TextForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea, label="ABC Notation")
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), required=True, label="Category"
    )

    class Meta:
        model = Text
        fields = ["name", "content", "copyrighted", "tags", "category"]
