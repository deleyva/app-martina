# Escrita a mano el 2026-10-17.
#
# La gente firmaba el campo «¿Quién eres?» con el @ de las menciones («@secretaría»), con
# acentos, mayúsculas o el correo completo. Se dejan todos en la forma canónica que ahora
# aplica `usuario_normalizado` al guardar: `secretaria`, `conserjeria`, `sgonzalez`.
import unicodedata

from django.conf import settings
from django.db import migrations


def _normaliza(valor: str) -> str:
    """Copia de `incidencias.models.usuario_normalizado` en el momento de escribir la migración."""
    valor = (valor or "").strip().lstrip("@").strip()
    if not valor or any(ch.isspace() for ch in valor):
        return valor
    valor = unicodedata.normalize("NFD", valor.lower())
    valor = "".join(ch for ch in valor if unicodedata.category(ch) != "Mn")
    dominio = getattr(settings, "DEFAULT_USER_EMAIL_DOMAIN", "iesmartinabescos.es")
    if valor.endswith(f"@{dominio}"):
        valor = valor[: -len(dominio) - 1]
    return valor


def normalizar_usuarios(apps, schema_editor):
    for modelo, campo in (("Comentario", "autor_nombre"), ("Incidencia", "reportero_nombre")):
        Modelo = apps.get_model("incidencias", modelo)
        for obj in Modelo.objects.all():
            nuevo = _normaliza(getattr(obj, campo))
            if nuevo != getattr(obj, campo):
                setattr(obj, campo, nuevo)
                obj.save(update_fields=[campo])


class Migration(migrations.Migration):
    dependencies = [
        ("incidencias", "0010_etiquetas_vivas_referencias"),
    ]

    operations = [
        migrations.RunPython(normalizar_usuarios, migrations.RunPython.noop),
    ]
