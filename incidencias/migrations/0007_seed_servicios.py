# ruff: noqa: E501
"""Semilla de servicios: la tabla «¿A quién va cada incidencia tecnológica?» de BookStack.

Idempotente por slug: un despliegue repetido no duplica. La inversa borra solo
estos slugs y solo los que no tengan derivaciones, porque en cuanto se despliega
el admin pasa a ser la fuente y secretaría editará contactos.
"""

from django.db import migrations

SERVICIOS = [
    {
        "slug": "hardware-software-4100",
        "nombre": "Hardware y software (4100)",
        "que_va_aqui": "Ordenadores que no arrancan, pantallas digitales, proyectores, cables y conexiones, periféricos (teclado, ratón), instalación o problemas de software en equipos del centro. Escribe secretaría desde el correo corporativo.",
        "correos": "4100@aragon.es, mantenimiento@educa.aragon.es",
        "telefono": "976 715 555",
        "url_formulario": "https://ast.service-now.com/esc",
        "orden": 10,
    },
    {
        "slug": "redes-y-conectividad",
        "nombre": "Redes y conectividad",
        "que_va_aqui": "Sin internet en un aula o departamento, WiFi que no llega o se cae, tomas de red, electrónica de red.",
        "correos": "eduinf.zaragoza@aragon.es, sigad.zaragoza@educa.aragon.es",
        "telefono": "976 716 407",
        "url_formulario": "",
        "orden": 20,
    },
    {
        "slug": "equipamiento-servicio-provincial",
        "nombre": "Necesidad de equipamiento (Servicio Provincial)",
        "que_va_aqui": "Peticiones de equipos nuevos o reposición: ordenadores, pantallas, carros de portátiles.",
        "correos": "eduinf.zaragoza@aragon.es, sigad.zaragoza@educa.aragon.es",
        "telefono": "976 716 407",
        "url_formulario": "",
        "orden": 30,
    },
    {
        "slug": "vitalinux",
        "nombre": "Vitalinux",
        "que_va_aqui": "Equipos con Vitalinux: instalación, postinstalación, Epoptes, paquetes que no se actualizan, impresoras desde Vitalinux.",
        "correos": "",
        "telefono": "",
        "url_formulario": "https://soporte.vitalinux.educa.aragon.es/",
        "orden": 40,
    },
    {
        "slug": "catedu-plataformas",
        "nombre": "Plataformas y CATEDU",
        "que_va_aqui": "Aeducar, Moodle, webs del centro alojadas en CATEDU y sus servicios.",
        "correos": "soportecatedu@educa.aragon.es",
        "telefono": "",
        "url_formulario": "",
        "orden": 50,
    },
    {
        "slug": "ast-correo-corporativo",
        "nombre": "AST — correo corporativo",
        "que_va_aqui": "Problemas con el correo corporativo @educa.aragon.es y cuentas de la DGA.",
        "correos": "",
        "telefono": "976 74 100 (ext. 814100)",
        "url_formulario": "https://ast.aragon.es/",
        "orden": 60,
    },
    {
        "slug": "gestion-de-residuos",
        "nombre": "Gestión de residuos",
        "que_va_aqui": "Retirada de equipos informáticos obsoletos o rotos.",
        "correos": "",
        "telefono": "",
        "url_formulario": "https://ast.service-now.com/esc",
        "orden": 70,
    },
    {
        "slug": "ciberseguridad",
        "nombre": "Ciberseguridad (INCIBE / OSI / CCN)",
        "que_va_aqui": "Incidentes de seguridad: suplantación, malware, fugas de datos.",
        "correos": "",
        "telefono": "",
        "url_formulario": "https://www.incibe.es/",
        "orden": 80,
    },
    {
        "slug": "servicio-tecnico-fotocopiadoras",
        "nombre": "Servicio técnico de fotocopiadoras",
        "que_va_aqui": "Fotocopiadoras e impresoras de alquiler: atascos, rayas, tóner. Avisa secretaría. Contactos por rellenar.",
        "correos": "",
        "telefono": "",
        "url_formulario": "",
        "orden": 90,
    },
]


def sembrar(apps, schema_editor):
    Servicio = apps.get_model("incidencias", "Servicio")
    for fila in SERVICIOS:
        datos = dict(fila)
        slug = datos.pop("slug")
        Servicio.objects.get_or_create(slug=slug, defaults=datos)


def retirar(apps, schema_editor):
    Servicio = apps.get_model("incidencias", "Servicio")
    slugs = [s["slug"] for s in SERVICIOS]
    Servicio.objects.filter(slug__in=slugs, derivaciones__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidencias", "0006_servicio_derivacion_comunicacion_incidencia_ambito"),
    ]

    operations = [
        migrations.RunPython(sembrar, retirar),
    ]
