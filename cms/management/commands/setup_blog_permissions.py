"""Permisos y flujo de revisión de los blogs de departamento.

Dos grupos por departamento, con los nombres que ya existen en el centro:

    Jefe del departamento de <Departamento>   escribe y PUBLICA
    Profesores de <Departamento>              escribe y ENVÍA A REVISIÓN

El nombre sale del título de la página, así que «Música» da «Jefe del
departamento de Música». Es la convención que ya estaba puesta a mano en
producción; el comando la adopta en vez de inventar grupos nuevos.

El permiso que se olvida siempre
--------------------------------
Los permisos de página NO abren el panel. Un grupo puede tener `add_page`,
`change_page` y `publish_page` sobre su departamento y aun así estrellarse
contra la puerta de `/cms/`, porque para entrar hace falta
`wagtailadmin.access_admin`, que es un permiso de Django, no de página.

Pasó de verdad el 2026-09-07: 32 de 36 grupos lo tenían todo menos eso. La
jefa de Música no podía editar ni le salía el pajarito de Wagtail, y los dos
síntomas eran el mismo fallo. Por eso este comando lo concede SIEMPRE, y por
eso hay un test que lo comprueba.

Quién aprueba
-------------
El jefe de departamento. Cada departamento recibe su propio workflow con una
`GroupApprovalTask` cuyo grupo aprobador es el de jefes, enganchado a la página
del departamento. Eso importa: Wagtail busca el workflow en el ancestro más
cercano, así que sin ese `WorkflowPage` los artículos caerían en el «Moderators
approval» que Wagtail trae de fábrica colgado de la raíz, y el visto bueno se
lo pediría al grupo Moderators en vez de al jefe.

Permisos de más
---------------
El comando no quita nada nunca, pero sí AVISA cuando un grupo tiene permisos
de Django que él no reparte. Importa porque Wagtail construye el menú lateral
a partir de los permisos: un `auth.add_group` suelto hace aparecer «Grupos» en
Ajustes, y un `cms.add_externalresource` hace aparecer «Fragmentos». Los dos
llevan a una pantalla que luego rechaza al usuario con un aviso rojo, porque
para ver el listado hacen falta más permisos que para crear.

Pasó en Filosofía: 17 de los 18 grupos de jefe tenían exactamente
`wagtailadmin.access_admin`, y ese tenía dos permisos más de una prueba
anterior. El resultado eran dos puertas pintadas en la pared del panel.

El comando es idempotente y NUNCA quita nada: solo añade lo que falte y avisa.
Ejecutar: `just manage setup_blog_permissions` (o con `--dry-run`).
"""

from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from wagtail.models import GroupApprovalTask
from wagtail.models import GroupPagePermission
from wagtail.models import Page
from wagtail.models import Workflow
from wagtail.models import WorkflowPage
from wagtail.models import WorkflowTask

from blogs.models import BlogIndexPage

# Quien manda en el departamento: escribe, publica y da el visto bueno.
PERMISOS_JEFE = ["add_page", "change_page", "publish_page", "lock_page", "unlock_page"]

# Quien escribe: sin `publish_page`, así que el botón dice «Enviar a revisión».
PERMISOS_PROFESOR = ["add_page", "change_page"]


def _permiso(codename, app_label="wagtailcore"):
    return Permission.objects.get(codename=codename, content_type__app_label=app_label)


class Command(BaseCommand):
    help = (
        "Crea los grupos de jefe y profesores de cada departamento, les da "
        "acceso al panel y monta el flujo de revisión. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Enseña lo que haría sin tocar la base de datos.",
        )

    def handle(self, *args, **options):
        self.seco = options["dry_run"]
        if self.seco:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se escribe nada.\n"))

        portada = self._encontrar_portada()
        if portada is None:
            self.stdout.write(
                self.style.ERROR(
                    "No hay portada de blogs (un BlogIndexPage con departamentos colgando)."
                )
            )
            return

        departamentos = BlogIndexPage.objects.child_of(portada).live()
        self.stdout.write(
            f"Portada «{portada.title}» con {departamentos.count()} departamentos\n"
        )

        self.acceso = _permiso("access_admin", app_label="wagtailadmin")
        cambios = 0

        for dept in departamentos:
            self.stdout.write(f"\n── {dept.title} ──")
            jefes = self._grupo(f"Jefe del departamento de {dept.title}")
            profes = self._grupo(f"Profesores de {dept.title}")

            cambios += self._dar_acceso_al_panel(jefes)
            cambios += self._dar_acceso_al_panel(profes)
            cambios += self._dar_permisos_de_pagina(jefes, dept, PERMISOS_JEFE)
            cambios += self._dar_permisos_de_pagina(profes, dept, PERMISOS_PROFESOR)
            cambios += self._montar_revision(dept, jefes)

        self._avisar_de_permisos_de_mas(departamentos)

        if self.seco:
            # En seco no se cuenta: montar una revisión son cinco objetos y
            # aquí se anuncia como una línea. Dar un número redondo sería
            # inventárselo, así que se remite a la lista de arriba.
            final = "Nada que cambiar." if not cambios else "Acciones listadas arriba."
        else:
            final = "Nada que cambiar." if not cambios else f"{cambios} cambios."
        self.stdout.write(self.style.SUCCESS(f"\n{final}"))

    def _avisar_de_permisos_de_mas(self, departamentos):
        """Permisos de Django que este comando no reparte.

        No se tocan: quitarlos podría cargarse algo que se dio a propósito. Lo
        que hace falta es que se VEAN, porque desde el panel de grupos no se
        distingue un grupo con un permiso de más de uno normal, y el síntoma
        aparece muy lejos: una entrada de menú que rechaza a quien la pulsa.
        """
        esperado = {"wagtailadmin.access_admin"}
        sobrantes = []
        for dept in departamentos:
            for plantilla in ("Jefe del departamento de {}", "Profesores de {}"):
                nombre = plantilla.format(dept.title)
                grupo = AuthGroup.objects.filter(name=nombre).first()
                if not grupo:
                    continue
                extra = {
                    f"{p.content_type.app_label}.{p.codename}"
                    for p in grupo.permissions.all()
                } - esperado
                if extra:
                    sobrantes.append((nombre, sorted(extra)))

        if not sobrantes:
            return
        self.stdout.write(
            self.style.WARNING(
                "\nGrupos con permisos que este comando no reparte "
                "(no se tocan; míralos por si pintan puertas de más en el menú):"
            )
        )
        for nombre, extra in sobrantes:
            self.stdout.write(self.style.WARNING(f"  {nombre}: {', '.join(extra)}"))

    # ── piezas ────────────────────────────────────────────────────────────

    def _encontrar_portada(self):
        for bip in BlogIndexPage.objects.all():
            if Page.objects.child_of(bip).type(BlogIndexPage).exists():
                return bip
        return None

    def _grupo(self, nombre):
        grupo = AuthGroup.objects.filter(name=nombre).first()
        if grupo:
            return grupo
        if self.seco:
            self.stdout.write(f"  crearía grupo: {nombre}")
            return AuthGroup(name=nombre)
        grupo = AuthGroup.objects.create(name=nombre)
        self.stdout.write(self.style.SUCCESS(f"  grupo creado: {nombre}"))
        return grupo

    def _dar_acceso_al_panel(self, grupo):
        """El permiso sin el cual los de página no sirven de nada."""
        if grupo.pk and self.acceso in grupo.permissions.all():
            return 0
        if self.seco:
            self.stdout.write(f"  daría acceso al panel: {grupo.name}")
            return 1
        grupo.permissions.add(self.acceso)
        self.stdout.write(self.style.SUCCESS(f"  acceso al panel: {grupo.name}"))
        return 1

    def _dar_permisos_de_pagina(self, grupo, dept, codenames):
        cambios = 0
        for codename in codenames:
            permiso = _permiso(codename)
            if grupo.pk and GroupPagePermission.objects.filter(
                group=grupo, page=dept, permission=permiso
            ).exists():
                continue
            if self.seco:
                self.stdout.write(f"  daría {codename} a {grupo.name}")
                cambios += 1
                continue
            GroupPagePermission.objects.create(
                group=grupo, page=dept, permission=permiso
            )
            self.stdout.write(self.style.SUCCESS(f"  {codename}: {grupo.name}"))
            cambios += 1
        return cambios

    def _montar_revision(self, dept, jefes):
        """Un workflow por departamento, aprobado por su jefe."""
        nombre_wf = f"Revisión: {dept.title}"
        nombre_tarea = f"Aprobación: {dept.title}"

        if self.seco:
            falta = not WorkflowPage.objects.filter(page=dept).exists()
            if falta:
                self.stdout.write(f"  montaría la revisión: {nombre_wf}")
            return 1 if falta else 0

        cambios = 0
        workflow, creado = Workflow.objects.get_or_create(
            name=nombre_wf, defaults={"active": True}
        )
        cambios += int(creado)

        tarea, creada = GroupApprovalTask.objects.get_or_create(
            name=nombre_tarea, defaults={"active": True}
        )
        cambios += int(creada)
        if jefes not in tarea.groups.all():
            tarea.groups.add(jefes)
            cambios += 1

        _, enlazada = WorkflowTask.objects.get_or_create(
            workflow=workflow, task=tarea, defaults={"sort_order": 0}
        )
        cambios += int(enlazada)

        _, asignada = WorkflowPage.objects.get_or_create(workflow=workflow, page=dept)
        cambios += int(asignada)

        if cambios:
            self.stdout.write(self.style.SUCCESS(f"  revisión: {nombre_wf}"))
        return cambios
