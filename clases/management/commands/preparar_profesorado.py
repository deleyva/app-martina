"""Crea el grupo «Profesorado» y le da Wagtail, pero solo el índice musical.

**Por qué no vale un grupo de los que trae Wagtail.** `Editors` y `Moderators`
tienen `GroupPagePermission` sobre `Root`: meter ahí a un profesor no le da
«editar los libros», le da editar el sitio entero, incluidos los 228 artículos
importados de los 16 departamentos. Decisión del principal (2026-09-10): solo lo
que cuelga de «Índice de Recursos Musicales».

Es idempotente: se puede pasar tantas veces como haga falta.

    just production-command preparar_profesorado
    just production-command preparar_profesorado --pagina "Otro índice"
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from wagtail.models import GroupPagePermission, Page

from martina_bescos_app.users.permisos import GRUPO_PROFESORADO

PAGINA_POR_DEFECTO = "Índice de recursos musicales"

# Qué puede hacer un profesor en esa rama. `publish` va incluido a propósito: sin
# él tendría que pedirle a alguien que le publicara cada cambio, y entonces no es
# autonomía sino un trámite más.
PERMISOS_DE_PAGINA = ["add_page", "change_page", "publish_page"]


class Command(BaseCommand):
    help = "Crea el grupo Profesorado y le da Wagtail solo sobre el índice musical"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pagina",
            default=PAGINA_POR_DEFECTO,
            help="Título de la página raíz que podrán editar",
        )

    def handle(self, *args, **opciones):
        raiz = (
            Page.objects.filter(title__iexact=opciones["pagina"]).first()
            or Page.objects.filter(title__icontains="recursos musicales").first()
        )
        if raiz is None:
            self.stderr.write(
                self.style.ERROR(
                    f"No encuentro la página «{opciones['pagina']}». "
                    "Pásale --pagina con el título exacto."
                )
            )
            return

        grupo, creado = Group.objects.get_or_create(name=GRUPO_PROFESORADO)
        self.stdout.write(
            f"Grupo «{grupo.name}»: {'creado' if creado else 'ya existía'}"
        )

        # Entrar al panel de Wagtail. No es `is_staff`: son permisos distintos, y
        # ese es justamente el punto de todo esto.
        acceso = Permission.objects.filter(
            content_type__app_label="wagtailadmin", codename="access_admin"
        ).first()
        if acceso:
            grupo.permissions.add(acceso)
            self.stdout.write("  + acceso al panel de Wagtail (sin admin de Django)")

        for codename in PERMISOS_DE_PAGINA:
            permiso = Permission.objects.filter(
                content_type__app_label="wagtailcore", codename=codename
            ).first()
            if permiso is None:
                self.stderr.write(f"  ! no existe el permiso {codename}")
                continue
            _obj, nuevo = GroupPagePermission.objects.get_or_create(
                group=grupo, page=raiz, permission=permiso
            )
            self.stdout.write(
                f"  {'+' if nuevo else '='} {codename} sobre «{raiz.title}»"
            )

        # Lo que NO se toca, dicho en voz alta: cualquier permiso sobre Root
        # daría el sitio entero, y eso es justo lo que se está evitando.
        sobre_root = GroupPagePermission.objects.filter(
            group=grupo, page__depth=1
        ).count()
        if sobre_root:
            self.stderr.write(
                self.style.WARNING(
                    f"  ¡OJO! {sobre_root} permiso(s) de este grupo apuntan a la raíz "
                    "del árbol: eso da el sitio entero."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nListo. Quien acepte una invitación de profesorado podrá editar "
                f"lo que cuelga de «{raiz.title}», y nada más."
            )
        )
