from django import forms
from .models import MusicItem, Text, Category


class MusicItemForm(forms.ModelForm):
    class Meta:
        model = MusicItem
        fields = ["title", "tags"]  # Ajusta los campos según sea necesario


class TextForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea, label="ABC Notation")
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), required=True, label="Category"
    )

    class Meta:
        model = Text
        fields = ["name", "content", "copyrighted", "tags", "category"]
