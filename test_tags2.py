import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()
from taggit.models import Tag, TaggedItem
for tag in Tag.objects.all():
    items = TaggedItem.objects.filter(tag=tag)
    if items.exists():
        content_types = set([item.content_type.model for item in items])
        print(f"Tag '{tag.name}': {content_types}")
