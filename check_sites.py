import os
import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.contrib.sites.models import Site as DjangoSite
from wagtail.models import Site as WagtailSite

print("\n--- Django Sites (django.contrib.sites) ---")
for s in DjangoSite.objects.all():
    print(f"ID: {s.id} | Domain: {s.domain} | Name: {s.name}")

print("\n--- Wagtail Sites (wagtail.models.Site) ---")
for s in WagtailSite.objects.all():
    print(f"ID: {s.id} | Hostname: {s.hostname} | Port: {s.port} | Root Page: {s.root_page}")
