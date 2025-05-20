from allauth.socialaccount.providers import registry

print("\n=== Proveedores registrados en allauth ===")
for provider_class in registry.get_class_list():
    print(f"ID: {provider_class.id}, Nombre: {provider_class.name}")

print("\n=== Configuración del proveedor Google ===")
google_provider_class = registry.get_class('google')
if google_provider_class:
    print(f"ID: {google_provider_class.id}")
    print(f"Nombre: {google_provider_class.name}")
    print(f"Paquete: {google_provider_class.package}")
else:
    print("Proveedor Google no encontrado")
    
print("\n=== Variables de contexto en la plantilla ===")
from django.template import Context, Template
from allauth.socialaccount import providers
from allauth.socialaccount.templatetags.socialaccount import get_providers

template = Template('{% load socialaccount %}{% get_providers as socialaccount_providers %}{{ socialaccount_providers|length }}')
context = Context({})
print(f"Número de proveedores en la plantilla: {template.render(context)}")
