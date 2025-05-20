from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

print("=== Sites configurados ===")
for site in Site.objects.all():
    print(f"ID: {site.id}, Domain: {site.domain}, Name: {site.name}")

print("\n=== Aplicaciones sociales configuradas ===")
for app in SocialApp.objects.all():
    print(f"ID: {app.id}, Provider: {app.provider}, Name: {app.name}")
    print(f"Client ID: {app.client_id}")
    print(f"Secret: {app.secret}")
    print("Sites asociados:")
    for site in app.sites.all():
        print(f"  - {site.domain} (ID: {site.id})")
    print("---")
