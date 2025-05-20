from allauth.socialaccount.providers import registry

print("\n=== Proveedores registrados en allauth ===")
providers = registry.get_list()
for provider in providers:
    print(f"ID: {provider.id}, Nombre: {provider.name}")

print("\n=== Configuración del proveedor Google ===")
google_provider = registry.by_id('google', None)
if google_provider:
    print(f"ID: {google_provider.id}")
    print(f"Nombre: {google_provider.name}")
    print(f"Paquete: {google_provider.package}")
else:
    print("Proveedor Google no encontrado")
