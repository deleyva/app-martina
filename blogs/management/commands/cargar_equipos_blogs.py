"""Meter a cada profesor y a cada jefe en el grupo de su blog de departamento.

`setup_blog_permissions` monta la tubería —grupos, permisos, un workflow por
departamento aprobado por el jefe— pero no mete a nadie dentro. Este comando
reparte a la gente a partir de las listas de la gestión del centro:

    just manage cargar_equipos_blogs \\
        --departamentos DepartamentosInstituto.sql \\
        --profesorado DepartamentosProfesorado.sql \\
        --cuentas CuentasGoogle.sql [--dry-run]

Resultado, por departamento:

    Jefe del departamento de X   el jefe: escribe, PUBLICA y aprueba
    Profesores de X              el resto: escribe y ENVÍA A REVISIÓN

Quien aún no ha entrado nunca
-----------------------------
No existe como usuario, y sin usuario no hay grupo donde meterlo. Se precrea con
su correo del centro y SIN contraseña usable. Cuando entre con Google,
`SocialAccountAdapter.pre_social_login` busca un usuario con ese correo y le
engancha la cuenta de Google: cae en el usuario precreado, con sus grupos ya
puestos. Se le crea además la `EmailAddress` verificada, que es lo que allauth
mira con `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`; el correo es del dominio del
centro y lo verifica Google, así que no hay nada que verificar a mano.

Lo que NO hace
--------------
- No quita a nadie de un grupo, salvo con `--quitar-sobrantes`. Por defecto
  avisa: hay cuentas de prueba y jefes puestos a mano que no salen en las listas.
- No toca `is_staff` ni da permisos fuera de los blogs.
- No guarda las listas en ningún sitio: las lee y ya.

Es idempotente: la segunda pasada no cambia nada.
"""

from io import StringIO
from pathlib import Path

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction
from django.utils.text import slugify
from wagtail.models import Page

from blogs.listas_centro import SIGAD_A_BLOG
from blogs.listas_centro import leer_tabla
from blogs.listas_centro import normalizar
from blogs.models import BlogIndexPage

DOMINIO = "@iesmartinabescos.es"


class Command(BaseCommand):
    help = (
        "Mete a los profesores y jefes de cada departamento en los grupos de su "
        "blog a partir de las listas del centro. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument("--departamentos", required=True, type=Path)
        parser.add_argument("--profesorado", required=True, type=Path)
        parser.add_argument("--cuentas", required=True, type=Path)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hace todo dentro de una transacción y la deshace al final.",
        )
        parser.add_argument(
            "--quitar-sobrantes",
            action="store_true",
            help="Saca de los grupos a quien no sale en las listas.",
        )

    def handle(self, *args, **opciones):
        departamentos = self._leer(opciones["departamentos"], "DepartamentosInstituto")
        profesorado = self._leer(opciones["profesorado"], "DepartamentosProfesorado")
        cuentas = self._leer(opciones["cuentas"], "CuentasGoogle")

        self.cambios = 0
        self.problemas = []
        seco = opciones["dry_run"]
        if seco:
            self.stdout.write(self.style.WARNING("DRY-RUN: se deshace todo al final.\n"))

        with transaction.atomic():
            equipos = self._equipos(departamentos, profesorado, cuentas)
            portada = self._portada()
            for titulo in sorted(equipos):
                self._asegurar_departamento(portada, titulo)

            # La tubería de cada departamento, incluidos los recién creados.
            call_command("setup_blog_permissions", stdout=StringIO())

            for titulo in sorted(equipos):
                self._repartir(titulo, equipos[titulo], opciones["quitar_sobrantes"])

            if seco:
                transaction.set_rollback(True)

        for problema in self.problemas:
            self.stdout.write(self.style.WARNING(f"  ⚠ {problema}"))
        verbo = "cambiaría" if seco else "cambió"
        self.stdout.write(
            self.style.SUCCESS(f"\nListo: se {verbo} {self.cambios} cosa(s).")
        )

    # ── las listas ────────────────────────────────────────────────────────

    def _leer(self, ruta, tabla):
        if not ruta.exists():
            raise CommandError(f"No existe {ruta}")
        filas = leer_tabla(ruta.read_text(encoding="utf-8"), tabla)
        if not filas:
            raise CommandError(f"{ruta} no trae filas de la tabla `{tabla}`")
        return filas

    def _equipos(self, departamentos, profesorado, cuentas):
        """{título del blog: {"jefes": {correo: cuenta}, "profesores": {...}}}"""
        por_id = {c["Id"]: c for c in cuentas}
        por_nombre = {}
        for cuenta in cuentas:
            por_nombre.setdefault(normalizar(cuenta["NombreCompleto"]), []).append(cuenta)

        equipos = {}

        def equipo(sigad):
            titulo = SIGAD_A_BLOG.get((sigad or "").strip())
            if titulo is None:
                self.problemas.append(
                    f"Departamento «{sigad}» sin blog asignado en SIGAD_A_BLOG: se salta"
                )
                return None
            return equipos.setdefault(titulo, {"jefes": {}, "profesores": {}})

        for dep in departamentos:
            destino = equipo(dep["Nombre"])
            if destino is None or not (dep.get("JefeDpto") or "").strip():
                continue
            candidatas = por_nombre.get(normalizar(dep["JefeDpto"]), [])
            if len(candidatas) != 1:
                self.problemas.append(
                    f"Jefe de {dep['Nombre']} («{dep['JefeDpto']}»): "
                    f"{len(candidatas)} cuentas con ese nombre, no se elige ninguna"
                )
                continue
            cuenta = candidatas[0]
            destino["jefes"][cuenta["email"].strip().lower()] = cuenta

        for prof in profesorado:
            destino = equipo(prof["Departamento"])
            if destino is None:
                continue
            cuenta = por_id.get(prof["IdProfesorado"])
            if cuenta is None:
                self.problemas.append(
                    f"«{prof['NombreCompletoProfesor']}» sin cuenta de Google "
                    f"(IdProfesorado {prof['IdProfesorado']})"
                )
                continue
            destino["profesores"][cuenta["email"].strip().lower()] = cuenta

        # El jefe no va además al grupo de profesores de su propio departamento:
        # ya puede todo lo que pueden ellos.
        for destino in equipos.values():
            for correo in destino["jefes"]:
                destino["profesores"].pop(correo, None)
        return equipos

    # ── el sitio ──────────────────────────────────────────────────────────

    def _portada(self):
        for bip in BlogIndexPage.objects.all():
            if Page.objects.child_of(bip).type(BlogIndexPage).exists():
                return bip
        raise CommandError("No hay portada de blogs con departamentos colgando")

    def _asegurar_departamento(self, portada, titulo):
        if BlogIndexPage.objects.child_of(portada).filter(title=titulo).exists():
            return
        pagina = BlogIndexPage(title=titulo, slug=slugify(titulo))
        portada.add_child(instance=pagina)
        pagina.save_revision().publish()
        self.cambios += 1
        self.stdout.write(self.style.SUCCESS(f"Blog creado: {titulo}"))

    # ── la gente ──────────────────────────────────────────────────────────

    def _repartir(self, titulo, equipo, quitar_sobrantes):
        self.stdout.write(
            f"── {titulo}: {len(equipo['jefes'])} jefe(s), "
            f"{len(equipo['profesores'])} profesor(es)"
        )
        for nombre_grupo, gente in (
            (f"Jefe del departamento de {titulo}", equipo["jefes"]),
            (f"Profesores de {titulo}", equipo["profesores"]),
        ):
            grupo = Group.objects.get(name=nombre_grupo)
            deseados = set()
            for correo, cuenta in gente.items():
                usuario = self._usuario(correo, cuenta)
                if usuario is None:
                    continue
                deseados.add(usuario.pk)
                if not grupo.user_set.filter(pk=usuario.pk).exists():
                    grupo.user_set.add(usuario)
                    self.cambios += 1
                    self.stdout.write(f"   + {cuenta['NombreCompleto']} → {nombre_grupo}")

            for sobrante in grupo.user_set.exclude(pk__in=deseados):
                quien = sobrante.name or sobrante.email.split("@")[0]
                if quitar_sobrantes:
                    grupo.user_set.remove(sobrante)
                    self.cambios += 1
                    self.stdout.write(f"   − {quien} fuera de {nombre_grupo}")
                else:
                    self.problemas.append(
                        f"{quien} está en «{nombre_grupo}» y no sale en las listas "
                        "(se deja; --quitar-sobrantes lo saca)"
                    )

    def _usuario(self, correo, cuenta):
        if not correo.endswith(DOMINIO):
            self.problemas.append(
                f"«{cuenta['NombreCompleto']}» no tiene correo del centro: se salta"
            )
            return None
        User = get_user_model()
        usuario = User.objects.filter(email__iexact=correo).first()
        if usuario is not None:
            return usuario

        nombre = (cuenta.get("given_name") or "").strip()
        apellidos = (cuenta.get("family_name") or "").strip()
        usuario = User(
            email=correo,
            name=(cuenta.get("NombreCompleto") or "").strip(),
            first_name=nombre,
            last_name=apellidos,
        )
        usuario.set_unusable_password()
        usuario.save()
        EmailAddress.objects.create(
            user=usuario, email=correo, verified=True, primary=True
        )
        self.cambios += 1
        self.stdout.write(f"   · usuario precreado: {usuario.name}")
        return usuario

