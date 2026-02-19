import os
import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.contrib.sites.models import Site as DjangoSite
from wagtail.models import Site as WagtailSite

print("Syncing Wagtail Sites to Django Sites...")

wagtail_sites = WagtailSite.objects.all()
for ws in wagtail_sites:
    domain = ws.hostname
    name = ws.site_name or domain
    
    # Check if a Django Site exists with this domain
    if not DjangoSite.objects.filter(domain=domain).exists():
        print(f"Creating Django Site for {domain}...")
        DjangoSite.objects.create(domain=domain, name=name)
    else:
        print(f"Django Site for {domain} already exists.")

print("\n--- Current Django Sites ---")
for s in DjangoSite.objects.all():
    print(f"ID: {s.id} | Domain: {s.domain} | Name: {s.name}")
