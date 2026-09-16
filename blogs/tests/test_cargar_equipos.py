"""Repartir al claustro en los blogs a partir de las listas del centro.

Lo que tiene que ser verdad (fase 35): el jefe publica, el profesor escribe y
envía a revisión, nadie escribe fuera de su departamento, y quien aún no ha
entrado nunca aterriza en su usuario precreado al entrar con Google.
"""

from io import StringIO

from allauth.account.models import EmailAddress
from allauth.core.context import request_context
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import RequestFactory
from django.test import TestCase
from wagtail.models import Collection
from wagtail.models import GroupCollectionPermission
from wagtail.models import Page

from blogs.listas_centro import leer_tabla
from blogs.models import BlogIndexPage
from martina_bescos_app.users.adapters import SocialAccountAdapter

User = get_user_model()

DEPARTAMENTOS = """
INSERT INTO `DepartamentosInstituto` (`Id`, `Nombre`, `JefeDpto`) VALUES
(7, 'FILOSOFÍA', 'Ana  Pérez Ruiz'),
(15, 'MÚSICA', 'Luis Gil'),
(17, 'INSTALACIONES ELECTROTÉCNICAS', 'Marta Sanz'),
(99, 'DEPARTAMENTO FANTASMA', 'Nadie');
"""

PROFESORADO = """
INSERT INTO `DepartamentosProfesorado` (`IdProfesorado`, `NombreCompletoProfesor`, `Departamento`) VALUES
(1, 'ANA PEREZ RUIZ', 'FILOSOFÍA'),
(2, 'PEDRO O\\'NEILL', 'FILOSOFÍA'),
(3, 'M. ROSA LOPEZ', 'FILOSOFÍA'),
(33, 'Rosa López', 'FILOSOFÍA'),
(4, 'LUIS GIL', 'MÚSICA'),
(5, 'EVA MORA', 'MÚSICA'),
(6, 'MARTA SANZ', 'INSTALACIONES ELECTROTÉCNICAS'),
(7, 'JUAN VIDAL', 'INSTALACIONES ELECTROTÉCNICAS');
"""

# La 3 y la 33 son la misma persona con dos fichas y un solo correo: pasa de
# verdad en las listas del centro (cinco casos el 2026-09-16).
CUENTAS = """
INSERT INTO `CuentasGoogle` (`Id`, `given_name`, `family_name`, `NombreCompleto`, `email`) VALUES
(1, 'Ana', 'Pérez Ruiz', 'Ana Pérez Ruiz', 'aperez@iesmartinabescos.es'),
(2, 'Pedro', 'O''Neill', 'Pedro O''Neill', 'poneill@iesmartinabescos.es'),
(3, 'María Rosa', 'López', 'María Rosa López', 'rlopez@iesmartinabescos.es'),
(33, 'Rosa', 'López', 'Rosa López', 'RLopez@iesmartinabescos.es'),
(4, 'Luis', 'Gil', 'Luis Gil', 'lgil@iesmartinabescos.es'),
(5, 'Eva', 'Mora', 'Eva Mora', 'emora@iesmartinabescos.es'),
(6, 'Marta', 'Sanz', 'Marta Sanz', 'msanz@iesmartinabescos.es'),
(7, 'Juan', 'Vidal', 'Juan Vidal', 'jvidal@iesmartinabescos.es');
"""


class LeerTablaTest(TestCase):
    def test_comillas_escapadas_de_las_dos_formas_y_comas_dentro(self):
        texto = (
            "INSERT INTO `T` (`a`, `b`, `c`) VALUES\n"
            "(1, 'O\\'Neill, Pedro (tutor)', NULL),\n"
            "(2, 'O''Neill', '');\n"
            "INSERT INTO `Otra` (`a`) VALUES (9);\n"
        )
        self.assertEqual(
            leer_tabla(texto, "T"),
            [
                {"a": "1", "b": "O'Neill, Pedro (tutor)", "c": None},
                {"a": "2", "b": "O'Neill", "c": ""},
            ],
        )


class CargarEquiposBlogsTest(TestCase):
    def setUp(self):
        root = Page.objects.filter(depth=1).first()
        self.portada = BlogIndexPage(title="Blogs", slug="blogs-equipos-test")
        root.add_child(instance=self.portada)
        self.filosofia = BlogIndexPage(title="Filosofía", slug="filosofia-equipos")
        self.portada.add_child(instance=self.filosofia)
        self.musica = BlogIndexPage(title="Música", slug="musica-equipos")
        self.portada.add_child(instance=self.musica)
        Collection.get_first_root_node().add_child(name="Blogs")
        # Sin la fila de Google, `connect()` no encuentra el proveedor al avisar
        # por correo (gotcha ya anotado en el ISA, fase de wifi).
        app, _ = SocialApp.objects.get_or_create(
            provider="google", defaults={"name": "Google", "client_id": "x", "secret": "x"}
        )
        app.sites.add(Site.objects.get_current())

        import tempfile
        from pathlib import Path

        self.dir = Path(tempfile.mkdtemp())
        for nombre, contenido in (
            ("dep.sql", DEPARTAMENTOS),
            ("prof.sql", PROFESORADO),
            ("cuentas.sql", CUENTAS),
        ):
            (self.dir / nombre).write_text(contenido, encoding="utf-8")

    def _cargar(self, *extra):
        salida = StringIO()
        call_command(
            "cargar_equipos_blogs",
            "--departamentos", str(self.dir / "dep.sql"),
            "--profesorado", str(self.dir / "prof.sql"),
            "--cuentas", str(self.dir / "cuentas.sql"),
            *extra,
            stdout=salida,
        )
        return salida.getvalue()

    def _correos(self, grupo):
        return sorted(Group.objects.get(name=grupo).user_set.values_list("email", flat=True))

    def _dept(self, titulo):
        return BlogIndexPage.objects.child_of(self.portada).get(title=titulo)

    # ── el reparto ────────────────────────────────────────────────────────

    def test_jefe_a_su_grupo_y_el_resto_a_profesores_sin_repetir_al_jefe(self):
        self._cargar()
        self.assertEqual(
            self._correos("Jefe del departamento de Filosofía"),
            ["aperez@iesmartinabescos.es"],
        )
        # Ana es jefa: no va además a profesores. Rosa, con dos fichas, una vez.
        self.assertEqual(
            self._correos("Profesores de Filosofía"),
            ["poneill@iesmartinabescos.es", "rlopez@iesmartinabescos.es"],
        )
        self.assertEqual(self._correos("Profesores de Música"), ["emora@iesmartinabescos.es"])

    def test_departamento_sin_mapeo_se_avisa_y_no_se_inventa(self):
        salida = self._cargar()
        self.assertIn("DEPARTAMENTO FANTASMA", salida)
        self.assertFalse(Group.objects.filter(name__icontains="fantasma").exists())

    def test_crea_el_blog_que_falta_completo(self):
        self._cargar()
        nuevo = self._dept("Instalaciones Electrotécnicas")
        self.assertTrue(nuevo.live)
        coleccion = Collection.objects.get(name="Instalaciones Electrotécnicas")
        codenames = set(
            GroupCollectionPermission.objects.filter(
                group__name="Profesores de Instalaciones Electrotécnicas",
                collection=coleccion,
            ).values_list("permission__codename", flat=True)
        )
        self.assertIn("add_image", codenames)
        self.assertIn("add_document", codenames)
        self.assertEqual(
            self._correos("Profesores de Instalaciones Electrotécnicas"),
            ["jvidal@iesmartinabescos.es"],
        )

    # ── lo que puede hacer cada uno ───────────────────────────────────────

    def test_el_profesor_escribe_pero_no_publica_y_el_jefe_si(self):
        self._cargar()
        profe = User.objects.get(email="poneill@iesmartinabescos.es")
        jefa = User.objects.get(email="aperez@iesmartinabescos.es")

        permisos_profe = self.filosofia.permissions_for_user(profe)
        self.assertTrue(permisos_profe.can_add_subpage())
        self.assertTrue(permisos_profe.can_edit())
        self.assertFalse(permisos_profe.can_publish())
        self.assertFalse(permisos_profe.can_publish_subpage())

        permisos_jefa = self.filosofia.permissions_for_user(jefa)
        self.assertTrue(permisos_jefa.can_publish())
        self.assertTrue(permisos_jefa.can_publish_subpage())

    def test_nadie_escribe_fuera_de_su_departamento(self):
        self._cargar()
        profe = User.objects.get(email="poneill@iesmartinabescos.es")
        self.assertFalse(self.musica.permissions_for_user(profe).can_add_subpage())
        self.assertFalse(self.portada.permissions_for_user(profe).can_add_subpage())

    # ── los que aún no han entrado ────────────────────────────────────────

    def test_precrea_sin_contrasena_y_con_correo_verificado(self):
        self._cargar()
        juan = User.objects.get(email="jvidal@iesmartinabescos.es")
        self.assertFalse(juan.has_usable_password())
        self.assertFalse(juan.is_staff)
        self.assertEqual(juan.name, "Juan Vidal")
        self.assertTrue(
            EmailAddress.objects.filter(user=juan, verified=True, primary=True).exists()
        )

    def test_al_entrar_con_google_cae_en_el_usuario_precreado(self):
        self._cargar()
        precreado = User.objects.get(email="poneill@iesmartinabescos.es")

        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        sociallogin = SocialLogin(
            user=User(email="poneill@iesmartinabescos.es"),
            account=SocialAccount(
                provider="google",
                uid="1234567890",
                extra_data={
                    "email": "poneill@iesmartinabescos.es",
                    "given_name": "Pedro José",
                    "family_name": "O'Neill Martín",
                    "name": "Pedro José O'Neill Martín",
                },
            ),
        )
        # En una petición real el middleware de allauth fija este contexto;
        # sin él, `connect()` revienta al avisar por correo y el adaptador se
        # traga la excepción.
        with request_context(request):
            SocialAccountAdapter().pre_social_login(request, sociallogin)

        self.assertEqual(sociallogin.user.pk, precreado.pk)
        # El nombre de la gestión del centro lo machaca el de Google.
        precreado.refresh_from_db()
        self.assertEqual(precreado.name, "Pedro José O'Neill Martín")
        self.assertEqual(precreado.first_name, "Pedro José")
        self.assertEqual(precreado.last_name, "O'Neill Martín")
        self.assertEqual(User.objects.filter(email__iexact=precreado.email).count(), 1)
        self.assertTrue(
            precreado.groups.filter(name="Profesores de Filosofía").exists()
        )

    def test_no_duplica_a_quien_ya_existe_aunque_cambien_mayusculas(self):
        existente = User.objects.create(email="LGil@iesmartinabescos.es", name="Luis")
        self._cargar()
        self.assertEqual(User.objects.filter(email__iexact="lgil@iesmartinabescos.es").count(), 1)
        self.assertTrue(existente.groups.filter(name="Jefe del departamento de Música").exists())

    # ── pasar dos veces, en seco, y los sobrantes ─────────────────────────

    def test_idempotente(self):
        self._cargar()
        self.assertIn("se cambió 0 cosa(s)", self._cargar())

    def test_dry_run_no_deja_rastro(self):
        usuarios = User.objects.count()
        self._cargar("--dry-run")
        self.assertEqual(User.objects.count(), usuarios)
        self.assertFalse(
            BlogIndexPage.objects.filter(title="Instalaciones Electrotécnicas").exists()
        )

    def test_sobrante_se_avisa_y_solo_se_quita_si_se_pide(self):
        self._cargar()
        intruso = User.objects.create(email="prueba@iesmartinabescos.es", name="Prueba")
        Group.objects.get(name="Jefe del departamento de Música").user_set.add(intruso)

        self.assertIn("Prueba está en «Jefe del departamento de Música»", self._cargar())
        self.assertIn(intruso, Group.objects.get(name="Jefe del departamento de Música").user_set.all())

        self._cargar("--quitar-sobrantes")
        self.assertNotIn(intruso, Group.objects.get(name="Jefe del departamento de Música").user_set.all())

    def test_en_cada_entrada_con_google_se_refresca_el_nombre(self):
        """Usuario ya vinculado: Google sigue mandando en entradas posteriores."""
        usuario = User.objects.create(email="eva@iesmartinabescos.es", name="EVA MORA")
        SocialAccount.objects.create(
            user=usuario, provider="google", uid="555", extra_data={}
        )
        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        sociallogin = SocialLogin(
            user=User(email="eva@iesmartinabescos.es"),
            account=SocialAccount(
                provider="google",
                uid="555",
                extra_data={"email": "eva@iesmartinabescos.es", "given_name": "Eva", "family_name": "Mora Sánchez"},
            ),
        )
        sociallogin.lookup()
        SocialAccountAdapter().pre_social_login(request, sociallogin)

        usuario.refresh_from_db()
        self.assertEqual(usuario.name, "Eva Mora Sánchez")
        self.assertEqual(usuario.last_name, "Mora Sánchez")
