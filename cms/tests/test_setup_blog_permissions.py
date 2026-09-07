"""El comando que reparte los permisos de los blogs de departamento.

El caso que motiva casi todo esto es el del 2026-09-07: grupos creados a mano
con TODOS los permisos de página y sin `wagtailadmin.access_admin`. La jefa de
Música no podía entrar en `/cms/` y no le salía el pajarito, y desde el panel
de grupos todo parecía correcto.
"""

from io import StringIO

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import (
    GroupApprovalTask,
    GroupPagePermission,
    Page,
    WorkflowPage,
)

from blogs.models import BlogIndexPage


class SetupBlogPermissionsTest(TestCase):
    def setUp(self):
        root = Page.objects.filter(depth=1).first()
        self.portada = BlogIndexPage(title="Blogs", slug="blogs-permisos-test")
        root.add_child(instance=self.portada)
        self.musica = BlogIndexPage(title="Música", slug="musica-permisos-test")
        self.portada.add_child(instance=self.musica)

    def _ejecutar(self, *args):
        salida = StringIO()
        call_command("setup_blog_permissions", *args, stdout=salida)
        return salida.getvalue()

    def _grupo(self, nombre):
        return Group.objects.get(name=nombre)

    def _codenames(self, grupo):
        return sorted(
            gp.permission.codename
            for gp in GroupPagePermission.objects.filter(group=grupo, page=self.musica)
        )

    # ── los grupos ────────────────────────────────────────────────────────

    def test_crea_los_dos_grupos_con_el_nombre_del_departamento(self):
        self._ejecutar()
        self._grupo("Jefe del departamento de Música")
        self._grupo("Profesores de Música")

    def test_el_jefe_publica_y_el_profesor_no(self):
        self._ejecutar()
        self.assertIn("publish_page", self._codenames(self._grupo("Jefe del departamento de Música")))
        self.assertNotIn("publish_page", self._codenames(self._grupo("Profesores de Música")))
        # Pero escribir, escriben los dos.
        for nombre in ("Jefe del departamento de Música", "Profesores de Música"):
            self.assertIn("add_page", self._codenames(self._grupo(nombre)))
            self.assertIn("change_page", self._codenames(self._grupo(nombre)))

    # ── el permiso del incidente ──────────────────────────────────────────

    def test_los_dos_grupos_pueden_entrar_al_panel(self):
        """Sin esto los permisos de página no sirven de nada."""
        self._ejecutar()
        acceso = Permission.objects.get(
            codename="access_admin", content_type__app_label="wagtailadmin"
        )
        for nombre in ("Jefe del departamento de Música", "Profesores de Música"):
            self.assertIn(acceso, self._grupo(nombre).permissions.all())

    def test_repara_un_grupo_hecho_a_mano_al_que_le_falta_el_acceso(self):
        """La situación exacta de producción: todo menos la puerta."""
        jefes = Group.objects.create(name="Jefe del departamento de Música")
        for codename in ("add_page", "change_page", "publish_page"):
            GroupPagePermission.objects.create(
                group=jefes,
                page=self.musica,
                permission=Permission.objects.get(
                    codename=codename, content_type__app_label="wagtailcore"
                ),
            )
        acceso = Permission.objects.get(
            codename="access_admin", content_type__app_label="wagtailadmin"
        )
        self.assertNotIn(acceso, jefes.permissions.all())

        self._ejecutar()

        jefes.refresh_from_db()
        self.assertIn(acceso, jefes.permissions.all())
        # Y no le ha quitado nada de lo que ya tenía.
        self.assertIn("publish_page", self._codenames(jefes))

    # ── quién aprueba ─────────────────────────────────────────────────────

    def test_el_que_aprueba_es_el_jefe_de_ese_departamento(self):
        self._ejecutar()
        tarea = GroupApprovalTask.objects.get(name="Aprobación: Música")
        self.assertEqual(
            [g.name for g in tarea.groups.all()],
            ["Jefe del departamento de Música"],
        )

    def test_la_revision_cuelga_del_departamento_no_de_la_raiz(self):
        """Wagtail coge el workflow del ancestro más cercano.

        Sin el `WorkflowPage` sobre el departamento, un artículo enviado a
        revisión acabaría en el workflow de la raíz y lo aprobaría otra gente.
        """
        self._ejecutar()
        enlace = WorkflowPage.objects.get(page=self.musica)
        self.assertEqual(enlace.workflow.name, "Revisión: Música")

    # ── se puede volver a lanzar ──────────────────────────────────────────

    def test_lanzarlo_dos_veces_no_cambia_nada_la_segunda(self):
        self._ejecutar()
        self.assertIn("Nada que cambiar", self._ejecutar())

    def test_dry_run_no_escribe(self):
        salida = self._ejecutar("--dry-run")
        self.assertIn("DRY-RUN", salida)
        self.assertFalse(
            Group.objects.filter(name="Jefe del departamento de Música").exists()
        )

    def test_avisa_de_los_permisos_que_el_no_reparte(self):
        """El caso de Filosofía: un permiso suelto que pinta menú de más."""
        from django.contrib.contenttypes.models import ContentType

        self._ejecutar()
        jefes = self._grupo("Jefe del departamento de Música")
        jefes.permissions.add(
            Permission.objects.get(
                codename="add_group",
                content_type=ContentType.objects.get_for_model(Group),
            )
        )

        salida = self._ejecutar()

        self.assertIn("auth.add_group", salida)
        self.assertIn("Jefe del departamento de Música", salida)
        # Avisa, pero no lo quita: quitar cosas no es su trabajo.
        jefes.refresh_from_db()
        self.assertIn("add_group", [p.codename for p in jefes.permissions.all()])
