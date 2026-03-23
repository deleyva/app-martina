import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()
from taggit.models import Tag
from cms.models import MusicTag
from wagtail.documents.models import Document
print("Taggit tags:", list(Tag.objects.values_list('name', flat=True)))
print("MusicTag tags:", list(MusicTag.objects.values_list('name', flat=True)))
print("Doc tags:", list(Document.objects.filter(tags__isnull=False).distinct().values_list('title', flat=True)))
