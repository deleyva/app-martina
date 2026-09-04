import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()
from wagtail.images.models import Image
from taggit.models import Tag
print("Bebop tagged imgs:", Image.objects.filter(tags__name__iexact='bebop').count())
print("All taggit tags on Images:")
for img in Image.objects.filter(tags__isnull=False).distinct():
    print(img.title, list(img.tags.values_list('name', flat=True)))
