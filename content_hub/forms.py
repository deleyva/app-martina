"""
Content Hub Forms - Quick Add and Management Forms
"""

from django import forms
from taggit.forms import TagField, TagWidget

from .models import ContentItem, ContentLink, Category


class QuickContentForm(forms.ModelForm):
    """
    Simplified form for rapid content ingestion.
    Auto-detects content type from input (URL vs file vs text).
    """

    tags = TagField(
        required=False,
        widget=TagWidget(attrs={
            "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
            "placeholder": "Separar con comas: jazz, piano, intermedio",
        }),
        help_text="Etiquetas separadas por comas",
    )

    class Meta:
        model = ContentItem
        fields = ["title", "url", "file", "text_content", "tags", "metadata"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Título del contenido",
                    "autofocus": True,
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "https://hooktheory.com/... o cualquier URL",
                }
            ),
            "file": forms.ClearableFileInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "accept": ".pdf,.mp3,.wav,.ogg,.jpg,.jpeg,.png,.gif,.mp4,.webm",
                }
            ),
            "text_content": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "rows": 4,
                    "placeholder": "Notas, código de embed, o contenido de texto...",
                }
            ),
            "metadata": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm",
                    "rows": 3,
                    "placeholder": '{"key": "C", "difficulty": 3}',
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        url = cleaned_data.get("url")
        file = cleaned_data.get("file")
        text_content = cleaned_data.get("text_content")

        # At least one content source required
        if not url and not file and not text_content:
            raise forms.ValidationError(
                "Debes proporcionar al menos una URL, archivo, o contenido de texto."
            )

        return cleaned_data


class ContentLinkForm(forms.ModelForm):
    """Form for creating links between ContentItems"""

    class Meta:
        model = ContentLink
        fields = ["target", "link_type", "notes"]
        widgets = {
            "target": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                }
            ),
            "link_type": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "rows": 2,
                    "placeholder": "Contexto del enlace (opcional)",
                }
            ),
        }


class AuthorContentForm(forms.ModelForm):
    """Specialized form for creating Author content items"""

    birth_year = forms.IntegerField(
        required=False,
        min_value=1000,
        max_value=2100,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "1685",
            }
        ),
    )
    death_year = forms.IntegerField(
        required=False,
        min_value=1000,
        max_value=2100,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "1750",
            }
        ),
    )
    nationality = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "Alemán",
            }
        ),
    )
    tags = TagField(required=False)

    class Meta:
        model = ContentItem
        fields = ["title", "text_content", "tags"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "Johann Sebastian Bach",
                }
            ),
            "text_content": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "rows": 4,
                    "placeholder": "Biografía breve...",
                }
            ),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.content_type = ContentItem.ContentType.AUTHOR
        instance.metadata = {
            "birth_year": self.cleaned_data.get("birth_year"),
            "death_year": self.cleaned_data.get("death_year"),
            "nationality": self.cleaned_data.get("nationality"),
        }
        # Remove None values
        instance.metadata = {k: v for k, v in instance.metadata.items() if v is not None}
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SongContentForm(forms.ModelForm):
    """Specialized form for creating Song content items"""

    key = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "C mayor",
            }
        ),
    )
    tempo = forms.IntegerField(
        required=False,
        min_value=20,
        max_value=300,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "120",
            }
        ),
    )
    time_signature = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "4/4",
            }
        ),
    )
    difficulty = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "1-5",
            }
        ),
    )
    author = forms.ModelChoiceField(
        queryset=ContentItem.objects.filter(
            content_type=ContentItem.ContentType.AUTHOR,
            is_archived=False,
        ),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
            }
        ),
    )
    tags = TagField(required=False)

    class Meta:
        model = ContentItem
        fields = ["title", "url", "file", "text_content", "tags"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "Preludio en C Mayor BWV 846",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "URL de referencia (opcional)",
                }
            ),
            "file": forms.ClearableFileInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                }
            ),
            "text_content": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "rows": 3,
                    "placeholder": "Notas sobre la pieza...",
                }
            ),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.content_type = ContentItem.ContentType.SONG
        instance.metadata = {
            "key": self.cleaned_data.get("key"),
            "tempo": self.cleaned_data.get("tempo"),
            "time_signature": self.cleaned_data.get("time_signature"),
            "difficulty": self.cleaned_data.get("difficulty"),
        }
        # Remove None values
        instance.metadata = {k: v for k, v in instance.metadata.items() if v is not None}
        if commit:
            instance.save()
            self.save_m2m()
            # Create link to author if provided
            author = self.cleaned_data.get("author")
            if author:
                ContentLink.objects.get_or_create(
                    source=instance,
                    target=author,
                    link_type=ContentLink.LinkType.CREATED_BY,
                )
        return instance


class CategoryForm(forms.ModelForm):
    """Form for managing categories"""

    class Meta:
        model = Category
        fields = ["name", "parent", "description", "icon", "order"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "Nombre de la categoría",
                }
            ),
            "parent": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "rows": 2,
                }
            ),
            "icon": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "🎵",
                }
            ),
            "order": forms.NumberInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                }
            ),
        }


class ContentSearchForm(forms.Form):
    """Form for searching content"""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "Buscar contenido...",
            }
        ),
    )
    content_type = forms.ChoiceField(
        choices=[("", "Todos los tipos")] + list(ContentItem.ContentType.choices),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
            }
        ),
    )
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                "placeholder": "Filtrar por tags (separados por coma)",
            }
        ),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="Todas las categorías",
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
            }
        ),
    )
